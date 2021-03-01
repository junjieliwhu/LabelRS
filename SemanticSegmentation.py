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
import utils.labels as ul
import utils.polygons as up
import utils.rasters as ur
from tqdm import tqdm

reload(sys)
sys.setdefaultencoding('utf-8')


def parse_args():

    parser = argparse.ArgumentParser(description="Making Remote Sensing Samples for semantic segmentation")
    # basic
    parser.add_argument('--input-image', type=str, default='')

    parser.add_argument('--input-shpfile', type=str, default='')

    parser.add_argument('--class-field', type=str, default='',
                        help='field to distinguish different features in shpfile,'
                             'Do not use the number 0 to refer to a class')

    parser.add_argument('--tile-size', type=int, default=256, metavar='N', help='tile size')

    parser.add_argument('--output-path', type=str, default='C:/', help='output folder')

    parser.add_argument('--output-img-format', type=str, default='TIFF', choices=['TIFF', 'JPEG', 'PNG'],
                        help='the output image foramt')

    # optional
    parser.add_argument('--overlap-size', type=int, default=16,
                        metavar='N', help='tile overlap size', required=False)

    parser.add_argument('--band-list', type=str, default='', required=False,
                        help='output bands list, split with comma, eg."3,2,1"')

    parser.add_argument('--write-xml', type=bool, default=True, help='write meta data in xml',
                        required=False)

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default='', required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    parser.add_argument('--gray-level-transformation', type=int, default=0,
                        required=False, choices=[0, 1, 2, 3],
                        help='0,None; 1,Maximum Contrast; 2,Positive Integer; 3,Custom')

    parser.add_argument('--glt-parameters', type=str, default='', required=False,
                        help='it is required when label mapping method is Custom, eg. "water:1,building:2,vege:3"')

    parser.add_argument('--filter', type=float, default=0.05, required=False,
                        help='Images with foreground pixels less than filter will be discarded')

    args = parser.parse_args()

    return args


