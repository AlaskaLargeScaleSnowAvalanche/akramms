import os,collections,re,itertools,functools
import netCDF4
import pandas as pd
from uafgi.util import shputil
from akramms import archive,avalparse,avalfilter,parse,resolve,file_info
from akramms.util import exputil

# =======================================================================
# ====== Extent Processing

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
    """Intersects to extents.
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
def nc_extent(nc_fname):
    """Determines the extent of an archived NetCDF file"""
    with netCDF4.Dataset(nc_fname) as nc:
        bbox = nc.variables['bounding_box'][:].reshape(-1)    # [x0,y0,x1,y1]
    return bbox
# -----------------------------------------------------------------
def add_margin(extent, margin):
    """Adds margin to an extent
    extent: [x1,y1,x2,y2]
    margin: (x-margin, y-margin)
        Amount of margin to add
    """
    return [extent[0]-margin[0], extent[1]-margin[1], extent[2]+margin[0], extent[3]+margin[1]]
# -----------------------------------------------------------------
@functools.lru_cache()
def tile_extents(exp_mod):
    """Loads the extents of the sub-domains defined for an experiment.
    (RAMMS is run separately on each subdomain)
    Yields: (idom, jdom, (x0y0,x1,y1))"""

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
def tile_extent(expmod, idom, jdom):
    """Returns extent of the (idom,jdom) experiment tile."""

    # Nothing user-provided, use extent of subdomain
    extent = expmod.gridD.sub(
        idom, jdom,
        expmod.resolution, expmod.resolution,
        margin=False).extent(order='xyxy')
    return extent

# ---------------------------------------------------------------------
# Make sure that extents are in (xmin,ymin, xmax,ymax) format
def check_extent_sign(extent):
    x0,y0,x1,y1 = extent
    assert x1>=x0
    assert y1>=y0
# =====================================================================
def filter_combos_by_extent(expmod, akdf, extent):
    """
    expmod:
        Overall experiment
    akdf:
        Resolved to combo level
        All combos in expmod
    extent: (x0,y0,x1,y1)
    """

    # --- A numeric extent is provided: filter (idom,jdom) based on it.
    # tiles is the set of (idom,jdom) we are happy to keep
    tiles_in_extent = {(idom,jdom)
        for idom,jdom,dom_ext in domain_extents(expmod)
        if extents_intersect(dom_ext, extent)}

    # Filter by tiles_in_extent (i.e. only keep combos on tiles that intersect extent)
    ijdom = akdf.combo.map(lambda x: (x[-2],x[-1]) )    # (idom,jdom)
    akdf = akdf[ijdom.isin(tiles_in_extent)]

    return akdf
# ---------------------------------------------------------------------
def extent_by_tiles(expmod, akdf):
    """Produces the extent that is the union of the tiles covered by
    combos in akdf

    akdf:
        At either combo or avalanche level"""

    # User wants extent to be same as a subdomain tile.
    # Get union of all the subdomain tiles
    ijdoms = {(x.idom, x.jdom) for x in akdf.combo}
    tile_extents = [
        expmod.gridD.sub(
            idom,jdom, expmod.resolution, expmod.resolution, margin=False) \
            .extent(order='xyxy')
        for idom,jdom in ijdoms]
    extent = union_extents(tile_extents)
    return extent

# ---------------------------------------------------------------------
def filter_avalanches_by_extent(expmod, adkf, extent):
    """
    expmod:
        Overall experiment
    akdf:
        Resolved to avalanche id level
        All avalnches in expmod
    extent: (x0,y0,x1,y1)
    """

    avlanche_extents = akdf['avalfile'].map(nc_extent)
    keep = avlanche_extents.map(lambda ext: extents_intersect(ext, extent))
    akdf = akdf[keep]
    return akdf
# ---------------------------------------------------------------------
def extent_by_avalanches(expmod, akdf):
    """Produces the extent that is the union of the avalanche extents in akdf
    akdf:
        """

    extents = akdf['avalfile'].map(nc_extent)
    extent = union_extents(extents.tolist())
    return extent

# ---------------------------------------------------------------------
def query(akdf0, sextent, include_overruns=False, scenetypes={'x', 'arc'},
    statuses=[file_info.JobStatus.OVERRUN, file_info.JobStatus.FINISHED], margin=None):

    """akdf:
        Resolved to the combo level (or should work at id level too)
        (If it contains specific IDs, that will be in the `parsed`
        column, and will come out later in this function as we resolve
        to ID level)
    extent: One of...
        (x0,y0,x1,y1)
            or
        experiment-specific extent label
            or
        'tile': Use the extent of an (idom,jdom) subdomain tile
            or
        'avlanche': Use avlanches to determine overall extent
    include_overruns:
        Should overrun avalanches be included when resolving avalanches

    Returns: extent, akdf
        extent: (x0,y0,x1,y1)
            Extent resulting from the query
        akdf:
            Exact set of avalanches resulting from the query
            Contains column: 'id'

    """

    ret_dfs = list()
    ret_extents = list()
    for exp,akdf1 in akdf0.groupby('exp'):

        # Make sure they all use the same experiment
        # (Because extents are queried from the experiment definition file)
        expmod = parse.load_expmod(exp)
        extent = parse.parse_extent(expmod, sextent)    # (x0,y0,x1,y1)

        extent_is_numeric = (not isinstance(extent, str))

        if extent_is_numeric:
            # --- A numeric extent is provided: filter (idom,jdom) based on it.
            # tiles is the set of (idom,jdom) we are happy to keep
            akdf1 = filter_combos_by_extent(expmod, akdf1, extent)
            need_aval_filter = True
        elif extent == 'tile':
            # User wants extent to be same as a subdomain tile.
            # Get union of all the subdomain tiles
            extent = extent_by_tiles(expmod, akdf1)

            # No need to further filter avalanches, the selected
            # avalanches will fit in the extent.
            need_aval_filter = False

        # --------- Move to the avalanche (id) level
        # Resolve to individual avalanches
        akdf1 = resolve.resolve_chunk(akdf1, scenetypes=scenetypes)
        akdf1 = resolve.resolve_id(akdf1, realized=True, status_col=True)
        akdf1 = akdf1[akdf1.id_status.isin(statuses)]

        # Resovle the extent to numeric
        if extent == 'tile':
            extent = extent_by_tiles(expmod, akdf1)
            need_aval_filter = False

        elif extent == 'aval':
            # extent='aval' means the avalanches define the extent.
            # So no need to ever filter out avalanches.
            need_aval_filter = False
            extent = extent_by_avalanches(expmod, akdf1)


        # Finally, filter avalanches to the extent, if needed
        if need_aval_filter:
            akdf1 = filter_avalanches_by_extent(expmod, akdf1, extent)

        ret_dfs.append(akdf1)
        ret_extents.append(extent)


    # ----------------------
    # Make final extent and avalanche list, across experiments even!
    # (IF that makes sense, i.e. the two experiements are in the same projection)

    # Deal with margin
    extent = union_extents(ret_extents)
    if margin is not None:
        extent = add_margin(extent, (margin,margin) )

    return extent, pd.concat(ret_dfs)

# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
