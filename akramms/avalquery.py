import os,collections,re,itertools

# -----------------------------------------------------------------
def union_extents(extents):
    """Finds an extent enclosing all the given extents
    extents: [(x0,y0, x1,y1), ...]
    """
    z0 = extents[0]
    for z1 in extents[1:]:
        z0 = (
            min(z0[0], z1[0]),
            min(z0[1], z1[1]),
            max(z0[0], z1[0]),
            max(z0[1], z1[1]))

    return z0
# -----------------------------------------------------------------
#def extents_intersect(ext0, ext1):
#    """
#    ext0, ext1: [x0,y0, x1,y1]
#
#    See: https://stackoverflow.com/questions/20925818/algorithm-to-check-if-two-boxes-overlap
#    """
#    xmin = min(ext0[0], ext1[0])    # .x0
#    ymin = min(ext0[1], ext1[1])    # .y0
#
#    xmax = min(ext0[2], ext1[2])    # .x1
#    ymax = min(ext0[3], ext1[3])    # .y1
#
#    A = [xmin,ymin,xmax,ymax]
#    B = [xmin,ymin,xmax,ymax]
#
#    return not ((A[0] > B[2]) or (A[2] < B[0]) or (A[1] > B[3]) or (A[3] < B[1]))



def extents_intersect(extent0, extent1):
    """
    ext0, ext1: [x0,y0, x1,y1]

    See: https://saturncloud.io/blog/algorithm-to-check-if-two-boxes-overlap/
    """
    x1_1, y1_1, x2_1, y2_1 = extent0
    x1_2, y1_2, x2_2, y2_2 = extent1

    if x2_1 < x1_2 or x2_2 < x1_1:
        return False

    if y2_1 < y1_2 or y2_2 < y1_1:
        return False

    return True

# -----------------------------------------------------------------
def nc_extent(nc_fname, margin=(0.,0.)):
    with netCDF4.Dataset(arc_fname) as nc:
        bbox = nc.variables['bounding_box'][:].reshape(-1)    # [x0,y0,x1,y1]
    return bbox
# -----------------------------------------------------------------
def add_margin(bbox, margin)
    return [bbox[0]-margin[0], bbox[1]-margin[1], bbox[2]+margin[0], bbox[2]+margin[1]]
# -----------------------------------------------------------------
@functools.lru_cache()
def domain_extents(exp_mod):
    # Load set of extents
    domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    df = shputil.read_df(domains_shp, read_shapes=True)
    for row in df.iterrows():
        xx,yy = row['shape'].exterior.coords.xy
        yield row.i,row.j,(xx[0],yy[0], xx[2],yy[2])    # Convert to an Extent-type list of (x0,y0,x1,y1)


# -----------------------------------------------------------------
# ===================================================================
# "Normalize" means convert whatever the user provided to a list of AvalSpecs
# that can be queried as lists of avalanche functions.
def _normalize_aval_spec(aspec0):

    """Remove all wildcards, makes a spec ready to turn into archive
    filenames and input into query() below.

    aspec0: AvalSpec
        * idom,jdom might be None (wildcard)
        * ids might be None (wildcard)
    Returns:
        [AvalSpec, ...]
        * idom,jdom specified everywhere
        * Exactly one extent

    """
    # ----------- Determine the list of combos to search, and mosaic extent

    # --- User specified one combo, use that.
    if aspec0.combo.idom is not None and aspec0.combo.jdom is not None:

        # Determine extent (depends on whether user supplied)
        if len(aspec0.extents) > 0:
            # Use user-provided extents, if any
            extent = union_extents(aspec0.extents)    # Our query extent
        else:
            # Nothing user-provided, use extent of subdomain
            extent = exp_mod.gridD.subgrid(
                aspec0.combo.idom, aspec0.combo.jdom,
                exp_mod.resolution, exp_mod.resolution,
                margin=False)

        # Determine IDs (depends on whether user supplied)
        return [ AvalSpec(aspec0.exp_mod, aspec0.combo, aspec0.ids, [extent]) ]


    # --- User specified a wildcard combo, select combos by extent
    else:
        # User should have specified at least one extent, but NO
        # individual IDs
        assert len(aspec0.extents) > 0
        assert len(aspec0.ids) == 0

        # Get extent
        extent = union_extents(aspec0.extents)    # Our query extent

        # Get list of combos intersecting that extent
        aspec1s = list()
        for idom,jdom,dom_ext in domain_extents(exp_mod):
            if extents_intersect(dom_ext, extent):
                lcombo = list(combo[:-2]) + [idom, jdom]
                combo = exp_mod.Combo(*lcombo)
                aspec1s.append(AvalSpec(aspec0.exp_mod, combo, [], [extent]))

        return aspec1s

