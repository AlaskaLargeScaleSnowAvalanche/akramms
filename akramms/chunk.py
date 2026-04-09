import bisect,os,typing,shutil
import numpy as np
import pandas as pd
import shapely,pyproj,geopandas
from uafgi.util import rasterize
import d8graph
from akramms.util import rammsutil
from akramms import snow,config,file_info,level,params,domain_mask
import shapely.geometry.multipolygon as multipolygon
import shapely.ops

"""Everything to do with reading, rearranging and writing release files and chunks.


Three shapefiles written:

1. by eCognition

OGRFeature(PRA_30y_For):1
  area_m2 (Real) = 3200.0000000000000000
  Mean_DEM (Real) = 942.0796947479248047
  Mean_Slope (Real) = 32.1327071189880371
  Scene_reso (Real) = 10.0000000000000000
  POLYGON (..)

   Reading this requires:
      df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"

2. By r_pra_post (split by size; the "master" release files...)

OGRFeature(x-113-045For_10m_30L_rel):1
  area_m2 (Real) = 69700.000000000000000
  Mean_DEM (Real) = 1125.810403087730947
  Mean_Slope (Real) = 39.163338208301170
  Scene_reso (Real) = 10.000000000000000
  Id (Integer64) = 1768
  j (Integer) = 908
  i (Integer) = 982
  sx3 (Real) = 0.963241636753082
  d0star (Real) = 0.963241636753082
  slopecorr (Real) = 1.000000000000000
  Wind (Integer64) = 0
  d0_30 (Real) = 0.963241636753082
  VOL_30 (Real) = 86590.637348969365121
  POLYGON (...)

3. CHUNK release files (same columns as master release files)

OGRFeature(x-113-04500005For_10m_30L_rel):0
  area_m2 (Real) = 60200.000000000000000
  Mean_DEM (Real) = 948.090781278388476
  Mean_Slope (Real) = 40.337525865168267
  Scene_reso (Real) = 10.000000000000000
  Id (Integer64) = 7290
  j (Integer64) = 2581
  i (Integer64) = 3364
  sx3 (Real) = 1.183910012245178
  d0star (Real) = 1.183910012245178
  slopecorr (Real) = 1.000000000000000
  Wind (Integer64) = 0
  d0_30 (Real) = 1.183910012245178
  VOL_30 (Real) = 93501.990431559752324
  POLYGON (...)





"""



# ===============================================================================
# -----------------------------------------------------------
def read_rel(relfname, **kwargs):
    """Reads a single _rel.shp and _dom.shp and merges them together.

    rfname: str
        Name of the releasefile
        Normally ends in _rel.shp
    dom:
        Also read the associated _dom.shp file?

    Returns: df
        Index set to Id column
    """

    # Read _rel shapefile
#    reldf = shputil.read_df(relfname, shape='pra', **kwargs)
    reldf = geopandas.read_file(str(relfname), **kwargs).rename_geometry('pra')
#    print('Read ', relfname)
#    print('reldf ', reldf.columns)
#    print(reldf.index)
#    print(reldf)
    if 'Id' in reldf:
        # This will be the case for files NOT written by eCog
        reldf = reldf.set_index('Id')

    # The index functions as the PRA Id.
    # If this is a file written by eCog, that is already the case.
    # Otherwise the PRA Id is stored in the Id column.
    return reldf
# -----------------------------------------------------------
def read_dom(domfname, **kwargs):
    """Reads a single _rel.shp and _dom.shp and merges them together.

    rfname: str
        Name of the releasefile
        Normally ends in _rel.shp
    dom:
        Also read the associated _dom.shp file?

    Returns: df
        Index set to Id column
    """
    df = geopandas.read_file(str(domfname), **kwargs).rename_geometry('dom')
#    return shputil.read_df(domfname, shape='dom', **kwargs) \
    return df.set_index('Id')
# -----------------------------------------------------------
def read_reldom(relfname, **kwargs):
    """Reads a RELEASE and related DOMAIN file and merges together resulting dataframes"""

    # Check for empty (dummy) file, typically written if no PRAs for a
    # given size class.
    if os.path.getsize(relfname) == 0:
        return None

    domfname = relfname.parents[1] / 'DOMAIN' / (relfname.parts[-1][:-8] + '_dom.shp')

    rdf = read_rel(relfname, **kwargs)
    ddf = read_dom(domfname, **kwargs)

    # Remove geometry columns
    rdf = pd.DataFrame(rdf)
    ddf = pd.DataFrame(ddf)

    # Drop rows with missing domain
    df = rdf.merge(ddf[['dom']], left_index=True, right_index=True)
    return df
