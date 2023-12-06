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
    ncout.createDimension(vname, len(poly)//2)
    ncv = ncout.createVariable(vname, 'd', (vname, 'two'), compression='zlib')
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
    Returns: ivec,jvec
        Coordinates of gridcells in the local subdomain grid
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

    return ivec,jvec

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
    """
    Returns: {name: val}
        Value of variables read
        (max_vel, max_height, depo)
    """
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
    ret = dict()
    for (name, val,_),ncv in zip(namevals, ncvs):
        ncv[:] = val
        ret[name] = val

    return ret


# ----------------------------------------------------------
def ramms_to_nc0(out_zip, ncout):
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
    base = out_zip[:-8]    # Remove .out.zip
    leaf = os.path.split(base)[1]
    with zipfile.ZipFile(f'{base}.in.zip', 'r') as in_zip:
      with zipfile.ZipFile(f'{base}.out.zip', 'r') as out_zip:

        in_infos = in_zip.infolist()
        out_infos = out_zip.infolist()

        # See if this avalanche overran its domain
        arcnames = [os.path.split(x)[1] for x in out_zip.namelist()]
        overrun = any(x.endswith('.out.overrun') for x in arcnames)

        if 'status' not in ncout.variables:
            ncv = ncout.createVariable('status', 'i')
        ncout.variables['status'].overrun = 'True' if overrun else 'False'

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
        ivec,jvec = nc_xy_coord(ncout, gridI, coord_attrs, in_zip, f'{leaf}.xy-coord')

        # The .out file
        vars = nc_out(ncout, out_zip, f'{leaf}.out',
            attrs={'grid_mapping': 'grid_mapping'})
            
        max_height = vars['max_height']

        # -----------------------------------
        # Determine bounding box
        nz = (max_height != 0)
        ivec_nz = ivec[nz]
        jvec_nz = jvec[nz]

        i0 = np.min(ivec_nz)
        i1 = np.max(ivec_nz)
        j0 = np.min(jvec_nz)
        j1 = np.max(jvec_nz)

        x0,y0 = gridI.to_xy(i0,j0)
        x1,y1 = gridI.to_xy(i1,j1)

        # Store the bounding box
        ncout.createDimension('lowhigh', 2)
        ncv = ncout.createVariable('bounding_box', 'd', ('lowhigh', 'two'))
        ncv.description = 'Oriented bounding box of region occupied by avalanche.'
        ncv.grid_mapping = 'grid_mapping'
#        for attr,val in coord_attrs.items():
#            setattr(ncv, attr, val)
        ncv[:] = np.array([
            [min(x0,x1), min(y0,y1)],
            [max(x0,x1) + gridI.dx*np.sign(gridI.dx), max(y0,y1) + gridI.dy*np.sign(gridI.dy) ]])
        


# ----------------------------------------------------------
# ----------------------------------------------------------
#def main():
#    out_zip = '/home/efischer/prj/ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/x-113-0450000230MFor_10m/RESULTS/x-113-04500002For_10m/30M/x-113-04500002For_10m_30M_3200.out.zip'
#    with netCDF4.Dataset('x.nc', 'w') as ncout:
#        ncv = ncout.createVariable('status', 'i')
#        ramms_to_nc0(out_zip, ncout)

#main()


#TODO: Add T/S/M/L categorization to netCDF file
#Add authorship metadata to netCDF file
