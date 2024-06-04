import sys,re,subprocess,os,gzip,shutil,zipfile,traceback,pathlib,datetime,struct
#from akramms import config
import glob,pathlib,sys

"""Identifies .out.zip files with inconsistent array lengths"""


# --------------------------------------------------------------
def parse_xy_coord_raw(fin):
    """Read the .xy-coord file.  Just return LENGTHS of the arrays"""

    # https://docs.python.org/3/library/struct.html
    # < = little-endian
    # L = unsigned long

    # Read the .xy-coord file
    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]
#    print('parse_xy_coords() ncells = ', ncells)


    # xvec: double64[ncells]
    vars = list()
    buf = fin.read(ncells * 8)
#    xvec = np.frombuffer(buf, dtype='<f8')
    vars.append(('xvec', len(buf) // 8))

    buf = fin.read(ncells * 8)
#    yvec = np.frombuffer(buf, dtype='<f8')
    vars.append(('yvec', len(buf) //8))

    return vars
#    return xvec, yvec

def parse_out(fin, zipname=None, check=True):
    """Read the .out file"""

    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]
#    print('parse_out() ncells = ', ncells)

    vars = list()
    buf = fin.read(ncells * 4)
#    max_vel = np.frombuffer(buf, dtype='<f4')
    vars.append(('max_vel', len(buf) // 4))

    buf = fin.read(ncells * 4)
#    max_height = np.frombuffer(buf, dtype='<f4')
    vars.append(('max_height', len(buf) // 4))

    buf = fin.read(ncells * 4)
#    depo = np.frombuffer(buf, dtype='<f4')
    vars.append(('depo', len(buf) // 4))

    return vars

# --------------------------------------------------------------
def names_by_ext(izip):
    names = izip.namelist()
    exts = (name.split('.',1)[1] for name in names)
    return dict(zip(exts,names))


def test_file(ozname):
    """Determines whether an .out.zip file has consistent array lengths"""

    izname = ozname.parents[0] / (ozname.parts[-1][:-8] + '.in.zip')

    with zipfile.ZipFile(izname, 'r') as in_zip:
        in_names = names_by_ext(in_zip)
        with in_zip.open(in_names['xy-coord'], 'r') as fin:
            vars = parse_xy_coord_raw(fin)

    with zipfile.ZipFile(ozname, 'r') as out_zip:
        out_names = names_by_ext(out_zip)
        with out_zip.open(out_names['out'], 'r') as fin:
            vars += parse_out(fin)

    # All arrays are the same length, this is good!
    return all(vars[0][1] == var[1] for var in vars[1:])

def fix_dir(dir):
    for sozname in glob.iglob(str(dir / '**/*.out.zip'), recursive=True):
        if 'todel' in sozname:
            continue

        ozname = pathlib.Path(sozname)
        if not test_file(ozname):
            print(ozname)
            sys.stdout.flush()

def main():
    fix_dir(pathlib.Path(sys.argv[1]).resolve())

main()
