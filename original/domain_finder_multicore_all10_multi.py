# coding: utf-8
# #-------------------------------------------------------------------------------
# Name:        domain_finder_multicore_all10.py
# Purpose:     Calculate domains for input release zones
#
# Author:      stoffel
#
# Created:     20.04.2017
# Copyright:   (c) stoffel 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import os, sys
import arcpy
from arcpy import env
from arcpy.sa import *
import multiprocessing
from functools import partial
import tempfile
import math
import shutil
import datetime

# Check out any necessary licenses
arcpy.CheckOutExtension("spatial")
# arcpy.CheckOutExtension("3d")

# Set environment variables
env.overwriteOutput = True
env.rasterStatistics = "None"
env.pyramid = "None"
env.scratchWorkspace = "in_memory"
env.workspace = "in_memory"
env.parallelProcessingFactor = "100%"

def calcDomain(workspace_tmp, fileDEM, fileFlowdir, buffdis, cellsize, row):
    try:
        # Make a unique scratch workspace
        tempfile.tempdir = workspace_tmp
        scratch = tempfile.mkdtemp()
        env.workspace = scratch
        env.scratchWorkspace = scratch

        shape = os.path.join(scratch, "shape" + str(row[0]) + ".shp")
        arcpy.CopyFeatures_management(row[1], shape)

        # Get shape extent
        desc = arcpy.Describe(shape)

        # Convert polygon to raster
        cpras = os.path.join(scratch, "cpras" + str(row[0]) + ".tif")
        arcpy.PolygonToRaster_conversion(shape, "Id", cpras, "CELL_CENTER", "None", 2)

        # Clip fileDEM and fileFlowdir to smaller processing extent
        d = 5000
        proc_extent = arcpy.Extent(desc.extent.XMin - d, desc.extent.YMin - d, desc.extent.XMax + d, desc.extent.YMax + d)
        demClip = os.path.join(scratch, "demclip" + str(row[0]) + ".tif")
        arcpy.Clip_management(fileDEM, str(proc_extent), demClip)
        flowDirClip = os.path.join(scratch, "flowdirclip" + str(row[0]) + ".tif")
        arcpy.Clip_management(fileFlowdir, str(proc_extent), flowDirClip)

        # Calculate CostPath raster
        costpath = os.path.join(scratch, "cp" + str(row[0]) + ".tif")
        outCostPath = CostPath(cpras, demClip, flowDirClip, "EACH_CELL")
        # outCostPath = CostPath(cpras, demClip, flowDirClip, "BEST_SINGLE")
        outCostPath.save(costpath)

        # Create CostPath polygon shapefile
        cppoly = os.path.join(scratch, "cppoly" + str(row[0]) + ".shp")
        arcpy.RasterToPolygon_conversion(costpath, cppoly, "SIMPLIFY", "VALUE")

        # MinimumBoundingGeometry_management(in_features, out_feature_class, {geometry_type}, {group_option}, {group_field}, {mbg_fields_option})
        cpbound = os.path.join(scratch, "cpbound" + str(row[0]) + ".shp")
        arcpy.MinimumBoundingGeometry_management(cppoly, cpbound, "RECTANGLE_BY_WIDTH", "ALL")

        # Buffer CostPath polygon shapefile with buffdis = buffer distance in m
        domain = os.path.join(scratch, "domain" + str(row[0]) + ".shp")
        arcpy.Buffer_analysis(cpbound, domain, buffdis, "FULL", "ROUND", "NONE")

        # Do field management stuff
        arcpy.AddField_management(domain, "Id", "LONG")
        arcpy.CalculateField_management(domain, "Id", str(row[0]), "PYTHON_9.3")

        # Delete tmp files in scratch workspace
        arcpy.Delete_management(os.path.join(scratch, shape))
        arcpy.Delete_management(os.path.join(scratch, cpras))
        arcpy.Delete_management(os.path.join(scratch, demClip))
        arcpy.Delete_management(os.path.join(scratch, flowDirClip))
        arcpy.Delete_management(os.path.join(scratch, costpath))
        arcpy.Delete_management(os.path.join(scratch, cppoly))
        arcpy.Delete_management(os.path.join(scratch, cpbound))

        # Return scratch workspace path
        return scratch
    except:
        # Some error occurred so return False
        return False


def calcAppend(workspace_tmp, sr, domains):
    try:
        # Make a unique scratch workspace
        tempfile.tempdir = workspace_tmp
        scratch = tempfile.mkdtemp()
        env.workspace = scratch
        env.scratchWorkspace = scratch

        # Create output shapefile "chunk_domains.shp"
        all_domains = "chunk_domains.shp"
        arcpy.CreateFeatureclass_management(scratch, all_domains, "POLYGON", None, None, None, sr)

        # Append domains to output shapefile "chunk_domains.shp"
        out_shapefile = os.path.join(scratch, all_domains)
        arcpy.Append_management(domains, out_shapefile, "NO_TEST")

        # Return scratch workspace path
        return scratch
    except:
        # Some error occurred so return False
        return False