# -----------------------------------------------------------
#def read_releasefiles(akdf0, **kwargs):
#    """Reads the releasefiles in akdf0 and returns as added columns
#    akdf0:
#        Resolved to ID level with index='id'
#    kwargs:
#        Sent to read_releasefile()"""
#
#    dfs = list()
#    for releasefile,akdf1 in akdf0.groupby('releasefile'):
#        rdf = read_releasefile(releasefile, **kwargs)
#        dfs.append(akdf1.merge(rdf, how='left', left_index=True, right_index=True))
#    return pd.concat(dfs)
# -----------------------------------------------------------
_post_cat_bounds = (0.,5000.,25000.,60000.,1e10)    # Dummy value at end
_pra_sizes = ('T', 'S', 'M', 'L')

def add_pra_size(reldf):
    """
    reldf:
        Releasefile read via read_releasefile()
        (or created by another means)
        Must have column: area_m2
    """
    # Find the column containing PRA volume: most begin with 'VOL_'
    for name in reldf.columns:
        if name.startswith('VOL_'):
            vol_col = name
            break

    pra_size = reldf[vol_col].map(
        lambda x: _pra_sizes[bisect.bisect(_post_cat_bounds, x) - 1])
    reldf['pra_size'] = pra_size.astype('string')
    return reldf
# -----------------------------------------------------------
def add_snow(df, snowI_tif, snow_density=200.):
    """
    snow_lokoup:
        See snow.RasterLookup
    """
    snow_lookup = snow.RasterLookup(snowI_tif)

# DEBUGGING code
#    for tup in df.itertuples(index=False):
#        try:
#            sx3 = snow_lookup.value_at_centroid(tup.pra)
#        except IndexError:
#            print(tup)
#            print('pra = ', type(tup.pra), tup.pra)
#            print('centroid = ', tup.pra.centroid)
#            print('geo_info = ', snow_lookup.geo_info.geotransform)
#            cent = tup.pra.centroid
#            print('ij = ', snow_lookup.geo_info.to_ij(cent.x,centy))
#            raise

    # This is a Series of tuple (j, i, sx3)
    jisx3 = df['pra'].map(snow_lookup.value_at_centroid)    # j,i,Raw snow amount [kg m-2]

    # Pick apart the tuple into separate columns
    df['j'] = jisx3.map(lambda x: x[0])
    df['i'] = jisx3.map(lambda x: x[1])
    sx3_mm_swe = jisx3.map(lambda x: x[2])

    # Compute snow depth in [m]
    by_SNOW_DENSITY = 1. / snow_density    # [m^3 kg-1]   (Wolken; based on data we have on field work in these areas).
        # Typical values: 1m
    df['sx3'] = sx3_mm_swe * by_SNOW_DENSITY    # Depth of SNOW [m]

    return df

# -----------------------------------------------------------
degree = np.pi / 180.
def add_corrections(df, return_period):
        # --- Elevation correction Reduces amount of snow with
        # steepness.  All traditional.  We measure 3-day snow depth
        # increase in flat field at a station.  But PRAs are very
        # different.  So they're putting it from flat to 28 degrees.
        # Then they add the lapse rate.  Then they do a second slope
        # angle correction for steeper terrain.  In the end, add
        # windblown snow parameter.  This is how every PRA gets its
        # own d0 dependent on slope angle and elevation.

        # GW: In SE Alaska, steep terrain can hold several meters of
        # snow in something almost 70 degrees from time to time.
# gradient_snowdepth needs to be based on precip. lapse rates around Juneau; Gabe will get back on that.
# Yves: reference_elevation should be elveation value from Rick's raster.
# If PRA is above DEM gridcell then must inflate reanalysis snow volume.  If PRA is below DEM, then defalte it.
        # def['Mean_DEM'] is mean elevation of the PRA

