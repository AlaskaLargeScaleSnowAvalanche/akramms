import scipy.spatial
import pandas as pd
import shapely
from osgeo import gdal
from akramms import params,process_tree
from akramms.util import rammsutil
from uafgi.util import shputil,gdalutil,wrfutil,make,cfutil,ioutil,rasterize
import os,sys
import subprocess
import json
from akramms import config
import pyproj
import netCDF4
import numpy as np
import d8graph


# ---------------------------------------------------------------------------------


def rule(scene_dir, dem_filled_file, return_period, forest, snowI_tif,
    min_alpha=18., max_runout=10000., margin=0.):
    """
    scene_dir:
        Uses params: name ("site"), resample_cell_size ("res")

    dem_filled_file: filename
        DEM that with sinks filled (while computing neighbor1)

    return_period:
        Return period we are calculating for.
        Must be included in scene_args['return_periods']

    forest: bool
        Whether we are doing with / without forest
    snowI_tif: str
        Name of the snowdepth file, in local scene coordinates, that we will use.

    min_alpha: [deg]
        Minimum slope that "avalanche" can continue in domain finder
    max_runout:
        Maximum distance avalanche can go
   margin: [m]
       Margin to add around convex hull to minimum bounding rectangle.
    """

    scene_args = params.load(scene_dir)

    # Main input and output files: THESE MUST BE FIRST
    inputs = list()
    resolution = scene_args['resolution']
    scene_name = scene_args['name']
    For = 'For' if forest else 'NoFor'

    # eCognition filename conventions
    pra_file = process_tree.pra_file(scene_args, return_period, forest)
    inputs.append(pra_file)    # This rule does NOT use the burn files for domains...

    # Full pathnames of release files generated from this (scene_name, return_period, forest) combo
    outputs = list()
    ramms_names = list(rammsutil.master_ramms_names(scene_args, return_period, forest))
    for jb,_ in ramms_names:
        for dir,ext in (('RELEASE', '_rel.shp'), ('RELEASE','_chull.shp'), ('RELEASE','_dom.shp')):
            outputs.append(
                os.path.join(scene_dir, dir, f'{jb.ramms_name}{ext}'))

    # Add one-off input files
    inputs.append(snowI_tif)

    def action(tdir):

        degree = np.pi / 180.
        name = scene_args['name']
        resolution = scene_args['resolution']

        # Load the polygons (output of eCognition)
        # Reads columns: area_m2 Mean_DEM Mean_Slope Scene_reso
        print('======== Reading {}'.format(inputs[0]))
        df = shputil.read_df(inputs[0], shape='pra')
        df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"

        # Adds columns: j,i,sx3
        df = chunk.add_snow(df, snowI_tif, snow_density=200.)

        # Adds columns: d0star, slopecorr, Wind, d0_{return_period}, VOL_{return_period}
        df = chunk.add_corrections(df, return_period)

        # (grind_info includes the domain margin)
        grid_info, dem_filled, dem_nodata = gdalutil.read_raster(dem_filled_file)

        # ---------------------------------------------------------------
        # Split into segments based on PRA size, and save

        # Remove PRAs of elevation <150m
        df =  df[df['Mean_DEM'] >= 150.]            

        # Clip to the non-margin part of the local grid (subdomain)
        df = chunk.clip(df, scene_args['domain'])

        # Compute the avalanche domains (domain finder algo)
        df = chunk.add_dom(df, grid_info)





        ioutil.mkdirs_for_files(outputs)
        for jb,pra_size in ramms_names:
            print('--- p_pra_post.rule() pra_size = ', pra_size)

            # Select out rows for this category
            low,high = post_cat_bounds[pra_size]
            print(f'Category: {pra_size}, [{low}, {high})')
            cat_rows = df['area_m2'].between(low, high, inclusive='left')
            cat_df = df[cat_rows]

            # Remove PRAs of elevation <150m
            cat_df = cat_df[cat_df['Mean_DEM'] >= 150.]            

<< CUT
            # Only keep PRAs that are >50% in the interior part of the domain (not margin)
            if 'domain' in scene_args:
                domain = scene_args['domain']    # list
                npoints = len(domain) // 2

                _xy = np.array(domain, dtype='d').reshape( (npoints, 2) )
                x0,y0 = _xy[0,:]
                x1,y1 = _xy[2,:]
                xmin = min(x0,x1)
                xmax = max(x0,x1)
                ymin = min(y0,y1)
                ymax = max(y0,y1)
                #domain = shapely.geometry.Polygon(_xy.reshape((len(_xy)//2,2)))
                #in_domain_fn = lambda pra: in_domain(domain, pra)
                in_domain_fn = lambda pra: in_domain(xmin,ymin,xmax,ymax, pra)
                cat_df = cat_df[cat_df['pra'].map(in_domain_fn)]

            # Add size designator to the internal RELEASE file rows
            cat_df['pra_size'] = pra_size
