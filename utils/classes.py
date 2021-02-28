# coding=utf-8

import rasters as ra


class ObjectInfo():

    def __init__(self, img_extent, boxes, geo_transform, tile_size):

        self.geoTransform = geo_transform
        self.imgExtent = img_extent
        self.tileSize = tile_size
        self.boxesGeo = boxes
        self.boxesPixel = self.geoExtent2pixelExtent(boxes)

    def geoExtent2pixelExtent(self, box_info_list):

        pixel_width = self.geoTransform.pixelWidth
        pixel_height = self.geoTransform.pixelHeight
        box_list = []
        for i in range(len(box_info_list)):
            box_info = box_info_list[i]
            box = box_info.extent
            label = box_info.label
            truncated = box_info.truncated
            xmin_geo = box.XMin
            xmax_geo = box.XMax
            ymin_geo = box.YMin
            ymax_geo = box.YMax

            original_x = self.imgExtent.XMin
            original_y = self.imgExtent.YMax

            upleft_x = int((xmin_geo - original_x) / pixel_width)
            if upleft_x < 0:
                upleft_x = 0
            upleft_y = int((ymax_geo - original_y) / pixel_height)
            if upleft_y < 0:
                upleft_y = 0
            lowright_x = int((xmax_geo - original_x) / pixel_width)
            if lowright_x > (self.tileSize - 1):
                lowright_x = self.tileSize - 1
            lowright_y = int((ymin_geo - original_y) / pixel_height)
            if lowright_y > (self.tileSize - 1):
                lowright_y = self.tileSize - 1

            box_list.append([upleft_x, upleft_y, lowright_x, lowright_y, label, truncated])
        return box_list

    def getObject(self):
        return [self.imgExtent, self.boxesPixel]


class BoxInfo():
    def __init__(self, extent, label, truncated):
        self.extent = extent
        self.label = label
        self.truncated = truncated


class GeoTransform():
    def __init__(self, tif_path):
        content = ra.readTransform(tif_path)
        self.pixelWidth = float(content[0])
        self.rotateX = float(content[1])
        self.rotateY = float(content[2])
        self.pixelHeight = float(content[3])
        self.originX = float(content[4])
        self.originY = float(content[5])

    def getValues(self):
        return [self.pixelWidth, self.rotateX, self.rotateY, self.pixelHeight, self.originX, self.originY]
