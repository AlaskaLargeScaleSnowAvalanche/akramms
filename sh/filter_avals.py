import os,pathlib
import pandas as pd
import geopandas
import akramms.experiment.akse as expmod
from akramms import archive,extent

odir = pathlib.Path(os.environ['HOME']) / 'tmp' / 'filter'
os.makedirs(odir, exist_ok=True)


comboss = [
    ('juneau', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 113, 45),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 113, 45))),
    ('cordova', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 91, 41),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 91, 41))),
    ('valdez', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 89, 39),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 89, 39))),
]


def main():
    for name,combos in comboss:
        print(f'================== {name}')
        reldfs = list()
        extdfs = list()
        for combo in combos:
            arcdir = expmod.combo_to_scenedir(combo, 'arc')
            reldfs.append(archive.read_reldom(arcdir / 'RELEASE.zip', 'rel', read_shapes=False))
            extent_gpkg = extent.extent_fname(expmod, combo, 'christen')
            extdfs.append(geopandas.read_file(str(extent_gpkg)))
        reldf = pd.concat(reldfs)
        extdf = pd.concat(extdfs)


        # Merge the two
        df = geopandas.GeoDataFrame(extdf.drop('Mean_DEM', axis=1).merge(reldf.drop('geometry',axis=1), on='Id'))

        # Separate
        df = df[df['Mean_DEM'] < 300]
        keep = (((df.rel_n41 + df.rel_n43) / df.rel_n) < 0.3)
        df_include = df[keep]
        df_exclude = df[~keep]

        # Show it...
        cols = ['Id', 'rel_n', 'rel_n41', 'rel_n43', 'ext_n', 'ext_n41', 'ext_n43']
        print(f'================== {name}')
        print('-------- include')
        print(df_include[cols])
        print('-------- exclude')
        print(df_exclude[cols])

        df_include.to_file(odir / f'{name}_include.gpkg', driver='GPKG')
        df_exclude.to_file(odir / f'{name}_exclude.gpkg', driver='GPKG')

main()

