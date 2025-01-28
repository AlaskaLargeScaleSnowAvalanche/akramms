import akramms.experiment.ak as expmod
from akramms import avalstats

def main():

    for combo in [
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'All', 30, 125,54)]:
        for res in (100, 1000, 10000):
            for vname in avalstats.stats_vars:
                avalstats.regrid_stdmosaic(expmod, combo, vname, res)

main()
