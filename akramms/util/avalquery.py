


Query = collections.namedtuple('Query', ('extent', 'avals'))

# -----------------------------------------------------------------
def ids_in_combo(exp_mod, combo):
    """Read the RELEASE files to determine which avalanche IDs are
    involved in a combo."""

    # Look in RELEASE-dir shapefiles to determine theoretical set Avalanche IDs
    # (By looking here, we avoid picking up random junk)
    shp_ids = list()
    for leaf in os.listdir(os.path.join(scene_dir, 'RELEASE')):
        match = _relRE.match(leaf)
        if match is not None:
            df = shputil.read_df(
                os.path.join(scene_dir, 'RELEASE', leaf), read_shapes=False)
            shp_ids += df['Id'].tolist()

    return shp_ids
# ----------------------------------------------------------
FetchSpec = collections.namedtuple('FetchSpec', ('exp_mod', 'combo', 'filter_fn', 'ids', 'nc_fnames', 'extent'))

def wrap_filter_by_extent(filter_fn, extent):
    def _filter(arc_fname):
        # Assume avalanche has already been archived to .nc
        # This might filter based on size, so we don't have to read it.
        if not filter_fn(arc_fname):
            return False
        
        # Filter based on extent
        # TODO: Compute a bounding box for each avalanche when archiving, based on the gridcells it touched.

    return _filter
                

def parsed_to_fetch_part1(spec, filter_in_fn=lambda x: True):
    """Converts a single AvalTuple spec to args for archive.fetch()
    spec: (AvalTuple, nc_fname)

    Returns:
        # The (exp_mod, combo, ids) will be turned to [nc_fnames] later...
        [ ((exp_mod, combo, ids), [nc_fnames], extent), ...]
    """
    aval_tuple, nc_fname = spec

    # This can't happen in the parser
    assert (aval_tupe is None) or (nc_fname is None):

    if nc_fname is not None:
        extent = ...extent of the NetCDF avalanche + margin...
        return [ (None, None, None, None, [nc_fname], extent) ]

    if aval_tuple is not None:
        exp_mod, combo, ids = aval_tuple
        rets = list()

        arc_fnames = set()

        # Figure out which combos and extents we will query
        if combo.idom is not None and combo.jdom is not None:
            extent = ...extent of (idom,jdom) subdomain...

            # Add IDs specified by the user
            arc_fnames.add(archive.fetch(exp_mod, combo, lambda x: True, [id for id in ids if id is not None]))

            # Add all FILTERED IDs for this combo, if a wildcard was used
            if None in ids:
                combos = [combo]
        else:    # Wildcard idom/jdom

            # Individual IDs don't make sense
            if ids != [None]:
                raise ValueError('Only wildcard Avalanche IDs allowed when querying across more than one combo')

            # Find at least one extent
            extent = union_extents(x for x in aval_tuple.ids if isinstance(x, Extent))
            if extent is None:    # No extents found in aval_tuple.ids
                raise Error('At least one extent must be present, or the i/j subdomain must be specified')

            # Look in all domains that intersect the extent
            combos = list()
            for idom,jdom in exp_mod.gridD.domains_intersecting_extent(extent):
                lcombo = list(combo[:-2]) + [idom, jdom]
                combo = exp_mod.Combo(*lcombo)
                combos.append(exp_mod.Combo(*lcombo))

        efilter_fn = wrap_filter_by_extent(filter_fn, extent)

        # Find everything in the combos (filtered)
        for combo in combos:
            # Add all IDs in each combo (if specified as a wildcard)
            if None in ids:
                # TODO: incorporate ok_statuses into the filter_fn
                arc_fnames.update(archive.fetch(exp_mod, combo, efilter_fn, list_all_ids_in_combo(combo)))

    return (arc_fnames, extent)








def prepare(aval_specs, filter=None_fn)

    """Turns a list of AvalTuple or archive .nc files into the things
    needed to run a mosaic operation:

    extent: [x0, y0, x1, y1]
        Rectangle for our output mosaic
    avals: [aval, ...]
        List of avalanche files to mosaic
    """








Cases:

1. All avalanche files: avals=filter_fn(input), extent based on avals + fixed margin (500m?)

# ak-ccsm-1981-1990-lapse-For-30 113 45   (ids=[None] implied)
# ak-ccsm-1981-1990-lapse-For-30/x-113-45  17    # Just 17
# ak-ccsm-1981-1990-lapse-For-30/x-113-45  . 17    # filter(None) + [17]
2. combo with non-wildcard idom/jdom: extent = same as idom/jdom domain
   if None in ids, then avals <- filter_fn(all avalanches in the domain).
   Also add in any other SPECIFIED ids (do not filter)

# ak-ccsm-1981-1990-lapse-For-30 .. southeast
3. combo with wildcard idom/jdom:
   A region in ids is REQUIRED, wildcard ids not allowed, but individual additional avalanches can be added as needed.

   Add in any aditional avalanche files (see 1) if specified, and expand domain as needed.


Can have combination of (1), (2), (3) above.  Set domain to superset of ALL.

