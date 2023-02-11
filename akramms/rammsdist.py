from akramms import config
from akramms.util import rammsutil
import gzip,time,traceback
import os,subprocess,re,sys,itertools,collections,shutil,zipfile
from uafgi.util import ioutil
from akramms.util import harnutil

def unpack_zipfile(ifname, odir, toplevel=True):
    """toplevel:
        Is everything in a top level directory that needs to be removed?
    """

    # Unpack the Zipfile
    with zipfile.ZipFile(ifname, 'r') as zipf:
        # Deal with zipfiles with a single top-level folder
        truncate = 0
        root = zipfile.Path(zipf)
        print(root.name)
        subdirs = list(root.iterdir())
        if len(subdirs) == 1:
            truncate = len(subdirs[0].name) + 1

        for info in zipf.infolist():
            name_path = info.filename[truncate:].split('/')

            # Don't copy top-level dir
            if info.is_dir():
                continue

            ofname = os.path.join(odir, *name_path)
            ofname_dir = os.path.split(ofname)[0]
#            print('makedirs ', ofname_dir)
            os.makedirs(ofname_dir, exist_ok=True)
            print(ofname)
            with open(ofname, 'wb') as out:
                out.write(zipf.open(info.filename).read())



_renames = {
    'ramms_aval_LHM.exe' : 'ramms_aval_LHM_orig.exe'
}

RAMMS_220922 = ('220922', 'RAMMS_LSHM_NEW2022.zip')
_base_upgrade_for_version = {
    '220922' : (RAMMS_220922, None),
    '220928' : (RAMMS_220922, '220928'),
    '221101' : (RAMMS_220922, '221101'),
    '230126' : (RAMMS_220922, '230126'),
    '230210' : (RAMMS_220922, '230210'),
}
def install_ramms_on_windows(version):
    """Installs RAMMS into the appropriate distro file inside the harness.
    Returns:
        Directory of installed RAMMS"""

    # See if this version of RAMMS is already installed.
    odir = os.path.join(harnutil.HARNESS, 'opt', 'RAMMS', version)
    INSTALLED_txt = os.path.join(odir, 'INSTALLED.txt')
    if os.path.exists(INSTALLED_txt):
        return odir

    # Unzip base
    shutil.rmtree(odir, ignore_errors=True)
    base_zip = config.roots.syspath('{DATA}/christen/RAMMS/220922/RAMMS_LSHM_NEW2022.zip')
    unpack_zipfile(base_zip, odir)

    # Unpack changes
    if version != '220922':
        delta_dir = config.roots.syspath('{DATA}/christen/RAMMS/'+version)
        shutil.copytree(delta_dir, odir, dirs_exist_ok=True)

    # Mark we are complete
    with open(INSTALLED_txt, 'w') as out:
        out.write('Completed RAMMS installation\n')

    return odir

#def main():
#    install_ramms_on_windows('230126')
#main()
# ==============================================================
# -----------------------------------------------------
# taskkill.exe /F /IM idlrt.exe
# taskkill.exe /F /IM idl_opserver.exe
def kill_idl():
    print('Killing IDL Tasks... (do not be alarmed by two "not found" errors)')
    sys.stdout.flush()
    sys.stderr.flush()

    sleep=False

    for cmd in (
        ['taskkill.exe', '/F', '/IM', 'idlrt.exe'],
        ['taskkill.exe', '/F', '/IM', 'idl_opserver.exe']):

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

#_doneRE = re.compile(r"\s*Creating MUXI-Files...")    # Demo
# RAMMS IDL prints this when it is done with Stage 1
_doneREs = {
    1 : re.compile(r'\s*(Starting LSHM SIMULATIONS|LSHM Analysis finished successfully|- VAR-Files: All files created \(IDLBridge\)!)'),
    3 : re.compile(r'LSHM Analysis finished successfully'),
}

#_doneRE = re.compile(r"\s*Finsihed writing GEOTIFF files!")    # Prod


