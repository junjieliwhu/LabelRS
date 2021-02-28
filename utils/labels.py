# coding=utf-8
import shutil

import arcpy
import os
from xml.dom.minidom import Document
import time
import getpass
from PIL import Image
import numpy as np
import rasters as ra


def errorMsg(msg):
    arcpy.AddError(msg)
    raise Exception, msg


def addMsg(msg):
    arcpy.AddMessage(msg)
    print msg


def warningMsg(msg):
    arcpy.AddWarning(msg)
    print msg


def writeVOCXML(xmlPath, originalImg, imgPath, objects):
    if os.path.exists(xmlPath):
        os.remove(xmlPath)
    doc = Document()
    # root
    Object = doc.createElement('annotation')
    doc.appendChild(Object)

    # folder, filename
    nodeNames = ['folder', 'filename']
    folder = os.path.dirname(xmlPath)
    fileName = os.path.basename(imgPath)
    values = [folder, fileName]
    for i in range(len(nodeNames)):
        nameNode = doc.createElement(str(nodeNames[i]))
        Object.appendChild(nameNode)
        data = doc.createTextNode(str(values[i]))
        nameNode.appendChild(data)

    # source node
    sourceNode = doc.createElement('source')
    Object.appendChild(sourceNode)
    nodeNames = ['imgsource', 'annotation']
    values = [str(originalImg), 'PASCAL VOC']
    for i in range(len(nodeNames)):
        nameNode = doc.createElement(str(nodeNames[i]))
        sourceNode.appendChild(nameNode)
        data = doc.createTextNode(str(values[i]))
        nameNode.appendChild(data)

    # size node
    sizeNode = doc.createElement('size')
    Object.appendChild(sizeNode)
    nodeNames = ['width', 'height', 'depth']
    width, height, bands = ra.getImgSize(imgPath)
    values = [str(width), str(height), str(bands)]
    for i in range(len(nodeNames)):
        nameNode = doc.createElement(str(nodeNames[i]))
        sizeNode.appendChild(nameNode)
        data = doc.createTextNode(str(values[i]))
        nameNode.appendChild(data)

    # spatial_reference = spatialReference
    # referenceCode = spatial_reference.factoryCode
    # referenceName=spatial_reference.name
    # spatialNode = doc.createElement('spatialReference')
    # Object.appendChild(spatialNode)
    # nodes=['name','factoryCode']
    # values=[referenceName,referenceCode]
    # for i in range(len(nodes)):
    #     childNode = doc.createElement(nodes[i])
    #     spatialNode.appendChild(childNode)
    #     data = doc.createTextNode(str(values[i]))
    #     childNode.appendChild(data)
    # geoNode=doc.createElement('geoTransform')
    # spatialNode.appendChild(geoNode)
    # nodes = ['pixelX', 'rtnX','rtnY','pixelY','ulX','ulY']
    # values = geoTransform.getValues()
    # for i in range(len(nodes)):
    #     childNode = doc.createElement(nodes[i])
    #     geoNode.appendChild(childNode)
    #     data = doc.createTextNode(str(values[i]))
    #     childNode.appendChild(data)

    # object node
    for object in objects:
        upleft_x = object[0]
        upleft_y = object[1]
        lowright_x = object[2]
        lowright_y = object[3]
        label = object[4]
        truncated = object[5]

        objectNode = doc.createElement('object')
        Object.appendChild(objectNode)

        # class node
        classNode = doc.createElement('class')
        objectNode.appendChild(classNode)
        data = doc.createTextNode(str(label))
        classNode.appendChild(data)

        # bndbox node
        boxNode = doc.createElement('bndbox')
        objectNode.appendChild(boxNode)
        nodeNames = ['xmin', 'xmax', 'ymin', 'ymax']
        values = [str(upleft_x), str(lowright_x), str(upleft_y), str(lowright_y)]
        for i in range(len(nodeNames)):
            nameNode = doc.createElement(str(nodeNames[i]))
            boxNode.appendChild(nameNode)
            data = doc.createTextNode(str(values[i]))
            nameNode.appendChild(data)

        # truncated node
        truncatedNode = doc.createElement('truncated')
        objectNode.appendChild(truncatedNode)
        data = doc.createTextNode(str(truncated))
        truncatedNode.appendChild(data)

    f = open(xmlPath, 'w')
    doc.writexml(f, indent='\t', newl='\n', addindent='\t', encoding='utf-8')
    f.close()


