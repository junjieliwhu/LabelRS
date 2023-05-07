import numpy as np
import os
from osgeo import gdal, gdalconst
from osgeo.gdalconst import *
from skimage.segmentation import slic, felzenszwalb, quickshift


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
        c = np.percentile(data[:, :, i], lower_percent)
        d = np.percentile(data[:, :, i], higher_percent)
        t = a + (data[:, :, i] - c) * (b - a) / (d - c)
        t[t < a] = a
        t[t > b] = b
        out[:, :, i] = t
    return out


def stretch2GeoTiff(imgPath, resultFolder):
    driver = gdal.GetDriverByName('GTiff')
    driver.Register()
    ds = gdal.Open(imgPath, GA_ReadOnly)
    bands = ds.RasterCount
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    geoTransform = ds.GetGeoTransform()
    proj = ds.GetProjection()
    data = np.empty([rows, cols, bands], dtype=float)
    for i in range(bands):
        band = ds.GetRasterBand(i + 1)
        data1 = band.ReadAsArray()
        data[:, :, i] = data1
    stretch = percentStretch(data)
    imgName = os.path.basename(imgPath)
    resultPath = os.path.join(resultFolder, imgName)
    driver = ds.GetDriver()
    outDataset = driver.Create(resultPath, cols, rows, bands, GDT_Byte)
    outDataset.SetGeoTransform(geoTransform)
    outDataset.SetProjection(proj)
    for i in range(bands):
        outBand = outDataset.GetRasterBand(i + 1)
        outBand.WriteArray(stretch[:, :, i], 0, 0)
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
    return (bands, cols, rows, proj, geoTransform)


def getDataType(imgPath):
    driver = gdal.GetDriverByName('GTiff')
    driver.Register()
    ds = gdal.Open(imgPath, GA_ReadOnly)
    da = ds.ReadAsArray()
    return da.dtype.name


def getRGB(data, rgb_list):
    r = data[rgb_list[0] - 1, :, :]
    g = data[rgb_list[1] - 1, :, :]
    b = data[rgb_list[2] - 1, :, :]
    rgb_stack = np.stack((r, g, b)).transpose(1, 2, 0)
    return rgb_stack


def getMaskImg(masks):
    img = np.zeros((masks[0]['segmentation'].shape[0], masks[0]['segmentation'].shape[1]))
    for i in range(len(masks)):
        seg = masks[i]['segmentation']
        seg = seg.astype(np.int) * (i + 1)
        img += seg
    return img


def segment(data, rgb_list, method, **kwargs):
    rgb_data = getRGB(data, rgb_list)

    if method.lower() == 'slic':
        segments = slic(rgb_data, n_segments=100, compactness=10,
                        enforce_connectivity=False, sigma=0.5,
                        max_size_factor=2)

    if method.lower() == 'felzenszwalb':
        segments = felzenszwalb(rgb_data, scale=1, sigma=0.8, min_size=20)

    if method.lower() == 'quickshift':
        segments = quickshift(rgb_data, ratio=1.0, kernel_size=5, max_dist=10)

    if method.lower() == 'sam':
        try:
            from AutoDraw.libs.segment_anything import SamAutomaticMaskGenerator, sam_model_registry
            import torch
            # Device configuration
            device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
            model_type = kwargs['model_type']
            sam = sam_model_registry[model_type](checkpoint=kwargs['model_path'])
            # sam.to(device=device)
            mask_generator = SamAutomaticMaskGenerator(sam)
            masks = mask_generator.generate(rgb_data)
            segments = getMaskImg(masks)

        except:
            raise 'sam is not installed, please install https://github.com/facebookresearch/segment-anything'

    return segments
