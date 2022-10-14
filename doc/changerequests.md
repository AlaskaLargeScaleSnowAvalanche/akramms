# RAMMS Change Requests: 2022-10-13

1. Divide up the work done by RAMMS_LSHM into phases.  Add an
   additional parameter to the `ramms_lshm.sav` command line program
   to run just a single phase.  Phases should be as follows:

   * **Phase 1:** Generate derivatives of the DEM and FOREST files:
     `curvidl.tif` and `slope.tif`.  These will be the same for any
     return period, so they may be generated just once and then copied
     into the appropriate directory for RAMMS runs.  Have an
     `--output` parameter that tells which directory to write the
     files into.

   * **Phase 2:** Generate the `_mu.tif` and `_xi.tif` files.

     **QUESTION:** Do these depend on `scenario.txt` or other
     avalanche-specific inputs, or can they ALSO be generated once per
     secene?  (If the former, combine with Phase 1).

   * **Phase 3:** Generate the `.xyz`, `.av2`, `.bat`, `.xy-coord`,
     `.dom`, `.rel`, `.var.` and `.out.bat` files.

   * **Phase 4:** Run the `.out.bat` files, i.e. the actual LSHM
     simulations.  Produces `.out.gz`, `.out.log` and `out.end` files.

   * **Phase 5:** Merge results

   * **Phase 6:** Write GEOTIFF result files: `MAXPRESSURE`,
     `MAXHEIGHT`, `MAXVELOCITY`, `XI`, `ALBAGERUNG STEF`, `ID
     GEOTIFF`, `COUNT`.

   * **Phase 7:** Delete Temporary Files

   **PUTTING IT TOGETHER:**

   Consider an overall run that is launched as follows:
   ```
   idlrt.exe ramms_lshm.sav -args scenario.txt
   ```

   With the work split up into phases, this will now be accomplished
   by launching the following series of commands:
   ```
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 1 -output C:\Users\efischer\av\prj\juneau1\RAMMS\juneau130yFor\RESULTS\juneau1_For
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 2
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 3
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 4
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 5
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 6
   idlrt.exe ramms_lshm.sav -args scenario.txt -phase 7
   ```

2. Send output to STDOUT instead of `lshm_rock.log`.

3. Make RAMMS IDL exit cleanly.  It seems to work OK when run locally
   on Windows.  But `ssh <windows-host> run_ramms.bat` from Linux
   never terminates on the Linux side.  The `ssh` command on Linux
   hangs after RAMMS is done running.  I don't know why this is, but
   it looks like maybe RAMMS is leaving Zombie IDL Bridge processes
   running on the Windows side.  Bottom line is, it needs to exit
   cleanly on Windows, all processes must terminate or be killed, and
   it must return to Linux if called through `ssh`.  Short of that, it
   needs to print an "Exiting" message just before it terminates, so
   the Linux-side `ssh` can recognize and kill the socket when
   computation is complete.

   (This issue will be easier to debug once RAMMS is split into phases).

4. **QUESTION:** * In the `_mu` and `_xi` filenames, where does `300`
   come from?  Eg: `juneau1_For_L300_mu.tif`.
