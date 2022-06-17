### -*- coding: utf-8 -*-
# data_prep_PRA_finder.py
# Created on: January 2018
# © Yves Buehler, Daniel von Rickenbach SLF Davos
# Modified by Elizabeth Fischer, University of Alaska, Fairbanks
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Add akramms to PYTHONPATH, and import utilities therein
import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..', '..')))
import dggs.util.arcgisutil

# Import system modules
import string
import arcpy
import arcpy.sa
import argparse

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")
# Check out ArcGIS 3D Analyst extension license
arcpy.CheckOutExtension("3d")

#-------------------------------------------------------------------------------
# Obtain script variables

dggs.util.arcgisutil.get_script_vars(globals(), (
    ('Workspace', 'GetParameterAsText'),
    ('inDEM', 'GetParameterAsText'),
    ('inForest', 'GetParameterAsText'),
    ('resampCellSize', 'GetParameterAsText'),
    ('inPerimeter', 'GetParameterAsText'),
    ('Slope_lowerlimit_frequent', 'GetParameterAsText'),
    ('Slope_lowerlimit_extreme', 'GetParameterAsText'),
    ('Slope_upperlimit', 'GetParameterAsText'),
    ('Curv_upperlimit', 'GetParameterAsText'),
    ('Rugged_neighborhood', 'GetParameterAsText'),
    ('Rugged_upperlimit', 'GetParameterAsText'),
    ('outCoordSystem', 'GetParameter'),
    ('Weightingkernel', 'GetParameterAsText'),
))

#Workspace += '\\'
#-------------------------------------------------------------------------------
# Convenience for constructing filenames
Name = os.path.basename(os.path.normpath(Workspace))
def BASE_DATA(leaf):
    return os.path.join(Workspace, 'base_data', leaf)
def ECOG(leaf):
    return os.path.join(Workspace, 'eCog', leaf)



# Local variables:
# Name of project, Eg: PRA_ElizabethAK

DEM_eCog = ECOG(f"{Name}_DEM.tif")
Forest = BASE_DATA(f"{Name}_Forest.tif")
Perimeter = BASE_DATA(f"{Name}_Perimeter.shp")
Perimeter_Envelope = BASE_DATA(f"{Name}_Perimeter_Envelope.shp")
Perimeter_Envelope_Buffer = BASE_DATA(f"{Name}_Perimeter_Envelope_Buffer.shp")
Slope_tif = BASE_DATA(f"{Name}_Slope.tif")
Slope_eCog = ECOG(f"{Name}_Slope.tif")
Aspect_tif = BASE_DATA(f"{Name}_Aspect.tif")
Aspect_sectors_N0_eCog = ECOG(f"{Name}_Aspect_sectors_N0.tif")
Aspect_sectors_Nmax_eCog = ECOG(f"{Name}_Aspect_sectors_Nmax.tif")
Curv = BASE_DATA(f"{Name}_Curv.tif")
Curv_profile_temp = BASE_DATA(f"{Name}_Curv_profile_temp.tif")
Curv_profile = BASE_DATA(f"{Name}_Curv_profile.tif")
Curv_plan_temp = BASE_DATA(f"{Name}_Curv_plan_temp.tif")
Curv_plan = BASE_DATA(f"{Name}_Curv_plan.tif")
Curv_profile_eCog_temp = ECOG(f"{Name}_Curv_profile_temp.tif")
Curv_profile_eCog = ECOG(f"{Name}_Curv_profile.tif")
Curv_plan_eCog_temp = ECOG(f"{Name}_Curv_plan_temp.tif")
Curv_plan_eCog = ECOG(f"{Name}_Curv_plan.tif")
Hillshade_eCog = ECOG(f"{Name}_Hillshade.tif")

#-------------------------------------------------------------------------------
# Give Messages
arcpy.AddMessage("Workspace = " + Workspace)
arcpy.AddMessage("inDEM = " + inDEM)
DEM_res = arcpy.GetRasterProperties_management(inDEM, "CELLSIZEX")
arcpy.AddMessage("inDEM resolution = " + str(DEM_res))
arcpy.AddMessage("Resampling resolution = " + resampCellSize)

#-------------------------------------------------------------------------------
# Set geoprocessing environments

