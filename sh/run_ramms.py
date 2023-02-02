import time,sys
import subprocess,os,signal
import argparse
from akramms import rammsdist

parser = argparse.ArgumentParser(prog='run_ramms',
    description='Executes and manages RAMMS top-level IDL code')

parser.add_argument('--idlrt', metavar='<IDL .exe file>',
    default=r'C:\Program Files\Harris\IDL88\bin\bin.x86_64\idlrt.exe',
#    default=r'C:\opt\220922-RAMMS-x0928\IDL85\bin\bin.x86_64\idlrt.exe',
    help='Main IDL executable idlrt.exe')

parser.add_argument('--ramms-version', metavar='<RAMMS distro version>',
    default=r'230126',
    help='Version of RAMMS to use')

parser.add_argument('ramms_dir', metavar='<RAMMS run directory>',
    help='Directory prepared to run RAMMS')

parser.add_argument('stage', type=int,
    help='Stage of RAMMS to run (1|3)')

args = parser.parse_args()
if args.stage == 1:
    rammsdist.run_on_windows_stage1(args.idlrt, args.ramms_version, args.ramms_dir)
elif args.stage == 3:
    rammsdist.run_on_windows_stage3(args.idlrt, args.ramms_version, args.ramms_dir)
else:
    raise ValueError(f'Illegal RAMMS stage: {stage}')
