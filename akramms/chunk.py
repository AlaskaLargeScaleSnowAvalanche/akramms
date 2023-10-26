
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
    reldf = shputil.read_df(relfname, shape='pra', **kwargs)
    if 'Id' in reldf:
        reldf = reldf.drop('fid', axis=1)
    else:
        # Release file written by eCog
        reldf = reldf.rename(columns={'fid': 'Id'})

    return reldf.set_index('Id')
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

    df = shputil.read_df(domfname, shape='dom', **kwargs) \
        .drop('fid', axis=1) \
        .set_index('Id')

    return dom
# -----------------------------------------------------------
def read_reldom(relfname, **kwargs):
    """Reads a RELEASE and related DOMAIN file and merges together resulting dataframes"""

    domfname = relfname.parents[1] / 'DOMAIN' / (relfname.parts[-1][-7:] + '_dom.shp')

    rdf = read_rel(relfname, **kwargs)
    ddf = read_dom(domfname, **kwargs)

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

def add_sizecat(reldf):
    """
    reldf:
        Releasefile read via read_releasefile()
        (or created by another means)
        Must have column: area_m2
    """
    reldf['sizecat'] = reldf['aream2'].map(
        lambda x: _pra_sizes[bisect.bisect(_post_cat_bounds, x) - 1])
# -----------------------------------------------------------
def add_snow(df, snow_density=200.):
    """
    snow_lokoup:
        See snow.RasterLookup
    """
    # This is a tuple (j, i, sx3)
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
def _in_domain(xmin,ymin,xmax,ymax, pra):
    """Returns True if the PRA is >50% in the domain"""
    centroid = pra.centroid
    x,y = centroid.x, centroid.y
    return (x >= xmin) and (x < xmax) and (y >= ymin) and (y < ymax)



