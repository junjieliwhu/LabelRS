# coding=utf-8
'''
created by Junjie li, December,2020
This code is used to create remote sensing samples for object detection
'''
import arcpy
import os
import sys
import shutil
import utils.polygons as up
import utils.classes as cl
import utils.rasters as ur
import utils.labels as fl
from tqdm import tqdm
import argparse
import cv2

reload(sys)
sys.setdefaultencoding('utf-8')


def parse_args():

    parser = argparse.ArgumentParser(description="Making Remote Sensing Samples for Object Detection")
    # basic
    parser.add_argument('--input-image', type=str, default='')

    parser.add_argument('--input-shpfile', type=str, default='')

    parser.add_argument('--class-field', type=str, default='',
                        help='field to distinguish different features in shpfile')

    parser.add_argument('--tile-size', type=int, default=512, metavar='N', help='tile size')

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

    parser.add_argument('--band-list', type=str, default='',
                        help='output bands list, split with comma, eg."3,2,1"', required=False)

    parser.add_argument('--stretch-method', type=int, default=0,
                        choices=[0, 1, 2], required=False,
                        help='0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum')

    parser.add_argument('--stretch-parameters', type=str, default='', required=False,
                        help='stretch parameters used for Percentage Truncation or Standard Deviation')

    parser.add_argument('--vision', type=bool, default=True, required=False)

    args = parser.parse_args()

    return args


