#ifndef ULAM_HPP
#define ULAM_HPP

#include <cmath>

namespace akramms {

// Converting to/from the Ulam Spiral
// Clockwise spiral to match D8 ArcGIS
//https://pro.arcgis.com/en/pro-app/2.8/tool-reference/spatial-analyst/flow-direction.htm
inline std::array<int,2> ulam_n_to_xy(int n)
{
    // sqrt_n = np.sqrt(n)
    double const sqrt_n = sqrt((double)n);

    // m = int(np.floor(sqrt_n))
    int const m = (int)floor(sqrt_n);
    int const m2 = (int)(2*sqrt_n);
    // if int(np.floor(2*sqrt_n))%2 == 0:
    
    // if int(np.floor(2*sqrt_n))%2 == 0:
    int k1x,k1y;
    if (m2%2 == 0) {
        k1x = n-m*(m+1);
        k1y = 0;
    } else {
        k1x = 0;
        k1y = n-m*(m+1);
    }

    // sgn = int(pow(-1,m))
    int const sgn = (m%2 == 0 ? 1 : -1);
    // k2 = int(np.ceil(.5*m))
    int const k2 = (int)ceil(.5*m);

    int const x = sgn * (k1x + k2);
    int const y = sgn * (k1y - k2);
    return std::array{x,y};
}

inline int ulam_xy_to_n(int x, int y)
{
    // sgn = -1 if x<y else 1
    int const sgn = (x<y ? -1 : 1);

    // k = max(np.abs(x), np.abs(y))
    int const k = std::max(std::abs(x), std::abs(y));

    // n = (4*k*k) + sgn * (2*k + x + y)
    int const n = (4*k*k) + sgn * (2*k + x + y);

    return n;
}

} // namespace

#endif
