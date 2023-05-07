# coding=utf-8
'''
created by Junjie li, December,2020
This code is used to create remote sensing samples for object detection
'''
import arcpy
import os
import sys
import shutil

from RS_Libs.Labels import writeYoloClass, writeVOCXML, writeYoloTxt, writeKittiTxt
from RS_Libs.Polygons import split_larget_objects, get_objects_info, extentToPolygon
from RS_Libs.Rasters import get_raster_info, GeoTransform, generateImg
from tqdm import tqdm
import argparse
import cv2

from RS_Libs.Utils import checkInput, copyFeatures, checkInputOutput

reload(sys)
sys.setdefaultencoding('utf-8')


def parse_args():
    parser = argparse.ArgumentParser(description="Making Remote Sensing Samples for Object Detection")
    # basic
    parser.add_argument('--input-image', type=str, default='')

    parser.add_argument('--input-shpfile', type=str, default='')

    parser.add_argument('--class-field', type=str, default='',
                        help='field to distinguish different features in shpfile')

    parser.add_argument('--tile-size', type=int, default=512, help='tile size')

    parser.add_argument('--output-path', type=str, default='', help='output folder')

    parser.add_argument('--meta-format', type=str, default='PASCAL VOC',
                        choices=['PASCAL VOC', 'YOLO', 'KITTI'],
                        help='the output sample foramt')

    parser.add_argument('--output-img-format', type=str, default='TIFF',
                        choices=['TIFF', 'JPEG', 'PNG'],
                        help='the output image foramt')

    # optional
    parser.add_argument('--overlap-size', type=int, default=16, metavar='N',
                        help='tile overlap size', required=False)

    parser.add_argument('--band-list', type=str, default='3,2,1',
                        help='output bands list, split with comma, eg."3,2,1"', required=False)

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default=None, required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    parser.add_argument('--vision', type=bool, default=True, required=False,
                        help='draws rectangular boxes on images for visualization')

    args = parser.parse_args()

    return args


