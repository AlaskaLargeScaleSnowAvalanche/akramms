from akramms import config
from akramms.util import rammsutil
import gzip,time,traceback
import os,subprocess,re,sys,itertools,collections,shutil,zipfile
from uafgi.util import ioutil
from akramms.util import harnutil

# def unpack_zipfile(ifname, odir, toplevel=True):
#     """toplevel:
#         Is everything in a top level directory that needs to be removed?
#     """
# 
#     # Unpack the Zipfile
#     with zipfile.ZipFile(ifname, 'r') as zipf:
#         # Deal with zipfiles with a single top-level folder
#         truncate = 0
#         root = zipfile.Path(zipf)
#         print(root.name)
#         subdirs = list(root.iterdir())
#         if len(subdirs) == 1:
#             truncate = len(subdirs[0].name) + 1
# 
#         for info in zipf.infolist():
#             name_path = info.filename[truncate:].split('/')
# 
#             # Don't copy top-level dir
#             if info.is_dir():
#                 continue
# 
#             ofname = os.path.join(odir, *name_path)
#             ofname_dir = os.path.split(ofname)[0]
# #            print('makedirs ', ofname_dir)
#             os.makedirs(ofname_dir, exist_ok=True)
#             print(ofname)
#             with open(ofname, 'wb') as out:
#                 out.write(zipf.open(info.filename).read())
# 
# 
# 
# _renames = {
#     'ramms_aval_LHM.exe' : 'ramms_aval_LHM_orig.exe'
# }
# 
# RAMMS_220922 = ('220922', 'RAMMS_LSHM_NEW2022.zip')
# _base_upgrade_for_version = {
#     '220922' : (RAMMS_220922, None),
#     '220928' : (RAMMS_220922, '220928'),
#     '221101' : (RAMMS_220922, '221101'),
#     '230126' : (RAMMS_220922, '230126'),
#     '230210' : (RAMMS_220922, '230210'),
# }
# def install_ramms_on_windows(version):
#     """Installs RAMMS into the appropriate distro file inside the harness.
#     Returns:
#         Directory of installed RAMMS"""
# 
#     # See if this version of RAMMS is already installed.
#     odir = os.path.join(harnutil.HARNESS, 'opt', 'RAMMS', version)
#     INSTALLED_txt = os.path.join(odir, 'INSTALLED.txt')
#     if os.path.exists(INSTALLED_txt):
#         return odir
# 
#     # Unzip base
#     shutil.rmtree(odir, ignore_errors=True)
#     base_zip = config.roots.syspath('{DATA}/christen/RAMMS/220922/RAMMS_LSHM_NEW2022.zip')
#     unpack_zipfile(base_zip, odir)
# 
#     # Unpack changes
#     if version != '220922':
#         delta_dir = config.roots.syspath('{DATA}/christen/RAMMS/'+version)
#         shutil.copytree(delta_dir, odir, dirs_exist_ok=True)
# 
#     # Mark we are complete
#     with open(INSTALLED_txt, 'w') as out:
#         out.write('Completed RAMMS installation\n')
# 
#     return odir
# 
#def main():
#    install_ramms_on_windows('230126')
#main()
# ==============================================================
# -----------------------------------------------------
# taskkill.exe /T /F /IM idlrt.exe
# taskkill.exe /T /F /IM idl_opserver.exe
#
# /T kills child processes.  I was getting the error:
#    ERROR: The process "idl_opserver.exe" with PID 5468 could not be terminated.
#    Reason: There is no running instance of the task.
# See: https://stackoverflow.com/questions/12528963/taskkill-f-doesnt-kill-a-process

def kill_idl():
    print('Killing IDL Tasks... (do not be alarmed by two "not found" errors)')
    sys.stdout.flush()
    sys.stderr.flush()

    sleep=False

    for cmd in (
        ['taskkill.exe', '/T', '/F', '/IM', 'idlrt.exe'],
        ['taskkill.exe', '/T', '/F', '/IM', 'idl_opserver.exe']):

        try:
            subprocess.run(cmd, check=True)
            sys.stdout.flush()
            sys.stderr.flush()
            sleep=True
        except subprocess.CalledProcessError:
            pass

    # Wait around for NTFS to unlock files used by tasks
    if sleep:
        print('Sleeping because tasks were killed')
        time.sleep(1)

