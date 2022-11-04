# syntax=docker/dockerfile:1
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
ADD 220922-RAMMS-x0928.tar.gz /opt/ramms

# Script to run RAMMS
COPY runaval.py /opt

# Set cwd to the place where the caller will mount directory full of
# RAMMS problems, eg:
#    docker run -v "$(pwd)":/ramms ...
WORKDIR /ramms

# Arguments to pass to ENTRYPOINT (sh)
#CMD wine /opt/ramms/bin/ramms_aval_LHM_orig.exe ${av2} ${out}
#CMD python /opt/runaval.py


# (avalanche) efischer@antevorta:~/av/prj/juneau1/RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L$ docker run -v "$(pwd)":/ramms -e avalanche=juneau1_For_5m_30L_6213 -u 1001:1001 -it ramms

