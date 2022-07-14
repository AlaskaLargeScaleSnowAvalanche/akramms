import dggs.data
from dggs import avalanche
from dggs.util import paramutil,harnutil
import os

scene_dir = dggs.data.join('prj', 'juneau1')

remote_scene_dir = harnutil.remote_linux_name(scene_dir)

files = ['PRA_extreme', 'PRA_frequent', 'scene.cdl', 'scene.nc']
cmd = ['rsync', 'antevorta', '-avz', #'--from0',
    '--files-from=-', scene_dir, '{}:{}'.format(hostname, harnutil.remote_linux_name(scene_dir))]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
p.communicate(input='\n'.join(files))