# -----------------------------------------------------------------------
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
def _run_on_windows(idlrt_exe, ramms_version, ramms_dir, ramms_stage):
    """Call this to run top-level RAMMS locally on Windows.
    idlrt_exe:
        Windows path to idlrt.exe IDL runtime
    ramms_version:
        Version of RAMMS to run (eg: '221101')
    ramms_dir:
        RAMMS directory to run
    ramms_stage: 1|2|3
        Stage of RAMMS to execute on this run (eg: 1)
    Returns:
        Nothing if OK.
        Raises Exception if it did not complete.
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
    ready_to_exit = (ramms_stage != 1)        
    
    # ----------------------------------------------------------------
    # Make sure we've added our stub properly
    ramms_distro = install_ramms_on_windows(ramms_version)

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
    ramms_sav = os.path.join(ramms_distro, 'ramms_lshm.sav')
    scenario_txt = os.path.join(ramms_dir, 'scenario.txt')
    batfile = os.path.join(ramms_dir, f'run_ramms_{ramms_stage}.bat')
    print('Writing {}'.format(batfile))
    with open(batfile, 'w') as out:
        bat_contents = f'"{idlrt_exe}" "{ramms_sav}" -args "{scenario_txt}" {ramms_stage} {ramms_stage}\n'
        print(bat_contents)
        out.write(bat_contents)

    # Run RAMMS
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

            # Read out everything in logfile since last time we looked
            while True:
                line = fin.readline()
                if not line:
                    break    # Nothing more to read for now

                print(line+'*', end='')

                # ---- Process the line we have read
                # Seek info on progress through release files
                # Eg: RELEASE 1/3
                match = _releaseRE.match(line)
                if match is not None:
                    release_file_ix = int(match.group(1))
                    num_release_files = int(match.group(2))
                    if release_file_ix == num_release_files:
                        ready_to_exit = True

                # If we've seen enough release files, look out for our
                # "done message."
                if ready_to_exit and (_doneREs[ramms_stage].match(line) is not None):
                    print('_run_on_windows() exiting')
                    sys.stdout.flush()
                    raise EOFError()   # Break out of double loop

            sys.stdout.flush()

    except EOFError:
        # Proper signal of end of IDL output; exit gracefully
        pass
    except Exception as e:
        # Inform user of errors in this program
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

# -----------------------------------------------------------------------
# -----------------------------------------------------------------------
def run_on_windows_stage1(idlrt_exe, ramms_version, ramms_dir):

    # Obtain list of input files (includes the release files)
    inputs_rel = read_inputs()

    release_files_rel = [x for x in inputs if x.endswith('_rel.shp')]
    print('release_files_rel ', release_files_rel)

    # Collect output files, to be be transferred back to Linux
    outputs = list()

    # Run RAMMS locally, managing the IDL process
    _run_on_windows(idlrt_exe, ramms_version, ramms_dir, 1)

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
            ('.av2', '.dom', '.rel', '.var.gz', '.xy-coord.gz', '.xyz.gz')))

    for release_file_rel in release_files_rel:
        release_file = config.roots.syspath(release_file_rel)

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

    # We have been provided a number of input files implicitly.

    # Un-gzip .xy-coord.gz files (leave .out.gz gzipped)
    gzipRE = re.compile(r'[^.]*\.xy-coord\.gz$|[^.]*\.log.zip$')
    for path,dirs,files in os.walk(os.path.join(ramms_dir, 'RESULTS')):
        for f in files:
            if gzipRE.match(f) is not None:
                if f.endswith('.gz'):
                    # Gunzip the .xy-coord file
                    ifname = os.path.join(path, f)
                    ofname = os.path.join(path, f[:-3])    # Remove .gz
                    if True or not os.path.exists(ofname):  # TODO: compare timestamps
                        print(f'Un-gzipping {ifname}')
                        with gzip.open(ifname, 'rb') as fin:
                            with open(ofname, 'wb') as out:
                                shutil.copyfileobj(fin, out)

                elif f.endswith('.zip'):
                    # Unzip the log
                    ifname = os.path.join(path, f)
                    print(f'Extracting log from {ifname}')
                    with zipfile.ZipFile(ifname, 'r') as izip:
                        arcnames = [os.path.split(x)[1] for x in izip.namelist()
                            if x.endswith('.out.log')]
                        for arcname in arcnames:
                            ofname = os.path.join(path, arcname)
                            if True or not os.path.exists(ofname):  # TODO: compare timestamps
                                bytes = izip.read(arcname)
                                with open(ofname, 'wb') as out:
                                    out.write(bytes)

#    print('** TODO: Uncomment so we actually run RAMMS **')
    print('Running RAMMS Stage 3 on Windows (launching IDL now)')
    _run_on_windows(idlrt_exe, ramms_version, ramms_dir, 3)


    # Figure out which output files exist, and print to STDOUT

#    # Determine the directory where RAMMS outputs are, by reading the
#    # scenario.txt file
#    scenario_file = os.path.join(ramms_dir, 'scenario.txt')
#    dirRE = re.compile('^DIR\s+(.*)$')
#    with open(scenario_file) as fin:
#        line = next(fin)
#        match = dirRE.match(line)
#        if match is not None:
#            data_dir = match.group(1)    # Top-level dir where the individaul avalanche files are; (same as ramms_dir, so no point in reading it out)
#            break
            
    # Look for top-level directories under RESULTS.
    # Each one of them will hold one or more sets of final outputs
    outputs = list()
    results_dir = os.path.join(ramms_dir, 'RESULTS')
    for x0 in os.listdir(results_dir):
        dir0 = os.path.join(results_dir, x0)
        if not os.path.isdir(dir0):
            continue

        for dir in [dir0, os.path.join(dir0, 'logfiles')]:
            for x1 in os.listdir(dir):
                fname1 = os.path.join(dir, x1)
                if os.path.isfile(fname1):
                    outputs.append(fname1)

    outputs.sort()

    # Tell calling process on Linux what the output files are
    harnutil.print_outputs(outputs)
# -----------------------------------------------------------------------
