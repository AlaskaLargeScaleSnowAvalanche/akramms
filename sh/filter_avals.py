import pandas as pd
import geopandas
import akramms.experiment.akse as expmod
from akramms import archive,extent

combos = [
    expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 113, 45),
    expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 113, 45)]


def main():
    reldfs = list()
    extdfs = list()
    for combo in combos:
        arcdir = expmod.combo_to_scenedir(combo, 'arc')
        reldf = archive.read_reldom(arcdir / 'RELEASE.zip', 'rel', read_shapes=False)
        extent_gpkg = extent.extent_fname(expmod, combo, 'christen')
        print('xxx ', extent_gpkg)
        extdf = geopandas.read_file(str(extent_gpkg))
        extdf = extdf.drop('Mean_DEM', axis=1)
        extdf = extdf.merge(reldf, on='Id')

        print(reldf.columns)
        print(extdf.columns)

        print(len(reldf))
        print(len(extdf))

        extdf = extdf[extdf.Mean_DEM < 200]
        print(len(extdf))




        return

main()

