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
def nc_extent(nc_fname, margin=(0.,0.)):
    with netCDF4.Dataset(arc_fname) as nc:
        bbox = nc.variables['bounding_box'][:].reshape(-1)    # [x0,y0,x1,y1]
    return bbox
# -----------------------------------------------------------------
def add_margin(bbox, marginx, marginy):
    return [bbox[0]-marginx, bbox[1]-marginy, bbox[2]+marginx, bbox[2]+marginy]
# -----------------------------------------------------------------
def nc_read_bbox(nc_fname):
    with netCDF4.Dataset(nc_fname, 'r') as nc:
        bbox = nc.variables['bounding_box'][:]
    return bbox
# ---------------------------------------------------------------------
def normalize_nc_fnames(nc_fnames):
    for nc_fname in nc_fnames:
        extent = ...extent of the NetCDF avalanche + margin...
        return [ [nc_fname], extent) ]

#AvalSpec1 = collections.namedtuple('AvalSpec', ('exp_mod', 'combo', 'ids', 'extent'))
# extent: Query within this extent (x0,y0,x1,y1)
# ids: List of ad-hoc IDs to DEFINITELY fetch, whether or not they pass any filter
#      (If you ONLY want these IDs, use filter_fn=lambda x: False)
def normalize_aval_spec(aspec0):

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
            # Use the default, same extent as the subdomain
            extent = ...extent of (idom,jdom) subdomain...

        # Determine IDs (depends on whether user supplied)
        return [ AvalSpec(aspec0.exp_mod, aspec0.combo, aspec0.ids, [extent]) ]


    # --- User specified a wildcard combo, select combos by extent
    else:
        # User should have specified at least one extent, but NO
        # individual IDs
        assert len(aspec0.extents) > 0
        assert len(aspec0.ids) == 0

        # Get extent and list of combos intersecting that extent
        extent = union_extents(aspec0.extents)    # Our query extent
        aspec1s = list()
        for idom,jdom in exp_mod.gridD.domains_intersecting_extent(extent):
            lcombo = list(combo[:-2]) + [idom, jdom]
            combo = exp_mod.Combo(*lcombo)
            aspec1s.append(AvalSpec(aspec0.exp_mod, combo, [], [extent]))

        return aspec1s

def normalize_aval_specs(aspec0s):
    """Normalizes a collection of AvalSpecs"""

    ret = list()
    for aspec0 in aspec0s:
        ret += normalize_aval_spec(aspec0)

# ---------------------------------------------------------------------
def query(aspecs, filter_fn=lambda x: True, ok_statuses={archive.OK, archive.OVERRIN}):

    """Produces lists of NetCDF filenames.  Also converts to NetCDF at
    this point if needed.

    aspecs: [AvalSpec, ...]
        Normalized AvalSpecs
    returns: [arc_fname, ...], extent
        [arc_fname, ...]
            Filenames of archive files to include in the mosaic]
        extent
            Final mosaic extent
    """

    # Get final query extent
    assert all(len(aspec.extents) == 1 for aspec in aspecs)
    extent = union_extents((aspec.extent[0] for aspec in aspecs))

    # Convert to set of archive filenames
    arc_fnames = list()
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
                    bbox = nc_read_bbox(nc_fname)

                # Include for real if this intersects.
                if intersect_extents(bbox, extent):
                    arc_fnames.append(nc_fname)

    return arc_fnames, extent
# ---------------------------------------------------------------


mosaic_query(exp_mod, query, margin=1000, filter_fn=lambda x: True, ok_statuses={archive.OK, archive.OVERRIN})
    """Run a "Mosaic" query, which can involve regular queries and/or additional NetCDF files.

    query: [avals, ...] where each avals is either:
        * Many Avalanches: AvalSpec
            (exp_mod, combo, ids)
        * Single Avalance: str
            arc_fname
        Result of avalaparse.parse_aval_specs()
    margin:
        Margin to add to extent (in meters)

    """

    # Determine query specs vs. netCDF files
    aspecs = [x for x in query if isinstance(x, AvalSpec)]
    nc_fnames = [x for x in query if not isinstance(x, AvalSpec)]

    # Determine extent for NetCDF queries
    nc_extent = union_extents((nc_read_bbox(nc_fname) for nc_fname in nc_fnames))

    # Determine files and extent for query specs
    ncq_fnames, ncq_extent = query(aspecs, filter_fn=filter_fn, ok_statuses=ok_statuses)

    # Combine the two together
    extent = union_extents((nc_extent, ncq_extent))
    arc_fnames = nc_fnames + ncq_fnames

    return arc_fnames, extent





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