# No lapse rate or smoothing for now
#        gradient_snowdepth_si_units = .01 * scene_args['gradient_snowdepth'] # gradient_snowdepth parameter is in m/100m, translate to unitless
#
#        snowdepth_correction = \
#            (df['Mean_DEM'] - scene_args['reference_elevation']) \
#            * gradient_snowdepth_si_units
#        sx3_corrected = (df['sx3'] + snowdepth_correction)
        sx3_corrected = df['sx3']    # [m]

        # TODO: Why are we multiplying by cos(28) = .883?

        # Very old rule developed 30-40 years ago: the steeper the
        # slope, the less snow that can accumulate.  Very
        # traditional from SLF.  DO NOT use for Alaska.

        # (BUT... the steeper a release point is, the less snow it
        # has, MIGHT be useful for Alaska.  TODO: Discuss with
        # Gabe).  If snow is very moist...???
        if False:
            df['d0star'] = sx3_corrected * np.cos(28. * degree)    # [m]
        else:
            df['d0star'] = sx3_corrected    # [m]


        # --- Slope angle correction (slopecorr)
        # TODO: Discuss with Gabe.  Do we want to apply slope angle correction?
        # If yes, we can make it much simpler than what we have here.
        mean_slope_rad = df['Mean_Slope'] * degree
#        df['slopecorr'] =  0.291 / \
#            (np.sin(mean_slope_rad) - 0.202 * np.cos(mean_slope_rad))
        df['slopecorr'] = 1.0    # Slope angle correction was removing too much snow, not appropriate for coastal Alaska.

        # Wind load interpolation between 100 (0) and 200 (full wind load) elevation
        # Change max wind load dependent on scenario!!
        # TODO: Discuss with Gabe, how we do the wind load.
#        df['Wind'] = np.clip((df['Mean_DEM'] - 1000.) * .0001, 0., 0.1)
        df['Wind'] = 0    # Wind loading doesn't make sense without downscaling.

        # Calculate final d0: d0_10, d0_30, d0_100, d0_300
        d0_vname = f'd0_{return_period}'
        df[d0_vname] = ((df['d0star'] + df['Wind']) * df['slopecorr'])    # [m]
#        df[d0_vname] = 0.5    # DEBUG: d0_30 is unrealistically low.

        # Calculate volume (VOL_returnperiod)
        VOL_vname = f'VOL_{return_period}'
        # df[VOL_vname] = df['area_m2'] / np.cos(df['Mean_Slope']*degree) * df[d0_vname]
        df[VOL_vname] = (df['area_m2'] * df[d0_vname]) / np.cos(df['Mean_Slope']*degree)

        return df
# -----------------------------------------------------------
def _in_domain(gridI, dem_mask, xmin,ymin,xmax,ymax, pra):
    """Returns True if the PRA is >50% in the domain"""
    centroid = pra.centroid
    x,y = centroid.x, centroid.y

    # See if it's in the natural margin of this tile
    if not ((x >= xmin) and (x < xmax) and (y >= ymin) and (y < ymax)):
        return False

    # No domain mask provided
    if dem_mask is None:
        return True

    # See if it's in a gridcell marked as margin
    i,j = gridI.to_ij(x,y)
    return (dem_mask[j,i] == domain_mask.Value.MASK_IN)


def clip(rdf, gridI,dem_mask, clip_domain):
    """Removes PRAs outside a given range
    rdf:
        Release file(s) as dataframe
        REQUIRED cols: pra
    gridI,dem_mask:
        The domain mask (as calculated in domain_mask.py)
        Or None if we are not using it to clip...
    clip_domain: [x0,y0, x1,y1, ...]
        Coordinates of clip domain.
        Eg: scene_args['domain']
    Returns:
        New dataframe with only in-bounds PRAs remaining
    """

    npoints = len(clip_domain) // 2

    _xy = np.array(clip_domain, dtype='d').reshape( (npoints, 2) )
    x0,y0 = _xy[0,:]
    x1,y1 = _xy[2,:]
    xmin = min(x0,x1)
    xmax = max(x0,x1)
    ymin = min(y0,y1)
    ymax = max(y0,y1)
    #clip_domain = shapely.geometry.Polygon(_xy.reshape((len(_xy)//2,2)))
    #in_domain_fn = lambda pra: in_domain(domain, pra)
    in_domain_fn = lambda pra: _in_domain(gridI,dem_mask, xmin,ymin,xmax,ymax, pra)

    return rdf[rdf['pra'].map(in_domain_fn)]

