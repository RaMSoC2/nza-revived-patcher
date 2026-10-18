package com.ramsoc2.nzarevived;

import android.app.Activity;
import android.content.pm.PackageManager;
import android.location.*;
import android.net.Uri;
import android.os.*;
import android.util.Log;
import org.json.*;
import org.xmlpull.v1.XmlSerializer;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Original response-schema adapter; only the internal typed broker uses the network. */
final class NzaNearbyCache {
    private static boolean started,busy,ready;
    private static long lastAttempt;
    static void start(Activity activity) {
        if(started||!activity.getClass().getName().startsWith("com.apportable."))return;
        if(activity.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)!=PackageManager.PERMISSION_GRANTED)return;
        started=true;
        File target=new File(activity.getFilesDir(),"LocalFiles/nza-nearby.plist");
        LocationManager manager=(LocationManager)activity.getSystemService(Activity.LOCATION_SERVICE);
        Handler main=new Handler(Looper.getMainLooper());
        LocationListener listener=new LocationListener(){
            public void onLocationChanged(Location location){if(accept(activity,target,location))manager.removeUpdates(this);}
            public void onStatusChanged(String p,int s,Bundle e){}
            public void onProviderEnabled(String p){}
            public void onProviderDisabled(String p){}
        };
        for(String provider:new String[]{LocationManager.GPS_PROVIDER,LocationManager.NETWORK_PROVIDER}){
            try {
                Location known=manager.getLastKnownLocation(provider);
                if(known!=null&&accept(activity,target,known))return;
                if(manager.isProviderEnabled(provider))manager.requestLocationUpdates(provider,1000,0,listener,Looper.getMainLooper());
            } catch(SecurityException failure){Log.w("NZA-Places","Provider not permitted: "+provider);}
        }
        // A temporary broker outage must not permanently disable this session.
        // At most two further attempts, still foreground-only, using recent fixes.
        for(long delay:new long[]{65000,130000})main.postDelayed(()->{
            if(activity.isFinishing()||activity.isDestroyed()||!activity.hasWindowFocus())return;
            for(String provider:new String[]{LocationManager.GPS_PROVIDER,LocationManager.NETWORK_PROVIDER}){
                try{Location known=manager.getLastKnownLocation(provider);if(known!=null&&accept(activity,target,known))break;}
                catch(SecurityException ignored){}
            }
        },delay);
        main.postDelayed(()->{manager.removeUpdates(listener);synchronized(NzaNearbyCache.class){started=false;}},60000);
    }
    private static synchronized boolean accept(Activity activity,File target,Location location){
        if(ready)return true;
        long age=(SystemClock.elapsedRealtimeNanos()-location.getElapsedRealtimeNanos())/1000000;
        long now=SystemClock.elapsedRealtime();
        if(age<0||age>300000||busy||now-lastAttempt<15000)return false;
        lastAttempt=now;
        busy=true;
        // Only these rounded numbers ever cross the IPC / network boundary.
        double lat=Math.round(location.getLatitude()*100)/100.0,lon=Math.round(location.getLongitude()*100)/100.0;
        new Thread(()->{
            try {
                Bundle input=new Bundle();input.putDouble("latitude",lat);input.putDouble("longitude",lon);
                Bundle output=activity.getContentResolver().call(Uri.parse("content://com.ramsoc2.nzarevived.nearby"),"nearby",null,input);
                String text=output==null?null:output.getString("json");
                if(text==null){Log.w("NZA-Places","Query unavailable: "+(output==null?"no_reply":output.getString("error")));return;}
                JSONArray rows=new JSONObject(text).getJSONArray("places");
                List<JSONObject> places=new ArrayList<>();
                for(int i=0;i<rows.length();i++)places.add(rows.getJSONObject(i));
                places.sort(Comparator.comparingDouble(p->distance(lat,lon,p.optDouble("latitude"),p.optDouble("longitude"))));
                File temporary=new File(target.getPath()+".tmp");target.getParentFile().mkdirs();
                try(FileOutputStream stream=new FileOutputStream(temporary)){
                    XmlSerializer x=android.util.Xml.newSerializer();x.setOutput(stream,"UTF-8");x.startDocument("UTF-8",true);
                    x.startTag(null,"plist").attribute(null,"version","1.0").startTag(null,"dict");
                    key(x,"placeSearchResults");x.startTag(null,"array");
                    for(JSONObject place:places.subList(0,Math.min(60,places.size()))){
                        x.startTag(null,"dict");value(x,"name","string",place.getString("name"));
                        value(x,"latitude","real",Double.toString(place.getDouble("latitude")));
                        value(x,"longitude","real",Double.toString(place.getDouble("longitude")));
                        int kind=place.getString("osm_type").equals("node")?0:place.getString("osm_type").equals("way")?1:2;
                        long id=-(1000000000000L+place.getLong("osm_id")*4+kind);
                        value(x,"poiId","integer",Long.toString(id));x.endTag(null,"dict");
                    }
                    x.endTag(null,"array");value(x,"source","string","OpenStreetMap contributors / Overpass; experimental adapter");
                    x.endTag(null,"dict").endTag(null,"plist");x.endDocument();x.flush();stream.getFD().sync();
                }
                Files.move(temporary.toPath(),target.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                synchronized(NzaNearbyCache.class){ready=true;}
                Log.i("NZA-Places","Nearby cache ready count="+places.size()+" broker_cached="+output.getBoolean("cached"));
                activity.runOnUiThread(()->android.widget.Toast.makeText(activity,"Lugares prontos: Â© OpenStreetMap contributors. Reabra a busca.",android.widget.Toast.LENGTH_LONG).show());
            } catch(Exception failure){Log.w("NZA-Places","Nearby cache unavailable: "+failure.getClass().getSimpleName());}
            finally {synchronized(NzaNearbyCache.class){busy=false;}}
        },"nza-nearby-cache").start();
        return false;
    }
    private static double distance(double a,double b,double c,double d){float[] r=new float[1];Location.distanceBetween(a,b,c,d,r);return r[0];}
    private static void key(XmlSerializer x,String k)throws IOException{x.startTag(null,"key").text(k).endTag(null,"key");}
    private static void value(XmlSerializer x,String k,String type,String v)throws IOException{key(x,k);x.startTag(null,type).text(v).endTag(null,type);}
}
