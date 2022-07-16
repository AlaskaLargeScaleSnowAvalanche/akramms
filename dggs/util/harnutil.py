import os
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

def remote_windows_name(fname, REMOTE_HARNESS, bash=False):
    """Assumes remote Windows host
    bash:
        Convert to bash-style pathname?"""

    ret = os.path.join(REMOTE_HARNESS, os.path.relpath(fname, HARNESS)).replace(os.path.sep, '\\')
    if bash:
        ret = bash_name(ret)
    print('remote_name: {} -> {}'.format(fname, ret))
    return ret


def remote_linux_name(fname):
    """Assumes same home directory structure on remote Linux host"""
    ret = os.path.join('~', os.path.relpath(fname, os.environ['HOME']))
    return ret
