# coding=utf-8
import arcpy
import os
import cv2
import numpy as np
import polygons as pl
import shutil


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


def getImgSize(imgPath):
    width = 0
    height = 0
    bands = 0
    if imgPath.endswith('.tif') or imgPath.endswith('.tiff'):
        raster = arcpy.Raster(imgPath)
        width = raster.width
        height = raster.height
        bands = raster.bandCount
    else:
        img = cv2.imread(imgPath)
        height, width, bands = img.shape
    return width, height, bands


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


def splitBands(inputTif, bandsOrder, workspace):
    arcpy.env.workspace = workspace
    tempRaster = 'tempRaster.tif'
    layer = "rdlayer"
    arcpy.MakeRasterLayer_management(inputTif, layer, "", "", bandsOrder)
    arcpy.CopyRaster_management(layer, tempRaster)
    arcpy.Delete_management(layer)
    arcpy.Delete_management(inputTif)
    arcpy.CopyRaster_management(tempRaster, inputTif)
    arcpy.Delete_management(tempRaster)


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


def createImgByObjectInfo(inputImg, tag, format, imgExtent,
                          workspace, splitBands=False, bandsOrder=[3, 2, 1],
                          stretch_method='Percentage Truncation', stretch_parameters=''):
    succeed = True
    arcpy.env.workspace = workspace
    outputTif = os.path.join(workspace, str(tag).zfill(6) + '.tif')
    arcpy.Clip_management(inputImg, "#", outputTif, pl.extentToPolygon(imgExtent),
                          "0", "None", "MAINTAIN_EXTENT")
    if splitBands:
        tempRaster = 'tempRaster.tif'
        layer = "rdlayer"
        arcpy.MakeRasterLayer_management(outputTif, layer, "", "", bandsOrder)
        arcpy.CopyRaster_management(layer, tempRaster)
        arcpy.Delete_management(layer)
        arcpy.Delete_management(outputTif)
        arcpy.CopyRaster_management(tempRaster, outputTif)
        arcpy.Delete_management(tempRaster)
    tfw = os.path.join(workspace, str(tag).zfill(6) + '.tfw')
    if not os.path.exists(tfw):
        arcpy.env.workspace = workspace
        arcpy.ExportRasterWorldFile_management(outputTif)

    if format == 'TIFF':
        if not checkFile(outputTif):
            arcpy.Delete_management(outputTif)
            succeed = False
        return succeed, outputTif

    if format == 'JPEG':
        outputImg = os.path.join(workspace, str(tag).zfill(6) + '.jpg')
        outputGeo = os.path.join(workspace, str(tag).zfill(6) + '.jgw')

    else:
        outputImg = os.path.join(workspace, str(tag).zfill(6) + '.png')
        outputGeo = os.path.join(workspace, str(tag).zfill(6) + '.pgw')

    my_array = arcpy.RasterToNumPyArray(outputTif)  #
    min = np.min(my_array)
    max = np.max(my_array)

    # default is Percentage Truncation stretch
    stretch = percentStretch(my_array)  # default is 0.5,99.5
    if stretch_method == 0:
        if len(stretch_parameters) != 0:
            stretchParameters = stretch_parameters.split(',')
            stretchParameters.sort()
            stretchPercentMin = float(stretchParameters[0])
            stretchPercentMax = float(stretchParameters[1])
            stretch = percentStretch(my_array, stretchPercentMin, stretchPercentMax)
    if stretch_method == 1:
        if len(stretch_parameters) != 0:
            stdDevStretch = float(stretch_parameters)
            stretch = stdStretch(my_array, stdDevStretch)
        else:
            stretch = stdStretch(my_array)  # default is 2.5
    if stretch_method == 2:
        stretch = minmaxStretch(my_array)
    new_raster = arcpy.NumPyArrayToRaster(stretch)
    arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "",
                                "8_BIT_UNSIGNED", "", "")
    arcpy.Delete_management(new_raster)
    shutil.copy(tfw, outputGeo)
    arcpy.Delete_management(outputTif)
    for file in os.listdir(workspace):
        if os.path.isdir(os.path.join(workspace, file)):
            shutil.rmtree(os.path.join(workspace, file))
        else:
            extensions = ['.jpg', '.png', '.jgw', '.pgw']
            _, extension = os.path.splitext(file)
            if not extension in extensions:
                os.remove(os.path.join(workspace, file))
    if not checkFile(outputImg):
        os.remove(outputImg)
        os.remove(outputGeo)
        succeed = False
    return succeed, outputImg