# Needed for memory/PRA_raw_NoForest and memory/PRA_raw_Forest.
# Because data_prep_PRA() is called twice.
arcpy.env.overwriteOutput = True
#arcpy.overwriteOutput = False

if outCoordSystem.name == "":
    outCoordSystem = arcpy.Describe(inDEM).spatialReference

arcpy.env.outputCoordinateSystem = outCoordSystem
arcpy.env.snapRaster = arcpy.sa.Raster(inDEM)

arcpy.CreateFolder_management(Workspace, 'base_data')
arcpy.CreateFolder_management(Workspace, 'eCog')

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Export input parameters to csv_file
import csv
row1 = ["Name", "inDEM", "inForest", "resamp_cellsize [m]", "inPerimeter", "Slope_lowerlimit_frequent [degree]", "Slope_lowerlimit_extreme [degree]", "Slope_upperlimit [degree]", "Curv_plan_upperlimit [rad/100m]", "Rugged_neighborhood [pixel]", "Rugged_upperlimit [ ]", "outCoordSystem", "Weithingkernel"]
row2 = [Name, inDEM, inForest, resampCellSize, inPerimeter, Slope_lowerlimit_frequent, Slope_lowerlimit_extreme, Slope_upperlimit, Curv_upperlimit, Rugged_neighborhood, Rugged_upperlimit, outCoordSystem.name, Weightingkernel]
array = [row1,row2]
Name_csv_file = Workspace + Name
with open("%s_DataPrep_InputParameters.csv" % Name_csv_file,"w") as f:
    writer = csv.writer(f,delimiter=";")
    writer.writerows(array)
    f.close()

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Check extent of inDEM
arcpy.AddMessage("checking inDEM...")
extent_inDEM = arcpy.sa.Raster(inDEM).extent
XMin_inDEM = int(round(extent_inDEM.XMin))
YMin_inDEM = int(round(extent_inDEM.YMin))
XMax_inDEM = int(round(extent_inDEM.XMax))
YMax_inDEM = int(round(extent_inDEM.YMax))

# Check extent of Raster Domain of inDEM
arcpy.RasterDomain_3d(inDEM, "in_memory/inDEM_RasterDomain", 'POLYGON')
buffer_dist = str(float(DEM_res.getOutput(0))/2)
arcpy.Buffer_analysis("in_memory/inDEM_RasterDomain", "in_memory/inDEM_RasterDomain_Buffer", '%s Meters' % (buffer_dist), 'FULL', 'ROUND', 'NONE', '#', 'PLANAR')
extent_RasterDomain = arcpy.Describe("in_memory/inDEM_RasterDomain_Buffer").extent
XMin_RasterDomain = int(round(extent_RasterDomain.XMin))
YMin_RasterDomain = int(round(extent_RasterDomain.YMin))
XMax_RasterDomain = int(round(extent_RasterDomain.XMax))
YMax_RasterDomain = int(round(extent_RasterDomain.YMax))

# Apply Clip if extent of Raster Domain smaller than inDEM
if (XMin_inDEM > XMin_RasterDomain) or (YMin_inDEM > YMin_RasterDomain) or (XMax_inDEM > XMax_RasterDomain) or (YMax_inDEM > YMax_RasterDomain):
    arcpy.AddMessage("clip DEM to raster domain, because extent of DEM bigger than raster domain...")
    inDEM_RasterDomain = BASE_DATA(f"{Name}_DEM_ExtentRasterDomain.tif")
    arcpy.Clip_management(inDEM, '%s %s %s %s' %(XMin_RasterDomain, YMin_RasterDomain, XMax_RasterDomain, YMax_RasterDomain), inDEM_RasterDomain, "in_memory/inDEM_RasterDomain_Buffer", '#', 'NONE', 'NO_MAINTAIN_EXTENT')
    inDEM_RasterDomainChecked = inDEM_RasterDomain