def detection(inputShp, inputTif, tag=0):

    arcpy.AddMessage('Creating images and labels for {}'.format(inputTif))

    # temp workspace
    tempWorkSpace = os.path.join(resultFolder, 'tempworkspace')
    if os.path.exists(tempWorkSpace):
        shutil.rmtree(tempWorkSpace)
    if not os.path.exists(tempWorkSpace):
        os.mkdir(tempWorkSpace)

    arcpy.env.workspace = tempWorkSpace

    # img meta data info
    raster = arcpy.Raster(inputTif)
    cell_height = raster.meanCellHeight
    cell_width = raster.meanCellWidth
    band_count = raster.bandCount
    geo_transform = cl.GeoTransform(inputTif)
    spatial_reference = raster.spatialReference
    tile_size = int(args.tile_size)
    class_field = args.class_field
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

    # copy
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
    fields = ['FID', 'SHAPE@', str(class_field), 'tempID']
    arcpy.env.workspace = tempWorkSpace
    deleteIDs = []
    count = arcpy.GetCount_management(processingFeatures).getOutput(0)
    count = int(count.encode('utf-8'))
    pbar = tqdm(total=count)
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
                clipPolygon = os.path.join(tempWorkSpace, 'clipPolygon.shp')
                up.splitPolygons(tempShp, cell_width, cell_height, tile_size, overlap_size, tempWorkSpace, clipPolygon)

                with arcpy.da.SearchCursor(clipPolygon, ['SHAPE@']) as cursor1:
                    for r in cursor1:
                        polygon = r[0]
                        if poly.contains(polygon) or not poly.disjoint(polygon):
                            intersectArea = poly.intersect(polygon, 4)
                            truncated = 1 - intersectArea.getArea() / (poly.getArea())
                            if truncated < 0: truncated = 0
                            boxInfo = cl.BoxInfo(intersectArea.extent, label, truncated)
                            boxInfoList.append(boxInfo)

                deleteIDs.append(row[0])
                arcpy.Delete_management(tempShp)
                arcpy.Delete_management(clipPolygon)

            pbar.set_description("Processing step1")
            pbar.update(1)
    pbar.close()
    # Delete the features that have been split in shpfile
    with arcpy.da.UpdateCursor(processingFeatures, fields) as cursor:
        for r in cursor:
            if r[0] in deleteIDs:
                r[3] = 1
                cursor.updateRow(r)
    input_lyr = "lyr"
    arcpy.MakeFeatureLayer_management(processingFeatures, input_lyr)
    arcpy.SelectLayerByAttribute_management(input_lyr, "NEW_SELECTION", '"tempID" = 1')
    if int(arcpy.GetCount_management(input_lyr).getOutput(0)) > 0:
        arcpy.DeleteFeatures_management(input_lyr)
    arcpy.Delete_management(input_lyr)

    boxinfos = up.getExtentWithClass(processingFeatures, class_field, tempWorkSpace)
    boxInfoList.extend(boxinfos)

    # yolo
    labelList = []
    for boxInfo in boxInfoList:
        if not boxInfo.label in labelList:
            labelList.append(boxInfo.label)
    labelList.sort()
    labelList = list(map(str, labelList))
    if args.meta_format == 'YOLO':
        with open(classNameTxt, "w+") as f:
            f.write('\n'.join(labelList))
    # # create extents shpfiles for vision
    # temp=os.path.join(tempWorkSpace,'extent.shp')
    # polygons=[]
    # for box in boxInfoList:
    #     extent=box.extent
    #     polygons.append(up.extentToPolygon(extent))
    # arcpy.CopyFeatures_management(polygons, temp)
    '''
    step2: get objects info
    '''
    objectList = []
    for i in tqdm(range(len(boxInfoList)), desc='Processing step2'):
        boxInfo = boxInfoList[i]
        ex = boxInfo.extent
        label = boxInfo.label
        truncation = boxInfo.truncated
        width, height = up.getWidthHeight(ex, cell_width, cell_height)
        center_x, center_y = up.getCenter(ex)

        xmin, xmax, ymin, ymax = up.getBoundry(center_x, center_y, tile_size * cell_width / 2,
                                               tile_size * cell_height / 2)
        imgPolygon = up.makePolygon(xmin, xmax, ymin, ymax, spatial_reference)

        neighbors = up.findNeighborBoxes(imgPolygon.extent, boxInfoList, cell_width, tile_size)
        boxList = []
        if len(neighbors) == 0:
            continue
        for j in range(len(neighbors)):
            neigBox = neighbors[j]
            ext = neigBox.extent
            value = neigBox.label
            trunca = neigBox.truncated

            poly = up.extentToPolygon(ext)
            if imgPolygon.contains(poly) or not imgPolygon.disjoint(poly):
                intersectArea = imgPolygon.intersect(poly, 4)
                truncated = 1 - intersectArea.getArea() / (poly.getArea())
                if truncated < 0: truncated = 0
                if trunca == 0 and truncated != 0:
                    boxList.append(cl.BoxInfo(intersectArea.extent, value, '{:.3f}'.format(truncated)))
                elif trunca != 0 and truncated == 0:
                    boxList.append(cl.BoxInfo(intersectArea.extent, value, '{:.3f}'.format(trunca)))
                else:
                    truncated = truncated * trunca
                    boxList.append(cl.BoxInfo(intersectArea.extent, value, '{:.3f}'.format(truncated)))

        object = cl.ObjectInfo(imgPolygon.extent, boxList, geo_transform, tile_size)
        objectInfos = object.getObject()
        objectList.append(objectInfos)

    arcpy.Delete_management(processingFeatures)

    '''
    step3: make samples
    '''
    arcpy.env.workspace = imageDir
    rasterExent = arcpy.Raster(inputTif).extent
    for object in tqdm(objectList, desc='Processing step3'):
        imgExtent = object[0]
        boxes = object[1]
        if not rasterExent.contains(imgExtent):
            continue
        bandSplit = False
        if len(bands_order) > 0:
            bandSplit = True
        succeed, ouputImg = ur.createImgByObjectInfo(inputTif, tag, args.output_img_format, imgExtent, imageDir,
                                                     splitBands=bandSplit, bandsOrder=bands_order,
                                                     stretch_method=args.stretch_method,
                                                     stretch_parameters=args.stretch_parameters)
        if not succeed:
            continue
        if args.meta_format == 'PASCAL VOC':
            xmlPath = os.path.join(labelDir, str(tag).zfill(6) + '.xml')
            fl.writeVOCXML(xmlPath, inputTif, ouputImg, boxes)
        elif args.meta_format == 'YOLO':
            txtPath = os.path.join(labelDir, str(tag).zfill(6) + '.txt')
            fl.writeYoloTxt(txtPath, boxes, tile_size, labelList)
        else:
            txtPath = os.path.join(labelDir, str(tag).zfill(6) + '.txt')
            fl.writeKittiTxt(txtPath, boxes)

        # for vision
        if args.vision:
            visionDir = os.path.join(resultFolder, 'vision')
            if not os.path.exists(visionDir):
                os.makedirs(visionDir)

            if args.output_img_format == 'TIFF':
                succeed, ouputImg = ur.createImgByObjectInfo(inputTif, tag, 'JPEG', imgExtent, visionDir,
                                                             splitBands=True, bandsOrder=[3, 2, 1])
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
    try:
        shutil.rmtree(tempWorkSpace)
    except Exception:
        pass
    finally:
        pass
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