# -----------------------------------------------------------
_empty_list = []
def add_dom(rdf, dem_filled, dem_nodata, grid_info, margins, **kwargs):
    """Does the domain finder algo.

    Runs the domain finder code
    rdf: (MODIFIES INPLACE)
        Release file(s) as dataframe
        REQUIRED cols: pra

    margins: {'T': float, 'M': float, ...}
        Margin to use for each PRA size

    Optional kwargs
        Forwarded to d8graph.find_domain()
        debug: int
            Set to 1 to put d8graph CPP code in debug mode
        min_alpha: (default 18.0 degrees)
            Minimum "alpha" angle at which avalanche expected to continue
        max_runout: (default 10000.)
            Maximum distance avalanche can go [m]

    """

    # Calculate domains
    chulls = list()
    doms = list()
    for ix,(_,row) in enumerate(rdf.iterrows()):

        if ix%1000 == 0:
            print('   Calculated {} of {} domains'.format(ix, len(rdf)))

        # --------- Get list of gridcells covered by the PRA polygon (the "PRA Burn")
        pra = row['pra']

        # Sometimes we get a MultiPolygon.  If the two overlap, we can
        # turn this back into a single Polygon and everyone will be
        # MUCH happier.  If not, then unary_union() will return a
        # MultiPolygon again.
        if type(pra) == multipolygon.MultiPolygon:
            # Choose the constituent polygon of maximum area
            polys = list(iter(pra.geoms))
            areas = [poly.area for poly in polys]
            max_area, max_poly = max(zip(areas,polys))
            pra = max_poly
#            print('aaaaaaaaa ', max_area, max_poly)
#            pra = shapely.ops.unary_union(pra)


        pra_burn = rasterize.rasterize_polygon_compressed(pra, grid_info)
#        if row['Id'] == 21:
#            print('BEGIN HHHHHHH')
#            print(pra_burn.shape, grid_info.nx, grid_info.ny, np.sum(pra_burn))
#            print(pra_burn)


        # Get the domain from the PRA burn
        args = ()
        margin = margins[row['pra_size']]
        ret = d8graph.find_domain(
            dem_filled, dem_nodata, grid_info.geotransform, pra_burn,
            debug=1, margin=margin, **kwargs)

#        if row['Id'] == 21:
#            print('END HHHHHHH')

        if ret is None:
            # This happens for some PRAs straddling the edge of the
            # overall domain (eg the US-Canada border).  See comment in d8graph.cpp:
            #    // Stop if we've hit the edge of the (valid) domain.
            #    // Clearly a useful avalanche simulation will not be possible.

            chulls.append(None)
            doms.append(None)
        else:
            _,chull_list,domain_list = ret
            try:
                chull_poly = shapely.geometry.Polygon(chull_list)
            except ValueError:
                print('Error on PRA')
                print(row)
                print(chull_list)
                raise

            chulls.append(chull_poly)
            doms.append(shapely.geometry.Polygon(domain_list))

    rdf['chull'] = chulls
    rdf['dom'] = doms

    return rdf
# -----------------------------------------------------------
def set_new_chunkinfo(df, scene_args, realized=False):
    """Adds a chunkinfo column to avalanches not currently assigned to a chhnk.
    This is useed to set CHUNK names.
    Avalanche ID is set to -1

    rdf:
        Dataframe of avalanches FOR ONE COMBO (see chunk.read_reldom())
        Must be at ID level and releasefiles read.
        Must have combo and pra_size columns.
        (return_period and forest must be fields in the combo objects)
    scene_args:
        AKRAMMS parameters for that combo"""
      

    assert realized == False

    resolution = scene_args['resolution']
    scene_name = scene_args['name']

    # Pull out return_period and forest (which we will call "rpfor")
    # TODO: This is experiment-specific!
    df['rpfor'] = df.combo.map(lambda x: (x.return_period, x.forest))

    dfs = list()
    for ((return_period,For), pra_size),dfg in df.groupby(['rpfor', 'pra_size']):

        dfg['chunkinfo'] = \
            [file_info.ChunkInfo(scene_args['scene_dir'], scene_args['name'], -1, For, resolution, return_period, pra_size)] * len(dfg.index)


        dfg = dfg.drop('rpfor', axis=1)
        dfs.append(dfg)

    return pd.concat(dfs)