def segmentation(inputShp, inputTif, tag=0):

    arcpy.AddMessage('Creating images and labels for {}'.format(inputTif))
    # temp workspace
    tempWorkSpace = os.path.join(resultFolder, 'tempworkspace')
    if os.path.exists(tempWorkSpace):
        shutil.rmtree(tempWorkSpace)
    if not os.path.exists(tempWorkSpace):
        os.mkdir(tempWorkSpace)

    # img meta data info
    arcpy.env.workspace = tempWorkSpace
    raster = arcpy.Raster(inputTif)
    cell_height = raster.meanCellHeight
    cell_width = raster.meanCellWidth
    band_count = raster.bandCount
    spatial_reference = raster.spatialReference
    tile_size = int(args.tile_size)
    overlap_size = int(args.overlap_size)
    filter = float(args.filter)
    bands_order = []
    GLT = args.gray_level_transformation
    GLT_para = args.glt_parameters
    stretch_method = int(args.stretch_method)

    # check input
    if len(args.band_list) != 0:
        bands = args.band_list.split(',')
        bands_order = list(map(int, bands))
        if max(bands_order) > band_count:
            raise Exception, 'input band list is illegal'
        if min(bands_order) < 1:
            raise Exception, 'Band index value must start from 1'
        if args.output_img_format in ['JPEG', 'PNG'] and len(bands_order) != 3:
            raise Exception, "If the export is PNG or JPG, the length of band_list must be 3"
    else:
        if args.output_img_format in ['JPEG', 'PNG'] and band_count != 3:
            raise Exception, "The number of bands of the input image " \
                             "does not match the output, band_list is required"
    if int(GLT) == 3 and len(GLT_para) == 0:
        raise Exception, 'gray level transformation parameters are required'

    # copy features
    processingFeatures = os.path.join(resultFolder, 'processing.shp')
    arcpy.CopyFeatures_management(inputShp, processingFeatures)

    labelMapping_dict = ul.getLabelMappingList(processingFeatures, args.class_field,
                                               GLT, GLT_para)
    arcpy.AddMessage('Creating vector grids ...')
    # polygon simplify
    arcpy.env.workspace = tempWorkSpace
    CA.SimplifyPolygon(processingFeatures, 'simplify.shp', "POINT_REMOVE", '50 meters')
    buffer_dis = cell_width * tile_size / 2
    buffer = os.path.join(tempWorkSpace, 'buffer.shp')
    arcpy.Buffer_analysis('simplify.shp', buffer, buffer_dis, "FULL", "ROUND", "ALL")
    buffer_single = os.path.join(tempWorkSpace, 'buffer_single.shp')
    arcpy.MultipartToSinglepart_management(buffer, buffer_single)
    arcpy.Delete_management(buffer)
    arcpy.Delete_management('simplify.shp')
    gridsPath = os.path.join(resultFolder, 'grids.shp')
    up.splitPolygons(buffer_single, cell_width, cell_height, tile_size,
                     overlap_size, tempWorkSpace, gridsPath, multiple=2)
    arcpy.AddMessage('Creating vector grids done !')
    arcpy.Delete_management(buffer_single)

    # Estimated total sample nums
    gridLyr = "gridsLyr"
    arcpy.MakeFeatureLayer_management(gridsPath, gridLyr)
    extent = raster.extent
    arcpy.CopyFeatures_management([up.extentToPolygon(extent)], 'poly.shp')
    tifLayer = 'tifLyr'
    arcpy.MakeFeatureLayer_management('poly.shp', tifLayer)
    arcpy.SelectLayerByLocation_management(gridLyr, 'intersect', tifLayer)
    matchcount = int(arcpy.GetCount_management(gridLyr)[0])
    arcpy.Delete_management(tifLayer)
    arcpy.Delete_management('poly.shp')
    arcpy.Delete_management(gridLyr)

    # make label tiff
    labelTiff = os.path.join(tempWorkSpace, 'label.tif')
    arcpy.env.extent = raster.extent
    if GLT in [0, 1]:
        arcpy.PolygonToRaster_conversion(processingFeatures, args.class_field, labelTiff, '#', '#', inputTif)
    else:
        arcpy.PolygonToRaster_conversion(processingFeatures, 'ClassValue', labelTiff, '#', '#', inputTif)
    arcpy.Delete_management("in_memory")
    arcpy.ResetEnvironments()

    pbar = tqdm(total=matchcount)
    pbar.set_description("creating")
    fields = ['FID', 'SHAPE@']
    bandSplit = False
    if len(bands_order) > 0:
        bandSplit = True
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
            succeed = ul.makeLabel(tag, tempShp, labelTiff, labelDir, GLT, labelMapping_dict, tile_size, filter)
            if not succeed:
                continue
            # generate img
            succeed = ur.createImgByPolygons(tag, inputTif, tempShp, imageDir, labelDir, args.output_img_format,
                                             stretch_method, args.stretch_parameters, bandSplit, bands_order)
            if not succeed:
                if os.path.exists(outLabel):
                    os.remove(outLabel)
                continue
            # generate xml
            if args.write_xml:
                xmlPath = os.path.join(labelDir, str(tag).zfill(6) + '.xml')
                ul.writeLabelXML(xmlPath, inputTif, outLabel, overlap_size, GLT, labelMapping_dict, spatial_reference)
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
    if str(up.getPolygonType(inputShp)).lower() != 'polygon':
        raise Exception, 'input shpfile must be polygon'
    # result path
    resultFolder = args.output_path
    if not os.path.exists(resultFolder):
        raise Exception, 'output not exists'
    imageDir = os.path.join(resultFolder, 'images')
    if not os.path.exists(imageDir):
        os.mkdir(imageDir)
    labelDir = os.path.join(resultFolder, 'labels')
    if not os.path.exists(labelDir):
        os.mkdir(labelDir)
    segmentation(inputShp, inputTif)
