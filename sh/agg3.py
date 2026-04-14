import datetime
from akramms import d_wrf


def main():
    dt0 = datetime.date(1979,7,1)
#    dt0 = datetime.date(1957,1,1)
    dt1 = datetime.date(2100,7,1)
    d_wrf.agg3(dt0, dt1, dataset='fut')

#main()

#d_wrf.write_single_agg3(1979, 1981, res=4, dataset='fut')
d_wrf.write_single_agg3(1979, 2100, res=4, dataset='fut')
d_wrf.write_single_agg3(1979, 2100, res=1.33, dataset='fut')

# ----------------------------------------------------

def mainx():
    dt0 = datetime.date(1940,1,1)
#    dt0 = datetime.date(1957,1,1)
    dt1 = datetime.date(2023,7,2)
    d_wrf.agg3(dt0, dt1, dataset='era5')


# This is step 2
#d_wrf.write_single_agg3(1940, 2023, dataset='era5')



#main()
