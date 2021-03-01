# LabelRS
A toolbox to make deep learning samples from remote sensing images  
We strongly recommend using Python scripts instead of ArcGIS plugins

# Requirements
* ESRI ArcGIS 10.2 and later versions  
* Python Library: tqdm, opencv, pillow  

<b>Note:</b> Need to select ArcGIS's python environment as the python interpreter, for example, C:\Python27\ArcGIS10.2\python.exe
Similarly, tqdm, opencv, pillow need to be installed in the ArcGIS python environment
# usage
create remote sensing images and labels for semantic segmentation  

`SemanticSegmentation.py --input-image=xxx.tif --input-shpfile=xxx.shp --class-field=xxx --output-path=xxx`  

Parameters Description  


