
# -- coding:cp936 –
import arcpy
import os
import shutil
from tqdm import tqdm
import arcpy.cartography as CA

from RS_Libs.Objects import ObjectInfo, BoxInfo


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
            boxInfo=BoxInfo(extent,label,0)
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


def copyShpfile(sourceShp,desDir,name):
    sourceDir=os.path.dirname(sourceShp)
    shpName=os.path.basename(sourceShp)
    name_withoutextension=os.path.splitext(shpName)[0]
    exList=['.cpg','.dbf','.prj','.sbn','.sbx','.shp','.shx']
    for ex in exList:
        sourceFile=os.path.join(sourceDir, name_withoutextension +ex)
        if os.path.exists(sourceFile):
            destinationFile=os.path.join(desDir,name+ex)
            if not os.path.exists(destinationFile):
                shutil.copyfile(sourceFile,destinationFile)

def copyShpfile2(sourceShp,desDir):
    sourceDir=os.path.dirname(sourceShp)
    shpName=os.path.basename(sourceShp)
    name_withoutextension=os.path.splitext(shpName)[0]
    exList=['.cpg','.dbf','.prj','.sbn','.sbx','.shp','.shx']
    for ex in exList:
        sourceFile=os.path.join(sourceDir, name_withoutextension +ex)
        if os.path.exists(sourceFile):
            destinationFile=os.path.join(desDir,name_withoutextension+ex)
            if not os.path.exists(destinationFile):
                shutil.copyfile(sourceFile,destinationFile)

def split_large_targets(shpfile, workspace, img_meta_info, args):
    boxInfoList = []
    fields = ['FID', 'SHAPE@', str(args.class_field), 'tempID']
    cell_width = img_meta_info['cell_width']
    cell_height = img_meta_info['cell_height']
    spatial_reference = img_meta_info['spatial_reference']
    tile_size = int(args.tile_size)
    overlap_size = int(args.overlap_size)
    arcpy.env.workspace = workspace
    count = arcpy.GetCount_management(shpfile).getOutput(0)
    count = int(count.encode('utf-8'))
    pbar = tqdm(total=count)
    pbar.set_description("Processing step1")
    with arcpy.da.SearchCursor(shpfile, fields) as cursor:
        for row in cursor:
            poly = row[1]
            extent = poly.extent
            label = row[2]
            center_x, center_y = getCenter(extent)
            xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tile_size * cell_width / 2,
                                                   tile_size * cell_height / 2)
            imgPolygon = makePolygon(xmin, xmax, ymin, ymax, spatial_reference)
            if not imgPolygon.contains(poly):  # find large target
                tempShp = 'temp.shp'
                arcpy.FeatureClassToFeatureClass_conversion(poly, workspace, tempShp)
                clipPolygons = classificationPolygons(tempShp, cell_width, cell_height, tile_size,
                                                         overlap_size, workspace)
                for polygon in clipPolygons:
                    boxInfoList.append(BoxInfo(polygon.extent, label, 0))
                arcpy.Delete_management(tempShp)
            else:
                boxInfoList.append(BoxInfo(extent, label, 0))
            pbar.update(1)
    pbar.close()
    return boxInfoList


def split_larget_objects(shpfile, workspace, img_meta_info, args):
    boxInfoList = []
    fields = ['FID', 'SHAPE@', str(args.class_field), 'tempID']
    cell_width = img_meta_info['cell_width']
    cell_height = img_meta_info['cell_height']
    spatial_reference = img_meta_info['spatial_reference']
    tile_size = int(args.tile_size)
    overlap_size = int(args.overlap_size)
    arcpy.env.workspace = workspace
    deleteIDs = []
    count = arcpy.GetCount_management(shpfile).getOutput(0)
    count = int(count.encode('utf-8'))
    pbar = tqdm(total=count)
    with arcpy.da.SearchCursor(shpfile, fields) as cursor:
        for row in cursor:
            poly = row[1]
            extent = poly.extent
            label = row[2]
            center_x, center_y = getCenter(extent)
            xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tile_size * cell_width / 2,
                                                   tile_size * cell_height / 2)
            imgPolygon = makePolygon(xmin, xmax, ymin, ymax, spatial_reference)
            if not imgPolygon.contains(poly):  # find large target
                tempShp = 'temp.shp'
                arcpy.FeatureClassToFeatureClass_conversion(poly, workspace, tempShp)
                clipPolygon = os.path.join(workspace, 'clipPolygon.shp')
                splitPolygons(tempShp, cell_width, cell_height, tile_size, overlap_size, workspace, clipPolygon)
                with arcpy.da.SearchCursor(clipPolygon, ['SHAPE@']) as cursor1:
                    for r in cursor1:
                        polygon = r[0]
                        if poly.contains(polygon) or not poly.disjoint(polygon):
                            intersectArea = poly.intersect(polygon, 4)
                            truncated = 1 - intersectArea.getArea() / (poly.getArea())
                            if truncated < 0: truncated = 0
                            boxInfo = BoxInfo(intersectArea.extent, label, truncated)
                            boxInfoList.append(boxInfo)
                deleteIDs.append(row[0])
                arcpy.Delete_management(tempShp)
                arcpy.Delete_management(clipPolygon)
            pbar.set_description("Processing step1")
            pbar.update(1)
    pbar.close()
    # Delete the features that have been split
    with arcpy.da.UpdateCursor(shpfile, fields) as cursor:
        for r in cursor:
            if r[0] in deleteIDs:
                r[3] = 1
                cursor.updateRow(r)
    input_lyr = "lyr"
    arcpy.MakeFeatureLayer_management(shpfile, input_lyr)
    arcpy.SelectLayerByAttribute_management(input_lyr, "NEW_SELECTION", '"tempID" = 1')
    if int(arcpy.GetCount_management(input_lyr).getOutput(0)) > 0:
        arcpy.DeleteFeatures_management(input_lyr)
    arcpy.Delete_management(input_lyr)
    boxinfos = getExtentWithClass(shpfile, str(args.class_field), workspace)
    boxInfoList.extend(boxinfos)
    return boxInfoList


