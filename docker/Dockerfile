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
ADD RAMMS/230423 /opt/ramms
RUN echo '230423.3' >/opt/build_version.txt

ADD RAMMS/230423 /opt/ramms

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
