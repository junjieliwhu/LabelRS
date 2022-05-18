# coding:utf-8

'''
1. stretch remote sensing image
2. read in blocks
3. segment
4. merge
'''

import numpy as np
from osgeo import gdal, gdalconst
from osgeo.gdalconst import *
import os
from PIL import Image
from PIL import ImageFile
import matplotlib.pyplot as plt
from skimage.segmentation import slic,felzenszwalb,quickshift,mark_boundaries,find_boundaries
import shutil
from tqdm import tqdm
import glob
from AutoDraw.ImgProcess import getRSdata,getRSinfo,getDataType,stretch2GeoTiff
from AutoDraw.VectorProcess import setBackground
from AutoDraw.GeoConvert import raster2Vector,getNewGeoTransform

try:
    from osgeo import ogr,osr
except:
    import ogr

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None

'''
SEGMENT_METHOD
- Select different segmentation methods
- Include  slic, felzenszwalb, quickshift
- Adjust function parameters in array2Vector() to obtain the best segmentation
Reference: https://scikit-image.org/docs/0.14.x/api/skimage.segmentation.html?highlight=seg#module-skimage.segmentation
'''
SEGMENT_METHOD='quickshift' # slic, felzenszwalb, quickshift

'''
RGB_LIST
- R,G,B band number in multispectral images
- for example, GF2 PMS data include B,G,R,NIR bands, RGB_LIST = [3,2,1]
'''
RGB_LIST=[3,2,1]

def autodraw(imgPath,outputFolder,rgb_list=RGB_LIST):

    tempDir=os.path.join(outputFolder,'tempdir')
    if os.path.exists(tempDir):
        shutil.rmtree(tempDir)
        os.mkdir(tempDir)
    else:
        os.mkdir(tempDir)

    # stretch
    if getDataType(imgPath) != 'uint8':
        newTif=stretch2GeoTiff(imgPath,tempDir)
        imgPath=newTif

    # block size
    cutW = 512
    cutH = 512

    ds = getRSdata(imgPath)
    bands,cols,rows,proj,geoTransform =getRSinfo(ds)

    print('segment')
    if cutW>cols or cutH>rows:

        data = ds.ReadAsArray()
        data = data.astype(np.uint8)
        if len(np.unique(data)) != 1:  # 单一颜色或者背景
            array2Vector(data,rgb_list,outputFolder,'segments',cols, rows,geoTransform,proj,0,0)
    else:
        tbar = tqdm(range(0, rows, cutH))
        # output vector
        ogr.RegisterAll()
        vectorDriver = ogr.GetDriverByName("ESRI Shapefile")
        segVector = os.path.join(outputFolder, 'segments.shp')
        vDs = vectorDriver.CreateDataSource(segVector)
        srs = osr.SpatialReference()
        srs.ImportFromWkt(proj)
        vLayer = vDs.CreateLayer("polygons", srs, ogr.wkbPolygon)
        for i in tbar:
            if i + cutH < rows:
                numRows = cutH
            else:
                numRows = rows - i
            for j in range(0, cols, cutW):
                if j + cutW < cols:
                    numCols = cutW
                else:
                    numCols = cols - j

                data = ds.ReadAsArray(j, i, numCols, numRows)
                data = data.astype(np.uint8)
                if len(np.unique(data)) == 1:
                    setBackground(vLayer, i, j, numCols, numRows, geoTransform)
                else:
                    array2Vector(data, rgb_list, tempDir, str(i) + "_" + str(j), numCols, numRows, geoTransform, proj,i,j)

        fieldDefn = ogr.FieldDefn('class', ogr.OFTString)
        fieldDefn.SetWidth(4)
        vLayer.CreateField(fieldDefn)
        shpList = glob.glob(tempDir + '/*.shp')
        for shp in tqdm(shpList):
            ds = ogr.Open(shp)
            lyr = ds.GetLayer()
            for feat in lyr:
                out_feat = ogr.Feature(vLayer.GetLayerDefn())
                out_feat.SetGeometry(feat.GetGeometryRef().Clone())
                vLayer.CreateFeature(out_feat)
                vLayer.SyncToDisk()
        vLayer=None
        vDs=None

    shutil.rmtree(tempDir)

def array2Vector(data,rgb_list,tempDir,segName,numCols, numRows,geoTransform,proj,startRow,startCol):
    rgb_order = list(map(int, rgb_list))
    r = data[rgb_order[0] - 1, :, :]
    g = data[rgb_order[1] - 1, :, :]
    b = data[rgb_order[2] - 1, :, :]
    rgb_stack = np.stack((r, g, b)).transpose(1, 2, 0)
    # segments = slic(newImg, slic_zero=True)
    if SEGMENT_METHOD.lower()=='slic':
        segments = slic(rgb_stack, n_segments=100, compactness=10,
                        enforce_connectivity=False, sigma=0.5,
                        max_size_factor=2)
    if SEGMENT_METHOD.lower()=='felzenszwalb':
        segments = felzenszwalb(rgb_stack, scale=1, sigma=0.8, min_size=20)

    if SEGMENT_METHOD.lower()=='quickshift':
        segments = quickshift(rgb_stack, ratio=1.0, kernel_size=5, max_dist=10)

    boundaries = find_boundaries(segments, mode='outer')
    seg_tif = os.path.join(tempDir, 'seg.tif')
    driver2 = gdal.GetDriverByName('GTiff')
    driver2.Register()
    outDataset = driver2.Create(seg_tif, numCols, numRows, 1, GDT_Float32)
    outDataset.SetGeoTransform(getNewGeoTransform(geoTransform, startRow, startCol))
    outDataset.SetProjection(proj)
    outDataset.GetRasterBand(1).WriteArray(boundaries)
    raster2Vector(outDataset, os.path.join(tempDir, segName+'.shp'))
    outDataset = None
    driver2 = None
    os.remove(seg_tif)

if __name__=="__main__":

    imgPath = r''
    output = r''
    autodraw(imgPath,output)