else:
    inDEM_RasterDomainChecked = inDEM

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Base Data preparation
#-------------------------------------------------------------------------------
# Apply Clip if Perimeter specified
def PerimeterClip():
    if outCoordSystem != arcpy.Describe(inPerimeter).spatialReference:
        arcpy.Copy_management(inPerimeter, Perimeter)

    arcpy.FeatureEnvelopeToPolygon_management(Perimeter, Perimeter_Envelope, 'SINGLEPART')
    arcpy.Buffer_analysis(Perimeter_Envelope, "in_memory/Perimeter_Envelop_Buffer", '200 Meters', 'FULL', 'ROUND', 'NONE', '#', 'PLANAR')
    arcpy.FeatureEnvelopeToPolygon_management("in_memory/Perimeter_Envelop_Buffer", Perimeter_Envelope_Buffer, 'SINGLEPART')
    extent_Perimeter = arcpy.Describe(Perimeter_Envelope_Buffer).extent
    XMin_Perimeter = extent_Perimeter.XMin
    YMin_Perimeter = extent_Perimeter.YMin
    XMax_Perimeter = extent_Perimeter.XMax
    YMax_Perimeter = extent_Perimeter.YMax
    inDEM_Perimeter = DEM = BASE_DATA(f"{Name}_DEM_Perimeter.tif")
    arcpy.Clip_management("in_memory/inDEM_resamp", '%s %s %s %s' %(XMin_Perimeter, YMin_Perimeter, XMax_Perimeter, YMax_Perimeter), inDEM_Perimeter, Perimeter_Envelope_Buffer, '#', 'NONE', 'NO_MAINTAIN_EXTENT')

#-------------------------------------------------------------------------------
# Prepare DEM
# Check Cellsize of inDEM raster
if DEM_res != resampCellSize:
    arcpy.AddMessage("preparing DEM...")
    arcpy.Resample_management(inDEM_RasterDomainChecked, "in_memory/inDEM_resamp", resampCellSize, 'BILINEAR')
    if inPerimeter != "":
        arcpy.AddMessage("clipping DEM to Perimeter")
        PerimeterClip()
        inDEM_Perimeter = DEM = BASE_DATA(f"{Name}_DEM_Perimeter.tif")
        inDEM_RasterDomainChecked_PerimeterChecked = inDEM_Perimeter
    else:
        inDEM_RasterDomainChecked_PerimeterChecked = "in_memory/inDEM_resamp"

    DEM_resamp_smooth = BASE_DATA(f"{Name}_DEM_resamp_smooth.tif")
    arcpy.gp.FocalStatistics_sa(inDEM_RasterDomainChecked_PerimeterChecked, DEM_resamp_smooth, 'Weight %s' % Weightingkernel, 'MEAN', 'NODATA')
    DEM = DEM_resamp_smooth

else:
    if inPerimeter != "":
        arcpy.AddMessage("clipping DEM to Perimeter")
        PerimeterClip()
    else:
        inDEM_RasterDomainChecked_PerimeterChecked = inDEM_RasterDomainChecked

    DEM_smooth = BASE_DATA(f"{Name}_DEM_smooth.tif")
    arcpy.gp.FocalStatistics_sa(inDEM_RasterDomainChecked_PerimeterChecked, DEM_smooth, 'Weight %s' % Weightingkernel, 'MEAN', 'NODATA')
    DEM = DEM_smooth

arcpy.ClearEnvironment("snapRaster")
arcpy.env.snapRaster = arcpy.sa.Raster(DEM)


# Check and Prepare inForest if specified
if inForest != "":
    arcpy.AddMessage("checking inForest...")

    # Checking for Intersection of inForest and DEM
    arcpy.RasterDomain_3d(inForest, "in_memory/inForest_RasterDomain", 'POLYGON')
    arcpy.RasterDomain_3d(DEM, "in_memory/DEM_RasterDomain", 'POLYGON')
    arcpy.Intersect_analysis(["in_memory/inForest_RasterDomain", "in_memory/DEM_RasterDomain"], "in_memory/Intersection", 'ALL', '#', 'INPUT')
    if arcpy.management.GetCount("in_memory/Intersection")[0] == "0":
        arcpy.AddError("InputError:Forest and DEM do not intersect")
        exit()

    # Checking Value range of inForest raster
    unique_value_count = int(arcpy.GetRasterProperties_management(inForest, "UNIQUEVALUECOUNT").getOutput(0))
    min_value = int(arcpy.GetRasterProperties_management(inForest, "MINIMUM").getOutput(0))
    max_value = int(arcpy.GetRasterProperties_management(inForest, "MAXIMUM").getOutput(0))
    if unique_value_count != 2 or min_value != 0 or max_value != 1:
        arcpy.AddError("InputError:Value range of the forest raster not conforming, reclassify raster to 0 (No Forest) and 1 (Forest)")
        exit()

    # Checking Cellsize of inForest raster
    if arcpy.GetRasterProperties_management(inForest, "CELLSIZEX") != resampCellSize:
        arcpy.AddMessage("preparing Forest...")
        arcpy.Resample_management(inForest, Forest, resampCellSize, 'BILINEAR')
    else:
        arcpy.Copy_management(inForest, Forest)

