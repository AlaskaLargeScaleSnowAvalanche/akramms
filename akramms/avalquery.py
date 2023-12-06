import os,collections,re,itertools,functools
import netCDF4
from uafgi.util import shputil
from akramms import archive,avalparse
from akramms.util import exputil

# -----------------------------------------------------------------
def union_extents(extents):
    """Finds an extent enclosing all the given extents
    extents: [(x0,y0, x1,y1), ...]
    """
    iext = iter(extents)

    z0 = next(iext)
    assert z0[2] >= z0[0]    # Check for correct sign
    assert z0[3] >= z0[1]
    for z1 in iext:
        assert z1[2] >= z1[0]
        assert z1[3] >= z1[1]
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
    with netCDF4.Dataset(nc_fname) as nc:
        bbox = nc.variables['bounding_box'][:].reshape(-1)    # [x0,y0,x1,y1]
    return bbox
# -----------------------------------------------------------------
def add_margin(bbox, margin):
    return [bbox[0]-margin[0], bbox[1]-margin[1], bbox[2]+margin[0], bbox[3]+margin[1]]
# -----------------------------------------------------------------
@functools.lru_cache()
def domain_extents(exp_mod):
    # Load set of extents
    domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    df = shputil.read_df(domains_shp, read_shapes=True)
    for _,row in df.iterrows():
        xx,yy = row['shape'].exterior.coords.xy
#        yield row.idom,row.jdom,(xx[0],yy[0], xx[2],yy[2])    # Convert to an Extent-type list of (x0,y0,x1,y1)
        # TODO: This version is just until we rewrite the domains file
        yield row.ix,row.iy,(
            min(xx[0],xx[2]),
            min(yy[0],yy[2]),
            max(xx[0],xx[2]),
            max(yy[0],yy[2]))    # Convert to an Extent-type list of (x0,y0,x1,y1)


# -----------------------------------------------------------------
# ---------------------------------------------------------------------
# Make sure that extents are in (xmin,ymin, xmax,ymax) format
def check_extent_sign(extent):
    x0,y0,x1,y1 = extent
    assert x1>=x0
    assert y1>=y0

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
            extent = aspec0.exp_mod.gridD.sub(
                aspec0.combo.idom, aspec0.combo.jdom,
                aspec0.exp_mod.resolution, aspec0.exp_mod.resolution,
                margin=False).extent(order='xyxy')

        # Determine IDs (depends on whether user supplied)
        return [ avalparse.AvalSpec(aspec0.exp_mod, aspec0.combo, aspec0.ids, [extent]) ]


    # --- User specified a wildcard combo, select combos by extent
    else:
        # User should have specified at least one extent, but NO
        # individual IDs
        if len(aspec0.extents) == 0:
            raise ValueError('If an (idom,jdom) subdomain is not specified, the user must specify at least one extent in the query')

        #if len(aspec0.ids) > 0:
        #    raise ValueError('No specific avalanche IDs allowed without (idom,jdom) subdomain)
        ## assert len(aspec0.ids) == 0

        # Get extent
        extent = union_extents(aspec0.extents)    # Our query extent

        # Get list of combos intersecting that extent
        aspec1s = list()
        for idom,jdom,dom_ext in domain_extents(exp_mod):
            if extents_intersect(dom_ext, extent):
                lcombo = list(combo[:-2]) + [idom, jdom]
                combo = exp_mod.Combo(*lcombo)
                aspec1s.append(avalparse.AvalSpec(aspec0.exp_mod, combo, [], [extent]))

        return aspec1s

def normalize(aspec0s):
    """Normalizes a collection of AvalSpecs"""

    ret = list()
    for aspec0 in aspec0s:
        ret += _normalize_aval_spec(aspec0)
    return ret

# ==========================================================================
# "Query" means converting whatever was normalized to:
#     [nc_fname, ...]    Avalanche files to mosaic
#     extent             Area to mosaic
def query(aspecs, nc_fnames0, margin=(0.,0.), filter_in_fn=lambda *args: True, ok_statuses={archive.OK, archive.OVERRUN}):
    """Produces lists of NetCDF filenames.  Also converts to NetCDF at
    this point if needed.

    extent:
        User-provided extent to include.  (Or typically comes from nc_fnames)
        This will be unioned with individual aspecs extents.
    aspecs: [AvalSpec, ...]
        Normalized AvalSpecs
    returns: [nc_fname, ...], extent
        [nc_fname, ...]
            Filenames of archive files to include in the mosaic]
        extent
            Final mosaic extent
    """

    # Determine extent
    for aspec in aspecs:
        assert len(aspec.extents) == 1
        check_extent_sign(aspec.extents[0])

    extent = union_extents(itertools.chain(
        (nc_extent(nc_fname) for nc_fname in nc_fnames0),
        (aspec.extents[0] for aspec in aspecs)))
    extent = add_margin(extent, margin)    # Give ourselves margin!

    # Convert to set of archive filenames
    nc_fnames = list(nc_fnames0)    # Start with filenames explicitly provided
    for aspec in aspecs:
        aspec_ids = set(aspec.ids)    # IDs we know we want to keep
        release_fname,release_df = exputil.release_df(aspec.exp_mod, aspec.combo)
#        print('release_df len ', len(release_df))
#        print('x1 ', type(release_df))
#        print('x2 ', type(release_df.index))
        all_ids = release_df.index.to_list()
#        print('all_ids len ', len(all_ids))

        # Filter IN user-provided IDs, filter OUT avalanches outside the extent
        # Otherwise, apply user's filter
        all_nc_fnames,archived_out_zips = archive.fetch(
            aspec.exp_mod, aspec.combo, all_ids, ok_statuses)
#        print('all_nc_fnames1 ', all_nc_fnames)
#        nc_fnames = [x for x in nc_fnames if x is not None]    # Ignore avalanches not found

        # Apply filter to result of archive.fetch()
        #efilter_fn = wrap_filter(filter_fn, aspec.ids, extent)
        print('AA1 extent ', extent)
        for (id,row),nc_fname in zip(release_df.iterrows(), all_nc_fnames):
            # No NetCDF file for that ID was found (or able to be generated)
            if nc_fname is None:
                continue

            # Include things in the ids list, or that the filter function allows.
            if (id in aspec_ids) or filter_in_fn(id, row, nc_fname):

                # Get the bounding box for the avalanche
                if 'bounding_box' in row:
                    bbox = row['bounding_box']
                    print('AA3 bbox ', bbox)
                else:
                    bbox = nc_extent(nc_fname)
                    #print('AA4 bbox ', bbox)


                # Include for real if this intersects.
                if extents_intersect(bbox, extent):
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
