# coding:utf-8

"""
automatic segment remote sensing images

include four steps：
1. stretch remote sensing image
2. read in blocks
3. segment
4. merge blocks

SEGMENT_METHOD
- slic, felzenszwalb, quickshift, reference: https://scikit-image.org/docs/0.14.x/api/skimage.segmentation.html?highlight=seg#module-skimage.segmentation
- sam (Segment Anything Model), reference: https://github.com/facebookresearch/segment-anything

note：If you want to use SAM, make sure you have installed the python packages that SAM depends on.
For details, see https://github.com/facebookresearch/segment-anything

"""

import numpy as np
import os
from PIL import Image
from PIL import ImageFile
import shutil
from tqdm import tqdm
from AutoDraw.libs.ImgProcess import getRSdata, getRSinfo, getDataType, stretch2GeoTiff
from AutoDraw.libs.VectorProcess import setBackground, mergeShp, array2Vector
import argparse

try:
    from osgeo import ogr, osr
except:
    import ogr

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None


def parse_args():

    parser = argparse.ArgumentParser()

    # basic parameters
    parser.add_argument('--segment-method', type=str, default='slic',
                        choices=['slic', 'felzenszwalb', 'quickshift', 'sam'],
                        help='Select different segmentation methods')

    parser.add_argument('--rgb-list', type=str, default='1,2,3',
                        help='RGB band index, split with comma, eg."3,2,1"')

    parser.add_argument('--input-image', type=str, help='input remote sensing image path',
                        default='')

    parser.add_argument('--output-dir', type=str, help='output dir path', default='')
    parser.add_argument('--output-name', type=str, default='segment_slic')

    # parameters for sam (Segment Anything Model)  ---optional
    parser.add_argument('--model-type', type=str, default='vit_h')
    parser.add_argument('--model-path', type=str, default='sam_vit_h_4b8939.pth')

    args = parser.parse_args()

    return args


def autodraw(args):

    imgPath = args.input_image
    tempDir = os.path.join(args.output_dir, 'tempdir')

    if not os.path.exists(tempDir):
        os.mkdir(tempDir)

    bands = args.rgb_list.split(',')
    rgb_index = list(map(int, bands))

    # stretch
    if getDataType(imgPath) != 'uint8':
        imgPath = stretch2GeoTiff(args.input_image, tempDir)

    # block size
    cutW, cutH  = 512, 512
    ds = getRSdata(imgPath)
    bands, cols, rows, proj, geoTransform = getRSinfo(ds)

    if cutW > cols or cutH > rows:
        data = ds.ReadAsArray()
        data = data.astype(np.uint8)
        if len(np.unique(data)) != 1:
            array2Vector(data, rgb_index, args, args.output_dir,
                         args.output_name, cols, rows, geoTransform, proj, 0, 0)
    else:
        tbar = tqdm(range(0, rows, cutH))
        # output vector
        ogr.RegisterAll()
        vectorDriver = ogr.GetDriverByName("ESRI Shapefile")
        segVector = os.path.join(args.output_dir, args.output_name + '.shp')
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
                    array2Vector(data, rgb_index, args, tempDir, str(i) + "_" + str(j),
                                 numCols, numRows, geoTransform, proj, i, j)
        mergeShp(vLayer, tempDir)
        vLayer = None
        vDs = None
    del ds
    shutil.rmtree(tempDir)


if __name__ == "__main__":

    args = parse_args()
    autodraw(args)
