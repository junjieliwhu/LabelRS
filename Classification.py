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
import utils.polygons as up
import utils.rasters as ur
import utils.classes as uc
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

    parser.add_argument('--tile-size', type=int, default=128, metavar='N', help='tile size')

    parser.add_argument('--output-path', type=str, default='', help='output folder')

    parser.add_argument('--output-img-format', type=str, default='TIFF', choices=['TIFF', 'JPEG', 'PNG'],
                        help='the output image foramt')
    # optional
    parser.add_argument('--overlap-size', type=int, default=16, metavar='N',
                        help='tile overlap size', required=False)

    parser.add_argument('--band-list', type=str, default='', required=False,
                        help='output bands list, split with comma, eg."3,2,1"')

    parser.add_argument('--resampling-type', type=int, default=0, required=False, choices=[0, 1, 2],
                        help='0,Nearest; 1,Bilinear; 2,Cubic')

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default='', required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    args = parser.parse_args()

    return args

def classification(inputShp, inputTif):

    arcpy.env.overwriteOutput = True
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
    bands_order = []

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

    # copy features
    processingFeatures = os.path.join(resultFolder, 'processing.shp')
    arcpy.CopyFeatures_management(inputShp, processingFeatures)
    arcpy.AddField_management(processingFeatures, "tempID", "SHORT")
    fields = ["tempID"]
    with arcpy.da.UpdateCursor(processingFeatures, fields) as cursor:
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)

    '''
       step1: Split large targets
    '''
    boxInfoList = []
    fields = ['FID', 'SHAPE@', str(args.class_field), 'tempID']
    arcpy.env.workspace = tempWorkSpace
    count = arcpy.GetCount_management(processingFeatures).getOutput(0)
    count = int(count.encode('utf-8'))
    pbar = tqdm(total=count)
    pbar.set_description("Processing step1")
    with arcpy.da.SearchCursor(processingFeatures, fields) as cursor:
        for row in cursor:
            poly = row[1]
            extent = poly.extent
            label = row[2]
            center_x, center_y = up.getCenter(extent)
            xmin, xmax, ymin, ymax = up.getBoundry(center_x, center_y, tile_size * cell_width / 2,
                                                   tile_size * cell_height / 2)
            imgPolygon = up.makePolygon(xmin, xmax, ymin, ymax, spatial_reference)
            if not imgPolygon.contains(poly):  # find large target
                tempShp = 'temp.shp'
                arcpy.FeatureClassToFeatureClass_conversion(poly, tempWorkSpace, tempShp)
                clipPolygons = up.classificationPolygons(tempShp, cell_width, cell_height, tile_size,
                                                         overlap_size, tempWorkSpace)
                for polygon in clipPolygons:
                    boxInfoList.append(uc.BoxInfo(polygon.extent, label, 0))
                arcpy.Delete_management(tempShp)
            else:
                boxInfoList.append(uc.BoxInfo(extent, label, 0))
            pbar.update(1)
    pbar.close()
    arcpy.Delete_management(processingFeatures)
    # create extents shpfiles for vision
    # temp=os.path.join(tempWorkSpace,'extent.shp')
    # polygons=[]
    # for box in boxInfoList:
    #     extent=box.extent
    #     polygons.append(up.extentToPolygon(extent))
    # arcpy.CopyFeatures_management(polygons, temp)

    count_dict = {}
    for boxInfo in boxInfoList:
        if not boxInfo.label in count_dict.keys():
            count_dict[str(boxInfo.label)] = 0

    raster_exent = raster.extent
    for object in tqdm(boxInfoList, desc='Processing step2'):
        imgExtent = object.extent
        label = object.label
        imageDir = os.path.join(resultFolder, str(label))
        if not os.path.exists(imageDir):
            os.makedirs(imageDir)

        if not raster_exent.contains(imgExtent):
            continue
        band_split = False
        if len(bands_order) > 0:
            band_split = True
        if args.output_img_format == 'TIFF':
            succeed = ur.makeTif(count_dict[str(label)], inputTif, up.extentToPolygon(imgExtent), imageDir,
                                 tile_size, args.resampling_type, band_split, bands_order)

        else:
            succeed = ur.makeJpgPng(count_dict[str(label)], inputTif, up.extentToPolygon(imgExtent), imageDir,
                                    tile_size, args.resampling_type,
                                    resultFormat=args.output_img_format,
                                    stretch_method=args.stretch_method,
                                    stretch_parameters=args.stretch_parameters,
                                    splitBands=band_split, bandsOrder=bands_order)
        if not succeed:
            continue

        count_dict[str(label)] += 1

    arcpy.Delete_management("in_memory")
    arcpy.ResetEnvironments()
    shutil.rmtree(tempWorkSpace)


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
    classification(inputShp, inputTif)
