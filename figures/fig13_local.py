import os,pathlib,subprocess,functools,sys
import cartopy
import numpy as np
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.akse as expmod
from uafgi.util import wrfutil,cartopyutil,gisutil,gdalutil,cptutil
import akfigs
import shapely.geometry

sres = 100

def plot_fig(stat_grid, stat_data, fhc_data, cmap, vmin, vmax, ofname, ticks, ticklabels, city, map_extent):
    map_crs = akfigs.map_crs()

#    map_extent = (320*1000, 1500*1000, 700*1000, 1445*1000)    # xmin, xmax, ymin, ymax; ymin in South
    # map_extent = akfigs.sealaska_map_extent
    print('setting map_extent ', map_extent)


    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(4.,4.))
    ax.set_extent(map_extent, crs=map_crs)
    print('DONE SETTING EXTENT')

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 11, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # --------------------------------------------------------
    # Add a statistic



#    # Land mask controls transparency
#    tif_dir = expmod.root_dir / 'stats.v1' / 'tif'
#    land_tif = tif_dir / f's{sres}' / f'land-s{sres}.tif'
#    land_grid, land_data, land_nd = gdalutil.read_raster(land_tif)
#    land_data[land_data == land_nd] = 0

#    cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
#    stat_data[land_data == 0] = np.nan
    stat_data = np.ma.masked_where(fhc_data==0, stat_data)    # Create masked array
#    print(stat_data.mask)
#    print(land_data)
#    stat_data[land_data == 0] = np.nan
#    print('nnan ', np.sum(land_data == 0))
#    return
    _vmin = np.nanmin(stat_data)
    _vmax = np.nanmax(stat_data)
    print('vmin vmax ', _vmin, _vmax)
    print('zzzzzzzzzzzz ', len(stat_grid.centersx), len(stat_grid.centersy), stat_data.shape)
    pcm_stat = ax.pcolormesh(
        stat_grid.centersx, stat_grid.centersy, stat_data,
        #alpha=0.5, rasterized=True,
        rasterized=True,
        transform=map_crs, cmap=cmap, vmin=vmin, vmax=vmax)

    pcm_stat.set_facecolor('yellow')


    # --------------------------------------------------------

#    # Cities
#    akfigs.plot_cities(ax,
#        text_kwargs=dict(
#            fontdict = {'size': 8, 'color': 'blue', 'fontweight': 'bold'}),
#        marker_kwargs=dict(
#            marker='*', markersize=2, color='black', alpha=0.9),
#        only={city})
##        only={'Juneau', 'Haines', 'Sitka', 'Cordova', 'Valdez', 'Yakutat'})

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='gray', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}
    gl.xlabels_top = False
    gl.xlabels_bottom = False
    gl.ylabels_right = False
    gl.ylabels_left = False


    # Write it out
    ofname = pathlib.Path(ofname)
    with akfigs.TrimmedPng(ofname) as tname:
        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off
#        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off
#        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

    return    # DEBUG

    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(60/25.4,60/25.4))
    cbar_ax = axs
    cbar = fig.colorbar(pcm_stat, ax=cbar_ax, ticks=ticks)
    labels = cbar.ax.set_yticklabels(ticklabels)
    cbar.ax.tick_params(labelsize=10)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

    bname = ofname.with_suffix('')
    ofname_cbar = bname.parents[0] / (bname.parts[-1] + '-cbar.pdf')
    with akfigs.TrimmedPng(ofname_cbar) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off




def plot_cbar():
    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(100/25.4,100/25.4))
    cbar_ax = axs
    cbar = fig.colorbar(pcm_stat, ax=cbar_ax)#, ticks=[0,100,200,300,400,500,600,700])
