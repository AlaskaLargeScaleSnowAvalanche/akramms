import os,subprocess,re,sys,contextlib
import functools
import redis,rq
from akramms import config

HARNESS = config.HARNESS    # Alias

def bash_name(wfname):
    """Gets the bash name of a Windows filename.
    Eg: C:\\Users\\me\\x.txt ==> /C/Users/me/x.txt

    wfname:
        Windows filename
    """

    wfname = wfname.replace('\\', '/')
    if wfname[1] == ':':
        wfname = '/{}{}'.format(wfname[0], wfname[2:])
    return wfname

def local_linux_name(fname, remote_harness_b):
    """Convert remote Windows name to a loca lLinux name
    remote_harness_bash:
        bash_name(REMOTE_HARNESS)
    """
    fname_b = bash_name(fname)
    return os.path.join(HARNESS, os.path.relpath(fname_b, remote_harness_b))

def remote_windows_name(fname, REMOTE_HARNESS, bash=False):
    """Converts local Linux name to remote Windows name
    Assumes remote Windows host
    bash:
        Convert to bash-style pathname?"""

    ret = os.path.join(REMOTE_HARNESS, os.path.relpath(fname, HARNESS)).replace(os.path.sep, '\\')
    if bash:
        ret = bash_name(ret)
    print('remote_name: {} -> {}'.format(fname, ret))
    return ret


def rsync_files(fnames, tdir, flags=['--copy-links', '-avz'], direction='up'):
    """Syncs a list of files into the same location in the remote harness.

    fnames: [filename, ...]
        Relative filenames to transfer to the remote Windows machine.
    Returns:
        Bash-style pathname of files, relative to the harness root
    """

    remote_harness_b = bash_name(REMOTE_HARNESS)
    src_harness = HARNESS if direction=='up' else remote_harness_b

    # Get names of the files, relative to the harness
    fnames_rel = [os.path.relpath(x, src_harness) for x in fnames]
    print('rsyncing: {}'.format(fnames_rel))

    # Write the names to a file contain a list of filenames
    list_file = tdir.filename(prefix='rsyncs_')
#    list_file = 'files.txt'
    with open(list_file, 'w') as out:
        out.write('\n'.join(fnames_rel))
        out.write('\n')

    # Run rsync
    if direction == 'up':
        # Create output directory
        cmd = config.ssh_w + ['mkdir', '-p', remote_harness_b]
        subprocess.run(cmd)

        cmd = ['rsync'] + flags + ['--files-from={}'.format(list_file),
            HARNESS+'/',
            f'{remote_host}:{remote_harness_b}']
    else:
        cmd = ['rsync'] + flags + ['--files-from={}'.format(list_file),
            f'{remote_host}:{remote_harness_b}/',
            HARNESS,
            ]

    print(cmd)
    subprocess.run(cmd)

    # Return relative names
    return fnames_rel


def run_remote(inputs, cmd, tdir, write_inputs=False):
    """Runs a command on the remote Windows machine.
    inputs:
        Input files to copy to Windows before running.
    cmd: [str, ...]
        The command to run on the remote host
    write_inputs: bool
        If set, write the input file list to STDIN, one file at a time.
    Returns outputs:
        Output files on remote machine (Relative pathnames)
    """

    cmd = [str(x) for x in cmd]
    print('cmd ', cmd)

    # Sync RAMMS input files to remote dir
    if not config.shared_filesystem:
        rsync_files(inputs, tdir, direction='up')

    # Run RAMMS

    # Start the remote process
    cmd = config.ssh_w + cmd
    kw = dict()
    if write_inputs:
        kw['stdin'] = stdin=subprocess.PIPE
    print(' '.join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, **kw)

    # Write to processes stdin (relative path of input files)
    if write_inputs:
        inputs_txt = ''.join('INPUT: {}\r\n'.format(config.roots.relpath(input)) for input in inputs) + 'END INPUTS\r\n'
        for input in inputs:
            proc.stdin.write(inputs_txt.encode('UTF-8'))
        proc.stdin.flush()

    # Read outputs
    outputs_rel = list()
    outputRE = re.compile(r'OUTPUT:\s([^\s]*)\s*$')
    while True:
        line = proc.stdout.readline().decode('UTF-8')
        if not line:
            break
        print(line, end='')
        sys.stdout.flush()

        # Exit if remote program is exiting
        if line == 'END OUTPUTS':
            break

        # Collect list of output files as declared by Windows-side program
        match = outputRE.match(line)
        if match is not None:
            outputs_rel.append(match.group(1))

    try:
        proc.wait(timeout=10)    # The process should be exited anyway, wait for 10 seconds
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
    except subprocess.TimeoutExpired as e:
        # The IDL on the other side has not exited cleanly.  We should
        # continue on Linux side; and next time Windows stuff is run,
        # IDL will be killed before it begins.
        print('***** WARNING:')
        print(e)

    # outputs contains relative names of files.
    if not config.shared_filesystem:
        harnutil.rsync_files(outputs_b, tdir, direction='down')

    # Outputs as local filenames
    outputs = [config.roots.syspath(x) for x in outputs_rel]
    return outputs

class QueueRunner:
    def __init__(self, qname, **kwargs):
        self.redis = redis.Redis()
        self.queue = rq.Queue(qname, connection=self.redis, **kwargs)

    # Timeout includes time waiting in the queue; so it needs to be as long as the longest job we MIGHT run.
    def run(self, func, *args, timeout=3*3600, at_front=False, **kwargs):
        print('func = ', func)
#        kw = dict(kwargs)
#        kw['timeout'] = timeout
        job = rq.job.Job.create(func, connection=self.redis, timeout=timeout, args=args, kwargs=kwargs)
        #job = self.queue.enqueue(*args, **kwargs)
        self.queue.enqueue_job(job, at_front=at_front)
        try:
            result = rq.results.Result.fetch_latest(job, serializer=job.serializer, timeout=timeout)
            if result.type == result.Type.SUCCESSFUL: 
                ret = result.return_value
                print('Success ', ret)
                return ret
            else: 
                print('Failure ', result.exc_string)
                raise RuntimeError(result.exc_string)

        except:
            print('Canceling...')
            try:
                rq.command.send_stop_job_command(self.redis, job.id)
            except Exception as e:
                print('Exception stopping job ', e)
                # Job is not currently executing, No such job
                pass
            try:
                job.cancel()
            except Exception as e:
                print('Exception canceling job ', e)

            try:
                job.delete()
            except Exception as e:
                print('Exception deleting job ', e)

            raise

# One queue per licensed piece of software
_queues = {qname: (lambda: QueueRunner(qname)) for qname in ('arcgis', 'ecognition', 'idl')}

@functools.lru_cache()
def queue(qname):
    return _queues[qname]()

#def run_remote_queued(qname, *args, **kwargs):
#    return queues[qname].run(run_remote, *args, **kwargs)

def run_queued(qname, fn, *args, **kwargs):
    if config.queue[qname]:
        return queue(qname).run(fn, *args, **kwargs)
    return fn(*args, **kwargs)

def print_outputs(outputs):
    """Helper function"""
    sys.stdout.flush()
    print()
    print('BEGIN OUTPUTS')
    for output in outputs:
        print('OUTPUT: {}'.format(config.roots.relpath(output)))
    print('END OUTPUTS')
    sys.stdout.flush()
