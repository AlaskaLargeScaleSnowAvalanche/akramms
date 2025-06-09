import os,sys

def bash_name(wfname):
    """Gets the bash name of a Windows filename.
    Eg: C:\\Users\\me\\x.txt ==> /C/Users/me/x.txt

    wfname:
        Windows filename
    """
    if sys.platform not in {'win32'}:
        return wfname

    wfname = wfname.replace('\\', '/')
    if wfname[1] == ':':
        wfname = '/{}{}'.format(wfname[0], wfname[2:])
    return wfname

def join_paths(paths):
    return ':'.join(bash_name(path) for path in paths)
# ----------------------------------
# Get location of the enclosing harness
def _harness_dir():
    path = os.path.abspath(__file__)
    for i in range(2):
        path = os.path.split(path)[0]
    return path
HARNESS = _harness_dir()

print(f"export HARNESS='{HARNESS}'")
print("export AKRAMMS='{}'".format(os.path.join(HARNESS, 'akramms')))

# --------- Append PYTHONPATH
vi = sys.version_info
SITE_PACKAGES = os.path.join(HARNESS, 'akramms', 'inst', 'lib', 'python{}.{}'.format(vi[0], vi[1]), 'site-packages')

pythonpath = list()
try:
    pythonpath += os.environ['PYTHONPATH'].split(os.pathsep)
except KeyError:
    pass

pythonpath += [
    os.path.join(HARNESS, 'uafgi'),
    os.path.join(HARNESS, 'akramms'),
    os.path.join(HARNESS, 'rq'),
    os.path.join(HARNESS, 'lshm'),
    SITE_PACKAGES,
]
if os.path.exists(SITE_PACKAGES):
    for leaf in os.listdir(SITE_PACKAGES):
        if leaf.endswith('.egg'):
            x = os.path.join(SITE_PACKAGES, leaf)
            pythonpath.append(x)

print('export PYTHONPATH="{}"'.format(join_paths(pythonpath)))

# ------ Append PATH
path = os.environ['PATH'].split(os.pathsep) + [
    os.path.join(HARNESS, 'akramms', 'sh')
]
print('export PATH="{}"'.format(join_paths(path)))


