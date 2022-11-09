import sys,re,subprocess,os

# Parse filenames
av2_file = sys.argv[1]
dir,av2_leaf = os.path.split(av2_file)
dir = os.path.abspath(dir)
base = os.path.splitext(av2_leaf)[0]


input_files = ' '.join(['{}.{}'.format(base, x) for x in
    ['dom', 'rel', 'xyz', 'av2', 'xy-coord', 'var']])

output_files = ' '.join(['{}.{}'.format(base, x) for x in
    ['out.log', 'out.gz']])


submit_txt = \
f"""universe                = docker
docker_image            = localhost:5000/ramms
executable              = /usr/bin/python
arguments               = /opt/runaval.py {base}

initialdir              = {dir}
#transfer_input_files    = {input_files}
transfer_input_files    = {base}.av2,{base}.dom,{base}.rel,{base}.xyz.gz,{base}.xy-coord.gz,{base}.var.gz
transfer_output_files   = {base}.out.log,{base}.out.gz
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
on_exit_hold            = False
on_exit_remove          = True

output                  = {base}.job.out
error                   = {base}.job.err
log                     = {base}.job.log
request_cpus            = 1
request_memory          = 1000M
queue 1
"""



with open('x.txt', 'w') as out:
    out.write(submit_txt)
    out.write('\n')



## Similar to how HTCondor sets up to run
#cmd = ['docker', 'run',
#    '-v', f'{dir}:/ramms',
#    '-w', '/ramms',
#    '-e', f'avalanche={base_leaf}',
#    '-u', f'{os.getuid()}:{os.getgid()}',    # Write mounted files as 
#    'ramms']
#print(' '.join(cmd))
proc = subprocess.Popen(['condor_submit', '-batch-name', base], cwd=dir, stdin=subprocess.PIPE)
proc.communicate(input=submit_txt.encode('utf-8'))
proc.wait()
print('Return code: {}'.format(proc.returncode))