def normalize(aspec0s):
    """Normalizes a collection of AvalSpecs"""

    ret = list()
    for aspec0 in aspec0s:
        ret += _normalize_aval_spec(aspec0)

# ---------------------------------------------------------------------
# ==========================================================================
# "Query" means converting whatever was normalized to:
#     [nc_fname, ...]    Avalanche files to mosaic
#     extent             Area to mosaic
def query(aspecs, nc_fnames0, margin=(0.,0.), filter_fn=lambda x: True, ok_statuses={archive.OK, archive.OVERRIN}):
    """Produces lists of NetCDF filenames.  Also converts to NetCDF at
    this point if needed.

    extent:
        User-provided extent to include.  (Or typically comes from nc_fnames)
        This will be unioned with individual aspecs extents.
    aspecs: [AvalSpec, ...]
        Normalized AvalSpecs
    returns: [arc_fname, ...], extent
        [arc_fname, ...]
            Filenames of archive files to include in the mosaic]
        extent
            Final mosaic extent
    """
    # Determine extent
    assert all(len(aspec.extents) == 1 for aspec in aspecs)    # From normalization above
    extent = union_extents(itertools.chain(
        (nc_extent(nc_fname) for nc_fname in nc_fnames0),
        (aspec.extent[0] for aspec in aspecs)))
    extent = add_margin(extent, margin)    # Give ourselves margin!

    # Convert to set of archive filenames
    nc_fnames = list(nc_fnames0)    # Start with filenames explicitly provided
    for aspec in aspecs:
        aspec_ids = set(aspec.ids)    # IDs we know we want to keep
        release_df = exputil.release_df(exp_mod, combo)
        all_ids = release_df.index.tolist()

        # Filter IN user-provided IDs, filter OUT avalanches outside the extent
        # Otherwise, apply user's filter
        nc_fnames = archive.fetch(exp_mod, aspec.combo, all_ids, ok_statuses)
        #efilter_fn = wrap_filter(filter_fn, aspec.ids, extent)
        for (id,row),nc_fname in zip(release_df.iterrows(), nc_fnames):

            # Include things in the ids list, or that the filter function allows.
            if (id in aspec_ids) or filter_in_fn(id, row, nc_fname:

                # Get the bounding box for the avalanche
                if 'bounding_box' in row:
                    bbox = row['bounding_box']
                else:
                    bbox = nc_extent(nc_fname)

                # Include for real if this intersects.
                if intersect_extents(bbox, extent):
                    nc_fnames.append(nc_fname)

    return nc_fnames, extent
# ---------------------------------------------------------------



#Cases:
#
#1. All avalanche files: avals=filter_fn(input), extent based on avals + fixed margin (500m?)
#
## ak-ccsm-1981-1990-lapse-For-30 113 45   (ids=[None] implied)
## ak-ccsm-1981-1990-lapse-For-30/x-113-45  17    # Just 17
## ak-ccsm-1981-1990-lapse-For-30/x-113-45  . 17    # filter(None) + [17]
#2. combo with non-wildcard idom/jdom: extent = same as idom/jdom domain
#   if None in ids, then avals <- filter_fn(all avalanches in the domain).
#   Also add in any other SPECIFIED ids (do not filter)
#
## ak-ccsm-1981-1990-lapse-For-30 .. southeast
#3. combo with wildcard idom/jdom:
#   A region in ids is REQUIRED, wildcard ids not allowed, but individual additional avalanches can be added as needed.
#
#   Add in any aditional avalanche files (see 1) if specified, and expand domain as needed.
#
#
#Can have combination of (1), (2), (3) above.  Set domain to superset of ALL.
#
#
