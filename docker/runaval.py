import sys,re,subprocess,os

HOME = '/tmp/home'
RAMMS_DIR = '/ramms'    # Volume mount
base = os.environ['avalanche']

av2_file = os.path.join(RAMMS_DIR, f'{base}.av2')
av3_file = os.path.join(HOME, f'{base}.av3')
#av3_file = os.path.join(RAMMS_DIR, f'{base}.av3')
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

# Launch RAMMS exe to run one avalanche
if False:
    os.chdir('/ramms')
    cmd = ['wine', '/opt/ramms/bin/ramms_aval_LHM_orig.exe', av3_file, f'{log_base}.out']
    print(' '.join(cmd))
    subprocess.run(cmd, check=True, env=env)
else:
    # Write dummy output for testing
    with open(f'{log_base}.out', 'w') as out:
        out.write('Sample output\n')

# gzip the output to temporary file
cmd = ['gzip', '-c', f'{log_base}.out']
with open(f'{log_base}.out.gz.tmp', 'wb') as out:
    subprocess.run(cmd, check=True, env=env, stdout=out)

# Atomically write the final output file
os.rename(f'{log_base}.out.gz.tmp', f'{log_base}.out.gz')

# Remove the uncompressed file
try:
    os.remove(f'{log_base}.out')
except OSError:
    pass
