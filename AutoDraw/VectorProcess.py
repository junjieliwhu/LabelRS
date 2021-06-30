import os
try:
    from osgeo import ogr,osr
except:
    import ogr

def createPolygon(line,col,width,high,geoTransform):

    ring = ogr.Geometry(ogr.wkbLinearRing)
    x, y = Pixel2world(geoTransform, line, col)
    ring.AddPoint(x, y)
    x, y = Pixel2world(geoTransform, line, col + width )
    ring.AddPoint(x, y)
    x, y = Pixel2world(geoTransform, line + high, col + width)
    ring.AddPoint(x, y)
    x, y = Pixel2world(geoTransform, line + high, col)
    ring.AddPoint(x, y)
    ring.CloseRings()
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    geomPolygon = ogr.CreateGeometryFromWkt(str(poly))
    return geomPolygon

def world2Pixel(geotransform, x, y):
  ulX = geotransform[0]
  ulY = geotransform[3]
  xDist = geotransform[1]
  yDist = geotransform[5]
  rtnX = geotransform[2]
  rtnY = geotransform[4]
  column = int((x - ulX) / xDist)
  line = int((ulY - y) / xDist)
  return column, line

def Pixel2world(geotransform, line, column):
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    x = column*pixelWidth + originX
    y = line*pixelHeight + originY
    return x,y

def createVectorLayer(vectorPath,proj):
    vectorDriver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(vectorPath):
        vectorDriver.DeleteDataSource(vectorPath)
    vDs = vectorDriver.CreateDataSource(vectorPath)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(proj)
    vLayer = vDs.CreateLayer(vectorPath, srs, ogr.wkbPolygon)
    return vLayer

def setBackground(bgLayer,line,col,width,high,geoTransform):
    featureDef = bgLayer.GetLayerDefn()
    feature = ogr.Feature(featureDef)
    poly = createPolygon(line, col, width, high, geoTransform)
    feature.SetGeometry(poly)
    bgLayer.CreateFeature(feature)
    bgLayer.SyncToDisk()

