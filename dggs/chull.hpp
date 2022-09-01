// A C++ program to find convex hull of a set of points. Refer
// https://www.geeksforgeeks.org/convex-hull-set-2-graham-scan/
// This uses the Graham Scan Algorithm

// More on Graham Scan
// https://leetcode.com/problems/erect-the-fence/discuss/103307/c-graham-scanmonotone-chain-dealing-with-collinear-cases

#include <iostream>
#include <vector>
#include <array>
#include <utility>
#include <cstdio>
#include <algorithm>

namespace dggs {

namespace chull {

template <class T>
using Point = std::array<T,2>;    // y,x
static int const Y=0;
static int const X=1;

// A utility function to return square of distance
// between p1 and p2
template <class T>
inline T dist_sq(Point<T> const &p1, Point<T> const &p2)
{
    return (p1[Y] - p2[Y])*(p1[Y] - p2[Y]) +
        (p1[X] - p2[X])*(p1[X] - p2[X]);
}
     

enum Orientation {COLLINEAR, CLOCKWISE, COUNTERCLOCKWISE};
enum IndexOrder {XY, YX};

// To find orientation of ordered triplet (p, q, r).
// The function returns following values
// 0 --> p, q and r are collinear
// 1 --> Clockwise
// 2 --> Counterclockwise
template <class T>
inline Orientation orientation(Point<T> const &p, Point<T> const &q, Point<T> const &r)
{
    double val = (q[Y] - p[Y]) * (r[X] - q[X]) -
              (q[X] - p[X]) * (r[Y] - q[Y]);
 
    if (val == 0.0) return Orientation::COLLINEAR;    // TODO: Use epsilon for comparison with 0?
    return (val > 0.0)? Orientation::CLOCKWISE : Orientation::COUNTERCLOCKWISE;
}


// A function used by library function qsort() to sort an array of
// points with respect to the first point
template <class T>
struct compare_vs {
    // A global point needed for  sorting points with reference
    // to  the first point Used in compare function of qsort()
    Point<T> const &p0;

    compare_vs(Point<T> const &_p0) : p0(_p0) {}

    inline bool operator()(Point<T> const &p1, Point<T> const &p2)
    {
       // Find orientation
       Orientation o = orientation(p0, p1, p2);
       if (o == Orientation::COLLINEAR) return dist_sq(p0, p2) >= dist_sq(p0, p1);
       return (o == Orientation::COUNTERCLOCKWISE);
    }
};
}    // namespace dggs::chull

/** Returns convex hull of a set of n points.

points: [(y,x), ...]
    NOTE: points array is modified
order: Orientation::COUNTERCLOCKWISE (DEFAULT)
    Order of output points: clockwise or counter-clockwise
    NOTE: This will be the order if points are in default (y,x) coordinates.
          If points are (x,y) then this will be the REVERSE of the order.
Returns: [(y,x), ...]
    Points of the convex hull polygon, in clockwise / counter-clockwise order.
    Not unique as to where the cycle of points is "split" into a linear array.
    The first point is NOT repeated at the end.
*/
template <class T>
std::vector<std::array<T,2>> convex_hull(
    std::vector<std::array<T,2>> &points,
    chull::IndexOrder iorder = chull::IndexOrder::XY,
    chull::Orientation orient = chull::Orientation::COUNTERCLOCKWISE)
{
    using namespace chull;

    // Place the bottom-most point at first position
    std::swap(points[0], *std::min_element(points.begin(), points.end()));
    Point<T> &p0(points[Y]);    // Alias for bottom-most point

    // Sort n-1 points with respect to the first point.
    // A point p1 comes before p2 in sorted output if p2
    // has larger polar angle (in counterclockwise
    // direction) than p1
    std::sort(points.begin()+1, points.end(), compare_vs(p0));
  
    // If two or more points make same angle with p0,
    // Remove all but the one that is farthest from p0
    // Remember that, in above sorting, our criteria was
    // to keep the farthest point at the end when more than
    // one points have same angle.
    size_t m = 1; // Initialize size of modified array
    for (size_t i=1; i<points.size(); ++i) {
        // Keep removing i while angle of i and i+1 is same
        // with respect to p0
        while ((i < points.size()-1) &&
            orientation(p0, points[i], points[i+1]) == Orientation::COLLINEAR) {
            ++i;
        }
  
        points[m] = points[i];
        m++;  // Update size of modified array
    }
    points.resize(m);
  
    // If modified array of points has fewer than 3 points,
    // convex hull is not possible
    if (m < 3) return std::vector<Point<T>>{};
  
    // Create an empty std::stack and push first three points
    // to it.
    std::vector<Point<T>> stack;
    stack.push_back(points[0]);
    stack.push_back(points[1]);
    stack.push_back(points[2]);
  
    // Process remaining n-3 points
    for (int i = 3; i < m; i++) {
        // Keep removing top while the angle formed by
        // points next-to-top, top, and points[i] makes
        // a non-left turn
        while (stack.size()>1 &&
            orientation(stack.end()[-2], stack.end()[-1], points[i]) != Orientation::COUNTERCLOCKWISE) {
            stack.pop_back();
        }
        stack.push_back(points[i]);
    }
  
    // Now std::stack has the output points
    if ((orient == Orientation::CLOCKWISE) != (iorder == chull::IndexOrder::XY)) {
        std::reverse(stack.begin(), stack.end());
    }
    return stack;
}
}    // namespace dggs

