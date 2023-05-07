# coding=utf-8

'''
created by Junjie li, November,2020
This code is used to create remote sensing images and labels for image classification
'''

import arcpy
import os
import sys
import shutil
import argparse
from RS_Libs.Polygons import split_large_targets, extentToPolygon
from RS_Libs.Rasters import get_raster_info, generateImg
from RS_Libs.Utils import checkInput, checkInputOutput, copyFeatures
from tqdm import tqdm

reload(sys)
sys.setdefaultencoding('utf-8')

def parse_args():
    parser = argparse.ArgumentParser(description="Making Remote Sensing Samples for image classification")
    # basic
    parser.add_argument('--input-image', type=str, default='')

    parser.add_argument('--input-shpfile', type=str, default='')

    parser.add_argument('--class-field', type=str, default='',
                        help='field to distinguish different features in shpfile')

    parser.add_argument('--tile-size', type=int, default=256, help='tile size')

    parser.add_argument('--output-path', type=str, default='', help='output folder')

    parser.add_argument('--output-img-format', type=str, default='TIFF', choices=['TIFF', 'JPEG', 'PNG'],
                        help='the output image foramt')
    # optional
    parser.add_argument('--overlap-size', type=int, default=16, metavar='N',
                        help='tile overlap size', required=False)

    parser.add_argument('--band-list', type=str, default='4,3,2', required=False,
                        help='output bands list, split with comma, eg."4,3,2" for Landsat-8 and Sentinel-2')

    parser.add_argument('--resampling-type', type=int, default=0, required=False, choices=[0, 1, 2],
                        help='0,Nearest; 1,Bilinear; 2,Cubic')

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default=None, required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    args = parser.parse_args()

    return args


def classification(inputShp, inputTif, args):

    arcpy.env.overwriteOutput = True
    tempWorkSpace = os.path.join(resultFolder, 'tempworkspace')
    if not os.path.exists(tempWorkSpace):
        os.mkdir(tempWorkSpace)

    # img meta data info
    arcpy.env.workspace = tempWorkSpace
    img_meta_info = get_raster_info(inputTif)

    # check input
    bands_order = checkInput(args, img_meta_info['band_count'])

    # copy features
    processingFeatures = copyFeatures(inputShp, resultFolder, create_temp_id=True)

    '-------------step1: Split large targets-------------------'
    boxInfoList = split_large_targets(processingFeatures, tempWorkSpace, img_meta_info, args)

    arcpy.Delete_management(processingFeatures)

    '-------------step2: Generate training images -------------'
    count_dict = {}
    for boxInfo in boxInfoList:
        if not boxInfo.label in count_dict.keys():
            count_dict[str(boxInfo.label)] = 0
    for object in tqdm(boxInfoList, desc='Processing step2'):
        imgExtent = object.extent
        label = object.label
        imageDir = os.path.join(resultFolder, str(label))
        if not os.path.exists(imageDir):
            os.makedirs(imageDir)
        if not img_meta_info['extent'].contains(imgExtent):
            continue
        band_split = False
        if len(bands_order) > 0:
            band_split = True
        status, _ = generateImg(count_dict[str(label)], inputTif, extentToPolygon(imgExtent), imageDir,
                                splitBands=band_split, bandsOrder=bands_order, resampling_type=args.resampling_type,
                                tile_size=int(args.tile_size), output_img_format=args.output_img_format,
                                stretch_method=args.stretch_method, stretch_parameters=args.stretch_parameters)
        if not status:
            continue
        count_dict[str(label)] += 1
    arcpy.Delete_management("in_memory")
    arcpy.ResetEnvironments()
    shutil.rmtree(tempWorkSpace)


if __name__ == "__main__":
    args = parse_args()
    inputShp = args.input_shpfile
    inputTif = args.input_image
    resultFolder = args.output_path
    checkInputOutput(inputShp, resultFolder)
    classification(inputShp, inputTif, args)
