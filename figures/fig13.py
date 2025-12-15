import os,pathlib,subprocess
import cartopy
import numpy as np
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.akse as expmod
from uafgi.util import wrfutil,cartopyutil,gisutil,gdalutil,cptutil
import akfigs
import shapely.geometry

#tif_dir = pathlib.Path('/Users/eafischer2/tmp/maps/tif')

sres = '1000'


def corr2(a,b):
    """Compute correllation between two 2D arrays"""
    mask_in = np.logical_and(
        np.logical_not(np.isnan(a)),
        np.logical_not(np.isnan(b)))
    a1 = a[mask_in]
    b1 = b[mask_in]
    print('a1 shape ', a1.shape)
    return np.corrcoef(a1,b1)




def format_corr(ccf, labels):

    lines = list()
    for j in range(ccf.shape[1]):
        line = [labels[j]]
        for i in range(ccf.shape[0]):
            if i <= j:
                line.append('{:2.0f} \%'.format(100 * ccf[i,j]))
            else:
                line.append('')
        lines.append(' & '.join(line) + '\\\\\n')
        lines.append('\\hline\n')

    return ''.join(lines)

def main():
    # Read the data
    data = dict()
    for return_period in ('30', '300'):
        for years in ('1981-2010', '2031-2060'):
                for stdir,var in (('stats', 'extentfull'), ('stats', 'extent040'), ('stats', 'extent160'), ('stats', 'snowfull')):
                    tif_dir = expmod.root_dir / stdir / 'tif'

                    ifname_tif = tif_dir / f's{sres}' / f'{expmod.name}-ccsm-{years}-lapse-All-{return_period}-{var}-s{sres}.tif'
                    stat_grid, stat_data, stat_nd = gdalutil.read_raster(ifname_tif)
                    stat_data[stat_data == stat_nd] = np.nan
                    if var.startswith('extent'):
                        stat_data *= 100.    # Convert to percent
                    data[(return_period,years, var)] = stat_data


    vals = list(data.values())
    mask_in = np.ones(vals[0].shape)
    for stat_data in data.values():
        mask_in = np.logical_and(mask_in, np.logical_not(np.isnan(stat_data)))

    base_cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
    diff_cmap_snow,_,_ = cptutil.read_cpt('palettes/seismic.cpt', reverse=False)
    diff_cmap,_,_ = cptutil.read_cpt('palettes/green-purple.cpt', reverse=False)
#    abs_cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
    abs_cmap,_,_ = cptutil.read_cpt('palettes/YlOrRd_09.cpt')


    diffs = [
        data[('300', '1981-2010', 'extentfull')] - data[('30', '1981-2010', 'extentfull')],
#        data[('300', '2031-2060', 'extentfull')] - data[('30', '2031-2060', 'extentfull')],
        data[('30', '2031-2060', 'extentfull')] - data[('30', '1981-2010', 'extentfull')],
#        data[('300', '2031-2060', 'extentfull')] - data[('300', '1981-2010', 'extentfull')],

#        data[('300', '1981-2010', 'snowfull')] - data[('30', '1981-2010', 'snowfull')],
#        data[('300', '2031-2060', 'snowfull')] - data[('30', '2031-2060', 'snowfull')],
        data[('30', '2031-2060', 'snowfull')] - data[('30', '1981-2010', 'snowfull')],
#        data[('300', '2031-2060', 'snowfull')] - data[('300', '1981-2010', 'snowfull')],

        ]

    diffs = [x[mask_in] for x in diffs]
    datamat = np.column_stack(diffs)
    ccf = np.corrcoef(datamat.transpose())

    labels = ['Freq', 'Climate', 'snowfull']
    scorr = format_corr(ccf, labels)
    with open('fig13_corr.tex', 'w') as out:
        out.write('\\begin{tabular}{|r|r|r|r|}\n')
        out.write('\\hline\n & ')
        out.write(' & '.join(labels))
        out.write(' \\\\\n')
        out.write('\\hline \\hline\n')
        out.write(scorr)
        out.write('\n\\end{tabular}')


#    return
#    print(ccf)






#    # ==================================================================
#    # Make the inset map
#    map_crs = akfigs.map_crs()
#    imap_extent = akfigs.allalaska_map_extent
#
#    fig,ax = plt.subplots(
#        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
#        figsize=(1.5,1.0))
#    ax.set_extent(imap_extent, crs=map_crs)
#
#    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 6, alpha=1)    # Use level 7 (lower # is coarser)
##    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)
#
#    # The overall bounding box
##    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')
#
#
#    # The original map bounds
#    imap_extent_poly = gisutil.xxyy_to_poly(*imap_extent)
##    x0,x1,y0,y1 = imap_extent
##    imap_extent_poly = shapely.geometry.Polygon([
##            (x0,y0),
##            (x1,y0),
##            (x1,y1),
##            (x0,y1),
##            (x0,y0)])
#    imap_extent_feature = cartopy.feature.ShapelyFeature(imap_extent_poly, map_crs)
#    ax.add_feature(imap_extent_feature, facecolor='none', edgecolor='black', lw=1.0)
#
#    # Outline this map
#    x0,x1,y0,y1 = imap_extent
#    iimap_extent_poly = shapely.geometry.Polygon([
#            (x0,y0),
#            (x1,y0),
#            (x1,y1),
#            (x0,y1),
#            (x0,y0)])
#    imap_extent_feature = cartopy.feature.ShapelyFeature(imap_extent_poly, map_crs)
#    ax.add_feature(imap_extent_feature, facecolor='none', edgecolor='black', lw=2.0)
#
#
#
#    ofname = pathlib.Path('./fig13-inset.png')
#    with akfigs.TrimmedPng(ofname) as tname:
#        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off
#    # ==================================================================



    # Plot the differences
    ticks = [-20, 0, 20]
    ticklabels = ['-20%', '0', '20%']
    plot_fig(stat_grid, data[('300', '1981-2010', 'extentfull')] - data[('30', '1981-2010', 'extentfull')], diff_cmap, -20, 20, 'fig13_1981_300-30.png', ticks, ticklabels)
    plot_fig(stat_grid, data[('300', '2031-2060', 'extentfull')] - data[('30', '2031-2060', 'extentfull')], diff_cmap, -20, 20, 'fig13_2031_300-30.png', ticks, ticklabels)

