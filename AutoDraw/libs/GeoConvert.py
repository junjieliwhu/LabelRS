from osgeo import gdal, gdalconst
from osgeo.gdalconst import *
import os

try:
    from osgeo import ogr,osr
except:
    import ogr

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

def getNewGeoTransform(sourceGeo,line,col):
    newX,newY=Pixel2world(sourceGeo, line, col)
    geoT=(newX,sourceGeo[1],sourceGeo[2],newY,sourceGeo[4],sourceGeo[5])
    return geoT


def raster2Vector(outDataset, vector):
    shp_driver = ogr.GetDriverByName("ESRI Shapefile")
    try:
        if os.path.exists(vector + ".shp"):
            shp_driver.DeleteDataSource(vector + ".shp")
            os.remove(vector + ".shp")
    except:
        pass
    proj = outDataset.GetProjection()
    output_shp = vector

    # create output file name
    output_shapefile = shp_driver.CreateDataSource(output_shp + ".shp")

    geosrs = osr.SpatialReference()
    geosrs.ImportFromWkt(proj)
    outLayer = output_shapefile.CreateLayer(output_shp, srs=geosrs)
    newField = ogr.FieldDefn('Class', ogr.OFTInteger)
    outLayer.CreateField(newField)

    gdal.Polygonize(outDataset.GetRasterBand(1), None, outLayer, 0, [], callback=None)
    # gdal.FPolygonize(outDataset.GetRasterBand(1), None, new_shapefile, 0)
    outLayer.SyncToDisk()

    #     output_name=output_shp + ".shp"
    return output_shp