# --------------------------------------------------------------
def get_max_chunkids(scenedir):
    cdf = level.scenedir_to_chunknames(scenedir)
    max_chunkids = cdf[['pra_size','chunkid']].groupby('pra_size').max()['chunkid'].to_dict()
    return max_chunkids

# --------------------------------------------------------------
def add_chunkid(rdf, scenedir, append=False):
    """Divides avalanches into chunks.
    rdf:
        
        Must have pra_size column.
    append:
        If True, add chunk numbers to the latest.
        Otherwise, start over. """

    #scene_args = params.load(scenedir)
    #scenedir = scene_args['scene_dir']

    # Determine max. chunkid for each pra_size  max_chunkid[pra_size]...
    if append:
        max_chunkids = get_max_chunkids(scenedir)
    else:
        max_chunkids = dict()

    # Assign chunk IDs differently for each different kind of thing
    dfs = list()
#    for (ci,pra_size),df in rdf.groupby(['chunkinfo', 'pra_size']):

    for pra_size,df in rdf.groupby('pra_size'):
        chunkid0 = max_chunkids.get(pra_size,-1) + 1

        for chunkid,chunkix in enumerate(range(0,df.shape[0],config.max_ramms_pras)):

            # Select out chunk
            dfc = df[chunkix:chunkix+config.max_ramms_pras]

            # Add the chunk number to the name
            dfc['chunkid'] = chunkid0 + chunkid

            dfs.append(dfc)

        max_chunkids[pra_size] = chunkid
    return pd.concat(dfs)


# -----------------------------------------------------------

# =======================================================================
def write_rel(rdf, wkt, return_period, ofname, **kwargs):
    """
    Writes the _rel.shp shapefile
    rdf:
        Release file(s) as dataframe
        MUST CONTAIN: pra
    """

    # Select columns to write
    cols = ['area_m2', 'Mean_DEM', 'Mean_Slope', 'Scene_reso', 'Id', 'i', 'j', 'sx3', 'd0star', 'slopecorr', 'Wind', f'd0_{return_period}', f'VOL_{return_period}', 'pra']
    cols += [name for name in ('chunkid', 'pra_size') if name in rdf]
    df = rdf.reset_index()[cols]

#    ofname.parents[0].mkdir(parents=True, exist_ok=True)
    os.makedirs(ofname.parents[0], exist_ok=True)
#    shputil.write_df(df, 'pra', 'Polygon', ofname, wkt=wkt, **kwargs)
    crs = pyproj.CRS.from_user_input(wkt)
    df = geopandas.GeoDataFrame(df, geometry='pra')
    df.to_file(ofname, engine='fiona', crs=crs, **kwargs)

def write_dom(rdf, wkt, ofname, **kwargs):
    """
    Writes the _dom.shp shapefile
    rdf:
        Release file(s) as dataframe
        MUST CONTAIN: pra
    """

    # Select columns to write
    df = rdf.reset_index()[['Id', 'dom']]
#    shputil.write_df(df, 'dom', 'Polygon', ofname, wkt=wkt, **kwargs)
    df = geopandas.GeoDataFrame(df, geometry='dom')
    crs = pyproj.CRS.from_user_input(wkt)
    df.to_file(ofname, engine='fiona', crs=crs, **kwargs)

def write_chull(rdf, wkt, ofname, **kwargs):
    """
    Writes the _chull.shp shapefile
    rdf:
        Release file(s) loaded into dataframe
        MUST CONTAIN: pra
    """

    # Select columns to write
    df = rdf.reset_index()[['Id', 'chull']]
    df = geopandas.GeoDataFrame(df, geometry='chull')
#    shputil.write_df(df, 'chull', 'Polygon', ofname, wkt=wkt, **kwargs)
    crs = pyproj.CRS.from_user_input(wkt)
    df.to_file(ofname, engine='fiona', crs=crs, **kwargs)

