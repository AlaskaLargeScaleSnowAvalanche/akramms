#1. Filename of existing arc-file: keep
#2. Filename of x-file: determine arc-dir, convert to arc-file
#3. experiment directory + combo: list all x- and arc-, then filter further










        if os.path.isfile(arc_fname):
            yield arc_fname

        # Try to convert from the original file
        for out_zip in globs:
            basename = out_zip[:-8]    # Remove .out.zip
            if out_zip_status(basename) in ok_statuses:
                ramms_to_nc0(basename, arc_fname)
                yield arc_fname

        yield None



# -----------------------------------------------------------------



# -----------------------------------------------------------------
out_zipRE = re.compile(r'(.*)_(\d+)\.out\.zip$')
_rammsdirRE = re.compile(r'(x|arc)-(.*)')
def nc_name(out_zip):
    """Given a .out.zip file, returns the corresponding arc-xxx-xxx.nc file."""

    # Chop 6 levels off of arg (the filename) to result in an
    # x-ddd-ddd RAMMS directory name.
    x_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(out_zip))))))   $ Eg: .../x-113-045
    x_dir_dir,x_dir_leaf = os.path.split(x_dir)
    match = _rammsdirRE.match(x_dir_leaf)    # Eg: x-113-045
    arc_dir = os.path.join(x_dir_dir, 'arc-' + match.group(2))  # Eg: .../arc-113-045

    # Determine the avalanche ID of this file
    match = out_zipRE.match(os.path.basename(out_zip))   # Eg: x-113-04500000For_10m_30L_2019.out.zip
    aval_id = int(match.group(2))
    return os.path.join(arc_dir, f'aval-{aval_id}.nc')


# -----------------------------------------------------------------
AvalFile = collections.namedtuple('AvalFile',
    ('id', 'fname', 'status'))

def list_unarchived(scene_dir):
    """
    scene_dir:
        Raw scene directory.  Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-026
    """

    for out_zip in glob.iglob(os.path.join(scene_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):

        # If HTCondor is in the middle of writing the .out.zip file,
        # it will have zero length.
        if not r_ramms.file_is_good(out_zip):
            continue

        # Get the avalanche ID
        out_zip_leaf = os.path.split(out_zip)[1]
        match = _out_zipRE.match(out_zip_leaf)
        id = int(match.group(2))

        yield AvalFile(id, out_zip, out_zip_status(out_zip))




avalRE = re.compile(r'aval-(\d+)\.nc')
def list_unarchived(arc_dir):
    """
    scene_dir:
        Achived scene directory.  Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-026
    """

    for name in os.listdir(arc_dir):
        match = avalRE.match(name)
        if match is not None:
            id = int(match.group(1))
            fname = os.path.join(arc_dir, name)
            yield AvalFile(id, fname, ARCHIVED)





# Ways to query the Avalanche database

out_zipRE = re.compile(r'(.*)_(\d+)\.out\.zip$')
_rammsdirRE = re.compile(r'(x|arc)-(.*)')
def _parse_arg(arg, aval_files):
    if os.path.isfile(arg):
        # It's the avalanche file, just use it
        if arg.endswith('.nc'):
            # Use directly.
            # No assumptions about directory structure this is sitting within.
            aval_files.append(os.path.abspath(os.path.realpath(arg)))
        elif arg.endswith('.out.zip'):
            # Must first convert to .nc
            # Assume it's within an x-ddd-ddd folder, and needs to be archived into arc-ddd-ddd
            out_zip_fname = arg

            # Chop 6 levels off of arg (the filename) to result in an
            # x-ddd-ddd RAMMS directory name.
            x_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(out_zip_fname))))))   $ Eg: .../x-113-045
            x_dir_dir,x_dir_leaf = os.path.split(x_dir)
            match = _rammsdirRE.match(x_dir_leaf)    # Eg: x-113-045
            arc_dir = os.path.join(x_dir_dir, 'arc-' + match.group(2))  # Eg: .../arc-113-045

            # Determine the avalanche ID of this file
            match = out_zipRE.match(os.path.basename(out_zip_fname))   # Eg: x-113-04500000For_10m_30L_2019.out.zip
            aval_id = int(match.group(2))
            arc_fname = os.path.join(arc_dir, f'aval-{aval_id}.nc')

            archive.archive_avalanche(out_zip_fname, arc_fname)
1



            x_fname = os.path.abspath(os.path.realpath(arg))
            x_dir,x_leaf = os.path.split(x_fname)
            x_dir_dir,x_dir_leaf = os.path.split(x_dir)
            arc_dir = os.path.join(x_dir_dir, 'arc-' + x_dir_leaf[2:])
            arc_leaf = 
            
            return os.path.abspath(os.path.realpath(arg))



    if (os.sep in arg) or os.path.isdir(arg):

        # One of either:
        #    .../ak_ccsm_1981_1990_lapse_For_30/x-113-045
        #    .../ak_ccsm_1981_1990_lapse_For_30/arc-113-045
        #    .../ak_ccsm_1981_1990_lapse_For_30

        parts = arg.split(os.sep)
        match = _rammsdirRE.match(parts[-1])
        if match is not None:
            #    Assume .../ak_ccsm_1981_1990_lapse_For_30/x-113-045
            return parts[-2].split('-') + match.group(2).split('-')
        else:
            #    Assume .../ak_ccsm_1981_1990_lapse_For_30
            return parts[-1].split('-')
    else:
        # Assume it's some random string with either space or skewer separator
        return re.split('-|\s', x)




def parse_combo(exp_mod, args)
    """Parses combo elements obtained from a filename, command line or elsewhere.
    args:
        Combo elements.  Space separated (as separate args), or
        underscore-separated in the same arg.



def single(
