import os,subprocess
import shapely.geometry
from osgeo import ogr
from akramms import config
from uafgi.util import shputil
import numpy as np
import pandas as pd
from akramms import params

# Compute the differen scenes across the state of Alaska
def write_scene_domains(ofname):
    if os.path.exists(ofname):
        print(f'Scenes file already created: {ofname}')
        return
    print(f'Creating scenes file {ofname}')

    ofname_margin = os.path.splitext(ofname)[0] + '_margin.shp'

    scene_size = (20000., 20000.)   # 50km^2
    scene_margin = (2000,2000)    # 10km margin


    # ---------------------------------------------------
    # Load the Alaska domain shapefile
    print('Loading SE Alaska shapefile')
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
    print('Loading overall Alaska shapefile')
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
    rows_margin = list()
    for iy in range(len(ypoints)-1):
        for ix in range(len(xpoints)-1):
            coords = [
                (xpoints[ix], ypoints[iy]),
                (xpoints[ix+1], ypoints[iy]),
                (xpoints[ix+1], ypoints[iy+1]),
                (xpoints[ix], ypoints[iy+1]),
                (xpoints[ix], ypoints[iy]),
            ]
            poly = shapely.geometry.Polygon(coords)
            coords_margin = [
                (xpoints[ix]-xmarg, ypoints[iy]-ymarg),
                (xpoints[ix+1]+xmarg, ypoints[iy]-ymarg),
                (xpoints[ix+1]+xmarg, ypoints[iy+1]+ymarg),
                (xpoints[ix]-xmarg, ypoints[iy+1]+ymarg),
                (xpoints[ix]-xmarg, ypoints[iy]-ymarg),
            ]
            poly_margin = shapely.geometry.Polygon(coords_margin)
            if poly.intersects(avdomain):
                rows.append((ix,iy,poly))
                rows_margin.append((ix,iy,poly_margin))

    wkt=params.DEFAULTS['alaska']['coordinate_system']
    df = pd.DataFrame(rows, columns=('ix', 'iy', 'domain'))
    shputil.write_df(df, 'domain', 'Polygon', ofname, wkt=wkt)
    df_margin = pd.DataFrame(rows_margin, columns=('ix', 'iy', 'domain'))
    shputil.write_df(df_margin, 'domain', 'Polygon', ofname_margin, wkt=wkt)


    # Try gdal_translate on one local area
    row = df[(df.ix==71) & (df.iy==10)]
    print(row)



def main():
    scenes_file = 'scene_domains.shp'
    write_scene_domains(scenes_file)

    # Select out one domain
    pd = shputil.read_df(scenes_file).set_ix(['index','iy'])
    row = pd.loc[180,24]
    print(row)

    # x0 and x1 will always be less than y0 and y1 because the polygon
    # is always counter clockwise.

    xx,yy = row['shape'].exterior.coords.xy
    print('xx ', xx)
    print('yy ', yy)
    x0 = xx[0]
    x1 = xx[2]
    y0 = yy[0]
    y1 = yy[2]

    print('deltax ', x1-x0)
    print('deltay ', y1-y0)
    ifsar_vrt = config.roots.syspath('{DATA}/fischer/ifsar_DTM.vrt')
    cmd = ['gdal_translate']
    # https://gis.stackexchange.com/questions/1104/should-gdal-be-set-to-produce-geotiff-files-with-compression-which-algorithm-sh
    cmd += ['-co', 'COMPRESS=DEFLATE']
    cmd += ['-eco']    # Error when completely outside (SANITY CHECK)
    cmd += ['-projwin', str(x0), str(y1), str(x1), str(y0), ifsar_vrt, 'xdtm.tif']    # North-up
    print(cmd)
    subprocess.run(cmd, check=True)

main()
