import os,collections,re,itertools,functools
import netCDF4
from uafgi.util import shputil
from akramms import archive,avalparse,avalfilter
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
        return [ avalparse.AvalSpec(aspec0.exp_mod.name, aspec0.combo, aspec0.ids, [extent]) ]


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
                aspec1s.append(avalparse.AvalSpec(aspec0.exp_mod.name, combo, [], [extent]))

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
def query(aspecs, nc_fnames0, margin=(0.,0.), filter_in_fn=avalfilter.all):
    """Produces lists of NetCDF filenames.  Also converts to NetCDF at
    this point if needed.

    aspecs: [AvalSpec, ...]
        Normalized AvalSpecs
    filter_in_fn:
        Used to determine which avalanches not explicitly specified to include.
        If NO such avalanches are to be included, use filter_in_fn=avalfilter.none()
    returns: [nc_fname, ...], extent
        [nc_fname, ...]

            Filenames of archive files to include in the mosaic.
            Filenames are included for three reasons:
              1. Valid NetCDF files provided in nc_fnames0
              2. IDs explicitly included in query spec(s) aspecs
              3. Any other avalanches that match filter_in_fn
        extent
            Final mosaic extent
    """

    # Sanity check
    for aspec in aspecs:
        assert len(aspec.extents) == 1
        check_extent_sign(aspec.extents[0])

    # Initial extent based on bounding boxes of provided netCDF files...
    extent = union_extents(itertools.chain(
        (nc_extent(nc_fname) for nc_fname in nc_fnames0),
        (aspec.extents[0] for aspec in aspecs)))
    extent = add_margin(extent, margin)    # Give ourselves margin!

    # Convert to set of archive filenames
    nc_fnames = list(nc_fnames0)    # Start with filenames explicitly provided
    for aspec in aspecs:
        release_files,release_df = exputil.release_df(aspec.exp_mod, aspec.combo)

        # Determine overall list of IDs to search (before filtering)
        # Each of these IDs will be converted to NetCDF.  If only
        # listed IDs are to be included, we can skip searching all IDs
        # in the RELEASE file.
        if filter_in_fn is avalfilter.none:
            all_ids = [id for id in aspec.ids if id in release_df.index]
        else:
            all_ids = release_df.index.to_list()
        all_ids.sort()
        print('len(all_ids) = ', len(all_ids))

        # Obtain initial list of NetCDF files to filter through
        all_avals,archived_out_zips = archive.fetch(
            aspec.exp_mod, aspec.combo, all_ids)

        # Apply filter to result of archive.fetch()
        aspec_ids = set(aspec.ids)    # IDs we know we want to keep
        for id,nc_fname in all_avals:
#            print(id, nc_fname)

            # Was not able to generate a NetCDF file for this ID
            if nc_fname is None:
                continue

            # No NetCDF file for that ID was found (or able to be generated)
            if nc_fname is None:
                continue

            row = release_df.loc[id]

            # Include things in the ids list, or that the filter function allows.
            if (id in aspec_ids) or filter_in_fn(id, row, nc_fname):
#                print('   -> passed filter')

                # Include for real if this intersects.
                if extents_intersect(nc_extent(nc_fname), extent):
                    nc_fnames.append(nc_fname)

    return nc_fnames, extent
# ---------------------------------------------------------------