>> END CUT

<< CUT
            # Calculate domains
            chulls = list()
            doms = list()
            for ix,(_,row) in enumerate(cat_df.iterrows()):

                if ix%1000 == 0:
                    print('   Calculated {} of {} domains'.format(ix, len(cat_df)))

                # Get list of gridcells covered by the PRA polygon (the "PRA Burn")
                pra_burn = rasterize.rasterize_polygon_compressed(row['pra'], grid_info)

                # Get the domain from the PRA burn
                args = ()
                ret = d8graph.find_domain(
                    dem_filled, dem_nodata, grid_info.geotransform, pra_burn,
                    margin=margin, debug=1, min_alpha=min_alpha, max_runout=max_runout)

                if ret is not None:
                    seen,chull_list,domain_list = ret
                    chulls.append(shapely.geometry.Polygon(chull_list))
                    doms.append(shapely.geometry.Polygon(domain_list))
                else:
                    # Not able to make a domain for this PRA
                    chulls.append(shapely.geometry.Polygon([]))
                    doms.append(shapely.geometry.Polygon([]))
>> END CUT

            # Store the _rel file
            shputil.write_df(
                cat_df, 'pra', 'Polygon',
                os.path.join(scene_dir, 'RELEASE', f'{jb.ramms_name}_rel.shp'),
                wkt=scene_args['coordinate_system'])

            # Store the _chull file
            chull_df = pd.DataFrame(index=cat_df.index)
            chull_df['Id'] = cat_df['Id']
            chull_df['chull'] = chulls
            #print('chull_df = ', chull_df)
            print('chull_df columns ', chull_df.columns)
            shputil.write_df(
                chull_df, 'chull', 'Polygon',
                os.path.join(scene_dir, 'RELEASE', f'{jb.ramms_name}_chull.shp'),
                wkt=scene_args['coordinate_system'])

            # Store the _dom file
            dom_df = pd.DataFrame(index=cat_df.index)
            dom_df['Id'] = cat_df['Id']
            dom_df['domain'] = doms
            shputil.write_df(
                dom_df, 'domain', 'Polygon',
                os.path.join(scene_dir, 'RELEASE', f'{jb.ramms_name}_dom.shp'),
                wkt=scene_args['coordinate_system'])

            # Create a _centroid file
            if False:
                centroids = np.zeros(snow_lookup.value.shape, dtype='b')    # byte
                jj = cat_df['j'].to_numpy()
                ii = cat_df['i'].to_numpy()
#                print('jj ', jj)
#                print('ii ', ii)
                for j,i in zip(jj,ii):
                    centroids[j,i] = 1
                gdalutil.write_raster(
                    os.path.join(scene_dir, 'RELEASE', f'{jb.ramms_name}_centroids.tif'),
                    snow_lookup.geo_info, centroids, 0, type=gdal.GDT_Byte)


    rule = make.Rule(action, inputs, outputs)
    return rule, ramms_names



# -------------------------------------------------------
#            # Split df for this category (size) PRAs into bite-size chunks
#            df_chunks = [df_cat[i:i+config.max_ramms_pras] for i in range(0,df_cat.shape[0],config.max_ramms_pras)]
#            ofnames = list()
#            for segment,dfc in enumerate(df_chunks):
#                jb.set(segment=segment)
#                ofname = os.path.join(jb.ramms_dir, 'RELEASE', f'{jb.ramms_name}_rel.shp')
#                ofnames.append(ofname)
#                os.makedirs(os.path.split(ofname)[0], exist_ok=True)
#                shputil.write_df(dfc, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])

#            # Write names of our PRA files into the final output file.
#            with open(output, 'w') as out:
#                for ofname in ofnames:
#                    out.write('{}\n'.format(config.roots.relpath(ofname)))
#
#                
#    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
#
#
#
#
#    # Full pathnames of release files generated from this (scene_name, return_period, forest) combo
#    outputs = list()
#    ramms_names = list()
#    for pra_size in rammsutil.PRA_SIZES.keys():    # T,S,M,L
#        # DEBUG: Only do 'L' for now
#        if pra_size not in config.allowed_pra_sizes:
#            continue
#        jb = rammsutil.RammsName(os.path.join(scene_dir, 'CHUNKS'), scene_name, None, forest, resolution, return_period, pra_size, None)
#        ramms_names.append((jb,pra_size))
#        # This filename does NOT have any segment numbers.
#        outputs.append(os.path.join(scene_dir, 'CHUNKS', f'{jb.ramms_name}_rel.shplist'))
#
