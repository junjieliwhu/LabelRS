
# -- coding:cp936 –
import arcpy
import os
import classes as cl

def getExtent(infeatures,workspace):
    polygonList = []
    fields = ['FID','SHAPE@']
    arcpy.env.workspace = workspace
    with arcpy.da.SearchCursor(infeatures, fields) as cursor:
        for row in cursor:
            poly=row[1]
            extent=poly.extent
            polygonList.append(extent)
    return polygonList

def getExtentWithClass(infeatures,attribute,workspace):
    boxInfoList=[]
    field_names = [f.name for f in arcpy.ListFields(infeatures)]
    assert str(attribute) in field_names,"class attribute not exist"
    fields = ['FID','SHAPE@',str(attribute)]
    arcpy.env.workspace = workspace
    with arcpy.da.SearchCursor(infeatures, fields) as cursor:
        for row in cursor:
            poly=row[1]
            label=row[2]
            extent=poly.extent
            boxInfo=cl.BoxInfo(extent,label,0)
            boxInfoList.append(boxInfo)
    return boxInfoList

def getWidthHeight(extent,meanCellWidth,meanCellHeight):
    xmin = extent.XMin
    xmax = extent.XMax
    ymin = extent.YMin
    ymax = extent.YMax

    width=(xmax-xmin)/meanCellWidth
    height=(ymax-ymin)/meanCellHeight
    return round(width),round(height)

def getCenter(extent):
    xmin = extent.XMin
    xmax = extent.XMax
    ymin = extent.YMin
    ymax = extent.YMax
    x=(xmin+xmax)/2
    y=(ymin+ymax)/2
    return x,y

def makePolygon(xmin,xmax,ymin,ymax,spatial_reference):
    pointArray = []
    point1 = arcpy.Point(xmin, ymin)
    pointArray.append(point1)
    point2 = arcpy.Point(xmax, ymin)
    pointArray.append(point2)
    point3 = arcpy.Point(xmax, ymax)
    pointArray.append(point3)
    point4 = arcpy.Point(xmin, ymax)
    pointArray.append(point4)
    polygon=arcpy.Polygon(arcpy.Array([pointArray]), spatial_reference)
    return polygon

def getBoundry(centerX,centerY,halfWidth,halfHeight):
    xmin = centerX - halfWidth
    xmax = centerX + halfWidth
    ymin = centerY - halfHeight
    ymax = centerY + halfHeight
    return xmin,xmax,ymin,ymax

'''
lower version: it is necessary
higher version (10.5): directly use extent.polygon
'''
def extentToPolygon(srcExtent):
    spatial_reference=srcExtent.spatialReference
    xmin=srcExtent.XMin
    xmax = srcExtent.XMax
    ymin = srcExtent.YMin
    ymax = srcExtent.YMax
    polygon = makePolygon(xmin, xmax, ymin, ymax, spatial_reference)
    return polygon


def findNeighborPolygons(srcExtent,extentList,cellWidth,tileSize):
    neighbors=[]
    srcPoly=extentToPolygon(srcExtent)
    neighborDis=cellWidth * tileSize/2
    for ex in extentList:
        polygon=extentToPolygon(ex)
        distance=polygon.distanceTo(srcPoly)
        if distance<neighborDis:
            neighbors.append(ex)
    return neighbors

def findNeighborBoxes(srcExtent,boxInfoList,cellWidth,tileSize):

    neighbors=[]
    srcPoly=extentToPolygon(srcExtent)
    neighborDis=cellWidth * tileSize/2

    for i in range(len(boxInfoList)):
        boxInfo=boxInfoList[i]
        ex=boxInfo.extent
        polygon = extentToPolygon(ex)
        distance = polygon.distanceTo(srcPoly)
        if distance < neighborDis:
            neighbors.append(boxInfo)
    return neighbors