def detection(inputShp, inputTif, tag=0):

    arcpy.AddMessage('Creating images and labels for {}'.format(inputTif))

    # temp workspace
    tempWorkSpace = os.path.join(resultFolder, 'tempworkspace')
    if not os.path.exists(tempWorkSpace):
        os.mkdir(tempWorkSpace)

    arcpy.env.workspace = tempWorkSpace

    # img meta data info
    img_meta_info = get_raster_info(inputTif)
    geo_transform = GeoTransform(inputTif)

    # check input
    bands_order = checkInput(args, img_meta_info['band_count'])

    # copy features
    processingFeatures = copyFeatures(inputShp, resultFolder, create_temp_id=True)

    '-------------step1: Split large objects-------------------'
    boxInfoList = split_larget_objects(processingFeatures, tempWorkSpace, img_meta_info, args)

    # get labels for Yolo
    if args.meta_format == 'YOLO':
        labelList = writeYoloClass(boxInfoList, classNameTxt)

    '------------step2: get objects info----------------------'
    objectList = get_objects_info(boxInfoList, img_meta_info, geo_transform, args)
    arcpy.Delete_management(processingFeatures)

    '-------------step3: generate samples-------------------------'
    arcpy.env.workspace = imageDir
    for object in tqdm(objectList, desc='Processing step3'):
        imgExtent = object[0]
        boxes = object[1]
        if not img_meta_info['extent'].contains(imgExtent):
            continue
        band_split = False
        if len(bands_order) > 0:
            band_split = True
        status, ouputImg = generateImg(tag, inputTif, extentToPolygon(imgExtent), imageDir,
                                splitBands=band_split, bandsOrder=bands_order,
                                output_img_format=args.output_img_format,
                                stretch_method=args.stretch_method,
                                stretch_parameters=args.stretch_parameters)
        if not status:
            continue
        if args.meta_format == 'PASCAL VOC':
            xmlPath = os.path.join(labelDir, str(tag).zfill(6) + '.xml')
            writeVOCXML(xmlPath, inputTif, ouputImg, boxes)
        elif args.meta_format == 'YOLO':
            txtPath = os.path.join(labelDir, str(tag).zfill(6) + '.txt')
            writeYoloTxt(txtPath, boxes, int(args.tile_size), labelList)
        else:
            txtPath = os.path.join(labelDir, str(tag).zfill(6) + '.txt')
            writeKittiTxt(txtPath, boxes)

        if args.vision and img_meta_info['band_count'] > 3 and not band_split:
            raise Exception('If you want to visualize the annotations and samples, '
                            'specify the RGB band index using the band-List parameter '
                            'when the number of bands in the image is greater than 3')
        if args.vision:
            visionDir = os.path.join(resultFolder, 'vision')
            if not os.path.exists(visionDir):
                os.makedirs(visionDir)

            if args.output_img_format == 'TIFF':
                status, ouputImg = status, ouputImg = generateImg(tag, inputTif,
                                extentToPolygon(imgExtent), visionDir,
                                splitBands=band_split, bandsOrder=bands_order,
                                output_img_format='JPEG',
                                stretch_method=args.stretch_method,
                                stretch_parameters=args.stretch_parameters)
            img = cv2.imread(ouputImg)
            for object in boxes:
                upleft_x = int(object[0])
                upleft_y = int(object[1])
                lowright_x = int(object[2])
                lowright_y = int(object[3])
                label = object[4]
                truncated = object[5]
                cv2.rectangle(img, (upleft_x, upleft_y), (lowright_x, lowright_y), (0, 255, 0), 2)
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(img, str(label), (int((upleft_x + lowright_x) / 2),
                                              int((upleft_y + lowright_y) / 2)), font,
                            0.5, (200, 255, 255), 1)
            cv2.imwrite(os.path.join(visionDir, str(tag).zfill(6) + '.jpg'), img)
            if os.path.exists(os.path.join(visionDir, str(tag).zfill(6) + '.jgw')):
                os.remove(os.path.join(visionDir, str(tag).zfill(6) + '.jgw'))
        tag += 1
    arcpy.Delete_management("in_memory")
    arcpy.ResetEnvironments()
    shutil.rmtree(tempWorkSpace)
    return tag


if __name__ == "__main__":
    args = parse_args()
    inputShp = args.input_shpfile
    inputTif = args.input_image
    resultFolder = args.output_path
    checkInputOutput(inputShp, resultFolder)
    # output images and labels path
    if args.meta_format == 'PASCAL VOC':
        vocDir = os.path.join(resultFolder, 'PASCAL VOC')
        if not os.path.exists(vocDir):
            os.mkdir(vocDir)
        imageDir = os.path.join(vocDir, 'JPEGImages')
        if not os.path.exists(imageDir):
            os.mkdir(imageDir)
        labelDir = os.path.join(vocDir, 'Annotations')
        if not os.path.exists(labelDir):
            os.mkdir(labelDir)
    elif args.meta_format == 'YOLO':
        yoloDir = os.path.join(resultFolder, 'YOLO')
        if not os.path.exists(yoloDir):
            os.mkdir(yoloDir)
        imageDir = os.path.join(yoloDir, 'images')
        if not os.path.exists(imageDir):
            os.mkdir(imageDir)
        labelDir = os.path.join(yoloDir, 'labels')
        if not os.path.exists(labelDir):
            os.mkdir(labelDir)
        classNameTxt = os.path.join(resultFolder, 'class_names.txt')
        if os.path.exists(classNameTxt):
            os.remove(classNameTxt)
    else:
        kittiDir = os.path.join(resultFolder, 'KITTI')
        if not os.path.exists(kittiDir):
            os.mkdir(kittiDir)
        imageDir = os.path.join(kittiDir, 'images')
        if not os.path.exists(imageDir):
            os.mkdir(imageDir)
        labelDir = os.path.join(kittiDir, 'labels')
        if not os.path.exists(labelDir):
            os.mkdir(labelDir)

    detection(inputShp, inputTif)
