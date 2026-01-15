import os,subprocess,re,sys,itertools,gzip,collections,io,typing,codecs,copy
import multiprocessing,pickle
import numpy as np
import datetime,time,zipfile
import contextlib
import itertools, functools,shutil
import numpy as np
import htcondor2 as htcondor
from akramms import config,params
from akramms.util import harnutil,rammsutil
from uafgi.util import make,ioutil,shputil,gdalutil
import pandas as pd



# --------------------------------------------------------------------




# -------------------------------------------------------
# ======================================================================
# ============= RAMMS Stage 2: Enlarge and re-submit domains that overran

# -----------------------------------------------------------




# -------------------------------------------------------
_parseRE = re.compile(
    r'(^\s*FINAL OUTFLOW VOLUME:\s+(?P<final_outflow_volume>[^\s]+)\s+m3)' +
    '|' +
    r'(^\s*INITIAL FLOW VOLUME:\s+(?P<initial_outflow_volume>[^\s]+)\s+m3)')


def _parse_aval_log(log_in):

    ret = dict()    # Key values pulled out of the file
    for line in log_in:
        match = _parseRE.match(line)
        if match is not None:
            match_names = [name for name, value in match.groupdict().items() if value is not None]
            # Remember first of each match value
            for name in match_names:
                if name not in ret:
                    ret[name] = match.group(name)

    return ret

def parse_aval_log(log_in):
    if isinstance(log_in, str):    # Open zip file
        with zipfile.ZipFile(log_in, 'r') as izip:
            arcnames = [os.path.split(x)[1] for x in izip.namelist()]
            lognames = [x for x in arcnames if x.endswith('.out.log')]
            bytes = izip.read(lognames[0])
            fin = io.TextIOWrapper(io.BytesIO(bytes))
            return _parse_aval_log(fin)
    else:
        return _parse_aval_log(fin)

# -------------------------------------------------------
def job_ids(release_file):
    """Reads a release file, and returns a (sorted) list of PRA IDs in that file."""
    release_df = shputil.read_df_noshapes(release_file)
    return sorted(list(release_df['Id']))
# --------------------------------------------------------

def ramms_iter(ramms_spec, ids=list()):
    """Iterates through a set of avalanches by spec
    ramms_spec:
        Spec indicating the release file(s) to include in the iteration
    ids: [int, ...]
        Avalanche IDs to include.
        If empty list, that means include all of them.
    """

    release_files = rammsutil.get_release_files(ramms_spec)

    rf_by_id = dict()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        for id in job_ids(release_file):
            rf_by_id[id] = jb

    for id in ids:
        yield rf_by_id[id],id


# Converts an extension on an arcname to extension on the zip filename
# (i.e.whether it is in _in.zip or _out.zip)
arcext2filext = {
    '.relp': '.in.zip',
    '.domp': '.in.zip',
    '.rel': '.in.zip',
    '.dom': '.in.zip',
    '.xyz': '.in.zip',
    '.xy-coord': '.in.zip',
    '.var': '.in.zip',
    '.av3': '.in.zip',
    '.out': '.out.zip',
    '.out.log': '.out.zip',
    '.out.overrun': '.out.zip',
}

# https://stackoverflow.com/questions/34447623/wrap-an-open-stream-with-io-textiowrapper
def cat(ramms_spec, ids=list(), ext='.out.log', out_bytes=sys.stdout.buffer):
    out_text = codecs.getwriter('utf-8')(out_bytes)
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        try:
            zip_fname = jb.zip_file(id, arcext2filext[ext])
        except KeyError:
            zip_fname = jb.zip_file(id, '.in.zip')

        with zipfile.ZipFile(zip_fname, 'r') as izip:
            print('======== {}'.format(zip_fname), file=out_text)
            sys.stdout.flush()
            bytes = izip.read(jb.arcname(id, ext))
            out_bytes.write(bytes)

            #os.write(1, bytes)    # 1 = STDOUT
            #with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
            #    stdout.write(bytes)
            #    stdout.flush()

def ls(ramms_spec, ids):
    """List the contenst of the .in.zip and .out.zip files for an id"""
    ret = list()
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        zip_fnames = [jb.zip_file(id, ext) for ext in ('.in.zip', '.out.zip')]
        for zip_fname in zip_fnames:
            if not os.path.exists(zip_fname):
                continue
            with zipfile.ZipFile(zip_fname, 'r') as izip:
                infos = izip.infolist()
                ret += [(jb,id,info) for info in infos]

    return ret


def infos(release_files, ids=None):
    """Provide summary info on one or more completed avalanches"""
    if ids is None:
        ids = set([])
    else:
        ids = set(ids)

    infos = list()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        exist_ids = job_ids(release_file)

        # Get list of ids to inspect
        if len(ids) == 0:
            process_ids = exist_ids
        else:
            process_ids = {x for x in exist_ids if x in ids}


        # Inspect them
        for id in process_ids:
            job_name = f'{jb.ramms_name}_{id}'
            info = {'job_name': job_name, 'id': id}

            # Add info from the logfile (if it exists)
            job_log_zip = f'{job_name}.log.zip'
            try:
                for k,v in parse_aval_log(job_log_zip).items():
                    info[k] = float(v)
#                info = {**info, **parse_aval_log(job_log_zip)}
            except FileNotFoundError:
                pass
            except zipfile.BadZipFile:
                pass

            # Add info from the release file
            rel_file = f'{job_name}.rel'
            try:
                rel = read_polygon(rel_file)
                info['release_area'] = rel.area
            except FileNotFoundError:
                pass

            # Add info from the domain file
            dom_file = f'{job_name}.dom'
            try:
                dom = read_polygon(dom_file)
                info['domain_area'] = dom.area
            except FileNotFoundError:
                pass

            # Find out how much domain and release intersect
            if 'domain_area' in info and 'release_area' in info:
                info['intersect_area'] = dom.intersection(rel).area

            infos.append(info)

    return pd.DataFrame(infos)

