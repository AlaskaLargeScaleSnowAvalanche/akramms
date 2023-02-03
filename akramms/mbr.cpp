#include <algorithm>
#include <akramms/mbr.hpp>

namespace akramms {

/** Find the smallest bounding rectangle for a set of points.
Returns a set of points representing the corners of the bounding box.

chull: [(x,y), ...]
    Points of the Convex Hull
    (or [(y,x), ...], doesn't matter)
    NOTE: This array is TEMPORARILY modified
Returns: [(x,y), ...]
    The four corners of the minimum area rectangle */
std::vector<std::array<double,2>> mbr_chull(
    std::vector<std::array<double,2>> &chull,
    double margin)
{
    double const pi_by_2 = M_PI / 2.;

    // Setup temporary to hold rotated chull
    std::vector<double> xrot;
    std::vector<double> yrot;
    xrot.reserve(chull.size());
    yrot.reserve(chull.size());

    // Area of each rotated bounding box
    std::vector<double> areas;
    areas.reserve(chull.size());

    // Iterate through each edge
    chull.push_back(chull[0]);    // Add sentinel
    double best_area = DBL_MAX;
    std::array<std::array<double,2>,2> best_R {};    // Best rotation matrix
    std::array<double,4> best_mmxy{};    // best (min_x, max_x, min_y, max_y) in rotate space
    for (size_t i=0; i<chull.size()-1; ++i) {
        std::array<double,2> const &p0(chull[i]);
        std::array<double,2> const &p1(chull[i+1]);
        std::array<double,2> const edge {p1[0]-p0[0], p1[1]-p0[1]};
        // Calculate the edge angle
        double angle = std::atan2(edge[1], edge[0]);
        
        // angles = np.abs(np.mod(angles, pi_by_2))
        angle = fmod(angle + pi_by_2, pi_by_2);  // https://github.com/brian-team/brian2/issues/286

        // This was NOP in Python because of how convex hull works; collinear
        // points along edges are removed.
        // angles = np.unique(angles)     

        // find rotation matrix
        // (Use of cos(x-p/2) instad of -sin(x) is intentional)
        std::array<std::array<double,2>,2> const R {
            std::array<double,2>{cos(angle), cos(angle - pi_by_2)},    // cos, -sin
            std::array<double,2>{cos(angle + pi_by_2), cos(angle)}};    // sin, cos

        // Rotate the chull
        // rot_points = np.dot(rotations, chull.T)
        xrot.clear();
        yrot.clear();
        for (size_t j=0; j<chull.size()-1; ++j) {
            std::array<double,2> const &p(chull[j]);
            // Compute matrix product R * point
            xrot.push_back(R[0][0]*p[0] + R[0][1]*p[1]);
            yrot.push_back(R[1][0]*p[0] + R[1][1]*p[1]);
        }

        // Bounding points of this box in rotated space
        // Requires a newer C++...
        auto const mmx(std::minmax_element(xrot.begin(), xrot.end()));
        double const min_x = *mmx.first;
        double const max_x = *mmx.second;
        auto const mmy(std::minmax_element(yrot.begin(), yrot.end()));
        double const min_y = *mmy.first;
        double const max_y = *mmy.second;

        // Area of this box
        double const area = (max_x - min_x) * (max_y - min_y);

        // Update max
        if (area < best_area) {
            best_R = R;
//printf("Found smaller MBR (area=%f): %f, %f, %f, %f\n", area, min_x, max_x, min_y, max_y);
            best_mmxy = std::array{min_x, max_x, min_y, max_y};
            best_area = area;
        }
    }

    // Construct the best box in original (unrotated) space
    // best_mmxy = [min_x, max_x, min_y, max_y]
    double const x1 = best_mmxy[1] + margin;
    double const x2 = best_mmxy[0] - margin;
    double const y1 = best_mmxy[3] + margin;
    double const y2 = best_mmxy[2] - margin;

    std::vector<std::array<double,2>> rval;
    rval.push_back({
        x1*best_R[0][0] + y2*best_R[1][0],
        x1*best_R[0][1] + y2*best_R[1][1]});

    rval.push_back({
        x2*best_R[0][0] + y2*best_R[1][0],
        x2*best_R[0][1] + y2*best_R[1][1]});

    rval.push_back({
        x2*best_R[0][0] + y1*best_R[1][0],
        x2*best_R[0][1] + y1*best_R[1][1]});

    rval.push_back({
        x1*best_R[0][0] + y1*best_R[1][0],
        x1*best_R[0][1] + y1*best_R[1][1]});

    // Remove sentinel point
    chull.pop_back();

    return rval;
}

}    // namespace akramms

/*
// Original Python code from:
// https://stackoverflow.com/questions/13542855/algorithm-to-find-the-minimum-area-rectangle-for-given-points-in-order-to-comput

import numpy as np
from scipy.spatial import ConvexHull

def minimum_bounding_rectangle(points):
    """
    Find the smallest bounding rectangle for a set of points.
    Returns a set of points representing the corners of the bounding box.

    :param points: an nx2 matrix of coordinates
    :rval: an nx2 matrix of coordinates
    """
    from scipy.ndimage.interpolation import rotate
    pi_by_2 = np.pi/2.

    // get the convex hull for the points
    chull = points[ConvexHull(points).vertices]

    // calculate edge angles
    edges = np.zeros((len(chull)-1, 2))
    edges = chull[1:] - chull[:-1]

    angles = np.zeros((len(edges)))
    angles = np.arctan2(edges[:, 1], edges[:, 0])

    angles = np.abs(np.mod(angles, pi_by_2))
    angles = np.unique(angles)

    // find rotation matrices
    // XXX both work
    rotations = np.vstack([
        cos(angles),
        cos(angles - pi_by_2),
        cos(angles + pi_by_2),
        cos(angles)]).T
//     rotations = np.vstack([
//         cos(angles),
//         -sin(angles),
//         sin(angles),
//         cos(angles)]).T
    rotations = rotations.reshape((-1, 2, 2))

    // apply rotations to the hull
    rot_points = np.dot(rotations, chull.T)

    // find the bounding points
    min_x = np.nanmin(rot_points[:, 0], axis=1)
    max_x = np.nanmax(rot_points[:, 0], axis=1)
    min_y = np.nanmin(rot_points[:, 1], axis=1)
    max_y = np.nanmax(rot_points[:, 1], axis=1)

    // find the box with the best area
    areas = (max_x - min_x) * (max_y - min_y)
    best_idx = np.argmin(areas)

    // return the best box
    x1 = max_x[best_idx]
    x2 = min_x[best_idx]
    y1 = max_y[best_idx]
    y2 = min_y[best_idx]
    r = rotations[best_idx]

    rval = np.zeros((4, 2))
    rval[0] = np.dot([x1, y2], r)
    rval[1] = np.dot([x2, y2], r)
    rval[2] = np.dot([x2, y1], r)
    rval[3] = np.dot([x1, y1], r)

    return rval
}
*/
