import time,sys
import subprocess,os,signal
import argparse
from dggs.avalanche import rammsdist

parser = argparse.ArgumentParser(prog='run_ramms',
    description='Executes and manages RAMMS top-level IDL code')

parser.add_argument('--idlrt', metavar='<IDL .exe file>',
    default=r'C:\Program Files\Harris\IDL88\bin\bin.x86_64\idlrt.exe',
#    default=r'C:\opt\220922-RAMMS-x0928\IDL85\bin\bin.x86_64\idlrt.exe',
    help='Main IDL executable idlrt.exe')

parser.add_argument('--ramms-version', metavar='<RAMMS distro version>',
    default=r'221101',
    help='Version of RAMMS to use')

parser.add_argument('ramms_dir', metavar='<RAMMS run directory>',
    help='Directory prepared to run RAMMS')

parser.add_argument('first_ramms_phase', type=int,
    help='First phase of RAMMS to run (1|2|3)')

parser.add_argument('last_ramms_phase', type=int,
    help='Last phase of RAMMS to run (1|2|3)')

args = parser.parse_args()
rammsdist.run_on_windows(args.idlrt, args.ramms_version, args.ramms_dir, args.first_ramms_phase, args.last_ramms_phase)
