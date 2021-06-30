import numpy as np
import os
from osgeo import gdal, gdalconst
from osgeo.gdalconst import *


def percentStretch(tifArray, lower_percent=0.5, higher_percent=99.5):
    '''
    Percentage Truncation stretch
    :param tifArray: remote sensing image of numpy format
    :param lower_percent: The pixels in the bottom lower_percent are assigned 0
    :param higher_percent: The pixels in the top higher_percent are assigned 255
    :return: image array range from 0 to 255
    '''
    data = tifArray
    n = data.shape[2]
    out = np.zeros_like(data, dtype=np.uint8)
    for i in range(n):
        a = 0
        b = 255
        c = np.percentile(data[:, :,i], lower_percent)
        d = np.percentile(data[:, :,i], higher_percent)
        t = a + (data[:, :,i] - c) * (b - a) / (d - c)
        t[t < a] = a
        t[t > b] = b
        out[:, :,i] = t
    return out


def stretch2GeoTiff(imgPath,resultFolder):
    driver = gdal.GetDriverByName('GTiff')
    driver.Register()
    ds = gdal.Open(imgPath, GA_ReadOnly)
    bands = ds.RasterCount
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    geoTransform = ds.GetGeoTransform()
    proj = ds.GetProjection()
    # 原始影像波段顺序为：B,G,R,NIR
    data = np.empty([rows, cols, bands], dtype=float)
    for i in range(bands):
        band = ds.GetRasterBand(i + 1)
        data1 = band.ReadAsArray()
        data[:,:,i] = data1
    # 拉伸后波段顺序为：B,G,R,NIR
    stretch = percentStretch(data)
    imgName = os.path.basename(imgPath)
    resultPath = os.path.join(resultFolder, imgName)
    driver = ds.GetDriver()
    outDataset = driver.Create(resultPath, cols, rows, bands, GDT_Byte)
    outDataset.SetGeoTransform(geoTransform)
    outDataset.SetProjection(proj)
    for i in range(bands):
        outBand = outDataset.GetRasterBand(i+1)
        outBand.WriteArray(stretch[:,:,i], 0, 0)
        outBand.FlushCache()
    return resultPath

def getRSdata(imgPath):
    driver = gdal.GetDriverByName('GTiff')
    driver.Register()
    ds = gdal.Open(imgPath, GA_ReadOnly)
    return ds

def getRSinfo(ds):
    bands = ds.RasterCount
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    proj = ds.GetProjection()
    geoTransform = ds.GetGeoTransform()
    return (bands,cols,rows,proj,geoTransform)

def getDataType(imgPath):
    driver = gdal.GetDriverByName('GTiff')
    driver.Register()
    ds = gdal.Open(imgPath, GA_ReadOnly)
    da=ds.ReadAsArray()
    return da.dtype.name