# -----------------------------------------------------
def read_inputs():
    """Read list of input files from stdin"""

    inputRE = re.compile(r'INPUT:\s([^\s]*)\s*$')
    inputs = list()
    while True:
        line = sys.stdin.readline().strip()
        if line == 'END INPUTS':
            break
        match = inputRE.match(line)
        if match is not None:
            inputs.append(match.group(1))
    return inputs

# -----------------------------------------------------------------------
_releaseRE = re.compile(r'\s*RELEASE\s+(\d+)/(\d+)')
_doneRE1 = re.compile(
    r'\s*(Starting LSHM SIMULATIONS|LSHM Analysis finished successfully|- VAR-Files: All files created \(IDLBridge\)!)')

_genRE = re.compile(r'\s*INPUT FILES DOM\s*')
#_varRE = re.compile(r'\s*VAR-FILES\s*')

#\s*(INPUT FILES DOM|INPUT FILES REL|INPUT FILES XYZ|INPUT FILES^|XY-COORDS-FILES|VAR-FILES
#
#_sectionRE = re.compile(r'\s*- DEBUG-MODE, creating input ([^ ]+) files in series')
#section2ext = {
#    'DOM': '.dom',
#    'REL': '.rel',
#    'XYZ': '.xyz',
#    'AV2': '.av2',
#    'XY-COORDS': '.xy-coord',


class LineProcessor1:

    def __init__(self, avalanche_dirs):
        self.avalanche_dirs = avalanche_dirs
        self.ready_to_exit = False
        self.var_begin = False

    def count_var_files(self):
        # Count the number of .var files
        nvar = 0
        for avalanche_dir in self.avalanche_dirs:
            for leaf in os.listdir(avalanche_dir):
                if leaf.endswith('.var'):
                    nvar += 1
        return nvar

    def count_files(self):
        nfiles = 0
        for avalanche_dir in self.avalanche_dirs:
            nfiles += len(os.listdir(avalanche_dir))
        return nfiles

    def check_end_chunk(self):
        # Don't start counting VAR files until we've begun generating them
        if not self.var_begin:
            return True

        # If >30 seconds have passed, check to see if the number of VAR
        # files has increased.
        t1 = time.time()
        if t1 - self.t0 < 30:
            return True

        self.t0 = t1
        nvar = self.count_files()
        if nvar > self.nvar:
            self.nvar = nvar
            return True
        else:
            return False

    def watch(self, line):
        # ---- Process the line we have read
        # Seek info on progress through release files
        # Eg: RELEASE 1/3
        match = _releaseRE.match(line)
        if match is not None:
            release_file_ix = int(match.group(1))
            num_release_files = int(match.group(2))
            if release_file_ix == num_release_files:
                self.ready_to_exit = True
            return True

        # Check for beginning of file generation
        if _genRE.match(line) is not None:
            self.var_begin = True
            self.nvar = self.count_files()
            self.t0 = time.time()+10    # Give an extra 10 seconds at first

        # If we've seen enough release files, look out for our
        # "done message."
        if self.ready_to_exit and (_doneRE1.match(line) is not None):
            return False

        return True

_doneRE3 = re.compile(r'\s*Finished writing GEOTIFF files!')
class LineProcessor3:
    def __init__(self):
#        self.ready_to_exit = False
        self.ready_to_exit = True    # Bug in RAMMS, only does one release file anyway
    def check_end_chunk(self):
        return True

    def watch(self, line):
        # ---- Process the line we have read
        # Seek info on progress through release files
        # Eg: RELEASE 1/3
        match = _releaseRE.match(line)
        if match is not None:
            release_file_ix = int(match.group(1))
            num_release_files = int(match.group(2))
            if release_file_ix == num_release_files:
                self.ready_to_exit = True
            return True

        # If we've seen enough release files, look out for our
        # "done message."
        if self.ready_to_exit and (_doneRE3.match(line) is not None):
            return False
        return True