#    ticks = [-10, 0, 10]
#    ticklabels = ['-10%', '0', '10%']
    ticks = [0]
    ticklabels = ['0']
    plot_fig(stat_grid, data[('30', '2031-2060', 'extentfull')] - data[('30', '1981-2010', 'extentfull')], diff_cmap, -8, 8, 'fig13_2031-1981_30.png', ticks, ticklabels)
    plot_fig(stat_grid, data[('300', '2031-2060', 'extentfull')] - data[('300', '1981-2010', 'extentfull')], diff_cmap, -8, 8, 'fig13_2031-1981_300.png', ticks, ticklabels)

    # Snow difference
    plot_fig(stat_grid, data[('30', '2031-2060', 'snowfull')] - data[('30', '1981-2010', 'snowfull')], diff_cmap_snow, -100, 100, 'fig13_snowdiff.png', [0], ['0'])

    # Baseline
    plot_fig(stat_grid, data[('30', '1981-2010', 'extent040')], abs_cmap, 0., 100, 'fig13_1981_30_extent040_baseline.png', [0,20,40,60,80,100], ['0%', '20', '40', '60', '80', '100%'])
    plot_fig(stat_grid, data[('30', '1981-2010', 'extent160')], abs_cmap, 0., 100, 'fig13_1981_30_extent160_baseline.png', [0,20,40,60,80,100], ['0%', '20', '40', '60', '80', '100%'])




#    # The stat to read
#    stat30_tif = tif_dir / f's{sres}' / f'ak-ccsm-1981-2010-lapse-All-30-extentfull-s{sres}.tif'
#    stat30_grid, stat30_data, stat30_nd = gdalutil.read_raster(stat30_tif)
#
#    stat300_tif = tif_dir / f's{sres}' / f'ak-ccsm-2031-2060-lapse-All-30-extentfull-s{sres}.tif'
#    stat300_grid, stat300_data, stat300_nd = gdalutil.read_raster(stat300_tif)
#
#    stat_data = stat300_data - stat30_data
##    stat_data[stat30_data == stat30_nd] = np.nan
##    stat_data[stat300_data == stat_nd] = np.nan
#
##    stat_data = stat30_data



def plot_fig(stat_grid, stat_data, cmap, vmin, vmax, ofname, ticks, ticklabels):
    if os.path.isfile(ofname):
        return
    tif_dir = expmod.root_dir / 'stats' / 'tif'
    map_crs = akfigs.map_crs()

    map_extent = (320*1000, 1500*1000, 700*1000, 1445*1000)    # xmin, xmax, ymin, ymax; ymin in South
    # map_extent = akfigs.sealaska_map_extent
    print('map_extent ', map_extent)

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(4.,4.))
    ax.set_extent(map_extent, crs=map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # --------------------------------------------------------
    # Add a statistic

    # Land mask controls transparency
    land_tif = tif_dir / f's{sres}' / f'{expmod.name}-ccsm-1981-2010-lapse-All-30-fhcfull-s{sres}.tif'
#f'fhcfull-s{sres}.tif'
    land_grid, land_data, land_nd = gdalutil.read_raster(land_tif)
    land_data[land_data == land_nd] = 0

#    cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
#    stat_data[land_data == 0] = np.nan
    stat_data = np.ma.masked_where(land_data==0, stat_data)    # Create masked array
#    print(stat_data.mask)
#    print(land_data)
#    stat_data[land_data == 0] = np.nan
#    print('nnan ', np.sum(land_data == 0))
#    return
    _vmin = np.nanmin(stat_data)
    _vmax = np.nanmax(stat_data)
    print('vmin vmax ', _vmin, _vmax)
    pcm_stat = ax.pcolormesh(
        stat_grid.centersx, stat_grid.centersy, stat_data,
        #alpha=0.5, rasterized=True,
        rasterized=True,
        transform=map_crs, cmap=cmap, vmin=vmin, vmax=vmax)

    pcm_stat.set_facecolor('yellow')


    # --------------------------------------------------------

    # Cities
    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 6, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=.9, color='black', alpha=0.9),
        only={'Juneau', 'Haines', 'Sitka', 'Cordova', 'Valdez', 'Yakutat'})

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

#    with akfigs.TrimmedPdf(ofname) as tname:
#        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off'

    with akfigs.TrimmedPng(ofname) as tname:
        fig.savefig(tname, dpi=2000, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


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
    with akfigs.TrimmedPdf(ofname_cbar) as tname:
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

main()
