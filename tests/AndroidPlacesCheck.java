package org.nza.integration;

/** Instrumentation for the isolated emulator only. Uses a labeled local cache fixture. */
public final class AndroidPlacesCheck extends android.app.Instrumentation {
    @Override public void onCreate(android.os.Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){
        android.os.Bundle result=new android.os.Bundle();
        try {
            android.content.Context context=getTargetContext();
            java.io.File marker=new java.io.File(context.getFilesDir(),"nza-network-policy-"+android.os.Process.myPid()+".json");
            // Instrumentation starts its thread before Application.onCreate can finish.
            long deadline=android.os.SystemClock.elapsedRealtime()+15000;
            while(!marker.isFile()&&android.os.SystemClock.elapsedRealtime()<deadline)android.os.SystemClock.sleep(100);
            org.json.JSONObject policy=new org.json.JSONObject(new String(java.nio.file.Files.readAllBytes(marker.toPath()),java.nio.charset.StandardCharsets.UTF_8));
            if(!policy.getBoolean("installed")||!policy.getBoolean("url_connections_blocked"))throw new AssertionError("Process policy missing");
            try {new java.net.URL("https://legacy.invalid/").openConnection();throw new AssertionError("Legacy URL escaped");}
            catch(java.io.IOException expected){}
            try(java.net.Socket socket=new java.net.Socket()) {
                try {socket.connect(new java.net.InetSocketAddress("127.0.0.1",9),1000);throw new AssertionError("Legacy socket escaped");}
                catch(java.io.IOException expected){}
            }
            java.io.File fixture=new java.io.File(context.getCacheDir(),"nearby-0-0.json");
            if(!fixture.isFile())throw new AssertionError("Labeled local fixture required before query");
            android.os.Bundle query=new android.os.Bundle();query.putDouble("latitude",0);query.putDouble("longitude",0);
            android.os.Bundle response=context.getContentResolver().call(android.net.Uri.parse("content://com.ramsoc2.nzarevived.nearby"),"nearby",null,query);
            if(response==null||response.getString("json")==null||!response.getBoolean("cached"))throw new AssertionError("Internal cache query failed");
            org.json.JSONArray rows=new org.json.JSONObject(response.getString("json")).getJSONArray("places");
            if(rows.length()!=1||!"LAB FIXTURE".equals(rows.getJSONObject(0).getString("name")))throw new AssertionError("Wrong test fixture");
            result.putString("validation","native_policy_installed; legacy_url_denied; legacy_socket_denied; internal_places_cache_ok");
            finish(-1,result);
        } catch(Throwable failure) {
            result.putString("failure",failure.toString());finish(0,result);
        }
    }
}
