import time
import os,subprocess,re,sys,itertools,collections,shutil,zipfile
from uafgi.util import ioutil
from dggs.util import harnutil

_dest_paths = {    # Relative path where files from Marc belong
    'ramms_lshm.sav': [],
}

_renames = {
    'ramms_aval_LHM.exe' : 'ramms_aval_LHM_orig.exe'
}

RAMMS_220922 = ('220922', 'RAMMS_LSHM_NEW2022.zip')
_base_upgrade_for_version = {
    '220922' : (RAMMS_220922, None),
    '220928' : (RAMMS_220922, '220928'),
    '221101' : (RAMMS_220922, '221101'),
}
def install_ramms_on_windows(version):
    """Installs RAMMS into the appropriate distro file inside the harness."""

    # See if this version of RAMMS is already installed.
    ramms_installed = os.path.join(harnutil.HARNESS, 'opt', 'RAMMS', version)
    INSTALLED_txt = os.path.join(ramms_installed, 'INSTALLED.txt')
    if os.path.exists(INSTALLED_txt):
        return ramms_installed

    # Create destination directory
    shutil.rmtree(ramms_installed, ignore_errors=True)
    os.makedirs(ramms_installed, exist_ok=True)

    # Figure out where raw distro files are for our version.
    base_args, upgrade_leaf = _base_upgrade_for_version[version]
    upgrade_dir = os.path.join(harnutil.HARNESS, 'data', 'christen', 'RAMMS', version)
    print('upgrade_dir ',upgrade_dir)

    # Copy the upgrade files
    upgrade_paths = set()
    for leaf in sorted(list(os.listdir(upgrade_dir))):
        src_file = os.path.join(upgrade_dir, leaf)

        # Ignore files we don't know what to do with
        try:
            dest_path = _dest_paths[leaf]
            upgrade_paths.add(tuple(list(dest_path) + [leaf]))
        except KeyError:
            # Ignore files we don't know what to do with
            continue
        dest_dir = os.path.join(ramms_installed, *dest_path)
        os.makedirs(dest_dir, exist_ok=True)
        print(src_file, dest_dir)
        shutil.copy(src_file, dest_dir)

    #print('** upgrade_paths ',upgrade_paths)

    # Unpack the Zipfile
    base_zip = os.path.join(harnutil.HARNESS, 'data', 'christen', 'RAMMS', *base_args)
    with zipfile.ZipFile(base_zip, 'r') as zipf:
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

            # Don't copy things we've already upgraded
            if tuple(name_path) in upgrade_paths:
                continue

            # Change output filename when unzipping
            try:
                new_leaf = _renames[name_path[-1]]
                new_path = name_path[:-1] + [new_leaf]
                ofname = os.path.join(ramms_installed, *new_path)
            except KeyError:
                # Not renaming this
                ofname = os.path.join(ramms_installed, *name_path)
            ofname_dir = os.path.split(ofname)[0]
            print('makedirs ', ofname_dir)
            os.makedirs(ofname_dir, exist_ok=True)
            print(info.filename, ofname)
            with open(ofname, 'wb') as out:
                out.write(zipf.open(info.filename).read())
            #zipf.extract(name, ofname)

    # Build the stub wrapper
    bin = os.path.join(ramms_installed, 'bin')
    with ioutil.pushd(bin):
#        if not os.path.exists('ramms_aval_LHM_orig.exe'):
#            # Need to move
#            print('Moving to ramms_aval_LHM_orig.exe')
#            os.rename('ramms_aval_LHM.exe', 'ramms_aval_LHM_orig.exe')

        if not os.path.exists('ramms_aval_LHM.exe'):
            # Need to build
            src = os.path.join(harnutil.HARNESS, 'akramms', 'ramms_aval_LHM_stub.cpp')
            cmd = ['g++', src, '-o', 'ramms_aval_LHM.exe']
            print(' '.join(cmd))
            subprocess.run(cmd, check=True)

    # Mark we are complete
    with open(INSTALLED_txt, 'w') as out:
        out.write('Completed RAMMS installation\n')

    return ramms_installed

#def main():
#    install_ramms_on_windows('221101')
#main()
# ==============================================================
# -----------------------------------------------------
def kill_idl():
    sleep=False

    for cmd in (
        ['taskkill.exe', '/F', '/IM', 'idlrt.exe'],
        ['taskkill.exe', '/F', '/IM', 'idl_opserver.exe']):

        try:
            subprocess.run(cmd, check=True)
            sleep=True
        except subprocess.CalledProcessError:
            pass

    # Wait around for NTFS to unlock files used by tasks
    if sleep:
        print('Sleeping because tasks were killed')
        time.sleep(1)

#_doneRE = re.compile(r"\s*Creating MUXI-Files...")    # Demo
_doneRE = re.compile(r'\s*Starting LSHM SIMULATIONS')
#_doneRE = re.compile(r"\s*Finsihed writing GEOTIFF files!")    # Prod

def run_on_windows(idlrt_exe, ramms_version, ramms_dir):
    """Call this to run top-level RAMMS locally on Windows.
    idlrt_exe:
        Windows path to idlrt.exe IDL runtime
    ramms_version:
        Version of RAMMS to run (eg: '221101')
    ramms_dir:
        RAMMS directory to run
    Returns:
        Nothing if OK.
        Raises Exception if it did not complete.
    """
    print(f'***** Running Top-Level RAMMS on {ramms_dir}')

    # Make sure we've added our stub properly
    ramms_distro = install_ramms_on_windows(ramms_version)

    # Avoid extra IDL's lying around that would eat our license
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
    batfile = os.path.join(ramms_dir, 'run_ramms.bat')
    with open(batfile, 'w') as out:
        out.write(f'"{idlrt_exe}" "{ramms_sav}" -args "{scenario_txt}"\n')

    # Run RAMMS
    try:
        fin = None
        proc1 = subprocess.Popen(batfile)

        timeout = 0.5
        state = 0
        while True:
            time.sleep(0.5)

            # See if RAMMS exited unexpectedly
            retcode = proc1.poll()
            if (retcode != None):
                print('IDL RAMMS exited with status code {}'.format(retcode))
                raise subprocess.CalledProcessError(retcode, cmd1)

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

                # Process the line we read
                print(line+'*', end='')
                if _doneRE.match(line) is not None:
                    raise EOFError()   # Break out of double loop

            sys.stdout.flush()

    except EOFError:
        # Proper signal of end of IDL output; exit gracefully
        pass

    finally:
        if fin is not None:
            fin.close()

        if proc1 is not None:
            # Kill the remaining process
            kill_idl()

            # Just in case, wait for it to exit.
            proc1.communicate()
            print('************ ALL DONE!!! ****************')

    # gzip all .var, .xy-coord and .xyz files
    gzipRE = re.compile(r'[^.]*\.var$|[^.]*\.xy-coord$|[^.]*\.xyz$')
    for path,dirs,files in os.walk(os.path.join(ramms_dir, 'RESULTS')):
        for f in files:
            if gzipRE.match(f) is not None:
                # Gzip the file
                ifname = os.path.join(path, f)
                ofname = os.path.join(path, f+'.gz')
                print(f'Gzipping {ifname}')
                with open(ifname, 'rb') as fin:
                    with gzip.open(ofname, 'wb') as out:
                        shutil.copyfileobj(fin, out)

                # Delete the original
                try:
                    os.remove(ifname)
                except FileNotFoundError:
                    pass
                    
