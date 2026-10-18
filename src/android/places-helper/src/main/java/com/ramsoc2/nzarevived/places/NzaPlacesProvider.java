package com.ramsoc2.nzarevived.places;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Non-exported, typed broker in the APK's dedicated :places process. */
public final class NzaPlacesProvider extends ContentProvider {
    private static final long TTL=24*60*60*1000L;
    private static long attemptedAt;
    public boolean onCreate(){return true;}

    @Override public synchronized Bundle call(String method,String arg,Bundle extras) {
        if(Binder.getCallingUid()!=android.os.Process.myUid())throw new SecurityException("Internal NZA caller required");
        if(!"nearby".equals(method)||extras==null)throw new IllegalArgumentException("Unknown operation");
        if(!getContext().getSharedPreferences("privacy",0).getBoolean("enabled",true)) {
            Bundle answer=new Bundle();answer.putString("error","disabled");return answer;
        }
        double lat=extras.getDouble("latitude",Double.NaN),lon=extras.getDouble("longitude",Double.NaN);
        if(!Double.isFinite(lat)||!Double.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)
            throw new IllegalArgumentException("Invalid region");
        // Privacy boundary enforced by the broker as well as the client.
        lat=Math.round(lat*100)/100.0;lon=Math.round(lon*100)/100.0;
        long identity=Binder.clearCallingIdentity();
        try {
            Bundle answer=new Bundle();
            File cache=new File(getContext().getCacheDir(),"nearby-"+Math.round(lat*100)+"-"+Math.round(lon*100)+".json");
            long now=System.currentTimeMillis();
            if(cache.isFile()&&now-cache.lastModified()<TTL){
                answer.putString("json",new String(Files.readAllBytes(cache.toPath()),StandardCharsets.UTF_8));answer.putBoolean("cached",true);return answer;
            }
            if(now-attemptedAt<60000){answer.putString("error","rate_limited");return answer;}
            attemptedAt=now;
            String point=String.format(Locale.ROOT,"%.2f,%.2f",lat,lon);
            String query="[out:json][timeout:15];(nwr(around:2500,"+point+")[\"name\"][\"shop\"];"
                +"nwr(around:2500,"+point+")[\"name\"][\"amenity\"~\"^(restaurant|cafe|fast_food|pharmacy|hospital|clinic|fuel|bank|cinema|library|school|police|fire_station)$\"];);out center 100;";
            JSONArray input=new JSONObject(NzaOverpassTransport.fetch(query)).getJSONArray("elements");
            JSONArray places=new JSONArray();Set<String> seen=new HashSet<>();
            for(int i=0;i<input.length();i++){
                JSONObject row=input.getJSONObject(i),tags=row.optJSONObject("tags");
                if(tags==null)continue;
                String name=tags.optString("name","").trim();
                JSONObject center=row.optJSONObject("center");
                double x=row.optDouble("lat",center==null?Double.NaN:center.optDouble("lat",Double.NaN));
                double y=row.optDouble("lon",center==null?Double.NaN:center.optDouble("lon",Double.NaN));
                if(name.isEmpty()||name.length()>150||!Double.isFinite(x)||!Double.isFinite(y))continue;
                String unique=name+":"+Math.round(x*10000)+":"+Math.round(y*10000);
                if(!seen.add(unique))continue;
                JSONObject place=new JSONObject().put("name",name).put("latitude",x).put("longitude",y)
                    .put("osm_type",row.getString("type")).put("osm_id",row.getLong("id"));
                places.put(place);
            }
            String result=new JSONObject().put("source","OpenStreetMap").put("fetched_at",now)
                .put("region_latitude",lat).put("region_longitude",lon).put("places",places).toString();
            File temp=new File(cache.getPath()+".tmp");Files.write(temp.toPath(),result.getBytes(StandardCharsets.UTF_8));
            Files.move(temp.toPath(),cache.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            answer.putString("json",result);answer.putBoolean("cached",false);return answer;
        } catch(Exception failure) {
            android.util.Log.w("NZA-PlacesBroker","Query failed: "+failure.getClass().getSimpleName());
            Bundle answer=new Bundle();answer.putString("error",failure.getClass().getSimpleName());return answer;
        } finally {Binder.restoreCallingIdentity(identity);}
    }
    public Cursor query(Uri u,String[] p,String s,String[] a,String o){throw new UnsupportedOperationException();}
    public String getType(Uri u){return null;}
    public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
    public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
}
