import os,pathlib,subprocess
import cartopy
import numpy as np
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.aksc5c as expmod

import akramms.experiment.aksc5c
import akramms.experiment.aksc5cfut4
from uafgi.util import wrfutil,cartopyutil,gisutil,gdalutil,cptutil
import akfigs
import shapely.geometry

#tif_dir = pathlib.Path('/Users/eafischer2/tmp/maps/tif')

sres = '100'


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

_prefix = {
    'aksc5c': ('aksc5c-ccsm-past', 'past'),
    'aksc5cfut4': ('aksc5cfut4-fut-past', 'fut'),
}

def _main(tdir):

    # Read the DEM
    dem_tif_lr = akfigs.resample_lr(
        expmod, expmod.anchorage_tiles(), tdir,
        vars=['dem'])
    dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)


    def plot_fig(stat_grid, stat_data, cmap, vmin, vmax, ofname, ticks, ticklabels):
        if os.path.isfile(ofname):
            return
        map_crs = akfigs.map_crs()

        # map_extent = (320*1000, 1500*1000, 700*1000, 1445*1000)    # xmin, xmax, ymin, ymax; ymin in South
        # map_extent = akfigs.sealaska_map_extent
        map_extent = akfigs.anchorage_map_extent
        print('map_extent ', map_extent)

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(4.,4.))
        ax.set_extent(map_extent.xxyy, crs=map_crs)

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=dem_grid.extent())

#        ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=0.8)    # Use level 7 (lower # is coarser)
    #    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

        # --------------------------------------------------------
        # Add a statistic

        # Land mask controls transparency
        tif_dir = expmod.root_dir / 'stats' / 'tif'
        land_tif = tif_dir / f's{sres}' / f'{expmod.name}-ccsm-past-sclapse-All-30-fhcfull-s{sres}.tif'
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
            alpha=0.5,
            #alpha=0.5, rasterized=True,
            rasterized=True,
            transform=map_crs, cmap=cmap, vmin=vmin, vmax=vmax)

        pcm_stat.set_facecolor('yellow')


        # --------------------------------------------------------

        # Cities
        akfigs.plot_cities(ax, 'anchorage',
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

        with akfigs.TrimmedPdf(ofname) as tname:
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




    # Read the data
    data = dict()
    for return_period in ('30', '300'):
#        for years in ('past', 'fut-2060'):
#        for years in ('past', ):#'fut-2060'):
        for expmod in (akramms.experiment.aksc5c, akramms.experiment.aksc5cfut4):
            prefix,years = _prefix[expmod.name]
            for stdir,var in (('stats', 'extentfull'), ('stats', 'extent040'), ('stats', 'extent160'), ('stats', 'snowfull')):
                tif_dir = expmod.root_dir / stdir / 'tif'

                ifname_tif = tif_dir / f's{sres}' / f'{prefix}-sclapse-All-{return_period}-{var}-s{sres}.tif'
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
        data[('300', 'past', 'extentfull')] - data[('30', 'past', 'extentfull')],
#        data[('300', 'fut', 'extentfull')] - data[('30', 'fut', 'extentfull')],
        data[('30', 'fut', 'extentfull')] - data[('30', 'past', 'extentfull')],
#        data[('300', 'fut', 'extentfull')] - data[('300', 'past', 'extentfull')],

#        data[('300', 'past', 'snowfull')] - data[('30', 'past', 'snowfull')],
#        data[('300', 'fut', 'snowfull')] - data[('30', 'fut', 'snowfull')],
        data[('30', 'fut', 'snowfull')] - data[('30', 'past', 'snowfull')],
#        data[('300', 'fut', 'snowfull')] - data[('300', 'past', 'snowfull')],

        ]

    diffs = [x[mask_in] for x in diffs]
    datamat = np.column_stack(diffs)
    ccf = np.corrcoef(datamat.transpose())

    labels = ['Freq', 'Climate', 'snowfull']
    scorr = format_corr(ccf, labels)
    with open('stats_corr.tex', 'w') as out:
        out.write('\\begin{tabular}{|r|r|r|r|}\n')
        out.write('\\hline\n & ')
        out.write(' & '.join(labels))
        out.write(' \\\\\n')
        out.write('\\hline \\hline\n')
        out.write(scorr)
        out.write('\n\\end{tabular}')




    # Plot the differences
    ticks = [-20, 0, 20]
    ticklabels = ['-20%', '0', '20%']
    plot_fig(stat_grid, data[('300', 'past', 'extentfull')] - data[('30', 'past', 'extentfull')], diff_cmap, -20, 20, 'stats_past_300-30.pdf', ticks, ticklabels)
    plot_fig(stat_grid, data[('300', 'fut', 'extentfull')] - data[('30', 'fut', 'extentfull')], diff_cmap, -20, 20, 'stats_fut_300-30.pdf', ticks, ticklabels)

#    ticks = [-10, 0, 10]
#    ticklabels = ['-10%', '0', '10%']
    ticks = [0]
    ticklabels = ['0']
    plot_fig(stat_grid, data[('30', 'fut', 'extentfull')] - data[('30', 'past', 'extentfull')], diff_cmap, -8, 8, 'stats_fut-past_30.pdf', ticks, ticklabels)
    plot_fig(stat_grid, data[('300', 'fut', 'extentfull')] - data[('300', 'past', 'extentfull')], diff_cmap, -8, 8, 'stats_fut-past_300.pdf', ticks, ticklabels)

    # Snow difference
    plot_fig(stat_grid, data[('30', 'fut', 'snowfull')] - data[('30', 'past', 'snowfull')], diff_cmap_snow, -100, 100, 'snow_fut-past.pdf', [0], ['0'])

    # Baseline
    plot_fig(stat_grid, data[('30', 'past', 'extent040')], abs_cmap, 0., 100, 'stats_past_30_extent040_baseline.pdf', [0,20,40,60,80,100], ['0%', '20', '40', '60', '80', '100%'])
    plot_fig(stat_grid, data[('30', 'past', 'extent160')], abs_cmap, 0., 100, 'stats_past_30_extent160_baseline.pdf', [0,20,40,60,80,100], ['0%', '20', '40', '60', '80', '100%'])




#    # The stat to read
#    stat30_tif = tif_dir / f's{sres}' / f'ak-ccsm-past-sclapse-All-30-extentfull-s{sres}.tif'
#    stat30_grid, stat30_data, stat30_nd = gdalutil.read_raster(stat30_tif)
#
#    stat300_tif = tif_dir / f's{sres}' / f'ak-ccsm-fut-2060-sclapse-All-30-extentfull-s{sres}.tif'
#    stat300_grid, stat300_data, stat300_nd = gdalutil.read_raster(stat300_tif)
#
#    stat_data = stat300_data - stat30_data
##    stat_data[stat30_data == stat30_nd] = np.nan
##    stat_data[stat300_data == stat_nd] = np.nan
#
##    stat_data = stat30_data







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

    ofname = pathlib.Path('stats-cbar.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off


main()
