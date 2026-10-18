package com.ramsoc2.nzarevived;

import android.content.Context;
import java.io.File;

/** Private diagnostic: records only this guest process's native SIGBUS state. */
final class NzaHostFaultCapture {
    static { System.loadLibrary("nza_host_fault"); }
    private static native boolean configure(String binary, String maps);
    static void install(Context context) {
        String name="nza-host-fault-"+android.os.Process.myPid();
        if(!configure(new File(context.getFilesDir(),name+".bin").getAbsolutePath(),
                      new File(context.getFilesDir(),name+".maps").getAbsolutePath())) {
            android.util.Log.e("NzaHostFault", "Cannot prepare private crash capture");
        }
    }
}