def createImgByPolygons(tag, inputImg, polygons, imageDir, labelDir, resultFormat='JPEG',
                        stretch_method=0, stretch_parameters='',
                        splitBands=False, bandsOrder=[3, 2, 1]):
    fileName = str(tag).zfill(6)
    outTif = os.path.join(imageDir, fileName + '.tif')
    arcpy.env.workspace = imageDir
    arcpy.Clip_management(inputImg, "#", outTif, polygons, "0", "None", "MAINTAIN_EXTENT")
    if splitBands:
        arcpy.env.workspace = imageDir
        tempRaster = 'tempRaster.tif'
        layer = "rdlayer"
        arcpy.MakeRasterLayer_management(outTif, layer, "", "", bandsOrder)
        arcpy.CopyRaster_management(layer, tempRaster)
        arcpy.Delete_management(layer)
        arcpy.Delete_management(outTif)
        arcpy.CopyRaster_management(tempRaster, outTif)
        arcpy.Delete_management(tempRaster)

    tfw = fileName + '.tfw'
    if not os.path.exists(os.path.join(imageDir, tfw)):
        arcpy.env.workspace = imageDir
        arcpy.ExportRasterWorldFile_management(outTif)
    shutil.copy(os.path.join(imageDir, tfw), os.path.join(labelDir, fileName + '.pgw'))

    if resultFormat == 'TIFF':
        if not checkFile(outTif):
            arcpy.Delete_management(outTif)
            os.remove(os.path.join(labelDir, fileName + '.pgw'))
            os.remove(os.path.join(labelDir, fileName + '.png'))
            return False
        return True

    if resultFormat == 'JPEG':
        outputImg = os.path.join(imageDir, fileName + '.jpg')
        outputGeo = os.path.join(imageDir, fileName + '.jgw')

    else:
        outputImg = os.path.join(imageDir, fileName + '.png')
        outputGeo = os.path.join(imageDir, fileName + '.pgw')

    arcpy.env.workspace = imageDir
    my_array = arcpy.RasterToNumPyArray(outTif)  #
    min = np.min(my_array)
    max = np.max(my_array)

    # default is Percentage Truncation stretch
    stretch = percentStretch(my_array)  # default is 0.5,99.5
    if stretch_method == 0:
        if len(stretch_parameters) != 0:
            stretchParameters = stretch_parameters.split(',')
            stretchParameters.sort()
            stretchPercentMin = float(stretchParameters[0])
            stretchPercentMax = float(stretchParameters[1])
            stretch = percentStretch(my_array, stretchPercentMin, stretchPercentMax)
    if stretch_method == 1:
        if len(stretch_parameters) != 0:
            stdDevStretch = float(stretch_parameters)
            stretch = stdStretch(my_array, stdDevStretch)
        else:
            stretch = stdStretch(my_array)  # default is 2.5
    if stretch_method == 2:
        stretch = minmaxStretch(my_array)
    new_raster = arcpy.NumPyArrayToRaster(stretch)
    # lower version 10.2
    arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "",
                                "8_BIT_UNSIGNED", "", "")
    # higher version 10.5
    # arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "",
    #                             "8_BIT_UNSIGNED", "", "", 'JPEG')
    arcpy.Delete_management(new_raster)
    shutil.copy(os.path.join(imageDir, tfw), outputGeo)
    arcpy.Delete_management(outTif)
    for file in os.listdir(imageDir):
        if os.path.isdir(os.path.join(imageDir, file)):
            shutil.rmtree(os.path.join(imageDir, file))
        else:
            extensions = ['.jpg', '.png', '.jgw', '.pgw']
            _, extension = os.path.splitext(file)
            if not extension in extensions:
                os.remove(os.path.join(imageDir, file))
    if not checkFile(outputImg):
        os.remove(outputImg)
        os.remove(outputGeo)
        os.remove(os.path.join(labelDir, fileName + '.pgw'))
        os.remove(os.path.join(labelDir, fileName + '.png'))
        return False

    return True


