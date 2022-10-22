import time,sys
import subprocess,os,signal
import argparse
from dggs.avalanche import ramms

parser = argparse.ArgumentParser(prog='run_ramms',
    description='Executes and manages RAMMS top-level IDL code')

parser.add_argument('--idlrt', metavar='<IDL .exe file>',
    default=r'C:\Program Files\Harris\IDL88\bin\bin.x86_64\idlrt.exe',
#    default=r'C:\opt\220922-RAMMS-x0928\IDL85\bin\bin.x86_64\idlrt.exe',
    help='Main IDL executable idlrt.exe')

parser.add_argument('--ramms', metavar='<RAMMS .sav file>',
    default=r'C:\opt\220922-RAMMS-x0928\ramms_lshm.sav',
    help='Main RAMMS .sav file')

parser.add_argument('ramms_dir', metavar='<RAMMS run directory>',
    help='Directory prepared to run RAMMS')

args = parser.parse_args()
ramms.run(args.idlrt, args.ramms, args.ramms_dir)