def _run_on_windows_once(idlrt_exe, ramms_version, ramms_dir, avalanche_dirs, ramms_stage):
    """Call this to run top-level RAMMS locally on Windows.
    idlrt_exe:
        Windows path to idlrt.exe IDL runtime
    ramms_version:
        Version of RAMMS to run (eg: '221101')
    ramms_dir:
        RAMMS directory to run
    avalanche_dirs:
        Avalanche directories inside the ramms_dir
    ramms_stage: 1|2|3
        Stage of RAMMS to execute on this run (eg: 1)
    Returns retry:
        True if we should retry.
        False if we should NOT retry
    """
    print(f'***** Running Top-Level RAMMS on {ramms_dir}')

    # ----------------------------------------------------------------
    # Stuff we will discern from the IDL stdout
    # RELEASE 1/2 
    #   - Release shapefile: C:\Users\efischer\av\prj\juneau1\RAMMS\juneau130yFor\RELEASE\juneau1_For_5m_30L_rel.shp 
    #   - Scenario: 5m_30L 
    #   - Creating SCENARIO directory: C:\Users\efischer\av\prj\juneau1\RAMMS\juneau130yFor\RESULTS\juneau1_For\5m_30L\ 
    release_file_ix = None      # Eg: 1
    num_release_files = None    # Eg: 2

    # This flag means we are ready to exit as soon as we identify the
    # "done message" (see _doneREs)
    #ready_to_exit = (ramms_stage != 1)        
    
    # ----------------------------------------------------------------
    # Make sure we've added our stub properly
    #ramms_distro = install_ramms_on_windows(ramms_version)

    # Avoid extra IDL processese lying around that would eat our license
    kill_idl()

    # Remove logfile (if it exists)
    # (must come after kill_idl())
    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')
    try:
        os.remove(logfile)
    except FileNotFoundError:
        pass

    # Create batch file to run
    ramms_sav = os.path.join(config.ramms_distro_dir, 'ramms_lshm.sav')
    scenario_txt = os.path.join(ramms_dir, 'scenario.txt')
    batfile = os.path.join(ramms_dir, f'run_ramms_{ramms_stage}.bat')
    print('Writing {}'.format(batfile))
    with open(batfile, 'w') as out:
        bat_contents = f'"{idlrt_exe}" "{ramms_sav}" -args "{scenario_txt}" {ramms_stage} {ramms_stage}\n'
        print(bat_contents)
        out.write(bat_contents)

    # Prepare to process RAMMS Lines
    line_processor = LineProcessor1(avalanche_dirs) if ramms_stage == 1 else LineProcessor3()

    # Run RAMMS
    retry = True    # Should we try running this again?
    try:
        fin = None
        proc1 = subprocess.Popen(batfile)

        timeout = 0.5
        state = 0
        while True:
            time.sleep(0.5)

            # See if RAMMS exited unexpectedly
            # Or if it exited before we could kill it and returned an error status code
            retcode = proc1.poll()
            if (retcode != None and retcode != 0):
                print('IDL RAMMS exited with status code {}'.format(retcode))
                raise subprocess.CalledProcessError(retcode, batfile)

            # Open logfile if it has appeared
            if fin is None:
                print('.', end='')
                sys.stdout.flush()
                if os.path.exists(logfile):
                    print('Opening logfile')
                    fin = open(logfile)
                    fin.seek(0, os.SEEK_END) 
                    print()
                continue

            while True:
                line = fin.readline()
                if not line:
                    # Nothing more to read for now
                    if not line_processor.check_end_chunk():
                        print('_run_on_windows() exiting (check end chunk)')
                        sys.stdout.flush()
                        raise TimeoutError()   # Break out of double loop
                    break    

                print(line+'*', end='')
                if not line_processor.watch(line):
                    print('_run_on_windows() exiting (watch)')
                    sys.stdout.flush()
                    raise EOFError()   # Break out of double loop

            sys.stdout.flush()

    except EOFError:
        # Proper signal of end of IDL output; exit gracefully
        retry = False
    except TimeoutError:
        # IDL has hung, we should retry
        retry = True
    except Exception as e:
        # Inform user of errors in this program
        retry = False
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        if fin is not None:
            fin.close()

        if proc1 is not None:
            # Kill the remaining process
            kill_idl()

            # Just in case, wait for it to exit.
            proc1.communicate()
            print('************ ALL DONE!!! ****************')
            sys.stdout.flush()
            sys.stderr.flush()

        # Delete any zero-length files
        for avalanche_dir in avalanche_dirs:
            for leaf in os.listdir(avalanche_dir):
                fname = os.path.join(avalanche_dir, leaf)
                if os.path.getsize(fname) == 0:
                    print('Removing zero-length file: {}'.format(fname))
                    os.remove(fname)




    return retry

