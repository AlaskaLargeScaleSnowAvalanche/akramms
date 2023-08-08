import shapely.geometry
from osgeo import ogr
from akramms import config
from uafgi.util import shputil
import numpy as np
import pandas as pd
from akramms import params

# Compute the differen scenes across the state of Alaska
def def write_scene_domins(ofname):
    if os.path.exists(ofname):
        print(f'Scenes file already created: {ofname}')
        return
    print(f'Creating scenes file {ofname}')

    scene_size = (50000., 50000.)   # 50km^2
    scene_margin = (10000,10000)    # 10km margin


    # ---------------------------------------------------
    # Load the Alaska domain shapefile
    avdomain_zip = config.roots.syspath('{DATA}/wolken/SE_AK_Domain_Land.zip')

    driver = ogr.GetDriverByName('ESRI Shapefile')
    src_ds = driver.Open(f'/vsizip/{avdomain_zip}/SE_AK_Domain_Land.shp')
    src_lyr = src_ds.GetLayer()   # Put layer number or name in her
    while True:
        feature = src_lyr.GetNextFeature()
#        print(feature)
        if feature is None:
            break

        geom = feature.GetGeometryRef()
#        geom.Transform(osr_transform)    # No need for coord transform
        polygons = list()
        npoly = geom.GetGeometryCount()
#        npoly = 3
        for ix in range(npoly):
            ring = geom.GetGeometryRef(ix).GetGeometryRef(0)
            npoints = ring.GetPointCount()
#            print('rrr ', type(ring), ring, npoints)
            points = list()
            for p in range(0,npoints):
                x,y,z = ring.GetPoint(p)
                points.append(shapely.geometry.Point(x,y))
            polygons.append(shapely.geometry.Polygon(points))
#        print('xxxxxxxxxx ', pointss)
        avdomain = shapely.geometry.MultiPolygon(polygons)
    # ---------------------------------------------------


    # Load the overall Alaska shapefile
    all_alaska_zip = config.roots.syspath('{DATA}/fischer/AlaskaBounds.shp')
    all_alaska = list(shputil.read(all_alaska_zip))[0]['_shape']
    print(all_alaska)
    alaska_bounds = all_alaska.envelope    # Smallest rectangle with sides oriented to axes
    print(alaska_bounds)
    xx,yy = alaska_bounds.exterior.coords.xy
    #print(xx)
    #print(yy)
    x0 = xx[0]
    x1 = xx[1]
    y0 = yy[0]
    y1 = yy[2]

    # Ends of each rectangle (not including margin)
    xsgn = np.sign(x1-x0)
    ysgn = np.sign(y1-y0)
    xpoints = list(np.arange(x0,x1,xsgn*scene_size[0])) + [x1]
    ypoints = list(np.arange(y0,y1,ysgn*scene_size[1])) + [y1]

    xmarg = scene_margin[0]*xsgn
    ymarg = scene_margin[1]*ysgn
    rows = list()
    for iy in range(len(ypoints)-1):
        for ix in range(len(xpoints)-1):
            coords = [
                (xpoints[ix]-xmarg, ypoints[iy]-ymarg),
                (xpoints[ix+1]+xmarg, ypoints[iy]-ymarg),
                (xpoints[ix+1]+xmarg, ypoints[iy+1]+ymarg),
                (xpoints[ix]-xmarg, ypoints[iy+1]+ymarg),
                (xpoints[ix]-xmarg, ypoints[iy]-ymarg),
            ]
            poly = shapely.geometry.Polygon(coords)
            if poly.intersects(avdomain):
                rows.append((ix,iy,poly))

    df = pd.DataFrame(rows, columns=('ix', 'iy', 'domain'))
    wkt=params.DEFAULTS['alaska']['coordinate_system']
    shputil.write_df(df, 'domain', 'Polygon', ofname, wkt=wkt)


    # Try gdal_translate on one local area
    row = df[(df.ix==71) & (df.iy==10)]
    print(row)



def main():
    scenes_file = 'scene_domains.shp'
    write_scene_domains(scenes_file)


    pd = shputil.read_df(scenes_file).set_index(['ix','iy'])
    row = pd.loc([71,10])
    print(row)


main()
