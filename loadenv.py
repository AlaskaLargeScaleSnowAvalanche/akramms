import os,sys

# Get location of the enclosing harness
def _harness_dir():
    path = os.path.abspath(__file__)
    for i in range(2):
        path = os.path.split(path)[0]
    return path
HARNESS = _harness_dir()

print(f'export HARNESS={HARNESS}')
print('export AKRAMMS={}'.format(os.path.join(HARNESS, 'akramms')))

# --------- Append PYTHONPATH
vi = sys.version_info
SITE_PACKAGES = os.path.join(HARNESS, 'akramms', 'inst', 'lib', 'python{}.{}'.format(vi[0], vi[1]), 'site-packages')

pythonpath = list()
try:
    pythonpath.append(os.environ['PYTHONPATH'])
except KeyError:
    pass

pythonpath += [
    os.path.join(HARNESS, 'uafgi'),
    os.path.join(HARNESS, 'akramms'),
    os.path.join(HARNESS, 'rq'),
    os.path.join(HARNESS, 'ramms_lshm'),
    SITE_PACKAGES,
]
if os.path.exists(SITE_PACKAGES):
    for leaf in os.listdir(SITE_PACKAGES):
        if leaf.endswith('.egg'):
            x = os.path.join(SITE_PACKAGES, leaf)
            pythonpath.append(x)

print('export PYTHONPATH={}'.format(os.pathsep.join(pythonpath)))

# ------ Append PATH
path = [
    os.environ['PATH'],
    os.path.join(HARNESS, 'akramms', 'sh')
]
print('export PATH={}'.format(os.pathsep.join(path)))