def writeYoloTxt(txtPath, objects, tileSize, labelList):
    with open(txtPath, "w+") as f:
        for object in objects:
            upleft_x = object[0]
            upleft_y = object[1]
            lowright_x = object[2]
            lowright_y = object[3]
            label = object[4]
            truncated = object[5]
            centerX = (upleft_x + lowright_x) / 2.0
            centerY = (upleft_y + lowright_y) / 2.0
            x_center = centerX / tileSize
            y_center = centerY / tileSize
            width = abs(lowright_x - upleft_x) * 1.0 / tileSize
            height = abs(lowright_y - upleft_y) * 1.0 / tileSize
            objectClassID = labelList.index(str(label))
            f.write(str(objectClassID) + " " + str(x_center) + " " + str(y_center) + " " + str(width) + " " + str(
                height) + "\n")


def writeKittiTxt(txtPath, objects):
    with open(txtPath, "w+") as f:
        for object in objects:
            upleft_x = object[0]
            upleft_y = object[1]
            lowright_x = object[2]
            lowright_y = object[3]
            label = str(object[4]).replace(" ", "")
            truncated = object[5]
            f.write(label + " " + str(truncated) + " 0 0 " + str(upleft_x) + " " + str(
                upleft_y) + " " + str(lowright_x) + " " + str(lowright_y) + " 0 0 0 0 0 0 0" + "\n")


def getLabelMappingList(infeatures, classAttribute, method, mappingParameters):
    # 0:None, 1:Maximum Contrast, 2:Positive Integer, 3:Custom
    mapping_dict = {}
    method=int(method)
    field_names = [f.name for f in arcpy.ListFields(infeatures)]
    if not str(classAttribute) in field_names:
        errorMsg("the field {} does not exist".format(classAttribute))
    fields = ['FID', classAttribute]
    values = []
    with arcpy.da.SearchCursor(infeatures, fields) as cursor:
        for row in cursor:
            classValue = str(row[1])
            if not classValue in values:
                values.append(classValue)
    values.sort()
    if values[0].isdigit() and values[-1].isdigit():  # class value is digital
        if int(values[0]) < 0 or int(values[-1]) > 255:
            if method in [0,1]:
                errorMsg('The label value is not in the range of 0 to 255,'
                         'gray level transformation must be Positive Integer or Custom')
        if method == 0:
            for i in values:
                mapping_dict[int(i)] = int(i)
        if method == 1:
            a = int(255 / len(values))
            for i in range(len(values)):
                mapping_dict[int(values[i])] = a * (i + 1)
    else:  # class value is string
        if method == 0 or method == 1:
            errorMsg('when class is string, '
                     'gray level transformation must be Positive Integer or Custom')
    if method == 2:
        # add a field
        arcpy.AddField_management(infeatures, "ClassValue", "SHORT")
        # get all label values
        fields = ["ClassValue", classAttribute]
        for i in range(len(values)):
            mapping_dict[str(values[i])] = i + 1
        # mapping dict
        with arcpy.da.UpdateCursor(infeatures, fields) as cursor:
            for row in cursor:
                for key in mapping_dict.keys():
                    if key == str(row[1]):
                        row[0] = mapping_dict[key]
                        cursor.updateRow(row)
    if method == 3:
        if len(mappingParameters) == 0:
            errorMsg('glt parameters is required')
        params = mappingParameters.replace(' ', '').split(',')
        if len(params) != len(values):
            errorMsg('glt parameters not match')
        for p in params:
            key = p.split(':')[0]
            value = p.split(':')[1]
            if not str(key) in values:
                errorMsg('glt parameters not match')
            if int(value) < 0 or int(value) > 255:
                errorMsg('glt parameters are illegal')
            mapping_dict[key] = int(value)

        # add a field
        arcpy.AddField_management(infeatures, "ClassValue", "SHORT")
        # get all label values
        fields = ["ClassValue", classAttribute]
        # mapping dict
        with arcpy.da.UpdateCursor(infeatures, fields) as cursor:
            for row in cursor:
                for key in mapping_dict.keys():
                    if key == str(row[1]):
                        row[0] = mapping_dict[key]
                        cursor.updateRow(row)
    return mapping_dict


