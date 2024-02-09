import io,os
import numpy as np
import matplotlib
import cartopy
from uafgi.util import cartopyutil,gdalutil,cptutil
from akramms import config
import cartopy.io.img_tiles
import urllib.request
import PIL
import matplotlib.pyplot as plt

PALETTES = config.HARNESS / 'akramms' / 'palettes'
OSM_DIR = config.HARNESS / 'data' / 'openstreetmap'

# https://www.theurbanist.com.au/2021/03/plotting-openstreetmap-images-with-cartopy/
def image_spoof(self, tile):
    '''this function reformats web requests from OSM for cartopy
    Heavily based on code by Joshua Hrisko at:
        https://makersportal.com/blog/2020/4/24/geographic-visualizations-in-python-with-cartopy'''

    leaf = 'osmtile-{}.png'.format('-'.join(str(x) for x in tile))
    img_file = OSM_DIR / leaf

    if os.path.exists(img_file):
        print(f'OSM Reading existing tile: {img_file}')
        img = PIL.Image.open(img_file)
#        with open(img_file, 'rb') as fin:
#            img = PIL.Image.open(fin)
    else:
        print(f'OSM Writing new tile: {img_file}')
        url = self._image_url(tile)                # get the url of the street map API
        req = urllib.request.Request(url)                         # start request
        req.add_header('User-agent','Anaconda 3')  # add user agent to request
        fh = urllib.request.urlopen(req)

        data = fh.read()
        fh.close()                                 # close url

        # Store it away
        os.makedirs(img_file.parents[0], exist_ok=True)
        with open(img_file, 'wb') as out:
            out.write(data)

        im_data = io.BytesIO(data)            # get image
        img = PIL.Image.open(im_data)                  # open image with PIL

    img = img.convert(self.desired_tile_form)  # set image format
    return img, self.tileextent(tile), 'lower' # reformat for cartopy


def plot_reference_map(mosaic_zip):
    """
    mosaic_zip:
        Name of the Mosaic .zip file prepared by AKRAMMS
    """

    fig = matplotlib.pyplot.figure(figsize=(6.5,6.5))

    mapinfo = cartopyutil.raster_mapinfo((mosaic_zip, 'dem.tif'))

    # Set up the basemap
    ax = fig.add_axes((.1,.1,.9,.86), projection=mapinfo.crs)
    #ax.set_facecolor('xkcd:light grey')    # https://xkcd.com/color/rgb/
    ax.set_facecolor('#E0E0E0')    # Map background https://xkcd.com/color/rgb/

    ax.set_extent(mapinfo.extents, crs=mapinfo.crs)
    ax.coastlines(resolution='50m')


    # -------- Plot the DEM
    if False:
        dem = gdalutil.read_raster((mosaic_zip, 'dem.tif'))
        dem_data = np.flipud(dem.data)
        cmap,_,_ = cptutil.read_cpt(PALETTES/'usgs-feet.cpt', scale=0.3048) # Convert ft->m

        pcm = ax.pcolormesh(
            dem.grid.centersx, dem.grid.centersy, dem_data, transform=mapinfo.crs,
            cmap=cmap, alpha=0.5)#, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1])

    # Hillshaded DEM
    # https://www.geophysique.be/2014/02/25/shaded-relief-map-in-python/
    # See Step 3...
    if True:
        dem = gdalutil.read_raster((mosaic_zip, 'dem.tif'))
        dem_data = np.flipud(dem.data)
        x,y = np.gradient(dem_data)
        slope = np.pi/2. - np.arctan(np.sqrt(x*x + y*y))

        # -x here because of pixel orders in the SRTM tile
        aspect = np.arctan2(-x, y)

        altitude = np.pi / 4.
        azimuth = np.pi / 2.

        shaded = np.sin(altitude) * np.sin(slope)\
            + np.cos(altitude) * np.cos(slope)\
            * np.cos((azimuth - np.pi/2.) - aspect)
        plt.imshow(shaded, extent=mapinfo.extents, transform=mapinfo.crs,
            cmap='Greys')


#        shaded_dem = cartopy.io.PostprocessedRasterSource(
#
#        ax.add_raster(shaded_dem, cmap='Greys')

    # -------- Plot max_height
    if True:
        max_height = gdalutil.read_raster((mosaic_zip, 'max_height.tif'))
        data = max_height.data
        dem = np.flipud(data)
        data[data==max_height.nodata] = np.nan
        data[data>1] = np.nan
#        data[data<.2] = np.nan    # Cutoff at 10cm max depth