def findDomain(workspace, fileShp, fileDEM, fileFlowdir, buffdis, name):
    try:
        # arcpy.AddMessage("Workspace = " + workspace)
        # arcpy.AddMessage("Input Shapefile = " + fileShp)
        # arcpy.AddMessage("Input DEM = " + fileDEM)
        # arcpy.AddMessage("Input FlowDir = " + fileFlowdir)
        # arcpy.AddMessage("Buffer distance = " + buffdis)
        # arcpy.AddMessage("Output Shapefile Name = " + name)
        print("Workspace = " + workspace)
        print("Input Shapefile = " + fileShp)
        print("Input DEM = " + fileDEM)
        print("Input FlowDir = " + fileFlowdir)
        print("Buffer distance = " + buffdis)
        print("Output Shapefile Name = " + name)

        #Get the cellsize form fileDEM
        result = arcpy.GetRasterProperties_management(fileDEM, "CELLSIZEX")
        cellsize = result.getOutput(0)
        # arcpy.AddMessage("Cellsize = " + cellsize)
        print("Cellsize = " + cellsize)

        # Create a tmp directory for domain workspaces
        workspace_tmp_domain = os.path.join(workspace, "temp_domain")
        if not os.path.exists(workspace_tmp_domain):
            os.makedirs(workspace_tmp_domain)

        # Create a list of ID's and shapes used to chunk the inputs
        inShp_rows = arcpy.da.SearchCursor(fileShp, ["ID", "SHAPE@"])
        rows = [[row[0],row[1]] for row in inShp_rows]
        # arcpy.AddMessage("There are " + str(len(rows)) + " object IDs (polygons) to process...")
        print("There are " + str(len(rows)) + " object IDs (polygons) to process...")

        # This line creates a "pointer" to the real function but its a nifty way for declaring parameters.
        # Note the layer objects are passing their full path as layer objects cannot be pickled
        func = partial(calcDomain, workspace_tmp_domain, fileDEM, fileFlowdir, buffdis, cellsize)

        # declare number of cores to use, use 2 less than the max
        # cpuNum = int(math.ceil(multiprocessing.cpu_count() / 2))
        cpuNum = multiprocessing.cpu_count() - 2
        # cpuNum = 40
        print("Number of cores = " + str(cpuNum))

        # Create the pool object
        pool = multiprocessing.Pool(processes=cpuNum)

        # Fire off list to worker function.
        # res is a list that is created with what ever the worker function is returning
        res = pool.map(func,rows)
        pool.close()
        pool.join()

        # If an error has occurred report it
        # print(res)
        if False in res:
            arcpy.AddError("A worker failed!")
        arcpy.AddMessage("Finished multiprocessing!")

        # Create a list of all domains in tmp directory for domain workspaces
        domains = []
        for dirpath, dirnames, filenames in arcpy.da.Walk(workspace_tmp_domain, datatype="FeatureClass", type="Polygon"):
            for filename in filenames:
                if "domain" in filename:
                    domains.append(os.path.join(dirpath,filename))
                    # print(filename)

        # Create a list of domain lists, build chunks with size n
        n = int(math.ceil(len(rows) / float(cpuNum)))
        print("Number of domain chunks = " + str(n))
        chunksDomainList = [domains[i:i + n] for i in range(0, len(domains), n)]
        # print(chunksDomainList)

        # Create a tmp directory for append workspaces
        workspace_tmp_append = os.path.join(workspace, "temp_append")
        if not os.path.exists(workspace_tmp_append):
            os.makedirs(workspace_tmp_append)

        # Define output spatial reference