# Create Slope
arcpy.AddMessage("creating Slope...")
arcpy.gp.Slope_sa(DEM, Slope_tif, 'DEGREE', '1')

# Create Aspect
arcpy.AddMessage("creating Aspect...")
arcpy.gp.Aspect_sa(DEM, Aspect_tif)

# Classify Aspect into sectors
arcpy.gp.Reclassify_sa(Aspect_tif, 'VALUE', '-1 0 NODATA; 0 22.5 0; 22.5 67.5 100; 67.5 112.5 200; 112.5 157.5 100; 157.5 202.5 0; 202.5 247.5 -100; 247.5 292.5 -200; 292.5 337.5 -100; 337.5 360 0', "memory/Aspect_sectors_N0_eCog", 'DATA')
arcpy.gp.Reclassify_sa(Aspect_tif, 'VALUE', '-1 0 NODATA; 0 22.5 200; 22.5 67.5 100; 67.5 112.5 0; 112.5 157.5 -100; 157.5 202.5 -200; 202.5 247.5 -100; 247.5 292.5 0; 292.5 337.5 100; 337.5 360 200', "memory/Aspect_sectors_Nmax_eCog", 'DATA')

# Create Curvature
arcpy.AddMessage("creating Curvature...")
arcpy.gp.Curvature_sa(DEM, Curv, '1', Curv_profile_temp, Curv_plan_temp)

# Create Profile Curvature
# for dataPrep in ArcGIS
arcpy.AddMessage("creating Profile Curvature...")
arcpy.gp.FocalStatistics_sa(Curv_profile_temp, Curv_profile, 'Rectangle 3 3 CELL', 'MEAN', 'DATA')
# for eCog
min_value = float(arcpy.GetRasterProperties_management(Curv_profile, "MINIMUM").getOutput(0))
min_factor = 200/((-1)*min_value)
max_value = float(arcpy.GetRasterProperties_management(Curv_profile, "MAXIMUM").getOutput(0))
max_factor = 200/max_value
# This command mysteriously resets the script-global variable Slope to arcpy.sa.Slope()
# Same for Aspect.
# Hence the variables Slope and Aspect were renamed to Slope_tif and Aspect_tif
rstr = 'arcpy.sa.Con("%s" <= 0, "%s" * %s, "%s" * %s)' % (Curv_profile, Curv_profile, min_factor, Curv_profile, max_factor)
arcpy.gp.RasterCalculator_sa(rstr, Curv_profile_eCog_temp) # expand value range from -200 to 200

# Create Plan Curvature
# for dataPrep in ArcGIS
arcpy.AddMessage("creating Plan Curvature...")
arcpy.gp.FocalStatistics_sa(Curv_plan_temp, Curv_plan, 'Rectangle 3 3 CELL', 'MEAN', 'DATA')
# for eCog
min_value = float(arcpy.GetRasterProperties_management(Curv_plan, "MINIMUM").getOutput(0))
min_factor = 200/((-1)*min_value)
max_value = float(arcpy.GetRasterProperties_management(Curv_plan, "MAXIMUM").getOutput(0))
max_factor = 200/max_value
arcpy.gp.RasterCalculator_sa('Con("%s" <= 0, "%s" * %s, "%s" * %s)' % (Curv_plan, Curv_plan, min_factor, Curv_plan, max_factor), Curv_plan_eCog_temp) # expand value range from -200 to 200

# Create Hillshade
arcpy.AddMessage("creating Hillshade...")
arcpy.gp.HillShade_sa(DEM, "memory/Hillshade_eCog", '315', '45', 'NO_SHADOWS', '1')

#-------------------------------------------------------------------------------
# Create Ruggedness
arcpy.AddMessage("creating Ruggedness, scaled by 100...")

