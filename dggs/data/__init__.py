import os

#HARNESS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

#HARNESS_WINDOWS = r'C:\Users\{}\av'.format(os.environ['USER'])
#HARNESS_WINDOWS = r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\av'


# Convenience function
#def join(*path):
#    return os.path.join(HARNESS, *path)


# Standard Projections
grs1980_wkt = epsg4019_wkt = \
"""GEOGCS["Unknown datum based upon the GRS 1980 ellipsoid",
    DATUM["Not_specified_based_on_GRS_1980_ellipsoid",
        SPHEROID["GRS 1980",6378137,298.257222101,
            AUTHORITY["EPSG","7019"]],
        AUTHORITY["EPSG","6019"]],
    PRIMEM["Greenwich",0,
        AUTHORITY["EPSG","8901"]],
    UNIT["degree",0.01745329251994328,
        AUTHORITY["EPSG","9122"]],
    AUTHORITY["EPSG","4019"]]"""

# https://spatialreference.org/ref/sr-org/epsg3857/proj4/
# We are LIKE EPSG 3857; except WRF uses radius of 6370000m
#    EPSG 3857: https://spatialreference.org/ref/sr-org/epsg3857/proj4/
#    WRF Radius: https://github.com/Unidata/thredds/issues/753
ll_spherical_wkt = \
"""GEOGCS["Unknown datum based upon the GRS 1980 ellipsoid",
    DATUM["Not_specified_based_on_GRS_1980_ellipsoid",
        SPHEROID["GRS 1980",6370000,0,
            AUTHORITY["EPSG","7019"]],
        AUTHORITY["EPSG","6019"]],
    PRIMEM["Greenwich",0,
        AUTHORITY["EPSG","8901"]],
    UNIT["degree",0.01745329251994328,
        AUTHORITY["EPSG","9122"]],
    AUTHORITY["EPSG","4019"]]"""
