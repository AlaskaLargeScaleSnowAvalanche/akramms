import sys,re,subprocess,os,gzip,shutil,zipfile,traceback

base = sys.argv[1]
#base = os.environ['avalanche']


RAMMS_DIR = os.getcwd()    # HTCondor sets this
HOME = '/tmp/home'

av2_file = os.path.join(RAMMS_DIR, f'{base}.av2')
#av3_file = os.path.join(HOME, f'{base}.av3')   # For some reason this crashes inside the RAMMS C++
av3_file = os.path.join(RAMMS_DIR, f'{base}.av3')
log_base = os.path.join(RAMMS_DIR, base)
#out_file = f'{log_base}.out'

# ----------------------------------------
pathRE = re.compile(r'((Domain|Altitude)\s+[^\s]*\s+)([^\s]*)\s*')
def write_av3(av2_file, av3_file):
    # Rewrite .av2 file to avoid absolute paths (on a Windows machine)
    with open(av2_file) as fin:
        with open(av3_file, 'w') as out:
            for line in fin:
                # Transform
                match = pathRE.match(line)
                if match is None:
                    out.write(line)
                else:
                    fname = match.group(3)
                    leaf = fname.split('\\')[-1]
                    out.write(f'{match.group(1)}{leaf}\n')
# ----------------------------------------
print('Starting runaval.py')
files_for_zip = set()

# Set up environment
env = dict(os.environ)
env['HOME'] = HOME
os.makedirs(os.path.join(HOME, 'Desktop'), exist_ok=True)

# Set up wine
os.chdir(HOME)
cmd = ['tar', 'xfz', '/opt/dotwine.tar.gz']
subprocess.run(cmd, check=True, env=env)

# Write the .av3 file
write_av3(av2_file, av3_file)

# Gunzip files; leave original .gz in scratch dir
for ext in ('var', 'xy-coord', 'xyz'):
    ifname = os.path.join(RAMMS_DIR, f'{base}.{ext}.gz')
    ofname = os.path.join(RAMMS_DIR, f'{base}.{ext}')
    with gzip.open(ifname, 'rb') as fin:
        with open(ofname, 'wb') as out:
            shutil.copyfileobj(fin, out)

# ----------------------
# Launch RAMMS exe to run one avalanche
os.chdir(RAMMS_DIR)
if True:
    cmd = ['wine', '/opt/ramms/bin/ramms_aval_LHM_orig.exe', av3_file, f'{log_base}.out']
    print(' '.join(cmd))
    subprocess.run(cmd, check=True, env=env)
else:
    # Write dummy output for testing
    with open(f'{log_base}.out', 'w') as out:
        out.write('Sample output\n')
    with open(f'{log_base}.out.log', 'w') as out:
        out.write('Sample log file\n')
        out.write(' FINAL OUTFLOW VOLUME: 17')

# We were successful... add outputs to our zip
files_for_zip.add(f'{log_base}.out')
files_for_zip.add(f'{log_base}.out.log')
# ----------------------

# See if avalanche overran its domain
with open(f'{log_base}.out.log') as fin:
    for line in fin:
        if line.startswith(' FINAL OUTFLOW VOLUME:'):
            with open(f'{log_base}.out.overrun', 'w') as out:
                out.write('Avalanche overran its domain\n')
            files_for_zip.add(f'{log_base}.out.overrun')

#except Exception as e:
#    # Something went wrong... dump it to the log file
#    with open(f'{log_base}.out.log', 'a') as out:
#        out.write('\n')
#        out.write(str(e))
#        out.write(traceback.format_exc())
#
#    files_for_zip.add(f'{log_base}.out.log')

# Put all outputs in a single zip file
with zipfile.ZipFile(f'{log_base}.out.zip', 'w', zipfile.ZIP_DEFLATED) as out_zip:
    for file in sorted(list(files_for_zip)):
        arcname = os.path.split(log_base)[1]
        out_zip.write(file, arcname=arcname)    # arcname is simple file without path






## gzip the output to temporary file
#cmd = ['gzip', '-c', f'{log_base}.out']
#with open(f'{log_base}.out.gz.tmp', 'wb') as out:
#    subprocess.run(cmd, check=True, env=env, stdout=out)
#
## Atomically write the final output file
#os.rename(f'{log_base}.out.gz.tmp', f'{log_base}.out.gz')
#
## Remove the uncompressed file
#try:
#    os.remove(f'{log_base}.out')
#except OSError:
#    pass