# to calcualte in radians
Rad = (math.pi/180)

# neighbourhood size
n = int(Rugged_neighborhood)

# Convert Slope and Aspect to radians
SlopeRad = arcpy.sa.Times(Slope_tif, Rad)
AspectRad = arcpy.sa.Times(Aspect_tif, Rad)

SlopeRad.save(BASE_DATA(f"{Name}_SlopeRad.tif"))
AspectRad.save(BASE_DATA(f"{Name}_AspectRad.tif"))

# Calculate x, y, and z Rasters
xyRaster = Sin(SlopeRad)
zRaster = Cos(SlopeRad)
SinAspectRad = Sin(AspectRad)
CosAspectRad = Cos(AspectRad)
xRaster = Con((AspectRad == -1), 0, (Times(SinAspectRad, xyRaster)))
yRaster = Con((AspectRad == -1), 0, (Times(CosAspectRad, xyRaster)))
xyRaster.save(BASE_DATA(f"{Name}_xyRaster.tif"))
zRaster.save(BASE_DATA(f"{Name}_zRaster.tif"))
SinAspectRad.save(BASE_DATA(f"{Name}_SinAspectRad.tif"))
CosAspectRad .save(BASE_DATA(f"{Name}_CosAspectRad.tif"))
xRaster.save(BASE_DATA(f"{Name}_xRaster.tif"))
yRaster.save(BASE_DATA(f"{Name}_yRaster.tif"))

# Calculate sums of x, y, and z rasters for selected neighborhood size
xSumRaster = FocalStatistics(xRaster, NbrRectangle(n, n, "CELL"), "SUM", "NODATA")
ySumRaster = FocalStatistics(yRaster, NbrRectangle(n, n, "CELL"), "SUM", "NODATA")
zSumRaster = FocalStatistics(zRaster, NbrRectangle(n, n, "CELL"), "SUM", "NODATA")
xSumRaster.save(BASE_DATA(f"{Name}_xSumRaster.tif"))
ySumRaster.save(BASE_DATA(f"{Name}_ySumRaster.tif"))
zSumRaster.save(BASE_DATA(f"{Name}_zSumRaster.tif"))

# Calculate the resultant vector (local variablility of the orientation of the vector)
RRaster = SquareRoot(Square(xSumRaster) + Square(ySumRaster) + Square(zSumRaster))

RRaster.save(BASE_DATA(f"{Name}_RRaster.tif"))
# Divide the vector through the number of cell in the neighbourhood and substrate of 1
Ruggedness1 = 1 - (RRaster / Square(n))

# scale ruggedness * 100
Ruggedness = Ruggedness1*100

# Save the output
Ruggedness.save(BASE_DATA(f"{Name}_Ruggedness_n" + Rugged_neighborhood + ".tif"))

#-------------------------------------------------------------------------------
# Clip eCog files to the same extent
arcpy.AddMessage("clipping eCog files to the same extent")
if inPerimeter != "":
    arcpy.gp.ExtractByMask_sa(DEM, Perimeter_Envelope_Buffer, "in_memory/Mask")
    Mask = "in_memory/Mask"
else:
    Mask = DEM

arcpy.gp.ExtractByMask_sa(DEM, Mask, DEM_eCog)
arcpy.gp.ExtractByMask_sa(Slope_tif, Mask, Slope_eCog)
arcpy.gp.ExtractByMask_sa("memory/Aspect_sectors_N0_eCog", Mask, Aspect_sectors_N0_eCog)
arcpy.gp.ExtractByMask_sa("memory/Aspect_sectors_Nmax_eCog", Mask, Aspect_sectors_Nmax_eCog)
arcpy.gp.ExtractByMask_sa(Curv_profile_eCog_temp, Mask, Curv_profile_eCog)
arcpy.gp.ExtractByMask_sa(Curv_plan_eCog_temp, Mask, Curv_plan_eCog)
arcpy.gp.ExtractByMask_sa("memory/Hillshade_eCog", Mask, Hillshade_eCog)

