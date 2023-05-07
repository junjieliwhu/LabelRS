import os
import glob
try:
    from osgeo import ogr,osr
except:
    import ogr
from AutoDraw.libs.GeoConvert import raster2Vector, getNewGeoTransform
from AutoDraw.libs.ImgProcess import segment
from osgeo import gdal
from osgeo.gdalconst import *


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

def mergeShp(layer, workspace):
    fieldDefn = ogr.FieldDefn('class', ogr.OFTString)
    fieldDefn.SetWidth(4)
    layer.CreateField(fieldDefn)
    shpList = glob.glob(workspace + '/*.shp')
    for shp in shpList:
        ds = ogr.Open(shp)
        lyr = ds.GetLayer()
        for feat in lyr:
            out_feat = ogr.Feature(layer.GetLayerDefn())
            out_feat.SetGeometry(feat.GetGeometryRef().Clone())
            layer.CreateFeature(out_feat)
            layer.SyncToDisk()
        ds = None


def array2Vector(data, rgb_list, args, workspace, segName, numCols, numRows, geoTransform, proj, startRow, startCol):
    segments = segment(data, rgb_list, args.segment_method, model_type=args.model_type, model_path=args.model_path)
    seg_tif = os.path.join(workspace, 'seg.tif')
    driver2 = gdal.GetDriverByName('GTiff')
    driver2.Register()
    outDataset = driver2.Create(seg_tif, numCols, numRows, 1, GDT_Float32)
    outDataset.SetGeoTransform(getNewGeoTransform(geoTransform, startRow, startCol))
    outDataset.SetProjection(proj)
    outDataset.GetRasterBand(1).WriteArray(segments)
    raster2Vector(outDataset, os.path.join(workspace, segName))
    outDataset = None
    driver2 = None
    os.remove(seg_tif)
    return os.path.join(workspace, segName + '.shp')