def writeLabelXML(xmlPath, originalImg, labelPath, overlapSize, gltMethod, labelMappingDict, spatialReference):
    '''
    create a xml file for label, includes create date, time, format, source image...
    '''
    if os.path.exists(xmlPath):
        os.remove(xmlPath)
    doc = Document()
    Object = doc.createElement('metadata')
    doc.appendChild(Object)

    nodeNames = ['LabelName', 'CreateDate', 'CreateTime', 'Creater', 'SourceImage', 'Format',
                 'Height', 'Width', 'Overlap', 'GrayLevelTransformation']
    labelName = os.path.basename(labelPath)
    createDate = str(time.strftime("%Y-%m-%d", time.localtime()))
    createTime = str(time.strftime("%H:%M:%S", time.localtime()))
    Creater = str(getpass.getuser())  # 获取当前用户名
    SourceImage = os.path.basename(originalImg)
    Format = 'PNG'
    img = Image.open(labelPath)
    Width, Height = img.size
    Overlap = overlapSize
    gltMethod=int(gltMethod)
    LabelMappingMethod='None'
    if gltMethod == 1:
        LabelMappingMethod='Maximum Contrast'
    if gltMethod == 2:
        LabelMappingMethod = 'Positive Integer'
    if gltMethod == 3:
        LabelMappingMethod = 'Custom'
    values = [labelName, createDate, createTime, Creater, SourceImage, Format, Width, Height, Overlap,
              LabelMappingMethod]
    for i in range(len(nodeNames)):
        nameNode = doc.createElement(str(nodeNames[i]))
        Object.appendChild(nameNode)
        data = doc.createTextNode(str(values[i]))
        nameNode.appendChild(data)

    # add label mapping dict
    labelMappingNode = doc.createElement('GLT')
    Object.appendChild(labelMappingNode)
    for key, value in labelMappingDict.items():
        keyNode = doc.createElement(str(key))
        labelMappingNode.appendChild(keyNode)
        data = doc.createTextNode(str(value))
        keyNode.appendChild(data)

    spatial_reference = spatialReference
    referenceCode = spatial_reference.factoryCode
    referenceName = spatial_reference.name
    spatialNode = doc.createElement('SpatialReference')
    Object.appendChild(spatialNode)
    nodes = ['Name', 'FactoryCode']
    values = [referenceName, referenceCode]
    for i in range(len(nodes)):
        childNode = doc.createElement(nodes[i])
        spatialNode.appendChild(childNode)
        data = doc.createTextNode(str(values[i]))
        childNode.appendChild(data)
    f = open(xmlPath, 'w')
    doc.writexml(f, indent='\t', newl='\n', addindent='\t', encoding='utf-8')
    f.close()

def checkLabel(labelPath,sampleQuality):
    '''
    If the label we created has a small percentage of foreground pixels,
     we consider it invalid. Return false
    :param labelPath:
    :param sampleQuality:
    :return:
    '''
    valid=True
    img = Image.open(labelPath)
    clrs = img.getcolors()
    blackGround = 0
    foreGround = 0
    for num, value in clrs:
        if value == 0:
            blackGround = num
        else:
            foreGround += num
    if foreGround == 0:
        valid=False
    else:
        rate = 1 - blackGround * 1.0 / (foreGround + blackGround)
        if rate < sampleQuality:
            valid=False
    return valid

def labelMapping(inputLabel,method,mapping_dict,tileSize):
    img = Image.open(inputLabel)
    width,height=img.size
    if width!=tileSize or height!=tileSize:
        img = img.resize((tileSize, tileSize), Image.NEAREST)
    img = np.array(img)
    if int(method) == 1:
        for key, values in mapping_dict.items():
            np.putmask(img, img == int(key), int(values))
    mask = Image.fromarray(img.astype('uint8')).convert('RGB')
    return mask


def makeLabel(tag,inputFeature,label,labelDir,gltMethod,glt_dict,tileSize,filter=0.05):
    succeed = False
    fileName = str(tag).zfill(6)
    outLabel = os.path.join(labelDir, fileName + '.png')
    arcpy.env.workspace=labelDir
    arcpy.Clip_management(label, "#", outLabel, inputFeature, "0", "None", "MAINTAIN_EXTENT")
    if not checkLabel(outLabel, filter):
        arcpy.Delete_management(outLabel)
        return succeed
    # label mapping
    labelArray = labelMapping(outLabel, gltMethod,glt_dict,tileSize)
    arcpy.Delete_management(outLabel)
    labelArray.save(outLabel)
    succeed=True
    return succeed


