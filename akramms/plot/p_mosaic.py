import string,subprocess,typing,pathlib
import io,os
import numpy as np
import matplotlib
import cartopy
from uafgi.util import cartopyutil,gdalutil,cptutil,openstreetmap,ioutil
from akramms import config
import cartopy.io.img_tiles
import matplotlib.pyplot as plt
import akramms.parse

PALETTES = config.HARNESS / 'akramms' / 'palettes'
OSM_DIR = config.HARNESS / 'data' / 'openstreetmap'

def parse_mosaic_zip(mosaic_zip):
    """Extracts info from name of a mosaic zip file"""
    scombo = mosaic_zip.parts[-1][:-4].split(',')
    info = akramms.parse.parse_parts(scombo, load=False)
    info['mosaic_zip'] = mosaic_zip
    return info

# ---------------------------------------------------------------------
class ColorBar(typing.NamedTuple):
    name: str
    cmap: object
    vmin: float
    vmax: float
    ticks: list        # [0, .5, 1, 5, 10, 15]
    labels: list        # ['0', '', '1', '5m', '10m', '']


def plot_cbar(cbar, ofname):

#    if os.path.isfile(ofname):
#        return

    fig = matplotlib.pyplot.figure(figsize=(4,0.4))

    #cmap,_,_ = cptutil.read_cpt(PALETTES/'max_height.cpt')
    norm = matplotlib.colors.Normalize(vmin=cbar.vmin, vmax=cbar.vmax, clip=True)
    ax = fig.add_axes((.1,.6,.8,.35))    # (left,bottom,width,height) of new Axes as fraction of figure width and height

    # Plot colorbar
    cb1 = matplotlib.colorbar.ColorbarBase(
        ax, cmap=cbar.cmap, norm=norm,
        orientation='horizontal')
    cb1.ax.tick_params(labelsize=10)
    cb1.set_ticks(
        ticks=cbar.ticks, #[0, .5, 1, 5, 10, 15],
        labels=cbar.labels) #['0', '', '1', '5m', '10m', ''])

    with TrimmedPng(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

# ---------------------------------------------------------------------

# =========================================================================
class LayerArgs(typing.NamedTuple):
    ax: object
    mosaic_zip: pathlib.Path
    mapinfo: object
    fast: bool

# ---------------------------------------------------------------------
def plot_dem_layer(args, hillshade=True):

    # -------- Plot the DEM

    # Hillshaded DEM
    # https://www.geophysique.be/2014/02/25/shaded-relief-map-in-python/
    # See Step 3...
    if hillshade:
        dem = gdalutil.read_raster((args.mosaic_zip, 'dem.tif'))
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
        return plt.imshow(shaded, extent=args.mapinfo.extents, transform=args.mapinfo.crs,
            cmap='Greys')

    else:
        # Plot with colors
        dem = gdalutil.read_raster((args.mosaic_zip, 'dem.tif'))
        dem_data = np.flipud(dem.data)
        cmap,_,_ = cptutil.read_cpt(PALETTES/'usgs-feet.cpt', scale=0.3048) # Convert ft->m

        pcm = args.ax.pcolormesh(
            dem.grid.centersx, dem.grid.centersy, dem_data, transform=args.mapinfo.crs,
            cmap=cmap, alpha=0.5)#, vmin=ELEV_RANGE[0], vmax=ELEV_RANGE[1])

        return pcm

# ---------------------------------------------------------------------
def plot_max_height_layer(args):

    cmap,_,_ = cptutil.read_cpt(PALETTES/'max_height.cpt')
    cbar = ColorBar('max_height', cmap, 0, 15, [0, .5, 1, 5, 10, 15], ['0', '', '1', '5m', '10m', ''])

    max_height = gdalutil.read_raster((args.mosaic_zip, 'max_height.tif'))
    data = max_height.data
    data[data==max_height.nodata] = np.nan

    # Smooth alpha
    if not args.fast:
        #alpha = data / 20. + .5
        #alpha[np.isnan(alpha)] = 0    # Fully transparent
        #alpha[alpha>1] = 1.0

        # Make just the green with low alpha, all else has alpha=1
        alpha = np.zeros(data.shape, dtype='d') + 1
        alpha[data < 1] = .5
        alpha[data < 0.5] = .3

    pcm = args.ax.pcolormesh(
        max_height.grid.centersx, max_height.grid.centersy, data,
        transform=args.mapinfo.crs, cmap=cmap,
        alpha=.5 if args.fast else alpha)
    return pcm,cbar

def plot_max_pressure_layer(args):

    cmap,_,_ = cptutil.read_cpt(PALETTES/'max_pressure.cpt')
    cbar = ColorBar('max_pressure', cmap, 0, 300,
        [0,60,120,180,240,300], ['0', '60', '120', '180', '240 kPa', ''])

    max_pressure = gdalutil.read_raster((args.mosaic_zip, 'max_pressure.tif'))    # Already in kPa
    data = max_pressure.data
#    data = max_pressure.data * .001    # Convert [Pa] -> [kPa]
    print(f'max_pressure range: {np.min(data)}, {np.max(data)}')
    data[data==max_pressure.nodata] = np.nan

    pcm = args.ax.pcolormesh(
        max_pressure.grid.centersx, max_pressure.grid.centersy, data,
        transform=args.mapinfo.crs, cmap=cmap, vmin=0, vmax=300.,
        alpha=.5)
    return pcm,cbar

def plot_deposition_layer(args):
    cmap,_,_ = cptutil.read_cpt(PALETTES/'max_height.cpt')
    cbar = ColorBar('deposition', cmap, 0, 15, [0, .5, 1, 5, 10, 15], ['0', '', '1', '5m', '10m', ''])

    deposition = gdalutil.read_raster((args.mosaic_zip, 'deposition.tif'))
    data = deposition.data
    print(f'deposition range: {np.min(data)}, {np.max(data)}, {np.nanmean(data)}')
    data[data==deposition.nodata] = np.nan
    data[data<0.5] = np.nan    # Don't show places where it didn't deposit


#    cmap,_,_ = cptutil.read_cpt(PALETTES/'deposition.cpt')
    pcm = args.ax.pcolormesh(
        deposition.grid.centersx, deposition.grid.centersy, data,
        transform=args.mapinfo.crs, cmap=cmap, alpha=.9)

    return pcm,cbar

# =========================================================================

# ---------------------------------------------------------------------
def plot_png(mosaic_zip, plot_layer_fn, ofname, ofname_cbar, labels={'top', 'right', 'bottom', 'left'}):
    """
    mosaic_zip:
        Name of the Mosaic .zip file prepared by AKRAMMS
    """

    fig = matplotlib.pyplot.figure(figsize=(4.5,4.5))

    mapinfo = cartopyutil.raster_mapinfo((mosaic_zip, 'dem.tif'))

    # Set up the basemap
    ax = fig.add_axes((.1,.1,.9,.86), projection=mapinfo.crs)
    #ax.set_facecolor('xkcd:light grey')    # https://xkcd.com/color/rgb/
    ax.set_facecolor('#E0E0E0')    # Map background https://xkcd.com/color/rgb/

    ax.set_extent(mapinfo.extents, crs=mapinfo.crs)
    ax.coastlines(resolution='50m')

    layer_args = LayerArgs(ax, mosaic_zip, mapinfo, True)
    pcm = plot_dem_layer(layer_args, hillshade=True)

    # Plot the main layer
    _,cbar = plot_layer_fn(layer_args)
    if ofname_cbar is not None:
        plot_cbar(cbar, ofname_cbar)

    # ---------  Add OpenStreetMap stuff
    # https://www.theurbanist.com.au/2021/03/plotting-openstreetmap-images-with-cartopy/
    if True:
        openstreetmap.plot_layer(ax, 10, cache=OSM_DIR, alpha=.5)

    # ----------  Plot scale in km
    if True:
        cartopyutil.add_osgb_scalebar(ax, at_y=(0.03, 0.04))
#'top' if selrow.w21t_Glacier in _top_scales else 'bottom') #, at_y=(0.10, 0.080))



    # ---------- Add GeoAxes

    # ---------- Add lat/lon gridlines.  (We really should do x/y gridlines?)
    # It cannot label gridlines in the normal way with EqualAlbers
    # https://www.theurbanist.com.au/2021/03/plotting-openstreetmap-images-with-cartopy/
    gl = ax.gridlines(draw_labels=True, #crs=mapinfo.crs,
                        color='k',lw=0.5, alpha=.7)

    for lab in ('top', 'right', 'bottom', 'left'):
        if lab not in labels:
            setattr(gl, f'{lab}_labels', False)

#    gl.xformatter = cartopy.mpl.gridliner.LONGITUDE_FORMATTER
#    gl.yformatter = cartopy.mpl.gridliner.LATITUDE_FORMATTER

    with TrimmedPng(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

    return ofname

# -------------------------------------------------------------
class TrimmedPng:
    def __init__(self, ofname):
        self.ofname = ofname
        baseleaf,ext = os.path.splitext(ofname.parts[-1])
        self.tname = ofname.parents[0] / f'{baseleaf}_tmp.{ext}'
    def __enter__(self):
        return self.tname

    def __exit__(self ,type, value, traceback):
        cmd = ['convert', self.tname, '-trim', self.ofname]
        subprocess.run(cmd, check=True)
        os.remove(self.tname)

# -------------------------------------------------------------


page_tpl = string.Template(r"""
\documentclass{article}

\usepackage{times}
%\usepackage[fontsize=11pt]{fontsize}
\usepackage{grid-system}
\usepackage{graphicx}
\usepackage[letterpaper,landscape,margin=.5in]{geometry}

% https://stackoverflow.com/questions/877597/how-do-you-change-the-document-font-in-latex
\renewcommand{\familydefault}{\sfdefault}

% No indents  https://github.com/PierreSenellart/erc-latex-template/issues/1
\setlength{\parindent}{0pt}
\pagestyle{empty}

\begin{document}

\begin{center}{\LARGE $TITLE}\end{center}

\begin{Row}

\begin{Cell}{1}
\begin{center}
{\large \textbf{Max. Pressure}} \vspace{1ex} \\
\includegraphics{max_pressure} \vspace{1ex} \\
\includegraphics{max_pressure_cbar}
\end{center}
\end{Cell}

%\end{Row} \begin{Row}

\begin{Cell}{1}
\begin{center}
{\large \textbf{Deposition}} \vspace{1ex} \\
\includegraphics{deposition} \vspace{1ex} \\
\includegraphics{deposition_cbar}
\end{center}
\end{Cell}



\end{Row}



\end{document}
""")


def plot_pdf(mosaic_zip, ofname):
    with ioutil.TmpDir(tdir=ofname.parents[0]/'tmp') as tdir: #tdir='./tmp') as tdir:

#        max_height_png = trim_png(
#            plot_png(mosaic_zip, plot_max_height_layer, tdir.location / 'max_height0.png'),
#            tdir.location / 'max_height.png')

        plot_png(mosaic_zip, plot_max_pressure_layer,
            tdir.location / 'max_pressure.png',
            tdir.location / 'max_pressure_cbar.png',
            labels={'left', 'bottom'})

        plot_png(mosaic_zip, plot_deposition_layer,
            tdir.location / 'deposition.png',
            tdir.location / 'deposition_cbar.png',
            labels={'right', 'bottom'}),

        page_tex = tdir.location / 'page.tex'
        page_pdf = tdir.location / 'page.pdf'
        with open(page_tex, 'w') as out:
            out.write(page_tpl.substitute(
                TITLE=mosaic_zip.parts[-1][:-4],
            ))


        cmd = ['pdflatex', '--interaction=nonstopmode', page_tex.parts[-1]]
        print(' '.join(cmd))
        print(f'cwd={page_tex.parents[0]}')
        subprocess.run(cmd, check=False, cwd=page_tex.parents[0])

        os.makedirs(ofname.parents[0], exist_ok=True)
        os.rename(page_pdf, ofname)





#def main():
#
#
#
#    mosaic_zip = pathlib.Path('/Users/eafischer2/tmp/maps/ak-ccsm-1981-1990-lapse-For-100-109-42-F.zip')
#    plot_pdf(mosaic_zip, 'x.pdf')
##    plot_max_height_cbar()
##    plot_reference_map(mosaic_zip, 'x.png', fast=True)
#
##    dem = gdalutil.read_raster(f'/vsizip/{mosaic_zip}/dem.tif')
###    print(dem.grid.wkt)
##    map_crs = cartopyutil.crs(dem.grid.wkt)
##    print(map_crs)
#
#
#def plot_page():
#    with open('page.tex', 'w') as out:
#        out.write(page_tpl.substitute(
#            TITLE='<TITLE>',
#            MAX_HEIGHT=max_height_png,
#            MAX_PRESSURE=max_pressure_png,
#            Title1='<Title1>',
#            Title3='<Title3>'
#        ))
#
#        cmd = ['pdflatex', 'page.tex']
#        subprocess.run(cmd, check=True)
#        #env = dict(os.environ.items())
#        #env['TEXINPUTS'] = '.:..:../..:'
#        #subprocess.run(cmd, cwd=odir_gl, env=env, check=True)
#
#main()
##plot_page()
#
#
#
