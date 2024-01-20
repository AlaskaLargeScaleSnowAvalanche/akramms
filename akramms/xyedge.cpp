

enum DomainMaskValue {
    MASK_OUT = 0,      // Not part of the domain
    MARGIN = 1,        // Avalanches can flow in here, but not start here
    MASK_IN = 2        // Avalanches can start here
}


/** Identifies the gridcells for a local avalanche run that:

  a) Have fewer than 4 neighbors (meaning, they are on the edge of the
     local avalanche domain).

       and

  b) In the wider tile domain for the scene, they do NOT border a
     masked-out gridcell (eg. Canada).

  This designates the set of cells that, if the avalanche ended in,
  then an overrun should be declared.
*/
void _xyedge_xyedge(
    // Info on the gridcells within gridA represented by RAMMS
    int const ngridA,    // Number of gridcells for this avalanche
    int32_t *iAs,    // 
    int32_t *jAs,    // (0-based, this was determined from (x,y) values)

    // Info on subdomain tile the avalanche ran in
    int gridA_nx, gridA_ny,

    // The domain mask
    char *domain_maskA,

    // OUTPUT: same dimension as iA/jA
    char *oedge)    // Is it an edge gridcell matching (a) and (b) criteria?
{

    // Determine limits of gridcells used.
    int mini=0, minj=0;
    int maxi=std::numeric_limits<int>::max();
    int maxj=std::numeric_limits<int>::max();
    for (int k=0; k<ngridA; ++k) {
        mini = std::min(min_i, iAs[k]);
        maxi = std::max(max_i, iAs[k]);
        minj = std::min(min_j, jAs[k]);
        maxj = std::max(max_j, jAs[k]);
    }

    // Creates subgrid S with just those limits (and one gridcell margin)
    int const i0 = mini - 1;
    int const i1 = maxi + 2;
    int const ni = i1-i0;
    int const j0 = minj - 1;
    int const j1 = maxj + 1;
    int const nj = j1-j0;

    // Create 0/1 raster on subgrid indicating which gridcells are in the Avalanche domain.
    std::unique_ptr<char> xygrid(new bool[nj*ni]);
    for (int k=0; k<nj*ni; ++k) xygrid[k] = 0;
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        xygrid[jj*ni + ii] = 1;
    }

    // Compute the number of neighbors of each gridcell (0-4)
    std::unique_ptr<char> nneighbor(new bool[nj*ni]);
    for (int k=0; k<nj*ni; ++k) nneighbor[k] = 0;
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        int const ix = jj*ni + ii;
        nneighbor[ix] = xygrid[ix-1] + xygrid[ix+1] + xygrid[ix-ni] + xygrid[ix+ni];
    }


    // Apply the condition to determine which gridcells are on a
    // domain edge that would be solved if we enlarge the domain.
    int const gridA_nxy = gridA_nx * gridA_ny;
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        int const ix = jj*ni + ii;

        oedge[k] = false;

        // It's an interior cell
        if (nneighbor[ix] == 4) continue;

        // Look at the domain mask
        int const dix = jAs[k]*gridA_nx + iAs[k];
        int[] const offset = [1, -1, gridA_nx, -gridA_nx];
        for (int kk=0; i<4; ++i) {
            int const off = offset[kk];
            ix1 = ix + off;
            // Check "neighbor" ix1 is on the grid
            if ((ix1 < 0) || (ix1 > gridA_nx * gridA_ny)) continue;

            if (domain_mask[ix1] == DomainMaskValue::MASK_OUT) goto continue_outer;
        }
        oedge[k] = true;
    continue_outer: ;
    }
}
