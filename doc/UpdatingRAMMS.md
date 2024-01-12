# HOWTO Update RAMMS Version

Each RAMMS version is designated by the date on which it was received
from Marc Christen, and is stored in the directory
`data/christen/RAMMS`:

```
(base) efischer@antevorta:~/av/data/christen/RAMMS$ ls -l
total 40
drwxrwxr-x 7 efischer efischer 4096 Sep 22  2022 220922
drwxrwxr-x 2 efischer efischer 4096 Dec  1  2022 220928
drwxrwxr-x 2 efischer efischer 4096 Dec  1  2022 221101
drwxrwxr-x 3 efischer efischer 4096 Jan 26  2023 230126
drwxrwxr-x 4 efischer efischer 4096 Feb 10  2023 230210
drwxrwxr-x 7 efischer efischer 4096 Mar 21  2023 230321
drwxrwxr-x 7 efischer efischer 4096 Apr  1  2023 230401
drwxrwxr-x 7 efischer efischer 4096 Apr 23  2023 230423
drwxrwxr-x 7 efischer efischer 4096 Apr 23  2023 240111
```

Here we document the steps to install a new RAMMS version once it is
received from Marc.

## 0. Clean Git

Make sure you have committed and pushed all changes in the `akramms`
repo.


## 1. Upack New Version

Create a directory based on the date received and unpack the `.zip`
file received from Marc into it.  The results should look like this:

```
(base) efischer@antevorta:~/av/data/christen/RAMMS$ ls 230423/
IDL85              RAMMS_Runtime.ini  bin  defaults   ramms_lshm.sav
RAMMS_Runtime.exe  Runtime            bmp  ramms.ico
```

If Marc provided only the files that change since the previous
distribution, create the new one by copying the entire previous
distribution, then only the new files on top of it.  For example, on
January 11, 2023, Marc provided just the new RAMMS `.exe` file, which
resulted in:

```
(base) efischer@antevorta:~/av/data/christen/RAMMS/240111/bin$ ls -ltrah
total 232K
-rw-rw-r-- 1 efischer efischer 6.5K Mar 19  2012 tail.exe
-rw-rw-r-- 1 efischer efischer  90K Mar 19  2012 gzip.exe
-rw-rw-r-- 1 efischer efischer  19K Sep 22  2017 mtee.exe
drwxrwxr-x 2 efischer efischer 4.0K Apr 23  2023 .
drwxrwxr-x 7 efischer efischer 4.0K Apr 23  2023 ..
-rw-rw-r-- 1 efischer efischer 103K Jan 11 16:48 ramms_aval_LHM.exe
```

## 2. Copy to Windows

The latest version of RAMMS needs to exist on `antevorta` and on the
Windows machine.  Once it has been installed on `antevorta`, it needs
to be copied to Windows.  The easiest way to do this is *from the
Windows machine*, via Rsync:

```
~/av/data/christen/RAMMS$ rsync -avz 10.10.132.212:~/av/data/christen/RAMMS/240111 .
receiving incremental file list
240111/
240111/RAMMS_Runtime.exe
240111/RAMMS_Runtime.ini
```

**NOTE:** The Windows machine does not recognize the DNS name
`antevorta`, therefore antevorta's IP address of `10.10.132.212` was
used.


## 3. Configure AKRAMMS to use the newly installed version.

Edit the variable `ramms_version` in `akramms/config.py` on `antevorta`:

```
...
#ramms_version = '230423'
ramms_version = '240111'
```


## 4. Build Docker Container

If the core `.exe` file doing the avalanche simulations changed with
your newly selected version, you will need to build and install a new Docker
container.

