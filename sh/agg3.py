import datetime
from akramms import d_wrf

def main():
    dt0 = datetime.date(1940,1,1)
#    dt0 = datetime.date(1957,1,1)
    dt1 = datetime.date(2023,7,2)
    d_wrf.agg3(dt0, dt1)

main()