#        sr = arcpy.SpatialReference(21781)
#        sr = arcpy.SpatialReference(2056)
        desc = arcpy.Describe(fileShp)
        print("Spatial reference name: {0}".format(desc.spatialReference.name))
        print("Spatial reference factoryCode: {0}".format(desc.spatialReference.factoryCode))
        sr = arcpy.SpatialReference(desc.spatialReference.factoryCode)

        # This line creates a "pointer" to the real function but its a nifty way for declaring parameters.
        # Note the layer objects are passing their full path as layer objects cannot be pickled
        funcAppend = partial(calcAppend, workspace_tmp_append, sr)

        # Create the pool object
        pool = multiprocessing.Pool(processes=cpuNum)
        # Fire off list to worker function.
        # resAppend is a list that is created with what ever the worker function is returning
        resAppend = pool.map(funcAppend, chunksDomainList)
        pool.close()
        pool.join()

        # If an error has occurred report it
        print(resAppend)
        if False in resAppend:
            arcpy.AddError("A worker failed!")
        arcpy.AddMessage("Finished multiprocessing!")

        # # Create output in_memory
        # all_domains = "all_domains"
        # sr = arcpy.SpatialReference(21781)
        # arcpy.CreateFeatureclass_management("in_memory", all_domains, "POLYGON", None, None, None, sr)
        # out = os.path.join("in_memory", all_domains)

        # Create output shapefile "..._dom.shp"
        all_domains = name + "_dom.shp"
        arcpy.CreateFeatureclass_management(workspace, all_domains, "POLYGON", None, None, None, sr)
        out_shapefile = os.path.join(workspace, all_domains)

        # Create a list of all appends in tmp directory for append workspaces
        appends = []
        for dirpath, dirnames, filenames in arcpy.da.Walk(workspace_tmp_append, datatype="FeatureClass", type="Polygon"):
            for filename in filenames:
                appends.append(os.path.join(dirpath,filename))
                # print(filename)

        # Create output shapefile "..._all_domains.shp"
        arcpy.AddMessage("Creating output shapefile " + all_domains)
        arcpy.Append_management(appends, out_shapefile, "NO_TEST")
        result = arcpy.GetCount_management(out_shapefile)
        domain_count = int(result.getOutput(0))
        arcpy.AddMessage("There are " + str(domain_count) + " Domains in shapefile " + out_shapefile)

        # Check counts for release and domain shapefiles
        if len(rows) != domain_count:
            arcpy.AddWarning("WARNING!: The number of release zones " + str(len(rows)) + " in " + fileShp + " is not equal to the number of domains " + str(domain_count) + " in " + out_shapefile + "!")
        else:
            # Cleanup temp workspace (permanent, no recycle bin)
            arcpy.AddMessage("Cleaning temp files...")
            shutil.rmtree(workspace_tmp_domain)
            shutil.rmtree(workspace_tmp_append)
            arcpy.Delete_management("in_memory")

    except arcpy.ExecuteError:
        # Geoprocessor threw an error
        arcpy.AddError(arcpy.GetMessages(2))
    except Exception as e:
        # Capture all other errors
        arcpy.AddError(str(e))


if __name__ == '__main__':
    # Import current script
    import domain_finder_multicore_all10_multi
    startTime = datetime.datetime.now()

    # Set domain finder input variables
    basename = r"D:\LSHIM\TerrainClass2020\TestSites\Davos\RAMMS_sim\RELEASE\PRAsteph_5m_10"
    fileDEM = r"D:\LSHIM\TerrainClass2020\TestSites\Davos\DTM_5m_Davos.tif"
    workspace = r"D:\LSHIM\TerrainClass2020\TestSites\Davos\RAMMS_sim\DOMAIN_Test_AS"


    # Create FlowDirection raster
    arcpy.AddMessage("Creating FlowDirection raster...")
    if arcpy.Exists(workspace):
        shutil.rmtree(workspace)
    arcpy.CreateFolder_management(os.path.dirname(workspace),os.path.basename(workspace))
    fileFlowdirSink = os.path.join(workspace, "flowdirSink.tif")
    outFlowdirSink = FlowDirection(fileDEM)
    outFlowdirSink.save(fileFlowdirSink)
    # Fill sinks in DEM
    fileSink = os.path.join(workspace, "sink.tif")
    outSink = Sink(outFlowdirSink)
    outSink.save(fileSink)
    fileFill = os.path.join(workspace, "fill.tif")
    outFill = Fill(fileDEM)
    outFill.save(fileFill)
    fileFlowdirFill = os.path.join(workspace, "flowdirFill.tif")
    outFlowdirFill = FlowDirection(fileFill)
    outFlowdirFill.save(fileFlowdirFill)
    fileFlowdir = os.path.join(workspace, "flowdir.tif")
    outFlowdir = Con(IsNull(fileSink), fileFlowdirFill)
    outFlowdir.save(fileFlowdir)

    # Delete temp files
    #arcpy.Delete_management(fileFlowdirSink)
    #arcpy.Delete_management(fileSink)
    #arcpy.Delete_management(fileFill)
    #arcpy.Delete_management(fileFlowdirFill)

    # Calculate domains for scenarios in collection
    collection = [ ['M', '800'], ['S', '400'], ['T', '200']] #['L', '1250'], ['M', '800'],
    for x in collection:
        fileShp = basename + x[0] + '_rel.shp'
        buffdis = x[1]
        name = os.path.basename(basename) + x[0]

        if arcpy.Exists(fileShp):
            arcpy.AddMessage("Calling multiprocessing code...")
            domain_finder_multicore_all10_multi.findDomain(workspace, fileShp, fileDEM, fileFlowdir, buffdis, name)
        else:
            print("Shapefile " + fileShp + " does not exist!")

    # Cleanup temp files
    # arcpy.Delete_management(fileFlowdir)
    arcpy.AddMessage("Done!")

    stopTime = datetime.datetime.now()
    diff = stopTime - startTime
    print("It took: {0} days, {1} hours, {2} minutes, {3} seconds".format(diff.days, diff.seconds//3600, (diff.seconds//60)%60, diff.seconds%60))
