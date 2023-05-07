# coding=utf-8
import arcpy
import os
import cv2
import numpy as np
import shutil


class GeoTransform():
    def __init__(self, tif_path):
        content = readTransform(tif_path)
        self.pixelWidth = float(content[0])
        self.rotateX = float(content[1])
        self.rotateY = float(content[2])
        self.pixelHeight = float(content[3])
        self.originX = float(content[4])
        self.originY = float(content[5])

    def getValues(self):
        return [self.pixelWidth, self.rotateX, self.rotateY, self.pixelHeight, self.originX, self.originY]

def readTransform(tifPath):
    folder, baseName = os.path.split(tifPath)
    name = os.path.splitext(baseName)[0]
    tfw = os.path.join(folder, name + '.tfw')
    if not os.path.exists(tfw):
        arcpy.env.workspace = folder
        arcpy.ExportRasterWorldFile_management(tifPath)
        arcpy.ResetEnvironments()
    with open(tfw, 'r') as f:
        content = f.read().replace("\n", ",").split(",")
    return content


def percentStretch(tifArray, lower_percent=0.5, higher_percent=99.5):
    '''
    Percentage Truncation stretch
    :param tifArray: remote sensing image of numpy format
    :param lower_percent: The pixels in the bottom lower_percent are assigned 0
    :param higher_percent: The pixels in the top higher_percent are assigned 255
    :return: image array range from 0 to 255
    '''
    data = tifArray
    n = data.shape[0]
    out = np.zeros_like(data, dtype=np.uint8)
    for i in range(n):
        a = 0
        b = 255
        c = np.percentile(data[i, :, :], lower_percent)
        d = np.percentile(data[i, :, :], higher_percent)
        t = a + (data[i, :, :] - c) * (b - a) / (d - c)
        t[t < a] = a
        t[t > b] = b
        out[i, :, :] = t
    return out


def stdStretch(tifArray, multiple=2.5):
    '''
    Standard Deviation stretch
    :param tifArray: remote sensing image of numpy format
    :param multiple: Multiple of standard deviation, default 2.5
    :return: image of unsigned int8 (0-255)
    '''
    data = tifArray
    n = data.shape[0]
    out = np.zeros_like(data, dtype=np.uint8)
    for i in range(n):
        band = data[i, :, :]
        mean = np.mean(band)
        stdDev = np.std(band, ddof=1)
        max = mean + multiple * stdDev
        min = mean - multiple * stdDev
        k = 255 / (max - min)
        b = (0 - min * 255) / (max - min)
        if min <= 0:
            min = 0
        band = np.select([band <= min, band >= max, k * band + b < 0,
                          k * band + b > 255, (k * band + b > 0) & (k * band + b < 255)],
                         [0, 255, 0, 255, k * band + b], band)
        out[i, :, :] = band
    return out


def minmaxStretch(tifArray):
    '''
    Maximum and Minimum stretch
    :param tifArray: remote sensing image of numpy format
    :return:
    '''
    data = tifArray
    n = data.shape[0]
    out = np.zeros_like(data, dtype=np.uint8)
    for i in range(n):
        band = data[i, :, :]
        min = np.min(band)
        max = np.max(band)
        if max == min:
            out[i, :, :] = band
        else:
            k = 255 * 1.0 / (max - min)
            b = (0 - min * 255) * 1.0 / (max - min)
            band = np.select([k * band + b < 0, k * band + b > 255, (k * band + b >= 0) & (k * band + b <= 255)],
                             [0, 255, k * band + b], band)
            out[i, :, :] = band
    return out

def checkFile(imgPath):
    legal = True
    if imgPath.endswith('.tif') or imgPath.endswith('.tiff'):
        my_array = arcpy.RasterToNumPyArray(imgPath)
        min = my_array.min()
        max = my_array.max()
        if min == max:
            legal = False
    else:
        img = cv2.imread(imgPath)
        np_array = np.array(img)
        min = np_array.min()
        max = np_array.max()
        if min == max:
            legal = False
    return legal