#        data = np.log(data)
#        vmin = np.nanmin(data)
#        vmax = np.nanmax(data)
#        print('vmax ', vmax)
        pcm = ax.pcolormesh(
            max_height.grid.centersx, max_height.grid.centersy, max_height.data, transform=mapinfo.crs, vmin=0, vmax=5)
    #        cmap=cmap)#, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1])


    # ---------  Add OpenStreetMap stuff
    # https://www.theurbanist.com.au/2021/03/plotting-openstreetmap-images-with-cartopy/
    if True:
        cartopy.io.img_tiles.OSM.get_image = image_spoof # reformat web request for street map spoofing
        img = cartopy.io.img_tiles.OSM() # spoofed, downloaded street map.  Contains img.crs
    #    stroke = [pe.Stroke(linewidth=1, foreground='w'), pe.Normal()]

        # or change scale manually
        # NOTE: scale specifications should be selected based on radius
        # but be careful not have both large scale (>16) and large radius (>1000), 
        #  it is forbidden under [OSM policies](https://operations.osmfoundation.org/policies/tiles/)
        # -- 2     = coarse image, select for worldwide or continental scales
        # -- 4-6   = medium coarseness, select for countries and larger states
        # -- 6-10  = medium fineness, select for smaller states, regions, and cities
        # -- 10-12 = fine image, select for city boundaries and zip codes
        # -- 14+   = extremely fine image, select for roads, blocks, buildings
        print('xxxxxxxxxxxxxx ', type(img))
        scale = 10
        ax.add_image(img, scale, alpha=0.5) # add OSM with zoom specification


    # ---------- Add Hillshaded DEM



    # ---------- Add lat/lon gridlines.  (We really should do x/y gridlines?)
    # It cannot label gridlines in the normal way with EqualAlbers
    # https://www.theurbanist.com.au/2021/03/plotting-openstreetmap-images-with-cartopy/
#    gl = ax.gridlines(draw_labels=True, crs=mapinfo.crs,
#                        color='k',lw=0.5)
#
#    gl.top_labels = False
#    gl.right_labels = False
#    gl.xformatter = cartopy.mpl.gridliner.LONGITUDE_FORMATTER
#    gl.yformatter = cartopy.mpl.gridliner.LATITUDE_FORMATTER



    fig.savefig('x.png', dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

#    # Plot depth in the fjord
#    fjord_gd = bedmachine.get_fjord_gd(bedmachine_file, selrow.fj_poly)
#    fjord = np.flip(fjord_gd, axis=0)
#    bedm = np.ma.masked_where(np.logical_not(fjord), bed)
#
#    bui_range = (0.,350.)
#    cmap,_,_ = cptutil.read_cpt('palettes/Blues_09a.cpt')
#
#    pcm = ax.pcolormesh(
#        xx, yy, bedm, transform=mapinfo.crs,
#        cmap=cmap, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1])
#    if not pub:
#        cbar = fig.colorbar(pcm, ax=ax)
#        cbar.set_label('Fjord Bathymetry (m)')
###    plot_reference_cbar(pcm, 'refmap_cbar.png')
#
#    # Plot the termini
#    date_termini = sorted(selrow.w21t_date_termini)
#
#    yy = [dtutil.year_fraction(dt) for dt,_ in date_termini]
#    year_termini = [(y,t) for y,(_,t) in zip(yy, date_termini) if y > 2000]
#
#    norm = matplotlib.colors.Normalize(vmin=1980, vmax=2020, clip=True)
#    mapper = matplotlib.cm.ScalarMappable(norm=norm, cmap=sigma_by_velyear_cmap)
#    edgecolor = 'red'    # Default
#    for year,term in year_termini:
#        edgecolor = mapper.to_rgba(year)
#        ax.add_geometries([term], crs=mapinfo.crs, edgecolor=edgecolor, facecolor='none', alpha=.8)
#
#    bounds = date_termini[0][1].bounds
#    for _,term in date_termini:
#        bounds = (
#            min(bounds[0],term.bounds[0]),
#            min(bounds[1],term.bounds[1]),
#            max(bounds[2],term.bounds[2]),
#            max(bounds[3],term.bounds[3]))
#    x0,y0,x1,y1 = bounds
#    ax.set_extent(extents=(x0-5000,x1+5000,y0-5000,y1+5000), crs=mapinfo.crs)
#
#    # Plot scale in km
#    cartopyutil.add_osgb_scalebar(ax, at_y='top' if selrow.w21t_Glacier in _top_scales else 'bottom') #, at_y=(0.10, 0.080))
#
#    # Add an arrow showing ice flow
#    dir = selrow.ns481_grid[0]
#    if dir == 'E':
#        coords = (.5,.05,.45,0)
#    else:    # 'W'
#        coords = (.95,.05,-.45,0)
#    arrow = ax.arrow(
#        *coords, transform=ax.transAxes,
#        head_width=.03, ec='black', length_includes_head=True,
#        shape='full', overhang=1,
#        label='Direction of Ice Flow')
#    ax.annotate('Ice Flow', xy=(.725, .07), xycoords='axes fraction', size=14, ha='center')
#


def main():

    mosaic_zip = '/Users/eafischer2/tmp/maps/ak-ccsm-1981-1990-lapse-For-100-109-42-F.zip'
    plot_reference_map(mosaic_zip)

#    dem = gdalutil.read_raster(f'/vsizip/{mosaic_zip}/dem.tif')
##    print(dem.grid.wkt)
#    map_crs = cartopyutil.crs(dem.grid.wkt)
#    print(map_crs)

main()


