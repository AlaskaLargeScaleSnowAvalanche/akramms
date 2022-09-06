#pragma once

#include <cmath>
#include <cfloat>
#include <vector>
#include <array>

namespace dggs {

/** Find the smallest bounding rectangle for a set of points.
Returns a set of points representing the corners of the bounding box.

chull: [(x,y), ...]
    Points of the Convex Hull
    (or [(y,x), ...], doesn't matter)
    NOTE: This array is TEMPORARILY modified
Returns: [(x,y), ...]
    The four corners of the minimum area rectangle */
extern std::vector<std::array<double,2>> mbr_chull(
    std::vector<std::array<double,2>> &chull,
    double margin=0.0);

}
