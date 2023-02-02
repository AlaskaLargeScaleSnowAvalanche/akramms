import sys,re,subprocess,os
import htcondor
import shapely
from akramms import ramms

p = ramms.read_polygon('juneau1_For_5m_30L_1456.dom')
#p = shapely.geometry.Polygon([(0,0),(2,0),(2,2),(0,2)])
print('edge lengths ', ramms.edge_lengths(p))
p = ramms.add_margin(p, -1000.)
print('edge lengths ', ramms.edge_lengths(p))
ramms.write_polygon(p, 'x.dom')

sys.exit(0)



release_files = ['/home/efischer/av/prj/juneau1/RAMMS/juneau130yFor/RELEASE/juneau1_For_5m_30L_rel.shp']
partition = ramms.job_status(release_files)
for k,v in partition.items():
    print(f'=========== {k}:')
    print(v)

if False:
    # xquery(constraint='true', projection=[], limit=- 1, opts=htcondor.htcondor.QueryOpts.Default, name=None) → QueryIterator:

    schedd = htcondor.Schedd()                   # get the Python representation of the scheduler
    #ads = schedd.query(constraint='ClusterId == 52')
    #ads = schedd.query(constraint='JobBatchName=="*1^"')


    cols = ['ClusterId', 'ProcId', 'JobBatchName', 'JobStatus']
    ads = schedd.query(
        constraint=r'regexp("^juneau1_For_5m_30L_[0-9]+$", JobBatchName)',
        projection=cols)


    #JobStatus in job ClassAds
    #
    #0	Unexpanded	U
    #1	Idle	I
    #2	Running	R
    #3	Removed	X
    #4	Completed	C
    #5	Held	H
    #6	Submission_err	E


    #

    for ad in ads:
        print(dict(ad))
        # the ClassAd objects returned by the query act like dictionaries, so we can extract individual values out of them using []
    #    print(f"{ad['ClusterId']} ProcID = {ad['ProcID']} has JobStatus = {ad['JobStatus']}: {ad['JobBatchName']}")


    #print('tag ',ads.tag())
    #ads = jobsit.nextAdsNonBlocking()
    #print(ads)




