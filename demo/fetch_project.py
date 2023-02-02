from akramms import config
from dggs import avalanche
from akramms.util import paramutil,harnutil
import os,subprocess

scene_dir = dggs.data.join('prj', 'juneau1')

remote_scene_dir = harnutil.remote_linux_name(scene_dir)
print('remote_scene_dir ',remote_scene_dir)
hostname = 'antevorta'

files = ['PRA_extreme/', 'PRA_frequent/', 'scene.cdl', 'scene.nc']
cmd = ['rsync', '-avz', #'--from0',
    '--files-from=-', '{}:{}'.format(hostname, remote_scene_dir), scene_dir]
print(' '.join(cmd))
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
proc.communicate(input='\n'.join(files).encode('utf-8'))