```
(avalanche) efischer@antevorta:~/av/akramms/docker$ python build.py
root[HARNESS] = /home/efischer/av
root[DATA] = /home/efischer/av/data
root[PRJ] = /home/efischer/av/prj
root[HARNESS] = C:\Users\efischer\av
root[DATA] = C:\Users\efischer\av\data
root[PRJ] = C:\Users\efischer\av\prj
Deleting tree /home/efischer/av/akramms/docker/RAMMS
docker build -t git.akdggs.com/efischer/ramms:240111.1 .
Sending build context to Docker daemon  175.7MB
Step 1/16 : FROM ubuntu:20.04
...
Successfully built 0b8ec5824401
Successfully tagged git.akdggs.com/efischer/ramms:240111.1
Writing /home/efischer/av/akramms/docker/builds.ini
...
The push refers to repository [git.akdggs.com/efischer/ramms]
...
```

**NOTES:**

1. The Docker container created in this case. called `ramms:240111.1`.
   The `.1` sub-version at the end means this is the *first* time a
   Docker container has been created for RAMMS version `240111`.

1. The file `docker/builds.ini` is generated / updated to keep track
   of the most recent sub-version of each RAMMS version that was
   built.  In this case, the most recent version for RAMMS `240111` is
   `240111.1`.

   ```
   ~/av/akramms/docker$ cat builds.ini 
   [builds]
   230321 = 1
   230401 = 11
   230423 = 3
   240111 = 1
   ```

1. When RAMMS Stage 2 is run, the Python code (`joblib.py`) reads the
   `builds.ini` file and runs the *most recent* sub-version; see
   `docker_tag()` in `config.py`.

## 5. Commit to Git

Review the changes to the files tracked by Git, and commit them so
make the version upgrade permanent.  The changes here are:

```
(avalanche) efischer@antevorta:~/av/akramms$ git diff
diff --git a/akramms/config.py b/akramms/config.py
index d850080..5a78c4f 100644
--- a/akramms/config.py
+++ b/akramms/config.py
@@ -54,7 +54,8 @@ auto_submit = True
 #ramms_version = '230210'
 #ramms_version = '230321'
 #ramms_version = '230401'
-ramms_version = '230423'
+#ramms_version = '230423'
+ramms_version = '240111'
 #docker_container_version = f'${ramms_version}.0'
 
 # Maximum number of PRAs in a RAMMS run
diff --git a/docker/Dockerfile b/docker/Dockerfile
index 1d4115e..33792fc 100644
--- a/docker/Dockerfile
+++ b/docker/Dockerfile
@@ -24,10 +24,10 @@ RUN apt install --yes python3 python-is-python3
 COPY dotwine.tar.gz /opt
 
 # Install RAMMS .exe file (and any supporting DLLs)
-ADD RAMMS/230423 /opt/ramms
-RUN echo '230423.3' >/opt/build_version.txt
+ADD RAMMS/240111 /opt/ramms
+RUN echo '240111.1' >/opt/build_version.txt
 
-ADD RAMMS/230423 /opt/ramms
+ADD RAMMS/240111 /opt/ramms
 
 # https://betterprogramming.pub/how-to-version-your-docker-images-1d5c577ebf54
 
diff --git a/docker/builds.ini b/docker/builds.ini
index 2286ad5..00b3f20 100644
--- a/docker/builds.ini
+++ b/docker/builds.ini
@@ -2,4 +2,5 @@
 230321 = 1
 230401 = 11
 230423 = 3
+240111 = 1
```

Therefore, commit and push:

```
(avalanche) efischer@antevorta:~/av/akramms$ git commit -a -m 'Updated RAMMS version'
[main 1fab0e9] Updated RAMMS version
 3 files changed, 6 insertions(+), 4 deletions(-)
(avalanche) efischer@antevorta:~/av/akramms$ git push
Enumerating objects: 13, done.
Counting objects: 100% (13/13), done.
Delta compression using up to 8 threads
Compressing objects: 100% (7/7), done.
Writing objects: 100% (7/7), 641 bytes | 641.00 KiB/s, done.
Total 7 (delta 5), reused 0 (delta 0)
remote: Resolving deltas: 100% (5/5), completed with 5 local objects.
To github.com:AlaskaLargeScaleSnowAvalanche/akramms.git
   680e22f..1fab0e9  main -> main
```

