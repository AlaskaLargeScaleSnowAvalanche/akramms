import sys,re,subprocess,os
import htcondor
import shapely
from akramms import ramms


ramms_dir = '/home/efischer/av/prj/juneau1/RAMMS/juneau130yFor'
release_files = [os.path.join(ramms_dir, 'RELEASE/juneau1_For_5m_30L_rel.shp')]
ramms.run_simulations(ramms_dir, release_files)

#st = ramms.job_status(release_files)
#for k,v in st._asdict().items():
#    print(f'=========== {k}:')
#    print([x[1] for x in v])


