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






## Project Members

* Gabriel Wolken <gabriel.wolken@alaska.gov>
* Yves Bühler <buehler@slf.ch>
* Richard Lader Jr. <rtladerjr@alaska.edu>
* Elizabeth Fischer <eafischer2@alaska.edu>
* Marc Christen <christen@slf.ch>

### All Project Members:

gabriel.wolken@alaska.gov,buehler@slf.ch,rtladerjr@alaska.edu,eafischer2@alaska.edu,christen@slf.ch