#    labels = cbar.ax.set_yticklabels(['0 mm', '100', '200', '300', '400', '500', '600', '>700 mm'])
    cbar.ax.tick_params(labelsize=10)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

    ofname = pathlib.Path('fig13-cbar.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

    # ==================================================================
    # Make the inset map
    imap_extent = akfigs.allalaska_map_extent

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(3.0,2.0))
    ax.set_extent(imap_extent, crs=map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 6, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The overall bounding box
#    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    # The original map bounds
    map_extent_poly = gisutil.xxyy_to_poly(*map_extent)
#    x0,x1,y0,y1 = map_extent
#    map_extent_poly = shapely.geometry.Polygon([
#            (x0,y0),
#            (x1,y0),
#            (x1,y1),
#            (x0,y1),
#            (x0,y0)])
    map_extent_feature = cartopy.feature.ShapelyFeature(map_extent_poly, map_crs)
    ax.add_feature(map_extent_feature, facecolor='none', edgecolor='black', lw=1.0)

    # Outline this map
    x0,x1,y0,y1 = imap_extent
    imap_extent_poly = shapely.geometry.Polygon([
            (x0,y0),
            (x1,y0),
            (x1,y1),
            (x0,y1),
            (x0,y0)])
    imap_extent_feature = cartopy.feature.ShapelyFeature(imap_extent_poly, map_crs)
    ax.add_feature(imap_extent_feature, facecolor='none', edgecolor='black', lw=2.0)



    ofname = pathlib.Path('./fig13-inset.png')
    with akfigs.TrimmedPng(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


@functools.lru_cache()
def read_data(stdir, years, return_period, ijdom, vname):

    if ijdom == 'tif':
        tif_dir = expmod.root_dir / stdir / 'tif'

        ifname_tif = tif_dir / f's{sres}' / f'{expmod.name}-ccsm-{years}-lapse-All-{return_period}-{vname}-s{sres}.tif'
    else:
        idom = ijdom[0]
        jdom = ijdom[1]
        ifname_tif = expmod.root_dir / stdir / 'tiles' / f's{sres}' / f'{expmod.name}-ccsm-{years}-lapse-All-{return_period}' / vname / f'{expmod.name}-ccsm-{years}-lapse-All-{return_period}-{idom:03d}-{jdom:03d}-F-{vname}-s{sres}.tif'


    stat_grid, stat_data, stat_nd = gdalutil.read_raster(ifname_tif)
    stat_data[stat_data == stat_nd] = np.nan
    if vname.startswith('extent'):
        stat_data *= 100.    # Convert to percent
    return stat_grid,stat_data,stat_nd

def read_climate_diff(stdir, return_period, ijdom, vname):
    stat0_grid,stat0_data,stat0_nd = read_data(stdir, '1981-2010', return_period, ijdom, vname)
    stat1_grid,stat1_data,stat1_nd = read_data(stdir, '2031-2060', return_period, ijdom, vname)
    data = stat1_data - stat0_data
    return stat0_grid, data, stat0_nd

def local_extent(idom, jdom, delta_extent, xyres=1000):
    """Computes the map_extent for a local map"""
    tilegrid = expmod.gridD.sub(idom, jdom, xyres, xyres, margin=False)
    map_extent = tilegrid.extent(order='xxyy')    # INCUDES margin

    if delta_extent is not None:
        map_extent = tuple(a+b for a,b in zip(map_extent, delta_extent))
    print('xxxxxxxxxxxxxxxxxxxxxx ', map_extent) 
    return map_extent

map_extents = [
    ('Juneau', 113, 45, (15000, -5000, 5000, -18000)),
    ('Haines', 110, 42, (12000, -5000, 0, -17000))
]

def main2():

    base_cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
    diff_cmap_snow,_,_ = cptutil.read_cpt('palettes/seismic.cpt', reverse=False)
    diff_cmap,_,_ = cptutil.read_cpt('palettes/green-purple.cpt', reverse=False)
    abs_cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')

    for city, idom, jdom, delta_extent in map_extents:

        if idom < 0:
            map_extent = delta_extent
        else:
            tile_grid = expmod.gridD.sub(idom, jdom, 100, 100, margin=False)
            map_extent = tile_grid.extent(order='xxyy')    # INCUDES margin
            map_extent = [a+b for a,b in zip(map_extent, delta_extent)]


        # Main Map


        # Difference Map
        ticks = [-15, 0, 15]
        ticklabels = ['-15%', '0', '15%']
        fhc_grid, fhc_data, fhc_nd = read_data('stats', '1981-2010', 30, (idom,jdom), 'fhc040')
        stat_grid, stat_data, stat_nd = read_climate_diff('stats', 30, (idom,jdom), 'extent040')
        stat_data[np.abs(stat_data) < 0.01] = np.nan
        plot_fig(stat_grid, stat_data, fhc_data, diff_cmap, -15, 15, f'fig13b_1981_300-30-{city}.png',
            ticks, ticklabels, city, map_extent)










# =================================================================================

main2()
