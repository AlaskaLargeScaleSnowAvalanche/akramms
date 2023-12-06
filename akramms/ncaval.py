import os,re,itertools,struct,pickle,zipfile,io
import numpy as np
import netCDF4
import pyproj
from uafgi.util import gdalutil

# Convert Avalanche outputs to NetCDF


# ------------------------------------------------------------------
# NOTE: Similar to rammsutil.read_polygon_from_zip()
_all_spaceRE = re.compile(r'$\s*^')
def _read_polygon(izip, poly_file):

#    with open(poly_file) as fin:
    with io.TextIOWrapper(izip.open(poly_file, 'r'), encoding='utf-8') as fin:
        line = next(fin).split(' ')
        # Get repeated coordinate at the end
        #print('line ', line)
        return np.array([float(x) for x in line[1:] if not _all_spaceRE.match(x)])
        ###### Get just the x,y coordinates, no count at beginning, no repeat at end
        ###### coords = [float(x) for x in line[1:-2]]

    return shapely.geometry.Polygon(list(zip(coords[::2], coords[1::2])))
# ------------------------------------------------------------------
def nc_poly(ncout, izip, arcname, vname, coord_attrs, attrs={}, required=True):
    """
    izip: zip.ZipFile
        Open zip file to read from
    arcname:
        Name of file to read out of izip
    """

    try:
        info = izip.getinfo(arcname)
    except KeyError:
        info = None


    if (not required) and (info is None):
        return None

    poly = _read_polygon(izip, arcname)
    ncout.createDimension(f'{vname}_len', len(poly)//2)
    ncv = ncout.createVariable(vname, 'd', (f'{vname}_len', 'two'), compression='zlib')
    for attr,val in attrs.items():
        setattr(ncv, attr, val)

    for vname in coord_attrs['X'].keys():
        attrval = (coord_attrs['X'][vname], coord_attrs['Y'][vname])
        setattr(ncv, vname, attrval)

    ncv[:] = poly.reshape((len(poly)//2, 2))
    return ncv
# ------------------------------------------------------------------
def difference_encode(ivec):
    """Encode a 1D Numpy vector by computing for compression by computing successive differences.
       Eg: [1, 5, 2] -> [1, 4, -3]
    """
    ret = np.full_like(ivec, ivec[0])
    ret[1:] = ivec[1:] - ivec[:-1]
    return ret

difference_decode = np.cumsum
# ------------------------------------------------------------------
# These are both binary files. The formats are the following:
#  
# File: *.out
#  
# nCells                                   Long
# MaxVelocityValues         fltarr(nCells)
# MaxHeightValues           fltarr(nCells)
# DepoValues                       fltarr(nCells)
#  
#  
# File: *.xy-coord
#  
# nCells                                   Long
# x_vector                              dblarr( NrCells )
# y_vector                              dblarr( NrCells )
#  
#  
# the File *.xy-coord contains the cell-center coordinate points of the result arrays. With this information, you should be able to mosaic the results, and then you have to output them as GeoTiff’s……
#  
# In case this information helps you enough to continue for the moment, we can also postpone the meeting, until you run into problems 😊, and we can discuss it then?
#  
# All the best
#  
# Marc

def parse_xy_coord(gridI, fin):
    """Read the .xy-coord file"""

    # https://docs.python.org/3/library/struct.html
    # < = little-endian
    # L = unsigned long

    # Read the .xy-coord file
    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]

    # xvec: double64[ncells]
    buf = fin.read(ncells * 8)
    xvec = np.frombuffer(buf, dtype='<f8')
    buf = fin.read(ncells * 8)
    yvec = np.frombuffer(buf, dtype='<f8')

    # Convert (double precision) x/y coordinates to (int) i/j
    ivec, jvec = gridI.to_ij(xvec, yvec)
    return ivec, jvec


def nc_xy_coord(ncout, gridI, coord_attrs, izip, arcname):
    """
    izip, arcname:
        File .xy-coord file to read (from inside a zip)
    """

    # Read the original file
#    with open(fname,'rb') as fin:
    with izip.open(arcname, 'r') as fin:
        ivec, jvec = parse_xy_coord(gridI, fin)

    # Difference-encode i/j to increase compression
    divec = difference_encode(ivec)
    djvec = difference_encode(jvec)

    ncout.createDimension('ncells', len(divec))
    ncvi = ncout.createVariable('i_diff', 'i', ('ncells',), compression='zlib')
    ncvi.description = "Difference-compressed X index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to X in projected space"

    for k,v in coord_attrs['X'].items():
        setattr(ncvi, k, v)

    ncvj = ncout.createVariable('j_diff', 'i', ('ncells',), compression='zlib')
    ncvj.description = "Difference-compressed Y index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to Y in projected space"
    for k,v in coord_attrs['Y'].items():
        setattr(ncvj, k, v)

    ncvi[:] = divec
    ncvj[:] = djvec

# --------------------------------------------------------------

def parse_out(fin):
    """Read the .out file"""

    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]
#    print('ncells ', ncells)

    buf = fin.read(ncells * 4)
    max_vel = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    max_height = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    depo = np.frombuffer(buf, dtype='<f4')


    return (
        ('max_vel', max_vel, {'units': 'm s-1'}),
        ('max_height', max_height, {'units': 'm'}),
        ('depo', depo,  {'units': 'm'}))

def nc_out(ncout, izip, arcname, attrs={}):
    # Read the values from the .out file
#    with open(fname, 'rb') as fin:
    with izip.open(arcname, 'r') as fin:
        namevals = parse_out(fin)

    # Create and populate the variables
    ncvs = list()
    for vname, val, vattrs in namevals:
        ncv = ncout.createVariable(vname, 'd', ('ncells',), compression='zlib')
        for k,v in attrs.items():
            setattr(ncv, k, v)
        for k,v in vattrs.items():
            setattr(ncv, k, v)
        ncvs.append(ncv)
    for (_, val,_),ncv in zip(namevals, ncvs):
        ncv[:] = val


# ----------------------------------------------------------
def ramms_to_nc0(base, ofname):
    """
    base:
        Base name of avalanche, including full pathname.
        Eg: ../mypath/juneauA00000For_5m_30L_4981

        The following files are expected to be present:

        $ ls -ltrah
        total 123720
        -rw-rw-r-- 2.4K Jul 10 14:15 juneauA00000For_5m_30L_4981.relp
        -rw-rw-r-- 186B Jul 10 14:15 juneauA00000For_5m_30L_4981.domp
        -rw-rw---- 104B Jul 11 03:12 juneauA00000For_5m_30L_4981.v1.dom
        -rw-rw---- 1.3K Jul 11 03:12 juneauA00000For_5m_30L_4981.rel
        -rw-rw----  15M Jul 11 03:12 juneauA00000For_5m_30L_4981.xyz
        -rw-rw----  14M Jul 11 03:13 juneauA00000For_5m_30L_4981.xy-coord
        -rw-rw----  14M Jul 11 03:13 juneauA00000For_5m_30L_4981.var
        -rw------- 1.1K Jul 11 03:13 juneauA00000For_5m_30L_4981.av3
        -rw-r--r--  10K Jul 12 03:55 juneauA00000For_5m_30L_4981.out.log
        -rw-r--r--  11M Jul 12 03:55 juneauA00000For_5m_30L_4981.out


    """
    leaf = os.path.split(base)[1]
    with zipfile.ZipFile(f'{base}.in.zip', 'r') as in_zip:
     with zipfile.ZipFile(f'{base}.out.zip', 'r') as out_zip:
      with netCDF4.Dataset(ofname, 'w') as ncout:

        in_infos = in_zip.infolist()
        out_infos = out_zip.infolist()

        # Get the grid
        gridI = pickle.loads(in_zip.read('grid.pik'))

        # http://cfconventions.org/cf-conventions/cf-conventions.html#coordinate-system
        # Write the CRS
        # (TODO: Move this to uafgi/gisutil.py)
        # https://pyproj4.github.io/pyproj/latest/build_crs_cf.html
        crs = pyproj.CRS(gridI.wkt)
        cf_grid_mapping = crs.to_cf()
        ncv = ncout.createVariable('grid_mapping', 'i')
        for k,v in cf_grid_mapping.items():
            setattr(ncv, k, v)
        ncv.crs_wkt = gridI.wkt
        ncv.GeoTransform = ' '.join(str(x) for x in gridI.geotransform)

        cf_coordinate_system = crs.cs_to_cf()
        coord_attrs = {x['axis']: x for x in cf_coordinate_system}
        #print(cf_coordinate_system)


        # The .relp and .domp files
        ncout.createDimension('two', 2)
        nc_poly(ncout, in_zip, f'{leaf}.relp', 'relp', coord_attrs,
            {'description': 'UNOFFICIAL release area polygon written by AKRAMMS Python code.',
            'grid_mapping': 'grid_mapping'},
            required=False)
        nc_poly(ncout, in_zip, f'{leaf}.domp', 'domp', coord_attrs,
            {'description': 'UNOFFICIAL domain polygon written by AKRAMMS Python code.',
            'grid_mapping': 'grid_mapping'},
            required=False)

        # The .rel file
        nc_poly(ncout, in_zip, f'{leaf}.rel', 'rel', coord_attrs,
            {'description': 'OFFICIAL release area polygon written by RAMMS IDL code.',
            'grid_mapping': 'grid_mapping'},
            required=False)

        # The .v?.dom files
        vdoms = list()
        for i in itertools.count(1):
            ifname = f'{base}.v{i}.dom'
            ret = nc_poly(ncout, in_zip, f'{leaf}.v{i}.dom', f'dom_v{i}', coord_attrs,
                {'description': f'OFFICIAL release area polygon written by RAMMS IDL code (enlargement try #{i}).'},
                required=False)
            if ret is None:
                break

        # The .xyz file (SKIP)

        # The .xy-coord file
        nc_xy_coord(ncout, gridI, coord_attrs, in_zip, f'{leaf}.xy-coord')

        # The .out file
        nc_out(ncout, out_zip, f'{leaf}.out',
            attrs={'grid_mapping': 'grid_mapping'})

# ----------------------------------------------------------
# ----------------------------------------------------------
#def main():
#    base = '/Users/eafischer2/tmp/aval/juneauA00000For_5m_30L_4981'
#    dem_file = '/Users/eafischer2/tmp/maps/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338_filled.tif'
#    gridI = gdalutil.read_grid(dem_file)
#    ramms_to_nc(gridI, base, 'x.nc')
#main()


#TODO: Add T/S/M/L categorization to netCDF file
#Add authorship metadata to netCDF file