# -----------------------------------------------------------
def dem_forest_links(scene_args, chunk_dir, oslope_name, For):
    """
    chunk_dir:        RAMMS directory where FOREST and DEM files are being created
    """

    # ---- DEM File
    idem_dir,idem_tif = os.path.split(scene_args['dem_file'])
    idem_stub = idem_tif[:-4]
    links = [
        (os.path.join(idem_dir, f'{idem_stub}.tif'),
            os.path.join(chunk_dir, 'DEM', f'{oslope_name}_DEM.tif')),
        (os.path.join(idem_dir, f'{idem_stub}.tfw'),
            os.path.join(chunk_dir, 'DEM', f'{oslope_name}_DEM.tfw')),
    ]


    # ---- Forest File
    if For == 'For':
        iforest_dir,iforest_tif = os.path.split(scene_args['forest_file'])
        iforest_stub = iforest_tif[:-4]
        links += [
            (os.path.join(iforest_dir, f'{iforest_stub}.tif'),
                os.path.join(chunk_dir, 'FOREST', f'{oslope_name}_forest.tif')),
            (os.path.join(iforest_dir, f'{iforest_stub}.tfw'),
                os.path.join(chunk_dir, 'FOREST', f'{oslope_name}_forest.tfw')),
        ]

    return links


# 2023-04-24 Marc Christen said:
#   As you do not run Stage 2 in RAMMS, you do not use the variable
#   “NRCPUS” in the scenario-file. In the new version (link below) you
#   can now use this variable. NRCPUS = 8 means, that RAMMS will start
#   the first 8 exe-files to create the xy_coord-files in parallel, but
#   then RAMMS will wait for the 8-th exe-file to finish. Then RAMMS
#   will start the next 8 exe-files, and so on…..This will give a small
#   break, such that not 100 exe-files will execute in parallel. What do
#   you think? Could you please try this workaround for the moment? Of
#   course you could also increase NRCPUS, or decrease…..


scenario_tpl = \
r"""LSHM    {scenario_name}
MODULE  AVAL
MUXI    VARIABLE
DIR     {ramms_dir}/
DEM     DEM/
RELEASE RELEASE/
DOMAIN  DOMAIN/
FOREST  FOREST/
NRCPUS  {ncpu}
COHESION {cohesion}
DEBUG   {debug}
CPUS_PRE {ncpu_preprocess}
{test_nr_tpl}KEEP_DATA {keep_data}
ALT_LIM_TOP  {alt_lim_top}
ALT_LIM_LOW  {alt_lim_low}
END
"""

def write_scenario_txt(chunk_dir, chunk_dir_final, alt_lim_top=1500, alt_lim_low=1000, ncpu=config.ramms_ncpu, ncpu_preprocess=config.ramms_ncpu_preprocess, cohesion=50):
    """ci: ChunkInfo
    """

    chunk_name = chunk_dir_final.parts[-1]

    # Create the scenario file
    kwargs = dict()
    kwargs['scenario_name'] = chunk_name
    kwargs['ramms_dir'] = str(chunk_dir_final)  #config.roots.convert_to(chunk_dir_final, config.roots_w)
    kwargs['ncpu'] = str(ncpu)
    kwargs['ncpu_preprocess'] = str(ncpu_preprocess)
    kwargs['cohesion'] = str(cohesion)
    if config.debug:
        kwargs['debug'] = '1'
        kwargs['keep_data'] = '1'
        kwargs['test_nr_tpl'] = "TEST_NR    20\n"
    else:
        kwargs['debug'] = '0'
        kwargs['keep_data'] = '1'
        kwargs['test_nr_tpl'] = ""
    kwargs['alt_lim_top'] = str(alt_lim_top)
    kwargs['alt_lim_low'] = str(alt_lim_low)

    scenario_txt = os.path.join(chunk_dir, 'scenario.txt')
    os.makedirs(chunk_dir, exist_ok=True)
    with open(scenario_txt, 'w') as out:
        out.write(scenario_tpl.format(**kwargs))


def setlink_or_copy(ifile, ofile):
    if config.shared_filesystem:    # No symlinks for Windows
        if os.path.islink(ofile) or not os.path.exists(ofile):
            os.makedirs(os.path.dirname(ofile), exist_ok=True)
            shutil.copy(ifile, ofile)
    else:
        ioutil.setlink(ifile, ofile)