def get_objects_info(boxInfoList, img_meta_info, geo_transform, args):
    objectList = []
    cell_width = img_meta_info['cell_width']
    cell_height = img_meta_info['cell_height']
    spatial_reference = img_meta_info['spatial_reference']
    tile_size = int(args.tile_size)
    for i in tqdm(range(len(boxInfoList)), desc='Processing step2'):
        boxInfo = boxInfoList[i]
        ex = boxInfo.extent
        center_x, center_y = getCenter(ex)
        xmin, xmax, ymin, ymax = getBoundry(center_x, center_y, tile_size * cell_width / 2,
                                               tile_size * cell_height / 2)
        imgPolygon = makePolygon(xmin, xmax, ymin, ymax, spatial_reference)
        neighbors = findNeighborBoxes(imgPolygon.extent, boxInfoList, cell_width, tile_size)
        boxList = []
        if len(neighbors) == 0:
            continue
        for j in range(len(neighbors)):
            neigBox = neighbors[j]
            ext = neigBox.extent
            value = neigBox.label
            trunca = neigBox.truncated
            poly = extentToPolygon(ext)
            if imgPolygon.contains(poly) or not imgPolygon.disjoint(poly):
                intersectArea = imgPolygon.intersect(poly, 4)
                truncated = 1 - intersectArea.getArea() / (poly.getArea())
                if truncated < 0: truncated = 0
                if trunca == 0 and truncated != 0:
                    boxList.append(BoxInfo(intersectArea.extent, value, '{:.3f}'.format(truncated)))
                elif trunca != 0 and truncated == 0:
                    boxList.append(BoxInfo(intersectArea.extent, value, '{:.3f}'.format(trunca)))
                else:
                    truncated = truncated * trunca
                    boxList.append(BoxInfo(intersectArea.extent, value, '{:.3f}'.format(truncated)))
        object = ObjectInfo(imgPolygon.extent, boxList, geo_transform, tile_size)
        objectInfos = object.getObject()
        objectList.append(objectInfos)

    return objectList

def simplify_polygon(workspace, shpfile, outputFolder, img_meta_info, tile_size, overlap_size):
    # simplify polygon
    arcpy.env.workspace = workspace
    cell_width = img_meta_info['cell_width']
    cell_height = img_meta_info['cell_height']
    CA.SimplifyPolygon(shpfile, 'simplify.shp', "POINT_REMOVE", '50 meters')
    buffer_dis = cell_width * tile_size / 2
    buffer = os.path.join(workspace, 'buffer.shp')
    arcpy.Buffer_analysis('simplify.shp', buffer, buffer_dis, "FULL", "ROUND", "ALL")
    buffer_single = os.path.join(workspace, 'buffer_single.shp')
    arcpy.MultipartToSinglepart_management(buffer, buffer_single)
    arcpy.Delete_management(buffer)
    arcpy.Delete_management('simplify.shp')
    gridsPath = os.path.join(outputFolder, 'grids.shp')
    splitPolygons(buffer_single, cell_width, cell_height, tile_size,
                     overlap_size, workspace, gridsPath, multiple=2)
    arcpy.AddMessage('Creating vector grids done !')
    arcpy.Delete_management(buffer_single)

    # Estimated total sample nums
    gridLyr = "gridsLyr"
    arcpy.MakeFeatureLayer_management(gridsPath, gridLyr)
    arcpy.CopyFeatures_management([extentToPolygon(img_meta_info['extent'])], 'poly.shp')
    tifLayer = 'tifLyr'
    arcpy.MakeFeatureLayer_management('poly.shp', tifLayer)
    arcpy.SelectLayerByLocation_management(gridLyr, 'intersect', tifLayer)
    matchcount = int(arcpy.GetCount_management(gridLyr)[0])
    arcpy.Delete_management(tifLayer)
    arcpy.Delete_management('poly.shp')
    arcpy.Delete_management(gridLyr)
    return gridsPath, matchcount
