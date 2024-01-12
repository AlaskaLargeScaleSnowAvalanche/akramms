import os,subprocess,shutil,sys
from uafgi.util import stringutil
from akramms.util import harnutil
from akramms import config
import configparser



Dockerfile_tpl = \
"""# syntax=docker/dockerfile:1
FROM ubuntu:20.04

# Update
RUN apt-get update

# Download Wine
RUN apt install --download-only --yes wine

# Install Wine Prerequisites
# https://serverfault.com/questions/949991/how-to-install-tzdata-on-a-ubuntu-docker-image
RUN DEBIAN_FRONTEND=noninteractive TZ=America/Anchorage apt-get -y install tzdata

# Install Wine
RUN apt install --yes wine
RUN dpkg --add-architecture i386
RUN apt update
RUN apt install --yes wine wine32 libwine

# Install Python (3)
RUN apt install --yes python3 python-is-python3

# Add basic ~/.wine directory
COPY dotwine.tar.gz /opt

# Install RAMMS .exe file (and any supporting DLLs)
ADD {ramms_distro} /opt/ramms
RUN echo '{ramms_version}.{build}' >/opt/build_version.txt

ADD RAMMS/{ramms_version} /opt/ramms

# https://betterprogramming.pub/how-to-version-your-docker-images-1d5c577ebf54

# Script to run RAMMS
RUN true  # https://stackoverflow.com/questions/51115856/docker-failed-to-export-image-failed-to-create-image-failed-to-get-layer
COPY runaval.py /opt

# Set cwd to the place where the caller will mount directory full of
# RAMMS problems, eg:
#    docker run -v "$(pwd)":/ramms ...
WORKDIR /ramms

# Arguments to pass to ENTRYPOINT (sh)
#CMD wine /opt/ramms/bin/ramms_aval_LHM.exe ${av2} ${out}
#CMD python /opt/runaval.py


# (avalanche) efischer@antevorta:~/av/prj/juneau1/RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L$ docker run -v "$(pwd)":/ramms -e avalanche=juneau1_For_5m_30L_6213 -u 1001:1001 -it ramms
"""

# Make sure we have the RAMMS version in place
odist_parent = os.path.join(config.HARNESS, 'akramms', 'docker', 'RAMMS')
odist = os.path.join(odist_parent, config.ramms_version)
idist = os.path.join(config.HARNESS, 'data', 'christen', 'RAMMS', config.ramms_version)
if not os.path.exists(odist):
    print('Deleting tree {}'.format(odist_parent))
    shutil.rmtree(odist_parent, ignore_errors=True)
    shutil.copytree(idist,odist)


docker_dir = os.path.join(config.HARNESS, 'akramms', 'docker')
with config.update_docker_build() as build:    # Build ID number

    # Make the Dockerfile
    Dockerfile_str = stringutil.partial_format(Dockerfile_tpl,
        ramms_distro=f'RAMMS/{config.ramms_version}',
        ramms_version=config.ramms_version, build=build)
    with open(os.path.join(docker_dir, 'Dockerfile'), 'w') as out:
        out.write(Dockerfile_str)

    # Docker push, now that we have fully updated and buil versions
    vers = f'{config.ramms_version}.{build}'
    docker_tag = f'{config.docker_host}/efischer/ramms:{vers}'

    # Build the Docker image on local machine
    cmd = ['docker', 'build', '-t', docker_tag, '.']
    print(' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except:
        print('******* Error Running!', file=sys.stdout)
        print('Do you need to run?: docker login')


#cmd = ['docker', 'build', '-t', f'ramms:{vers}', '.']
#subprocess.run(cmd, cwd=docker_dir, check=True)

#cmd = ['docker', 'tag', f'ramms:{vers}', docker_tag]
#subprocess.run(cmd, check=True)

cmd = ['docker', 'push', docker_tag]
subprocess.run(cmd, check=True)
