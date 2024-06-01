#!/usr/bin/env python3
#

import sys,re,subprocess,os,gzip,shutil,zipfile,traceback,pathlib,datetime,struct
#from akramms import config,archive



# --------------------------------------------------------------
def parse_xy_coord_raw(fin):
    """Read the .xy-coord file"""

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
    buf = fin.read(ncells * 8)
    xvec = np.frombuffer(buf, dtype='<f8')
    buf = fin.read(ncells * 8)
    yvec = np.frombuffer(buf, dtype='<f8')

    return xvec, yvec

def parse_out(fin, zipname=None, check=True):
    """Read the .out file"""

    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]
#    print('parse_out() ncells = ', ncells)

    buf = fin.read(ncells * 4)
    max_vel = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    max_height = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    depo = np.frombuffer(buf, dtype='<f4')

    # Check that all lengths match!
    if check:
        vecs = [max_vel, max_height, depo]
        if not all((vecs[0].shape == vec.shape for vec in vecs[1:])):
            raise ValueError(f'ERROR reading .OUT IN {zipname}: lengths are {[vec.shape for vec in vecs]}')

    return (
        ('max_vel', max_vel, {'units': 'm s-1'}),
        ('max_height', max_height, {'units': 'm'}),
        ('depo', depo,  {'units': 'm'}))

# --------------------------------------------------------------


base = sys.argv[1]
RAMMS_DIR = os.getcwd()    # HTCondor sets this
HOME = '/tmp/home'

av3_file = os.path.join(RAMMS_DIR, f'{base}.av3')
log_base = os.path.join(RAMMS_DIR, base)
#out_file = f'{log_base}.out'

# ----------------------------------------
with open('/opt/build_version.txt') as fin:
    build_version = fin.read().strip()

print(f'Starting runaval.py (Docker Container Build: {build_version}')
files_for_zip = set()

# --------------------------------------------
# Unzip the files
in_zip = os.path.join(RAMMS_DIR, f'{base}.in.zip')

domRE = re.compile(r'(.*)\.v(\d+)\.dom')
with zipfile.ZipFile(in_zip, 'r') as izip:

    # Unzip everything
    v1_dom = f'{base}.v1.dom'
    for info in izip.infolist():
        # JUST UNZIP IT
        bytes = izip.read(info)

        # Rename .v1.dom to .dom (backwards compatibility)
        fname = f'{base}.dom' if info.filename == v1_dom else info.filename

        with open(os.path.join(AVAL_DIR, fname), 'wb') as out:
            print(f'Unzipping {info.filename} ({datetime.datetime(*info.date_time):%Y-%m-%d %H:%m})')
            out.write(bytes)    # read()returns bytes

#        # DEBUG: Try providing everything in .gz format too!
#        with gzip.open(os.path.join(AVAL_DIR, info.filename+'.gz'), 'wb') as out:
#            out.write(bytes)

# ----------------------
# Debug: Print out files in current directory (on HTCondor)
print('Local Files:')
files = sorted(os.listdir('.'))
print('\n'.join(files))

# ----------------------
# Launch RAMMS exe to run one avalanche

out_zip_fname = f'{log_base}.out.zip'    # Assume it did not overrun base and we have a successful run
out_tmp_zip_fname = f'{log_base}.out_tmp.zip'    # Assume it did not overrun base and we have a successful run
files_for_zip.add(f'{log_base}.out')
files_for_zip.add(f'{log_base}.out.log')

try:

    if True:
        cmd = [/opt/ramms/ramms_aval_LHM, av3_file, f'{log_base}.out']
        print(' '.join(str(x) for x in cmd))
        subprocess.run(cmd, check=True)
    else:
        # Write dummy output for testing
        print('**** Writing dummy outputs for testing of runaval.py ****')
        with open(f'{log_base}.out', 'w') as out:
            out.write('Sample output\n')
        with open(f'{log_base}.out.log', 'w') as out:
            out.write('Sample log file\n')
            out.write(' FINAL OUTFLOW VOLUME: 17\n')


    # Check that input and output array lengths match
    fname = f'{log_base}.xy-coord'
    with open(fname, 'rb') as fin:
        xvec, yvec = archive.parse_xy_coord_raw(fin)
        vecs = [('xvec', fname, xvec), ('yvec', fname, yvec)]

    fname = f'{log_base}.out'
    with open(fname, 'rb') as fin:
        for name, val, attrs in archive.parse_out(fin):
            vecs.append((name, fname, val))

    if not all(vecs[0][2].shape == vec[2].shape for vec in vecs[1:]):
        raise ValueError('Inconsistent shape of input / output: {vecs}')


    # We were successful... add outputs to our zip

    # See if avalanche overran its domain
    if os.path.isfile(f'{log_base}.out.overrun'):
        files_for_zip.add(f'{log_base}.out.overrun')

#    with open(f'{log_base}.out.log') as fin:
#        for line in fin:
#            if line.startswith(' FINAL OUTFLOW VOLUME:'):
#                with open(f'{log_base}.out.overrun', 'w') as out:
#                    out.write('Avalanche overran its domain\n')
#                files_for_zip.add(f'{log_base}.out.overrun')
#
#
# Do not catch exceptions... they will propagate to the .job.err file!
#except Exception as e:
#    # Something went wrong... dump it to the log file
#    with open(f'{log_base}.out.log', 'a') as out:
#        out.write('\n')
#        out.write(str(e))
#        out.write(traceback.format_exc())
#
#    files_for_zip.add(f'{log_base}.out.log')

finally:
    # Whatever happened, make sure we collect the files written by the .exe
    with zipfile.ZipFile(out_tmp_zip_fname, 'w', zipfile.ZIP_DEFLATED) as out_zip:
        for file in sorted(list(files_for_zip)):
            if os.path.exists(file):
                out_zip.write(file, arcname=os.path.split(file)[1])

    # ...and write it atomically
    os.rename(out_tmp_zip_fname, out_zip_fname)


