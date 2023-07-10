import os,subprocess,re,sys,contextlib
import functools
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


def run_remote(inputs, cmd, tdir,
    with contextlib.ExitStack() as stack:
        write_inputs=False, sync_files=(not config.shared_filesystem),
        stdout_log=None):
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

        # Sync RAMMS input files to remote dir
        if sync_files:
            rsync_files(inputs, tdir, direction='up')

        # Open file to log stdout
        stdout_log = None
        if stdout_log is not None:
            log_out = stack.enter_context(open(stdout_log, 'w'))

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
            #for input in inputs:
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
            print(line, end='', file=stdout_out)
            sys.stdout.flush()
            stdout_out.flush()

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
        if sync_files:
            harnutil.rsync_files(outputs_b, tdir, direction='down')

        # Outputs as local filenames
        outputs = [config.roots.syspath(x) for x in outputs_rel]
        return outputs

class QueueRunner:
    def __init__(self, **kwargs):
        self.redis = redis.Redis()
        self.queue = rq.Queue(connection=self.redis, **kwargs)

    def run(self, *args, timeout=1800, stdout_log=None, **kwargs):
        job = rq.job.Job.create(args=args, kwargs=kwargs)
        #job = self.queue.enqueue(*args, **kwargs)
        self.queue.enqueue(job)
        try:
            result = rq.results.Result.fetch_latest(job, serializer=job.serializer, timeout=timeout)
            if result.type == result.Type.SUCCESSFUL: 
                print('Success ', result.return_value) 
                return result.return_value
            else: 
                print('Failure ', result.exc_string)
                raise RuntimeError(result.exc_string)

        finally:
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


def run_remote_queued(inputs, cmd, tdir, **kwargs):
    stdout_log = tdir.join('stdout.log')
    kw = dict(kwargs)
    kw['timeout'] = 30*60    # 30 minutes
    job = rq.job.Job.create(run_remote, args=(inputs, cmd, tdir), kwargs=kw)
    qr.run(job)


def print_outputs(outputs):
    """Helper function"""
    sys.stdout.flush()
    print()
    print('BEGIN OUTPUTS')
    for output in outputs:
        print('OUTPUT: {}'.format(config.roots.relpath(output)))
    print('END OUTPUTS')
    sys.stdout.flush()
