from uafgi.util import make
from akramms import config,d_mesonet

# https://mesonet.agron.iastate.edu/request/coop/fe.phtml?network=AKCLIMATE

URL_TPL = 'https://mesonet.agron.iastate.edu/cgi-bin/request/coop.py?network={network}&stations=_ALL&year1={year1}&month1={month1}&day1={day1}&year2={year2}&month2={month2}&day2={day2}&vars%5B%5D=high&vars%5B%5D=highc&vars%5B%5D=low&vars%5B%5D=lowc&vars%5B%5D=temp_estimated&vars%5B%5D=precip&vars%5B%5D=precipmm&vars%5B%5D=precip_estimated&vars%5B%5D=snow&what=download&delim=comma&gis=yes&scenario_year=2025'


def main():
    makefile = make.Makefile()
#    for year in range(1940,2026):
    for year in range(2002, 2023):
        for month in range(1,13):
            rule = d_mesonet.r_download_month(year, month, network='AKCLIMATE')
            print(rule)
            makefile.add(rule)
    makefile.generate('download_akclimate.mk', run=True, ncpu=1)


#download_year(1940)

#curl 'https://mesonet.agron.iastate.edu/cgi-bin/request/coop.py?network={network}&stations=_ALL&year1=1940&month1=1&day1=1&year2=1940&month2=12&day2=31&vars%5B%5D=high&vars%5B%5D=highc&vars%5B%5D=low&vars%5B%5D=lowc&vars%5B%5D=temp_estimated&vars%5B%5D=precip&vars%5B%5D=precipmm&vars%5B%5D=precip_estimated&vars%5B%5D=snow&what=download&delim=comma&gis=yes&scenario_year=2025' -o changeme.txt

main()
