# coding=utf-8
'''
created by Junjie li, November,2020
This code is used to create remote sensing images and labels for semantic segmentation
'''
import arcpy
import os
import sys
import shutil
import arcpy.cartography as CA
import argparse
from tqdm import tqdm

from RS_Libs.Labels import getLabelMappingList, makeLabel, writeLabelXML
from RS_Libs.Polygons import simplify_polygon, extentToPolygon
from RS_Libs.Rasters import get_raster_info, generateImg
from RS_Libs.Utils import checkInput, copyFeatures, checkInputOutput

reload(sys)
sys.setdefaultencoding('utf-8')


def parse_args():

    parser = argparse.ArgumentParser(description="Making Remote Sensing Samples for semantic segmentation")
    # basic
    parser.add_argument('--input-image', type=str, default='')

    parser.add_argument('--input-shpfile', type=str, default='')

    parser.add_argument('--class-field', type=str, default='class',
                        help='field to distinguish different features in shpfile,'
                             'Do not use the number 0 to refer to a class')

    parser.add_argument('--tile-size', type=int, default=256, help='tile size')

    parser.add_argument('--output-path', type=str, default='', help='output folder')

    parser.add_argument('--output-img-format', type=str, default='JPEG', choices=['TIFF', 'JPEG', 'PNG'],
                        help='the output image foramt')

    # optional
    parser.add_argument('--overlap-size', type=int, default=16,
                        metavar='N', help='tile overlap size', required=False)

    parser.add_argument('--band-list', type=str, default='4,3,2', required=False,
                        help='output rgb bands list, split with comma, eg."3,2,1"')

    parser.add_argument('--write-xml', type=bool, default=True, help='write meta data in xml',
                        required=False)

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default=None, required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    parser.add_argument('--gray-level-transformation', type=int, default=1,
                        required=False, choices=[0, 1, 2, 3],
                        help='0,None; 1,Maximum Contrast; 2,Positive Integer; 3,Custom')

    parser.add_argument('--glt-parameters', type=str, default=None, required=False,
                        help='it is required when label mapping method is Custom, eg. "water:1,building:2,vege:3"')

    parser.add_argument('--filter', type=float, default=0.05, required=False,
                        help='Images with foreground pixels less than filter will be discarded')

    args = parser.parse_args()

    return args


def segmentation(inputShp, inputTif,resultFolder,tag=0):

    arcpy.AddMessage('Creating images and labels for {}'.format(inputTif))
    # temp workspace
    tempWorkSpace = os.path.join(resultFolder, 'tempworkspace')
    if not os.path.exists(tempWorkSpace):
        os.mkdir(tempWorkSpace)

    # img meta data info
    arcpy.env.workspace = tempWorkSpace
    img_meta_info = get_raster_info(inputTif)

    # check input
    bands_order = checkInput(args, img_meta_info['band_count'])
    GLT = int(args.gray_level_transformation)
    GLT_para = args.glt_parameters
    if GLT == 3 and len(GLT_para) == 0:
        raise Exception('gray level transformation parameters are required')

    # copy features
    processingFeatures = copyFeatures(inputShp, resultFolder, create_temp_id=False)

    labelMapping_dict = getLabelMappingList(processingFeatures, args.class_field,
                                               GLT, GLT_para)
    arcpy.AddMessage('Creating vector grids ...')

    # polygon simplify
    gridsPath, matchcount = simplify_polygon(tempWorkSpace, processingFeatures,
                                resultFolder, img_meta_info,
                                args.tile_size, args.overlap_size)

    # generate label tif
    labelTiff = os.path.join(tempWorkSpace, 'label.tif')
    arcpy.env.extent = img_meta_info['extent']
    if GLT in [0, 1]:
        arcpy.PolygonToRaster_conversion(processingFeatures, args.class_field, labelTiff, '#', '#', inputTif)
    else:
        arcpy.PolygonToRaster_conversion(processingFeatures, 'ClassValue', labelTiff, '#', '#', inputTif)
    arcpy.Delete_management("in_memory")
    arcpy.ResetEnvironments()

    pbar = tqdm(total=matchcount)
    pbar.set_description("creating")
    fields = ['FID', 'SHAPE@']
    band_split = False
    if len(bands_order) > 0:
        band_split = True
    arcpy.env.workspace = tempWorkSpace
    with arcpy.da.SearchCursor(gridsPath, fields) as cursor:
        for row in cursor:
            tempShp = os.path.join(tempWorkSpace, 'temp0.shp')
            if os.path.exists(tempShp):
                arcpy.Delete_management(tempShp)
            arcpy.FeatureClassToFeatureClass_conversion(row[1], tempWorkSpace, 'temp0.shp')
            pbar.update(1)
            # generate label
            outLabel = os.path.join(labelDir, str(tag).zfill(6) + '.png')
            succeed = makeLabel(tag, tempShp, labelTiff, labelDir, GLT,
                                labelMapping_dict, args.tile_size, args.filter)
            if not succeed:
                continue
            # generate img
            status, _ = generateImg(tag, inputTif, tempShp, imageDir,labelDir=labelDir,
                                    output_img_format=args.output_img_format,
                                    splitBands=band_split, bandsOrder=bands_order,
                                    stretch_method=args.stretch_method, stretch_parameters=args.stretch_parameters)
            if not status:
                if os.path.exists(outLabel):
                    os.remove(outLabel)
                continue

            # generate xml
            if args.write_xml:
                xmlPath = os.path.join(labelDir, str(tag).zfill(6) + '.xml')
                writeLabelXML(xmlPath, inputTif, outLabel, args.overlap_size,
                              GLT, labelMapping_dict, img_meta_info['spatial_reference'])
            arcpy.Delete_management(tempShp)
            tag += 1

    arcpy.Delete_management(labelTiff)
    arcpy.Delete_management(gridsPath)
    arcpy.Delete_management(processingFeatures)
    shutil.rmtree(tempWorkSpace)
    pbar.close()
    return tag


if __name__ == "__main__":

    args = parse_args()
    inputShp = args.input_shpfile
    inputTif = args.input_image
    resultFolder = args.output_path
    checkInputOutput(inputShp, resultFolder)
    imageDir = os.path.join(resultFolder, 'images')
    if not os.path.exists(imageDir):
        os.mkdir(imageDir)
    labelDir = os.path.join(resultFolder, 'labels')
    if not os.path.exists(labelDir):
        os.mkdir(labelDir)
    segmentation(inputShp, inputTif, resultFolder, tag=0)
