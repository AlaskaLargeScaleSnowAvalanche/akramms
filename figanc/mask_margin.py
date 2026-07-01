            # ------------------------------------------------         
            # Mask out the margin
#            sub0 = exp.gridD.sub(idom, jdom, 10, 10, margin=True)    # Assumes 10m resolution
            dx,dy = (np.abs(subgrid.dx), np.abs(subgrid.dy))
            nmargx = int(exp.gridD.domain_margin[0] / dx)
            nmargy = int(exp.gridD.domain_margin[1] / dy)
            print(nmargx, nmargy)

            margin_out = np.ones((subgrid.ny, subgrid.nx), dtype=bool)
            margin_out[nmargy:-nmargy, nmargx:-nmargx] = 0
            print('margin_out ', margin_out.shape, np.sum(margin_out))
            # ------------------------------------------------         
