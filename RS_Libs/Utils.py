import os
import arcpy
import shutil


def getPolygonType(shpPath):
    fl = arcpy.MakeFeatureLayer_management(shpPath)
    desc = arcpy.Describe(fl)
    shape_type = desc.shapeType
    return shape_type


def checkInput(args, band_count):
    bands_order = []
    if args.band_list is None:
        return bands_order
    if len(args.band_list) != 0:
        bands = args.band_list.split(',')
        bands_order = list(map(int, bands))
        if max(bands_order) > band_count:
            raise Exception('input band list is illegal')
        if min(bands_order) < 1:
            raise Exception('Band index value must start from 1')
        if args.output_img_format in ['JPEG', 'PNG'] and len(bands_order) != 3:
            raise Exception("If the export is PNG or JPG, the length of band_list must be 3")
    else:
        if args.output_img_format in ['JPEG', 'PNG'] and band_count != 3:
            raise Exception("The number of bands of the input image does not match the output, band_list is required")

    return bands_order


def copyFeatures(inputShp, output_dir, create_temp_id=False):
    processingFeatures = os.path.join(output_dir, 'processing.shp')
    arcpy.CopyFeatures_management(inputShp, processingFeatures)
    if create_temp_id:
        arcpy.AddField_management(processingFeatures, "tempID", "SHORT")
        fields = ["tempID"]
        with arcpy.da.UpdateCursor(processingFeatures, fields) as cursor:
            for row in cursor:
                row[0] = 0
                cursor.updateRow(row)
    return processingFeatures

def getArcpyVersion():
    version = arcpy.GetInstallInfo()['Version']
    numbers = str(version).split('.')


def checkInputOutput(inputShp, outputFolder):
    if str(getPolygonType(inputShp)).lower() != 'polygon':
        raise Exception('input shpfile must be polygon type')
    if not os.path.exists(outputFolder):
        os.mkdir(outputFolder)