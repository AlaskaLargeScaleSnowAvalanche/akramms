
#ifndef AKRAMMS_RASTER_HPP
#define AKRAMMS_RASTER_HPP

namespace akramms {

class RasterInfo {
public:
    std::string const wkt;
    int const nx, ny;
    std::array<double,6> const geotransform;
    std::array<double,6> const geoinv;
    double const dx, dy;

    RasterInfo(std::string const &_wkt, int _nx, int _ny, std::array<double, 6> const &_geotransform);

    std::array<double,2> to_xy(int i, int j)
    {
        // Converts an (i,j) pixel address to an (x,y) geographic value
        std::array<double, 6> const &GT(this->geotransform);
        double Xgeo = GT[0] + i*GT[1] + j*GT[2];
        double Ygeo = GT[3] + i*GT[4] + j*GT[5];
        return std::array<double,2> {Xgeo, Ygeo};
    }

    std::array<int,2> to_ij(double x, double y)
    {
        // Converts an (x,y) value to an (i,j) index into raster
        // NOTE: Similar to geoio.GeoImage.proj_to_raster()


        // https://stackoverflow.com/questions/40464969/why-does-gdal-grid-turn-image-upside-down
        std::array<double, 6> const &GT(this->geoinv);
        int ir = GT[0] + x*GT[1] + y*GT[2];
        int jr = GT[3] + x*GT[4] + y*GT[5];
        return std::array<double,2> {ir, jr};
    }
};

}    // namespace
