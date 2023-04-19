import sys,re,subprocess,os,gzip,shutil,zipfile,traceback

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

# Set up environment
env = dict(os.environ)
env['HOME'] = HOME
os.makedirs(os.path.join(HOME, 'Desktop'), exist_ok=True)

# Set up wine
try:
    os.chdir(HOME)
    cmd = ['tar', 'xfz', '/opt/dotwine.tar.gz']
    print(' '.join(cmd))
    subprocess.run(cmd, check=True, env=env)
finally:
    os.chdir(RAMMS_DIR)    # Poor mans popd

# --------------------------------------------
# Unzip the files
in_zip = os.path.join(RAMMS_DIR, f'{base}.in.zip')

domRE = re.compile(r'(.*)\.v(\d+)\.dom')
with zipfile.ZipFile(in_zip, 'r') as izip:
    infos = izip.infolist()

    # Unzip everything but the .dom file
    max_itry = -1
    iofiles = list()
    for info in infos:
        match = domRE.match(info.filename)
        print('domRE: {} --> {}'.format(info.filename, match))
        if match is not None:
            # It's a .dom.vXXX file.; identify the one with largest number
            itry = int(match.group(2))
            if itry > max_itry:
                dom_file = match.group(1) + '.dom'
                dom_info = info
                max_itry = itry
        else:
            # It's not a .dom file, just unzip it.
            bytes = izip.read(info)
            with open(os.path.join(RAMMS_DIR, info.filename), 'wb') as out:
                print(f'Unzipping {info.filename} ({info.date_time})')
                out.write(bytes)    # read()returns bytes

            # DEBUG: Try providing everything in .gz format too!
            with gzip.open(os.path.join(RAMMS_DIR, info.filename+'.gz'), 'wb') as out:
                out.write(bytes)

    # Unzip the .dom file (of maximum version number)
    print(f'Unzipping {dom_info.filename} ({dom_info.date_time})')
    with open(os.path.join(RAMMS_DIR, dom_file), 'wb') as out:
        out.write(izip.read(dom_info))

# ----------------------
# Debug: Print out files in current directory (on HTCondor)
print('Local Files:')
files = sorted(os.listdir('.'))
print('\n'.join(files))

# ----------------------
# Launch RAMMS exe to run one avalanche

out_zip_fname = f'{log_base}.out.zip'    # Assume it did not overrun base and we have a successful run
files_for_zip.add(f'{log_base}.out')
files_for_zip.add(f'{log_base}.out.log')

try:

    if True:
        cmd = ['wine', '/opt/ramms/bin/ramms_aval_LHM.exe', av3_file, f'{log_base}.out']
        print(' '.join(cmd))
        subprocess.run(cmd, check=True, env=env)
    else:
        # Write dummy output for testing
        print('**** Writing dummy outputs for testing of runaval.py ****')
        with open(f'{log_base}.out', 'w') as out:
            out.write('Sample output\n')
        with open(f'{log_base}.out.log', 'w') as out:
            out.write('Sample log file\n')
            out.write(' FINAL OUTFLOW VOLUME: 17\n')

    # We were successful... add outputs to our zip

    # See if avalanche overran its domain
    with open(f'{log_base}.out.log') as fin:
        for line in fin:
            if line.startswith(' FINAL OUTFLOW VOLUME:'):
                with open(f'{log_base}.out.overrun', 'w') as out:
                    out.write('Avalanche overran its domain\n')
                files_for_zip.add(f'{log_base}.out.overrun')
                # Name our output zipfile to indicate we don't yet have a final answer.
#                out_zip_fname = f'{log_base}_out_v{max_itry}.zip'


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
    with zipfile.ZipFile(out_zip_fname, 'w', zipfile.ZIP_DEFLATED) as out_zip:
        for file in sorted(list(files_for_zip)):
            if os.path.exists(file):
                out_zip.write(file, arcname=os.path.split(file)[1])