def makeTif(tag, inputImg, inputFeature, imageDir, tileSize, resample_method, splitBands=False, bandsOrder=[3, 2, 1]):
    outTif = os.path.join(imageDir, str(tag).zfill(6) + '.tif')
    arcpy.Clip_management(inputImg, "#", outTif, inputFeature, "0", "None", "MAINTAIN_EXTENT")
    tfw = os.path.join(imageDir, str(tag).zfill(6) + '.tfw')
    if not os.path.exists(tfw):
        arcpy.env.workspace = imageDir
        arcpy.ExportRasterWorldFile_management(outTif)
    if splitBands:
        arcpy.env.workspace = imageDir
        tempRaster = 'tempRaster.tif'
        layer = "rdlayer"
        arcpy.MakeRasterLayer_management(outTif, layer, "", "", bandsOrder)
        arcpy.CopyRaster_management(layer, tempRaster)
        arcpy.Delete_management(layer)
        arcpy.Delete_management(outTif)
        arcpy.CopyRaster_management(tempRaster, outTif)
        arcpy.Delete_management(tempRaster)
    if not checkFile(outTif):
        arcpy.Delete_management(outTif)
        return False
    resample(outTif, tileSize, resample_method)
    return True


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


def makeJpgPng(tag, inputImg, inputFeature, imageDir,
               tileSize, resample_method, resultFormat='JPEG',
               stretch_method='Percentage Truncation', stretch_parameters='',
               splitBands=False, bandsOrder=[3, 2, 1]):
    outTif = os.path.join(imageDir, str(tag).zfill(6) + '.tif')
    arcpy.Clip_management(inputImg, "#", outTif, inputFeature, "0", "None", "MAINTAIN_EXTENT")
    if splitBands:
        arcpy.env.workspace = imageDir
        tempRaster = 'tempRaster.tif'
        layer = "rdlayer"
        arcpy.MakeRasterLayer_management(outTif, layer, "", "", bandsOrder)
        arcpy.CopyRaster_management(layer, tempRaster)
        arcpy.Delete_management(layer)
        arcpy.Delete_management(outTif)
        arcpy.CopyRaster_management(tempRaster, outTif)
        arcpy.Delete_management(tempRaster)

    resample(outTif, tileSize, resample_method)
    if resultFormat == 'JPEG':
        outputImg = os.path.join(imageDir, str(tag).zfill(6) + '.jpg')
        outputGeo = os.path.join(imageDir, str(tag).zfill(6) + '.jgw')
    else:
        outputImg = os.path.join(imageDir, str(tag).zfill(6) + '.png')
        outputGeo = os.path.join(imageDir, str(tag).zfill(6) + '.pgw')
    arcpy.env.workspace = imageDir
    my_array = arcpy.RasterToNumPyArray(outTif)  #
    min = np.min(my_array)
    max = np.max(my_array)
    if min < 0 or max > 255:
        # default is Percentage Truncation stretch
        stretch = percentStretch(my_array)  # default is 0.5,99.5
        if stretch_method == 'Percentage Truncation':
            if len(stretch_parameters) != 0:
                stretchParameters = stretch_parameters.split(',')
                stretchParameters.sort()
                stretchPercentMin = float(stretchParameters[0])
                stretchPercentMax = float(stretchParameters[1])
                stretch = percentStretch(my_array, stretchPercentMin, stretchPercentMax)
        if stretch_method == 'Standard Deviation':
            if len(stretch_parameters) != 0:
                stdDevStretch = float(stretch_parameters)
                stretch = stdStretch(my_array, stdDevStretch)
            else:
                stretch = stdStretch(my_array)  # default is 2.5
        if stretch_method == 'Maximum and Minimum':
            stretch = minmaxStretch(my_array)
        new_raster = arcpy.NumPyArrayToRaster(stretch)

        arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "",
                                    "8_BIT_UNSIGNED", "", "")
        # higher version 10.5
        # arcpy.CopyRaster_management(new_raster, outputImg, "DEFAULTS", "0", "0", "", "","8_BIT_UNSIGNED", "", "", 'JPEG')
        arcpy.Delete_management(new_raster)

    else:
        arcpy.CopyRaster_management(outTif, outputImg, "DEFAULTS", "0", "0", "", "",
                                    "8_BIT_UNSIGNED", "", "")

    tfw = str(tag).zfill(6) + '.tfw'
    if not os.path.exists(os.path.join(imageDir, tfw)):
        arcpy.env.workspace = imageDir
        arcpy.ExportRasterWorldFile_management(outTif)

    shutil.copy(os.path.join(imageDir, tfw), outputGeo)
    arcpy.Delete_management(outTif)

    for file in os.listdir(imageDir):
        if os.path.isdir(os.path.join(imageDir, file)):
            shutil.rmtree(os.path.join(imageDir, file))
        else:
            extensions = ['.jpg', '.png', '.jgw', '.pgw']
            _, extension = os.path.splitext(file)
            if not extension in extensions:
                os.remove(os.path.join(imageDir, file))

    if not checkFile(outputImg):
        os.remove(outputImg)
        os.remove(outputGeo)
        return False

    return True
