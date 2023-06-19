#include <akramms/raster.hpp>

#include <cmath>

namespace akramms {

// -----------------------------------------------------------------------
// Taken from original GDAL Source
// https://github.com/OSGeo/gdal/blob/master/alg/gdaltransformer.cpp
inline std::array<double, 6> invert_geotransform(std::array<double, 6> const &gt_in)
{
    std::array<double, 6> gt_out;

    // Special case - no rotation - to avoid computing determinate
    // and potential precision issues.
    if (gt_in[2] == 0.0 && gt_in[4] == 0.0 && gt_in[1] != 0.0 &&
        gt_in[5] != 0.0)
    {
        /*X = gt_in[0] + x * gt_in[1]
          Y = gt_in[3] + y * gt_in[5]
          -->
          x = -gt_in[0] / gt_in[1] + (1 / gt_in[1]) * X
          y = -gt_in[3] / gt_in[5] + (1 / gt_in[5]) * Y
        */
        gt_out[0] = -gt_in[0] / gt_in[1];
        gt_out[1] = 1.0 / gt_in[1];
        gt_out[2] = 0.0;
        gt_out[3] = -gt_in[3] / gt_in[5];
        gt_out[4] = 0.0;
        gt_out[5] = 1.0 / gt_in[5];
        return gt_out;
    }

    // Assume a 3rd row that is [1 0 0].

    // Compute determinate.

    const double det = gt_in[1] * gt_in[5] - gt_in[2] * gt_in[4];
    const double magnitude = std::max(std::max(std::fabs(gt_in[1]), std::fabs(gt_in[2])),
                                      std::max(std::fabs(gt_in[4]), std::fabs(gt_in[5])));

    if (std::fabs(det) <= 1e-10 * magnitude * magnitude)
        throw std::runtime_error("invert_geotransform(): zero determinate\n");

    const double inv_det = 1.0 / det;

    // Compute adjoint, and divide by determinate.

    gt_out[1] = gt_in[5] * inv_det;
    gt_out[4] = -gt_in[4] * inv_det;

    gt_out[2] = -gt_in[2] * inv_det;
    gt_out[5] = gt_in[1] * inv_det;

    gt_out[0] = (gt_in[2] * gt_in[3] - gt_in[0] * gt_in[5]) * inv_det;
    gt_out[3] = (-gt_in[1] * gt_in[3] + gt_in[0] * gt_in[4]) * inv_det;

    return gt_out;
}

RasterInfo::RasterInfo(std::string const &_wkt, int _nx, int _ny, std::array<double, 6> const &_geotransform) :
    wkt(_wkt), nx(_nx), ny(_ny), geotransform(_geotransform), geoinv(invert_geotransform(_geotransform)), dx(_geotransform[1]), dy(_geotransform[0])
{}

}    // namespace
