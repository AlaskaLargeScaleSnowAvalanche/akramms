# Alaska RAMMS
Pipeline of Code used to prepare data for and run RAMMS Mega Scale Hazard Mapping (MSHM) in Alaska

## Running MSHM

MSHM requires the following processes to be able to run concurrently:

1. The launch process
1. ArcGIS on Windows
1. Reddis Queue (rq) working (and also the generic rq server process)
1. Overrun processing

The following should be used to set this up:

1. On Windows, launch ArcGIS and make sure you are logged into it.

1. On your laptop, set up a tunnel to the Linux machine (antevorta; or just use the `antevorta_tunnel` shell script):
   ```
   ssh -N -T -L 5900:localhost:5900 antevorta
   ```
   Then login normally via `ssh antevorta` from other laptop windows.  Use this in your `~/.ssh/config`:
   ```
   Host antevorta
       User <your username>
       HostName <ip address of antevorta>
       ControlMaster auto
       ControlPath ~/.ssh/master-%r%h:%p
       ServerAliveInterval 900
       LogLevel Quiet
       Protocol 2
       ConnectTimeout 300
       ForwardX11 yes
       ForwardX11Timeout 7d
       ForwardAgent yes
   ```

1. On Linux (antevorta), start the rq worker, which provides queues for eCognition and ArcGIS jobs to run.  (The rq server must also be running, if it is not automatically started with Linux).
   ```
   screen -S rq
   rq worker  --with-scheduler q_idl q_ecognition q_arcgis

1. IDL *requires* an X11 server to run:
   ```
   screen -S x11
   ~/sh/start_mate
   ```

1. Start the main process running:
   ```
   screen -S akramms
   crashloop -w 30 :: akramms run ak.full
   ```

1. At some point, start the overrun process, necessary to finish up and close out combos
   ```
   screen -S overrun
   crashloop -p 3600 :: akramms overrun <ak>.full
   ```

## Installing eCognition

MSHM uses the *eCognition Server* from a Docker container.  To get this working, you must install the eCognition license manager (which is just the FlexLM license manager licensed by Trimble) on a Windows machine, and then point the Docker container to it:

1. Follow eCognition instructions, get an entitlement, install the license server on a Windows machine, etc.  We do not believe eCognition Developer needs to be installed, just the license manager.

1. Open incoming ports 27000 -- 27009 on the Windows machine (read up on Windows Defender, how to do this).

1. On the Windows machine, point your browser to *localhost:8090* to administer the license manager.  Username is *admin*, set a password if required.

1. Click on *Vendor Daemon Configuration* and figure out which port the Vendor Daemon uses.  Open that incoming port in the firewall as well.

Now it should work.  **NOTE:** Docker containers can remain in Zombie state.  If you get the message that too many licenses are checked out, use `docker ps` and `docker rm` to remove Zombie Docker runs of eCognition that are taking up licenses.




## Project Members

* Gabriel Wolken <gabriel.wolken@alaska.gov>
* Yves Bühler <buehler@slf.ch>
* Richard Lader Jr. <rtladerjr@alaska.edu>
* Elizabeth Fischer <eafischer2@alaska.edu>
* Marc Christen <christen@slf.ch>

### All Project Members:

gabriel.wolken@alaska.gov,buehler@slf.ch,rtladerjr@alaska.edu,eafischer2@alaska.edu,christen@slf.ch
