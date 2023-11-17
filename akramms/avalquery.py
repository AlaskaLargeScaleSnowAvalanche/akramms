import os,collections,re,itertools,functools
import netCDF4
from uafgi.util import shputil
from akramms import archive,avalparse,avalfilter
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
def domain_extents(exp_mod):
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
# ---------------------------------------------------------------------
def query(akdf, extent):
    """
    akdf:
        Resolved to the combo level
    extent: One of...
        (x0,y0,x1,y1)
            or
        'tile': Use the extent of an (idom,jdom) subdomain tile
            or
        'dynamic': Use extent determined by the avalanches

    """
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
