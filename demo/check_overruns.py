import pathlib,re,os
from akramms import archive

prj = pathlib.Path('/home/efischer/prj/ak')
dem_mask_tif = prj / 'dem' / 'ak_dem_111_042_mask.tif'
avaldir = prj / 'ak-ccsm-1981-1990-lapse-For-30/x-111-042/CHUNKS/c-M-00000/RESULTS/c-M-00000For_10m/30M'

ids = (2432, 3255)


baseRE = re.compile(r'c-M-(\d+)For_10m_30M_(\d+).out.zip')
def main():

    ids = list()
    for name in os.listdir(avaldir):
        match = baseRE.match(name)
        if match is None:
            continue
        ids.append(int(match.group(2)))

    print('ids ', ids)

    check_overruns = archive.OverrunChecker(dem_mask_tif)
    for id in ids:
        base_leaf = f'c-M-00000For_10m_30M_{id}'
        in_zip = avaldir / (base_leaf + '.in.zip')
        out_zip = avaldir / (base_leaf + '.out.zip')

        is_overrun = check_overruns.is_overrun(in_zip, out_zip)

        if is_overrun:
            print(f'{base_leaf}: {is_overrun}')

main()
