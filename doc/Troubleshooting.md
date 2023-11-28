


## SSH Permission Denied

### Problem

The `sshpass` command yields *permission denied*

### Reason

This happens after you change your password as per OIT requirements.

### Solution

Update to the new password in `~/.ssh/davos_password`.  Make sure that file has `rw` permissions ONLY for the owner (not group or public).



## IDL Hangs

### Problem

A RAMMS Stage 1 job has been launched but it's hanging on `antevorta` and not actually running RAMMS STage 1.

### Reason

IDL lost its license key.  Now it's being "helpful" by running, but not before putting up a click-through dialog.  Unfortunately you cannot see that dialog becuase this is happening via `ssh` and not on the Windows desktop.  So all you see is IDL hangs.

### Solution

1. Launch `procexp.exe`, found on the Windows desktop, and use that to kill any processes starting with `idl` (use the search box).

1. Launch `L3Harrice License Administrator` (also on the desktop), and you can see if its license still exists.  You can look at the `idl8.8-per...` file (also on the desktop) to see the Activation Code.

1. Typically, rebooting the Windows machine will restore the IDL license.

1. If not, contact DGGS support.



## ArcGIS: Unexpected Error

### Problem

ArcGIS gives the error:

```
arcgisscripting.ExecuteError: ERROR 999999: Something unexpected
caused the tool to fail. Contact Esri Technical Support
(http://esriurl.com/support) to Report a Bug, and refer to the error
help for potential solutions or workarounds.
```

### Reason

The  `ERROR 999999: Something unexpected caused the tool to fail` is the standard ArcGis undefined error. This has always something to do with the ArcGis software who hang itself up somehow. (Yves)

### Solution

The approach to solve this error is to restart ArcGis. Changing the script would not help.  (Yves)



## ArcGIS: Permission Denied

### Reason

ArcGIS has logged you out, and you need to log back into the mother ship to resume.

### Solution

Launch the ArcGIS Desktop app and login as appropriate.  Leave ArcGIS running on the desktop.