def clip(rdf, clip_domain):
    """Removes PRAs outside a given range
    rdf:
        Release file(s) as dataframe
        REQUIRED cols: pra
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
    in_domain_fn = lambda pra: _in_domain(xmin,ymin,xmax,ymax, pra)

    return rdf[rdf['pra'].map(in_domain_fn)]

# -----------------------------------------------------------
_empty_list = []
def add_dom(rdf, grid_info):
    """Does the domain finder algo.

    Runs the domain finder code
    rdf: (MODIFIES INPLACE)
        Release file(s) as dataframe
        REQUIRED cols: pra
    """

    # Calculate domains
    chulls = list()
    doms = list()
    for ix,(_,row) in enumerate(rdf.iterrows()):

        if ix%1000 == 0:
            print('   Calculated {} of {} domains'.format(ix, len(rdf)))

        # Get list of gridcells covered by the PRA polygon (the "PRA Burn")
        pra_burn = rasterize.rasterize_polygon_compressed(row['pra'], grid_info)

        # Get the domain from the PRA burn
        args = ()
        ret = d8graph.find_domain(
            dem_filled, dem_nodata, grid_info.geotransform, pra_burn,
            margin=margin, debug=1, min_alpha=min_alpha, max_runout=max_runout)

        if ret is None:
            chull_list = _empty_list
            domain_list = _empty_list
        else:
            _,chull_list,domain_list = ret
        chulls.append(shapely.geometry.Polygon(chull_list))
        doms.append(shapely.geometry.Polygon(domain_list))

    rdf['chull'] = chull
    rdf['doms'] = doms

    return rdf
# -----------------------------------------------------------
def add_master_rammsname(df, scene_args):
    """Adds a master_rammsname (type rammsutil.RammsName) column.
    This is useed to set CHUNK names.

    rdf:
        Avalanches for JUST ONE COMBO.
        Must have combo and pra_size columns.
        (return_period and forest must be fields in the combo objects)
    scene_args:
        AKRAMMS parameters for that combo"""
      

    # Pull out return_period and forest (which we will call "rpfor")
    df['rpfor'] = pd.map(df.combo, lambda x: (x.return_period, x.forest))

    dfs = list()
    for ((return_period,forest), pra_size),dfg in df.groupby(['rpfor', 'pra_size']):
        dfg['master_rammsname'] = rammsutil.RammsName(
            os.path.join(scene_args['scene_dir'], 'CHUNKS'),
            scene_args['name'], None, forest, scene_args['resolution'],
            return_period, pra_size, None)
        dfg = dfg.drop('rpfor', axis=1)
        dfs.append(dfg)

    return pd.concat(dfs)
# --------------------------------------------------------------
def add_chunkname(rdf, scene_args, append=False):
    """Divides avalanches into chunks.
    rdf:
        Must have master_rammsname column.
    append:
        If True, add chunk numbers to the latest.
        Otherwise, start over.
    """

    #scene_args = params.load(scenedir)
    scenedir = scene_args['scene_dir']

    # Determine max. chunkid for each sizecat  max_chunkid[sizecat]...
    if append:
        cdf = level.scenedir_to_chunknames(scenedir)
        max_chunkids = cdf[['sizecat','chunkid']].groupby('sizecat').max()['chunkid'].to_dict()
    else:
        max_chunkids = dict()

    # Assign chunk IDs differently for each different kind of thing
    dfs = list()
    for jb,df in rdf.groupby('master_rammsname'):
       base = scenedir / 'RELEASE' / jb.ramms_name

            ofnames = list()
            chunk_info = list()
            for segment,chunkix0 in enumerate(range(0,df.shape[0],config.max_ramms_pras)):
                chunkix = chunkix0 + max_chunkids.get(jb.pra_size,0)

                # Select out chunk
                dfc = df[chunkix:chunkix+config.max_ramms_pras]

                # Add the chunk number to the name
                jb1 = copy.copy(jb)
                jb1.set(segment=segment)
                dfc['chunkname'] = jb1.rammsdir_name

                dfs.append(dfc)

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
    df = rdf.reset_index()[['area_m2', 'Mean_DEM', 'Mean_Slope', 'Scene_reso', 'Id', 'i', 'j', 'sx3', 'd0star', 'slopecorr', 'Wind', 'd0_{return_period}', 'VOL_{return_period}', 'pra']]

    shputil.write_df(df, 'pra', 'Polygon', ofname, wkt=wkt, **kwargs)

def write_dom(rdf, wkt, ofname, **kwargs):
    """
    Writes the _rel.shp shapefile
    rdf:
        Release file(s) as dataframe
        MUST CONTAIN: pra
    """

    # Select columns to write
    df = rdf.reset_index()[['Id', 'dom']]
    shputil.write_df(df, 'dom', 'Polygon', ofname, wkt=wkt, **kwargs)

def write_chull(rdf, wkt, ofname, **kwargs):
    """
    Writes the _rel.shp shapefile
    rdf:
        Release file(s) as dataframe
        MUST CONTAIN: pra
    """

    # Select columns to write
    df = rdf.reset_index()[['Id', 'chull']]
    shputil.write_df(df, 'chull', 'Polygon', ofname, wkt=wkt, **kwargs)

# -----------------------------------------------------------
def prepare_chunk(scene_args, jb1, dfc):
    """Writes a full RAMMS run (chunk), ready for RAMMS Stage 1.
    scene_args:
        The overall AKRAMMS scene (combo) this chunk will be a part of
    jb1: RammsName
        Describes the resulting name of the chunk (including directory of the RAMMS run).
    dfc: DataFrame describing the chunk.

    """

    # Make symlinks for DEM file, etc.
    for ifile,ofile in dem_forest_links(scene_args, jb1.ramms_dir, jb1.slope_name, forest=jb1.forest):
        setlink_or_copy(ifile, ofile)

    # Write scenario.txt
    scenario_txt = os.path.join(jb1.ramms_dir, 'scenario.txt')
    write_scenario_txt(jb1, **scenario_kwargs)

    # Write the _rel.shp file
    ofname = os.path.join(jb1.ramms_dir, 'RELEASE', f'{jb1.ramms_name}_rel.shp')
    os.makedirs(os.path.dirname(ofname), exist_ok=True)
    _dfx = dfc[list(rel_df.columns)]
    shputil.write_df(_dfx, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])
    
    # Write the _dom.shp file 
    ofname = os.path.join(jb1.ramms_dir, 'DOMAIN', f'{jb1.ramms_name}_dom.shp')
    os.makedirs(os.path.dirname(ofname), exist_ok=True)
    shputil.write_df(dfc[list(dom_df)], 'dom', 'Polygon', ofname, wkt=scene_args['coordinate_system'])

    # Write the .relp and .domp files for each avalanche
    # (Secondary files, as written by Python)
    os.makedirs(jb1.avalanche_dir, exist_ok=True)
    for _,row in dfc.iterrows():
        id = row['Id']
        ofname = os.path.join(jb1.avalanche_dir, f'{jb1.ramms_name}_{id}.relp')
        rammsutil.write_polygon(row['pra'], ofname)
        ofname = os.path.join(jb1.avalanche_dir, f'{jb1.ramms_name}_{id}.domp')
        rammsutil.write_polygon(row['dom'], ofname)

    # Store chunk info
    For = 'For' if jb1.forest else 'NoFor'
    chunk_info += [
        (segment, id,
        f'{jb1.scene_name}{jb1.segment:05d}{jb1.return_period}{jb1.pra_size}{For}_{jb1.resolution}m')
        for id in dfc['Id']]
    #chunk_info.append(segment, list(dfc['Id']))
# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------
