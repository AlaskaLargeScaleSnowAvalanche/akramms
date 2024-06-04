# syntax=docker/dockerfile:1
FROM ubuntu:20.04

# Update
RUN apt-get update

# Install Python (3)
RUN apt install --yes python3 python-is-python3

# Install RAMMS .exe file (and any supporting DLLs)
ADD RAMMS/2.0.0-1-g26d12f8 /opt/ramms
RUN echo '2.0.0-1-g26d12f8.17' >/opt/build_version.txt

ADD RAMMS/2.0.0-1-g26d12f8 /opt/ramms

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