# Delete all files, which are not needed
arcpy.Delete_management(Curv_plan_temp)
arcpy.Delete_management(Curv_plan_eCog_temp)
arcpy.Delete_management(Curv_profile_temp)
arcpy.Delete_management(Curv_profile_eCog_temp)
arcpy.Delete_management(SlopeRad)
arcpy.Delete_management(AspectRad)
arcpy.Delete_management(xyRaster)
arcpy.Delete_management(zRaster)
arcpy.Delete_management(SinAspectRad)
arcpy.Delete_management(CosAspectRad)
arcpy.Delete_management(xRaster)
arcpy.Delete_management(yRaster)
arcpy.Delete_management(xSumRaster)
arcpy.Delete_management(ySumRaster)
arcpy.Delete_management(zSumRaster)
arcpy.Delete_management(RRaster)

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Boolean Model

def data_prep_PRA(Slope_lowerlimit, name_scenario):
    arcpy.AddMessage("executing Scenario_" + name_scenario + "...")

    tdir = f"temp_model_{name_scenario}"
    arcpy.CreateFolder_management(Workspace, tdir)
    def TDIR(leaf):
        return os.path.join(Workspace, tdir, leaf)

    #-------------------------------------------------------------------------------
    arcpy.AddMessage("creating binary layers...")

    # create Slope binary
    SlopeBinary = Con((arcpy.sa.Raster(Slope_tif) < float(Slope_lowerlimit)) | (arcpy.sa.Raster(Slope_tif) > float(Slope_upperlimit)), 0, 1)
    SlopeBinary.save(TDIR(f"{Name}_Slope_binary.tif"))

    # create Curvature binary
    CurvBinary = Con((arcpy.sa.Raster(Curv_plan) < (-1*float(Curv_upperlimit))) | (arcpy.sa.Raster(Curv_plan) > float(Curv_upperlimit)), 0, 1)
    CurvBinary.save(TDIR(f"{Name}_Curv_binary.tif"))

    # create Ruggedness binary
    RuggednessBinary = Con((Ruggedness > float(Rugged_upperlimit)), 0, 1)
    RuggednessBinary.save(TDIR(f"{Name}_Ruggedness_n{Rugged_neighborhood}_binary.tif"))

    #-------------------------------------------------------------------------------
    arcpy.AddMessage("combining binary layers...")

    # Boolean Overlay: Slope AND Curvature AND Ruggedness
    SlopeCurvRuggednessBinary = SlopeBinary * CurvBinary * RuggednessBinary
    SlopeCurvRuggednessBinary.save(TDIR(f"{Name}_Slope_Curv_Ruggedness_binary.tif"))

    if inForest != "":
        # Boolean Overlay: Slope AND Curvature AND Ruggedness AND Forest
        SlopeCurvRuggednessForestBinary = TDIR(f"{Name}_Slope_Curv_Ruggedness_Forest_binary.tif")
        SlopeCurvRuggednessForestBinary = SlopeBinary * CurvBinary * RuggednessBinary * BooleanNot(arcpy.sa.Raster(inForest))
        SlopeCurvRuggednessForestBinary.save(TDIR(f"{Name}_Slope_Curv_Ruggedness_Forest_binary.tif"))

    #-------------------------------------------------------------------------------
    arcpy.AddMessage("writing out PRA_raw...")

    # Boolean Overlay Raster to PRA_raw Raster

    # NoForest
    PRA_raw_NoForest = ECOG(f"{Name}__PRA_raw_{name_scenario}_NoForest.tif")
    arcpy.gp.Reclassify_sa(SlopeCurvRuggednessBinary, 'Value', '1 200;0 0', "memory/PRA_raw_NoForest", 'DATA')
    arcpy.gp.ExtractByMask_sa("memory/PRA_raw_NoForest", Mask, PRA_raw_NoForest)

    # Forest
    if inForest != "":
        PRA_raw_Forest = ECOG(f"{Name}__PRA_raw_{name_scenario}_Forest.tif")
        arcpy.gp.Reclassify_sa(SlopeCurvRuggednessForestBinary, 'Value', '1 200;0 0', "memory/PRA_raw_Forest", 'DATA')
        arcpy.gp.ExtractByMask_sa("memory/PRA_raw_Forest", Mask, PRA_raw_Forest)

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
# Execute Model
if Slope_lowerlimit_frequent != "":
    data_prep_PRA(Slope_lowerlimit_frequent, "frequent")

if Slope_lowerlimit_extreme != "":
    data_prep_PRA(Slope_lowerlimit_extreme, "extreme")
