import pathlib
from akramms import joblib

prj = pathlib.Path('/home/efischer/prj/ak')
dem_mask_tif = prj / 'dem' / 'ak_dem_111_042_mask.tif'
avaldir = prj / 'ak-ccsm-1981-1990-lapse-For-30/x-111-042/CHUNKS/c-M-00000/RESULTS/c-M-00000For_10m/30M'

ids = (2423, 3255)


def main():
    check_overruns = joblib.OverrunChecker(dem_mask_tif)
    for id in ids:
        base_leaf = f'c-M-00000For_10m_30M_{id}'
        in_zip = avaldir / (base_leaf + '.in.zip')
        out_zip = avaldir / (base_leaf + '.out.zip')

        is_overrun = check_overruns.is_overrun(in_zip, out_zip)

        print(f'{base_leaf}: {is_overrun}')

main()