def splitPolygons(inputFeatures,cellWidth,cellHeight,tileSize,overlapSize,tempWorkSpace,outputPath,multiple=1):

    desc = arcpy.Describe(inputFeatures)
    spatial_reference = desc.spatialReference

    extents = getExtent(inputFeatures, tempWorkSpace)
    polygonList = []
    for ex in extents:
        width, height = getWidthHeight(ex, cellWidth, cellHeight)
        center_x, center_y = getCenter(ex)
        XMin = ex.XMin
        XMax = ex.XMax
        YMin = ex.YMin
        YMax = ex.YMax
        if width < multiple*tileSize and height < multiple*tileSize:
            xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tileSize * cellWidth / 2,
                                                tileSize * cellHeight / 2)
            polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))

        elif width > multiple * tileSize and height < multiple * tileSize:

            center_x_right = center_x

            while center_x + tileSize * cellWidth / 2 > XMin:
                xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tileSize * cellWidth / 2,
                                                    tileSize * cellHeight / 2)
                polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))
                center_x = center_x - (tileSize - overlapSize) * cellWidth

            center_x_right = center_x_right + (tileSize - overlapSize) * cellWidth
            while center_x_right - tileSize * cellWidth / 2 < XMax:
                xmin, xmax, ymin, ymax = getBoundry(center_x_right, center_y, tileSize * cellWidth / 2,
                                                    tileSize * cellHeight / 2)
                polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))
                center_x_right = center_x_right + (tileSize - overlapSize) * cellWidth

        elif width < multiple * tileSize and height > multiple*tileSize:

            center_y_up = center_y
            while center_y + tileSize * cellHeight / 2 > YMin:
                xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tileSize * cellWidth / 2,
                                                    tileSize * cellHeight / 2)
                polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))
                center_y = center_y - (tileSize - overlapSize) * cellHeight

            center_y_up = center_y_up + (tileSize - overlapSize) * cellHeight
            while center_y_up - tileSize * cellHeight / 2 < YMax:
                xmin, xmax, ymin, ymax = getBoundry(center_x, center_y_up, tileSize * cellWidth / 2,
                                                    tileSize * cellHeight / 2)
                polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))
                center_y_up = center_y_up + (tileSize - overlapSize) * cellHeight

        else:
            leftTop_x = XMin + tileSize * cellWidth / 2
            leftTop_y = YMax - tileSize * cellHeight / 2
            centerY = leftTop_y
            centerX = leftTop_x
            while centerY + tileSize * cellHeight / 2 > YMin:
                while centerX - tileSize * cellWidth / 2 < XMax:
                    xmin, xmax, ymin, ymax = getBoundry(centerX, centerY, tileSize * cellWidth / 2,
                                                        tileSize * cellHeight / 2)
                    polygonList.append(makePolygon(xmin, xmax, ymin, ymax, spatial_reference))
                    centerX = centerX + (tileSize - overlapSize) * cellWidth
                centerY = centerY - (tileSize - overlapSize) * cellHeight
                centerX = leftTop_x

    polygon_path = outputPath
    if os.path.exists(polygon_path):
        arcpy.DeleteFeatures_management(polygon_path)
    arcpy.CopyFeatures_management(polygonList, polygon_path)
    return polygon_path


def classificationPolygons(inputFeatures,cellWidth,cellHeight,tileSize,overlapSize,tempWorkSpace,multiple=1):

    desc = arcpy.Describe(inputFeatures)
    spatial_reference = desc.spatialReference

    extents = getExtent(inputFeatures,tempWorkSpace)
    polygonList = []
    for ex in extents:
        width, height = getWidthHeight(ex, cellWidth, cellHeight)
        center_x, center_y = getCenter(ex)
        XMin = ex.XMin
        XMax = ex.XMax
        YMin = ex.YMin
        YMax = ex.YMax
        if width < multiple*tileSize and height < multiple*tileSize:
            polygonList.append(extentToPolygon(ex))

        elif width > multiple * tileSize and height < multiple * tileSize:

            leftX=XMin
            rightX=leftX+tileSize * cellWidth
            while rightX<=XMax:
                polygonList.append(makePolygon(leftX, rightX, YMin, YMax, spatial_reference))
                leftX = leftX+(tileSize - overlapSize) * cellWidth
                rightX = leftX + tileSize * cellWidth
            if leftX<XMax and rightX>XMax:
                polygonList.append(makePolygon(XMax-tileSize * cellWidth, XMax, YMin, YMax, spatial_reference))

        elif width < multiple * tileSize and height > multiple*tileSize:
            topY=YMax
            belowY=topY-tileSize * cellHeight
            while belowY>=YMin:
                polygonList.append(makePolygon(XMin, XMax, belowY, topY, spatial_reference))
                topY=topY-(tileSize - overlapSize) * cellHeight
                belowY = topY - tileSize * cellHeight
            if topY>YMin and belowY<YMin:
                polygonList.append(makePolygon(XMin, XMax, YMin, YMin + (tileSize - overlapSize) * cellHeight, spatial_reference))
        else:

            leftTop_x = XMin
            leftTop_y = YMax
            while leftTop_y - tileSize * cellHeight >= YMin:
                while leftTop_x + tileSize * cellWidth <= XMax:
                    polygonList.append(makePolygon(leftTop_x, leftTop_x + tileSize * cellWidth,
                                                   leftTop_y - tileSize * cellHeight, leftTop_y, spatial_reference))
                    leftTop_x = leftTop_x + (tileSize - overlapSize) * cellWidth
                if leftTop_x+ tileSize * cellWidth>XMax and leftTop_x<XMax:
                    polygonList.append(makePolygon(XMax-tileSize * cellWidth, XMax,
                                                   leftTop_y - tileSize * cellHeight, leftTop_y, spatial_reference))
                leftTop_x = XMin
                leftTop_y = leftTop_y - (tileSize - overlapSize) * cellHeight

            if leftTop_y - tileSize * cellHeight<YMin and leftTop_y>YMin:
                leftTop_x = XMin
                while leftTop_x + tileSize * cellWidth <= XMax:
                    polygonList.append(makePolygon(leftTop_x, leftTop_x + tileSize * cellWidth,
                                                   YMin + tileSize * cellHeight, YMin, spatial_reference))
                    leftTop_x = leftTop_x + (tileSize - overlapSize) * cellWidth
                if leftTop_x + tileSize * cellWidth > XMax and leftTop_x < XMax:
                    polygonList.append(makePolygon(XMax - tileSize * cellWidth, XMax,
                                                   YMin + tileSize * cellHeight, YMin, spatial_reference))
    return polygonList


def getPolygonType(shpPath):
    fl = arcpy.MakeFeatureLayer_management(shpPath)
    desc = arcpy.Describe(fl)
    shape_type = desc.shapeType
    return shape_type

