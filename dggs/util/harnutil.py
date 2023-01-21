import os,subprocess
import functools

def _harness_dir():
    path = os.path.abspath(__file__)
    for i in range(4):
        path = os.path.split(path)[0]
    return path
HARNESS = _harness_dir()


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


def remote_linux_name(fname):
    """Converts local Linux name to remote Linux name.
    Assumes same home directory structure on remote Linux host"""
    ret = os.path.join('~', os.path.relpath(fname, os.environ['HOME']))
    return ret

def rsync_files(fnames, remote_host, REMOTE_HARNESS, tdir, flags=['--copy-links', '-avz'], direction='up'):
    """Syncs a list of files into the same location in the remote harness.

    fnames: [filename, ...]
        Files to transfer to remote harness (bash-style filename)
        (These files must be within the implied local harness)
    REMOTE_HARNESS:
        Root of remote harness
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
