import subprocess
import os

IDLRT_EXE = r'C:\Program Files\Harris/IDL88/bin/bin.x86_64/idlrt.exe'
RAMMS_ROOT = r'C:\Users\efischer\Downloads\RAMMS_LSHM_NEW2022'


scenario_tpl = \
"""LSHM    Obergoms
MODULE  AVAL            ( AVAL or DBF or EXT )
MUXI    VARIABLE    ( CONSTANT or VARIABLE )
DIR             D:\Temp\LSHM\Obergoms\
DEM     DEM\
SLOPE   SLOPE\
RELEASE RELEASE\
DOMAIN  DOMAIN\
FOREST  FOREST\
NRCPUS  10
COHESION 50
DEBUG 0
CPUS_PRE 2
END


KEEP_DATA  1
TEST_NR 20

ALT_LIM_TOP  2000
ALT_LIM_LOW  1250
"""

scenario_txt = os.path.abspath('scenario.txt')
with open(scenario_txt, 'w') as out:
    out.write(scenario_tpl)

cmd = [IDLRT_EXE, os.path.join(RAMMS_ROOT, 'ramms_lshm.sav'), '-args', scenario_txt]

print(cmd)
subprocess.run(cmd)