def generateImg(tag, inputImg, inputFeature, imageDir, splitBands=False, bandsOrder=None, resampling_type=None, labelDir=None, **kwargs):
    outTif = os.path.join(imageDir, str(tag).zfill(6) + '.tif')
    arcpy.Clip_management(inputImg, "#", outTif, inputFeature, "0", "None", "MAINTAIN_EXTENT")
    tfw = os.path.join(imageDir, str(tag).zfill(6) + '.tfw')
    label_png, label_pgw = '', ''
    if not os.path.exists(tfw):
        arcpy.env.workspace = imageDir
        arcpy.ExportRasterWorldFile_management(outTif)
    if splitBands:
        split_rgb_bands(imageDir, outTif, bandsOrder)
    if labelDir is not None:
        label_png = os.path.join(labelDir, str(tag).zfill(6) + '.png')
        label_pgw = os.path.join(labelDir, str(tag).zfill(6) + '.pgw')
        shutil.copy(tfw, label_pgw)
    if not checkFile(outTif):
        arcpy.Delete_management(outTif)
        if labelDir is not None:
            if os.path.exists(label_pgw):
                os.remove(label_pgw)
            if os.path.exists(label_png):
                os.remove(label_png)
        return False, ''
    if resampling_type is not None:
        resample(outTif, kwargs['tile_size'], resampling_type)
    if kwargs['output_img_format'] in ['TIFF', 'TIF', 'tiff', 'tif']:
        removeTempFiles(imageDir)
        return True, outTif
    if kwargs['output_img_format'] in ['JPEG', 'jpg']:
        outputImg = os.path.join(imageDir, str(tag).zfill(6) + '.jpg')
        outputGeo = os.path.join(imageDir, str(tag).zfill(6) + '.jgw')
    else:
        outputImg = os.path.join(imageDir, str(tag).zfill(6) + '.png')
        outputGeo = os.path.join(imageDir, str(tag).zfill(6) + '.pgw')
    stretch_tif(imageDir, outTif, outputImg,
                stretch_method=kwargs['stretch_method'],
                stretch_parameters=kwargs['stretch_parameters'])
    tfw = str(tag).zfill(6) + '.tfw'
    if not os.path.exists(os.path.join(imageDir, tfw)):
        arcpy.env.workspace = imageDir
        arcpy.ExportRasterWorldFile_management(outTif)
    shutil.copy(os.path.join(imageDir, tfw), outputGeo)
    arcpy.Delete_management(outTif)
    removeTempFiles(imageDir)
    if not checkFile(outputImg):
        os.remove(outputImg)
        os.remove(outputGeo)
        if labelDir is not None:
            if os.path.exists(label_pgw):
                os.remove(label_pgw)
            if os.path.exists(label_png):
                os.remove(label_png)
        return False, ''
    return True, outputImg


def split_rgb_bands(imageDir, tif, bandsOrder=[4,3,2]):
    """
    default bandsOrder = [4,3,2] for landsat-8 and sentinel-2
    """
    arcpy.env.workspace = imageDir
    tempRaster = 'tempRaster.tif'
    layer = "rdlayer"
    arcpy.MakeRasterLayer_management(tif, layer, "", "", bandsOrder)
    arcpy.CopyRaster_management(layer, tempRaster)
    arcpy.Delete_management(layer)
    arcpy.Delete_management(tif)
    arcpy.CopyRaster_management(tempRaster, tif)
    arcpy.Delete_management(tempRaster)


def resample(inputTif, tileSize, resample):
    # 0,Nearest; 1,Bilinear; 2,Cubic
    if int(resample) == 0:
        method = 'Nearest'
    if int(resample) == 1:
        method = 'Bilinear'
    if int(resample) == 2:
        method = 'Cubic'
    raster = arcpy.Raster(inputTif)
    width = raster.width
    height = raster.height
    cellWidth = raster.meanCellWidth
    cellHeight = raster.meanCellHeight
    cellSizeX = width * cellWidth / tileSize
    cellSizeY = height * cellHeight / tileSize
    tempTif = 'resample.tif'
    arcpy.Resample_management(inputTif, tempTif, str(cellSizeX) + " " + str(cellSizeY), method)
    arcpy.Delete_management(inputTif)
    arcpy.CopyRaster_management(tempTif, inputTif)
    arcpy.Delete_management(tempTif)


def get_raster_info(raster_path):
    info_dict = {}
    raster = arcpy.Raster(raster_path)
    info_dict['cell_height'] = raster.meanCellHeight
    info_dict['cell_width'] = raster.meanCellWidth
    info_dict['band_count'] = raster.bandCount
    info_dict['spatial_reference'] = raster.spatialReference
    info_dict['extent'] = raster.extent
    return info_dict


def stretch_tif(imageDir, outTif, outputImg, stretch_method=0, stretch_parameters=None):
    arcpy.env.workspace = imageDir
    my_array = arcpy.RasterToNumPyArray(outTif)  #
    min = np.min(my_array)
    max = np.max(my_array)
    if stretch_parameters == '' or stretch_parameters == 0:
        stretch_parameters = None
    # default is Percentage Truncation stretch
    stretch = percentStretch(my_array)
    if stretch_method == 0:  # Percentage Truncation
        if stretch_parameters is not None:
            stretchParameters = stretch_parameters.split(',')
            stretchParameters.sort()
            stretchPercentMin = float(stretchParameters[0])
            stretchPercentMax = float(stretchParameters[1])
            stretch = percentStretch(my_array, stretchPercentMin, stretchPercentMax)
    if stretch_method == 1:  # Standard Deviation
        if stretch_parameters is not None:
            stdDevStretch = float(stretch_parameters)
            stretch = stdStretch(my_array, stdDevStretch)
        else:
            stretch = stdStretch(my_array)  # default is 2.5
    if stretch_method == 2:  # Maximum and Minimum
        stretch = minmaxStretch(my_array)
    new_raster = arcpy.NumPyArrayToRaster(stretch)
    arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "",
                                "8_BIT_UNSIGNED")
    arcpy.Delete_management(new_raster)


def removeTempFiles(imageDir):
    for file in os.listdir(imageDir):
        if os.path.isdir(os.path.join(imageDir, file)):
            shutil.rmtree(os.path.join(imageDir, file))
        else:
            extensions = ['.jpg', '.png', '.jgw', '.pgw', '.tif', '.tfw']
            _, extension = os.path.splitext(file)
            if not extension in extensions:
                os.remove(os.path.join(imageDir, file))
