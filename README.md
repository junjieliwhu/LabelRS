# LabelRS
A toolbox to make deep learning samples from remote sensing images  
We strongly recommend using **Python scripts** instead of ArcGIS plugins

# Requirements
* ESRI ArcGIS 10.2 and later versions  
* Python Library: `tqdm`, `opencv`, `pillow`  

> <b>Note:</b> select ArcGIS's python environment as the python interpreter, the location usually is C:\Python27\ArcGIS10.2\python.exe  
> tqdm, opencv, pillow need to be installed in the ArcGIS python environment

# Data preparation
* Multispectral GeoTif, eg. GF2, WorldView，SPOT, Landsat (Layer Stacking is needed)
* Labeled vector polygon data, it can be from the following
 1. Public land use vector data
 2. Drawn by users in ArcGIS. Build a new shapefile and add a field in attribute table, then start editing and draw polygons, finally set different attribute values for different types of features.
 3. Use eCognition. Use multiresolution segmentation in eCognition, and then output the segmentation vectors.
 4. Use [AutoDraw](https://github.com/junjieliwhu/LabelRS/tree/main/AutoDraw) in LabelRS to to assist segmentation. This is an independent toolkit based on GDAL, skimage and PIL, which can run in python2 and python3 environments. First, go to [main.py](https://github.com/junjieliwhu/LabelRS/blob/main/AutoDraw/main.py), set SEGMENT_METHOD and RGB_LIST, set input and output. Then run main.py.

# Usage
* ## create semantic segmentation  samples

```Python  
SemanticSegmentation.py --input-image=xxx.tif --input-shpfile=xxx.shp --class-field=xxx --output-path=xxx  
```

![water](https://github.com/junjieliwhu/LabelRS/blob/main/img/seg1.jpg)
![water](https://github.com/junjieliwhu/LabelRS/blob/main/img/seg1.png)


### Parameters Description  

|             NAME            |  TYPE | REQUIRED |                                             DESCRIPTION                                            | DEFAULT |               EXAMPLE               |
|:---------------------------:|:-----:|:--------:|:--------------------------------------------------------------------------------------------------:|:-------:|:-----------------------------------:|
|        --input-image        |  str  |   True   |                                      the input source imagery                                      |   None  | C:/GF2_PMS1_ L1A0003131556-MSS1.tif |
|       --input-shpfile       |  str  |   True   |                                       the labeled vector data                                      |   None  |             C:/Water.shp            |
|        --class-field        |  str  |   True   |                     The field used to distinguish different features in shpfile                    |   None  |                class                |
|         --tile-size         |  int  |   False  |                                    The size of the output sample                                   |   256   |                 256                 |
|        --output-path        |  str  |   True   |                                            output folder                                           |   None  |              C:/output              |
|     --output-img-format     |  str  |   False  |                    The format of the output sample, including JPEG, PNG and TIFF                   |   TIFF  |                 JPEG                |
|        --overlap-size       |  int  |   False  |                                          tile overlap size                                         |    16   |                  16                 |
|         --band-list         |  str  |   False  |                        Bands used to generate samples, default is all bands                        |   None  |                3,2,1                |
|         --write-xml         |  bool |   False  |                                  whether to write meta data in xml                                 |   True  |                 True                |
|       --stretch-method      |  int  |   False  |     Band stretching method 0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum    |    0    |                  0                  |
|     --stretch-parameters    |  str  |   False  |                the input parameters for Percentage Truncation or Standard Deviation                |   None  |               0.5,99.5              |
| --gray-level-transformation |  int  |   False  | The method of setting output label value, 0,None; 1,Maximum Contrast; 2,Positive Integer; 3,Custom |    0    |                  3                  |
|       --glt-parameters      |  str  |   False  |                    The input parameters when Gray Level Transformation is Custom                   |   None  |         Water:1, building:2         |
|           --filter          | float |   False  |                            Filter out samples with few foreground pixels                           |   0.05  |                   0.05              |

***

* ## create object detection samples

```Python  
ObjectDetection.py --input-image=xxx.tif --input-shpfile=xxx.shp --class-field=xxx --output-path=xxx  
```

![building](https://github.com/junjieliwhu/LabelRS/blob/main/img/object1.jpg)

### Parameters Description  

|         NAME         | TYPE | REQUIRED |                                          DESCRIPTION                                          |   DEFAULT  |               EXAMPLE              |
|:--------------------:|:----:|:--------:|:---------------------------------------------------------------------------------------------:|:----------:|:----------------------------------:|
|     --input-image    |  str |   TRUE   |                                    the input source imagery                                   |    None    | C:/GF2_PMS1_L1A0003131556-MSS1.tif |
|    --input-shpfile   |  str |   TRUE   |                                    the labeled vector data                                    |    None    |            C:/bridge.shp           |
|     --class-field    |  str |   TRUE   |                       The field used to distinguish different categories                      |    None    |                class               |
|      --tile-size     |  int |   FALSE  |                                 The size of the output sample                                 |     512    |                 512                |
|     --output-path    |  str |   TRUE   |                                         output folder                                         |    None    |              C:/output             |
|     --meta-format    |  str |   FALSE  |         The format of the output metadata labels, including PASCAL VOC, YOLO and KITTI        | PASCAL VOC |             PASCAL VOC             |
|  --output-img-format |  str |   FALSE  |                     the output image foramt, including JPEG, PNG and TIFF                     |    TIFF    |                JPEG                |
|    --overlap-size    |  int |   FALSE  |                             The overlap size of the output sample                             |     16     |                 16                 |
|      --band-list     |  str |   FALSE  |                            output bands list, default is all bands                            |    None    |                3,2,1               |
|   --stretch-method   |  int |   FALSE  | Band stretching method.  0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum |      0     |                  0                 |
| --stretch-parameters |  str |   FALSE  |           the input parameters used for Percentage Truncation or Standard Deviation           |    None    |              0.5,99.5              |
|       --vision       | bool |   FALSE  |                           whether to generate visualization results                           |    True    |                True                |                              |


***

* ## create  classification samples 

```Python 
Classification.py --input-image=xxx.tif --input-shpfile=xxx.shp --class-field=xxx --output-path=xxx 
```

![class](https://github.com/junjieliwhu/LabelRS/blob/main/img/classification.jpg)

### Parameters Description  

|         NAME         | TYPE | REQUIRED |                                              DESCRIPTION                                              | DEFAULT |               EXAMPLE              |
|:--------------------:|:----:|:--------:|:-----------------------------------------------------------------------------------------------------:|:-------:|:----------------------------------:|
|     --input-image    |  str |   TRUE   |                                        the input source imagery                                       |   None  | C:/GF2_PMS1_L1A0003131556-MSS1.tif |
|    --input-shpfile   |  str |   TRUE   |                                        the labeled vector data                                        |   None  |           C:/landuse.shp           |
|     --class-field    |  str |   TRUE   |                           The field used to distinguish different categories                          |   None  |                class               |
|      --tile-size     |  int |   FALSE  |                                     The size of the output sample                                     |   128   |                 64                 |
|     --output-path    |  str |   TRUE   |                                            The ouput folder                                           |   None  |              C:/output             |
|  --output-img-format |  str |   FALSE  |                     The format of the output sample, including JPEG, PNG and TIFF                     |   TIFF  |                TIFF                |
|    --overlap-size    |  int |   FALSE  |                                 The overlap size of the output sample                                 |    16   |                 16                 |
|      --band-list     |  str |   FALSE  |                                     Bands used to generate samples                                    |   None  |                3,2,1               |
|   --resampling-type  |  int |   FALSE  |                      Resampling method, including 0,Nearest; 1,Bilinear; 2,Cubic                      |    0    |                  0                 |
|   --stretch-method   |  int |   FALSE  | Band stretching method,including 0,Percentage Truncation; 1,Standard Deviation; 2,Maximum and Minimum |    0    |                  0                 |
| --stretch-parameters |  str |   FALSE  |                                the input parameters of band stretching                                |   None  |              0.5,99.5              |

# Citation


# Contact

Junjie Li, School of Remote Sensing and Information Engineering, Wuhan University  

Email: junjieli@whu.edu.cn




