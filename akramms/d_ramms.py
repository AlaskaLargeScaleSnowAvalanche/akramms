# Read RAMMS files







# These are both binary files. The formats are the following:
#  
# File: *.out
#  
# nCells                                   Long
# MaxVelocityValues         fltarr(nCells)
# MaxHeightValues           fltarr(nCells)
# DepoValues                       fltarr(nCells)
#  
#  
# File: *.xy-coord
#  
# nCells                                   Long
# x_vector                              dblarr( NrCells )
# y_vector                              dblarr( NrCells )
#  
#  
# the File *.xy-coord contains the cell-center coordinate points of the result arrays. With this information, you should be able to mosaic the results, and then you have to output them as GeoTiff’s……
#  
# In case this information helps you enough to continue for the moment, we can also postpone the meeting, until you run into problems 😊, and we can discuss it then?
#  
# All the best
#  
# Marc
