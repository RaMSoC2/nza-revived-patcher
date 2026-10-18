package com.ramsoc2.nzarevived;

/** Fail closed before plugin import/execution if the process policy is unavailable. */
final class NzaNetworkGuard {
    private static boolean ready;
    private static int failure;
    private static native int installNative();
    static synchronized boolean install(android.content.Context context) {
        if(ready)return true;
        try {
            System.loadLibrary("nza_network_guard");
            failure=installNative();ready=failure==0;
            if(ready)NzaNetworkPolicy.blockLegacyUrlConnections();
        } catch(Throwable problem) {
            failure=-1;ready=false;
            android.util.Log.e("NZA-NetGuard","Cannot install process network policy",problem);
        }
        android.util.Log.i("NZA-NetGuard","legacy_sockets_blocked="+ready+" code="+failure);
        try(java.io.FileOutputStream out=context.openFileOutput("nza-network-policy-"+android.os.Process.myPid()+".json",0)) {
            out.write(("{\"installed\":"+ready+",\"code\":"+failure+",\"url_connections_blocked\":"+ready+"}").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        } catch(java.io.IOException ignored) {}
        return ready;
    }
    static void requireReady() throws java.io.IOException {
        if(!ready)throw new java.io.IOException("Proteção de rede indisponível ("+failure+"). O cliente antigo não foi iniciado.");
    }
}
