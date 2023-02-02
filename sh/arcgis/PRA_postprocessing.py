#PRA_postprocessing.py
# Created on: October 17th, 2019
# Yves Buehler, Andreas Stoffel, SLF Davos
# ---------------------------------------------------------------------------
# Add akramms to PYTHONPATH, and import utilities therein
import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..', '..')))
import akramms.util.arcgisutil

# Import system modules
import sys, string, os

import arcpy
from arcpy import env
from arcpy.sa import *
import traceback


# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")
# Check out ArcGIS 3D Analyst extension license
arcpy.CheckOutExtension("3d")


env.overwriteOutput = True

#Script varibles...

akramms.util.arcgisutil.get_script_vars(globals(), (
    ('workspace', 'GetParameterAsText'),
    ('site' 'GetParameterAsText'),
    ('inShp', 'GetParameterAsText'),
    ('HS_flatfield', 'GetParameterAsText'),
    ('ref_elevation', 'GetParameterAsText'),
    ('gradient_snowdepth', 'GetParameterAsText'),
    ('wind_load', 'GetParameterAsText'),
    ('return_period', 'GetParameterAsText'),
    ('Naming', 'GetParameterAsText'),
))

#workspace += '\\'


arcpy.AddMessage("workspace = " + workspace)
arcpy.AddMessage("input Shapefile = " + inShp)
arcpy.AddMessage("HS delta 3 days = " + HS_flatfield)
arcpy.AddMessage("return periode = " + return_period)

#-------------------------------------------------------------------------------
# Export input parameters to csv_file
import csv
row1 = ["Site", "Shapefile with delineated PRA", "DHS3_flatfield [m]", "elevation of DHS3_flatfield [m.a.s.l.]", "snow depth increase with elevation [m/100m]", "snow drift [m]", "return period [years]", "Naming (For/NoFor)"]
row2 = [site, inShp, HS_flatfield, ref_elevation, gradient_snowdepth, wind_load, return_period, Naming]
array = [row1,row2]
Name_csv_file = os.path.join(workspace, site)
with open("%s_input_parameters.csv" % Name_csv_file,"w") as f:
    writer = csv.writer(f,delimiter=";")
    writer.writerows(array)
    f.close()

#-------------------------------------------------------------------------------
# calcualte release volume

# add fields to attribute table
#arcpy.AddField_management(inShp, "ID", "LONG")
arcpy.AddField_management(inShp, "d0star", "DOUBLE")
arcpy.AddField_management(inShp, "slopecorr", "DOUBLE")
arcpy.AddField_management(inShp, "d0_"+ return_period, "DOUBLE")
arcpy.AddField_management(inShp, "VOL_" + return_period, "DOUBLE")
arcpy.AddField_management(inShp, "Wind", "DOUBLE")

# add ID
#arcpy.CalculateField_management(inShp, 'ID', '!FID!', 'PYTHON3', '#')

# elevation correction
expression1 = "(" + str(HS_flatfield) + "+((" + "!Mean_DEM! -" + str(ref_elevation) + ")/100* %s))* math.cos(28 * (3.14159/180))" % gradient_snowdepth
d0star = arcpy.CalculateField_management(inShp, "d0star", expression1, "PYTHON")
arcpy.AddMessage(expression1)

# slope angle correction (slopecorr)
expression2 =  "0.291/(math.sin(!Mean_slope!*(3.14159/180)) - 0.202 * math.cos(!Mean_slope!*(3.14159/180)))"
slopecorr = arcpy.CalculateField_management(inShp, "slopecorr", expression2, "PYTHON", "")

# wind load interpolation between 1000 (0) and 2000 (full wind load) elevation
# change max windload dependent on scenario!!!
expression_wind = "Wind_calc(!Mean_DEM!)"
codeblock = """def Wind_calc(mean_dem):
    if mean_dem >= 2000:
        return 0.1
    elif mean_dem <= 1000:
        return 0
    else:
        return (mean_dem - 1000) * 0.0001""" # windload/1000 also z.B. 0.5/1000 = 0.0005

wind_load2 = arcpy.CalculateField_management(inShp, "Wind", expression_wind, "PYTHON", codeblock)


# calculate final d0 (d0_returnperiod)
expression3 =  "((!d0star! + !Wind!) * !slopecorr! )"
arcpy.CalculateField_management(inShp, "d0_" + str(return_period), expression3, "PYTHON", "")

# calculate volume (Vol_returnperiod)
expression3 =  "(!area_m2!/math.cos(!Mean_slope!*(3.14159/180))*!d0_" + str(return_period) + "!)"
arcpy.CalculateField_management(inShp, f"VOL_{return_period}", expression3, "PYTHON", "")

# Rick's raster file d0*, apply correction in Schweitz to get d0.  Probably also need to geometrically correct for slope angle.
# Need to compute mean d0 from each polygon, then do the slope angle correction.  Also have a factor wind-blown snow, discuss whether to include.
# Or just take value of d0 at center of release polygon.  Ricks' grid is very large.

#-------------------------------------------------------------------------------
# Same for Alaska and Schweitz
# categorize avalanches based on release volume

# get resolution
def unique_values(table, field):
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor})
res = unique_values(inShp,'Scene_reso')
res = str(int(res[0]))

# get field map
field_map = arcpy.FieldMappings()
field_map.addTable(inShp)

# execute categorization
category_tiny = f'{site}{Naming}_{res}m_{return_period}T_rel.shp'
arcpy.FeatureClassToFeatureClass_conversion(inShp, workspace, category_tiny, '"VOL_%s" < 5000' % (return_period), field_map, '#')

category_small = f'{site}{Naming}_{res}m_{return_period}S_rel.shp'
arcpy.FeatureClassToFeatureClass_conversion(inShp, workspace, category_small, '"VOL_%s" >= 5000 AND "VOL_%s" < 25000' % (return_period, return_period), field_map, '#')

category_medium = f'{site}{Naming}_{res}m_{return_period}M_rel.shp'
arcpy.FeatureClassToFeatureClass_conversion(inShp, workspace, category_medium, '"VOL_%s" >= 25000 AND "VOL_%s" < 60000' % (return_period, return_period), field_map, '#')

category_large = f'{site}{Naming}_{res}m_{return_period}L_rel.shp'
arcpy.FeatureClassToFeatureClass_conversion(inShp, workspace, category_large, '"VOL_%s" >= 60000' % (return_period), field_map, '#')

# delete empty shapefiles
category_list = [category_tiny, category_small, category_medium, category_large]
for file in category_list:
     file_path = os.path.join(workspace, file)
     if arcpy.management.GetCount(file_path)[0] == "0":
        arcpy.Delete_management(file_path)