def _run_on_windows(*args, ntry=1):
    """Retry up to a specified number of times."""
    for n in range(ntry):
        print(f'===***===*** Retrying _run_on_windows: {n}')
        if not _run_on_windows_once(*args):
            break

# -----------------------------------------------------------------------
# -----------------------------------------------------------------------
def run_on_windows_stage1(idlrt_exe, ramms_version, ramms_dir):

    # Obtain list of input files (includes the release files)
    inputs_rel = read_inputs()

    release_files_rel = [x for x in inputs_rel if x.endswith('_rel.shp')]
    print('release_files_rel ', release_files_rel)
    release_files = [config.roots.syspath(x_rel) for x_rel in release_files_rel]
    jbs = [rammsutil.parse_release_file(x) for x in release_files]
    avalanche_dirs = set(jb.avalanche_dir for jb in jbs)

    # Collect output files, to be be transferred back to Linux
    outputs = list()

    # Run RAMMS locally, managing the IDL process
    _run_on_windows(idlrt_exe, ramms_version, ramms_dir, avalanche_dirs, 1, ntry=2)

    # Rename the log file to reflect stage1
    ilogfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')
    ologfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock_stage1.log')
    if os.path.exists(ologfile):
        try:
            os.remove(ologfile)
            os.rename(ilogfile, ologfile)
        except:
            print('WARNING: Cannot create logfile in final location, is it locked?: ', ologfile)

    outputs.append(ologfile)

    # Find all .var.gz, .xy-coord.gz and .xyz.gz files in the avalanche
    # directories, and declare as output files

    outRE = re.compile('|'.join(
        r'[^.]*{}$'.format(ext.replace('.', r'\.')) \
            for ext in
            ('.av2', '.dom', '.rel', '.var', '.xy-coord', '.xyz')))

#    for release_file_rel in release_files_rel:
#        release_file = config.roots.syspath(release_file_rel)

    for release_file in release_files:
        # Identify our list of avalanche directories based release files listed as inputs
        # Turn release file name into directory of avalanche simulations
        jb = rammsutil.parse_release_file(release_file)

        # Look at files inside avalanche directory
        for f in os.listdir(jb.avalanche_dir):
            if outRE.match(f) is not None:
                ofname = os.path.join(jb.avalanche_dir, f)
                outputs.append(ofname)

    # Tell calling process on Linux what the output files are
    harnutil.print_outputs(outputs)

# -----------------------------------------------------------------------
def run_on_windows_stage3(idlrt_exe, ramms_version, ramms_dir):

    results_dir = os.path.join(ramms_dir, 'RESULTS')

    # Get list of avalanche_dirs
    # Look for top-level directories under RESULTS.
    # Each one of them will hold one or more sets of final outputs
    slope_dirs = list()
    avalanche_dirs = list()
    for x0 in os.listdir(results_dir):
        slope_dir = os.path.join(results_dir, x0)
        if not os.path.isdir(slope_dir):
            continue

        slope_dirs.append(slope_dir)        
        for y0 in os.listdir(slope_dir):
            avalanche_dir = os.path.join(slope_dir, y0)
            if os.path.isdir(avalanche_dir):
                avalanche_dirs.append(avalanche_dir)

    # We have been provided a number of input files implicitly.
    print('Running RAMMS Stage 3 on Windows (launching IDL now)')
    _run_on_windows(idlrt_exe, ramms_version, ramms_dir, avalanche_dirs, 3, ntry=1)

    # Figure out which output files exist, and print to STDOUT

    # Look for top-level directories under RESULTS.
    # Each one of them will hold one or more sets of final outputs
    outputs = list()
    results_dir = os.path.join(ramms_dir, 'RESULTS')
    outputs.append(os.path.join(results_dir, 'lshm_rock.log'))

    # List files in the slope_dirs
    for x0 in os.listdir(results_dir):
        dir = os.path.join(results_dir, x0)
        if not os.path.isdir(dir):
            continue

        for x1 in os.listdir(dir):
            fname1 = os.path.join(dir, x1)
            if os.path.isfile(fname1):
                outputs.append(fname1)

    outputs.sort()

    # Tell calling process on Linux what the output files are
    harnutil.print_outputs(outputs)
# -----------------------------------------------------------------------