# TODO: Write this atomically!!!
def write_chunk(scene_args, chunk_info, dfc, scenario_kwargs):
    """Writes a full RAMMS run (chunk), ready for RAMMS Stage 1.
    scene_args:
        The overall AKRAMMS scene (combo) this chunk will be a part of
    chunk_dir:
        RAMMS directory for this chunk
        Eg: /home/efischer/prj/ak/bak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/x-113-0450000030SFor_10m
    slope_name:
        Alternate arrangement of details
    dfc: DataFrame describing the chunk.

    Returns:
        chunk_dir

    NOTE:
        chunk_name = f'{ci.scene_name}{ci.chunkid:05d}{ci.For}_{ci.resolution}m_{ci.return_period}{ci.pra_size}'
        slope_name = f'{scene_name}{chunkid:05d}{For}_{resolution}m'    # Used for DEM / Forest files
        chunk_dir = scene_dir / 'CHUNKS' / chunk_name

    """

    ci = chunk_info

#    chunk_dir_final = scene_args['scene_dir'] / 'CHUNKS' / ci.chunk_name    # Final atomically written location
#    chunk_dir = scene_args['scene_dir'] / 'CHUNKS' / f'{ci.chunk_name}.tmp'    # Temporary while we write it

    chunk_dir_final = scene_args['scene_dir'] / 'CHUNKS' / ci.chunk_name    # Final atomically written location
    chunk_dir = chunk_dir_final

    slope_dir = chunk_dir / 'RESULTS' / ci.slope_name
    avalanche_dir = slope_dir / ci.avalanche_name

    # Make symlinks for DEM file, etc.
    for ifile,ofile in dem_forest_links(scene_args, chunk_dir, ci.slope_name, ci.For):
        setlink_or_copy(ifile, ofile)

    # Write scenario.txt
    scenario_txt = os.path.join(chunk_dir, 'scenario.txt')
    write_scenario_txt(chunk_dir, chunk_dir_final, **scenario_kwargs)

    # Write the _rel.shp file
    os.makedirs(chunk_dir / 'RELEASE', exist_ok=True)
    ofname = chunk_dir / 'RELEASE' / f'{ci.slope_name}_{ci.avalanche_name}_rel.shp'
    _dfx = dfc.reset_index()[['area_m2', 'Mean_DEM', 'Mean_Slope', 'Scene_reso', 'Id', 'i', 'j', 'sx3', 'd0star', 'slopecorr', 'Wind', f'd0_{ci.return_period}', f'VOL_{ci.return_period}', 'pra']]
#    shputil.write_df(_dfx, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])
    _dfx = geopandas.GeoDataFrame(_dfx, geometry='pra')
    _dfx.to_file(ofname, engine='fiona', crs=pyproj.CRS.from_user_input(scene_args['coordinate_system']))

    # Write the _dom.shp file 
    os.makedirs(chunk_dir / 'DOMAIN', exist_ok=True)
    ofname = chunk_dir / 'DOMAIN' / f'{ci.slope_name}_{ci.avalanche_name}_dom.shp'
    _dfx = dfc.reset_index()[['Id', 'dom']]
#    shputil.write_df(_dfx, 'dom', 'Polygon', ofname, wkt=scene_args['coordinate_system'])
    _dfx = geopandas.GeoDataFrame(_dfx, geometry='dom')
    _dfx.to_file(ofname, engine='fiona', crs=pyproj.CRS.from_user_input(scene_args['coordinate_system']))

#    os.rename(chunk_dir, chunk_dir_final)
    return chunk_dir_final
# Commented out because these files differ from the (by definition
# correct) versions created by RAMMS.
#    # Write the .relp and .domp files for each avalanche
#    # (Secondary files, as written by Python)
#    os.makedirs(avalanche_dir, exist_ok=True)
#    for _,row in dfc.iterrows():
#        id = row['Id']
#        ofname = os.path.join(avalanche_dir, f'{chunk_name}_{id}.relp')
#        rammsutil.write_polygon(row['pra'], ofname)
#        ofname = os.path.join(avalanche_dir, f'{chunk_name}_{id}.domp')
#        rammsutil.write_polygon(row['dom'], ofname)

# -----------------------------------------------------------
