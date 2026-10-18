package com.ramsoc2.nzarevived;
import android.content.Context;
import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Applies only an exact-checkpoint recipe before the extracted private engine is loaded. */
final class NzaPlacesCompat {
    static void apply(Context host,File library)throws Exception {
        JSONObject recipe;
        try(InputStream in=host.getAssets().open("nza-probe/nearby-engine.json")){
            ByteArrayOutputStream buffer=new ByteArrayOutputStream();
            byte[] block=new byte[8192];int count;
            while((count=in.read(block))!=-1){if(buffer.size()+count>262144)throw new IOException("Oversized places recipe");buffer.write(block,0,count);}
            recipe=new JSONObject(new String(buffer.toByteArray(),java.nio.charset.StandardCharsets.UTF_8));
        }
        byte[] data=Files.readAllBytes(library.toPath());
        if(hash(data).equals(recipe.getString("after_sha256")))return;
        NzaSaveCompat.apply(library);data=Files.readAllBytes(library.toPath());
        if(!hash(data).equals(recipe.getString("before_sha256")))throw new IOException("Nearby engine hash guard");
        byte[] append=Base64.getDecoder().decode(recipe.getString("append_base64"));
        byte[] output=Arrays.copyOf(data,data.length+append.length);System.arraycopy(append,0,output,data.length,append.length);
        JSONArray edits=recipe.getJSONArray("changes");
        for(int i=0;i<edits.length();i++){
            JSONObject edit=edits.getJSONObject(i);int offset=edit.getInt("offset");
            byte[] before=hex(edit.getString("before")),after=hex(edit.getString("after"));
            if(!Arrays.equals(before,Arrays.copyOfRange(data,offset,offset+before.length)))throw new IOException("Nearby byte guard");
            System.arraycopy(after,0,output,offset,after.length);
        }
        if(!hash(output).equals(recipe.getString("after_sha256")))throw new IOException("Nearby output hash guard");
        File temporary=new File(library.getParentFile(),"nza-nearby-engine.tmp");
        try {
            try(FileOutputStream out=new FileOutputStream(temporary)){out.write(output);out.getFD().sync();}
            if(!temporary.setReadOnly())throw new IOException("Engine protection failed");
            Files.move(temporary.toPath(),library.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        } finally {Files.deleteIfExists(temporary.toPath());}
        android.util.Log.i("NZA-Places","Verified original places-failure adapter installed");
    }
    private static String hash(byte[] bytes)throws Exception{
        StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();
    }
    private static byte[] hex(String value){byte[] b=new byte[value.length()/2];for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(value.substring(i*2,i*2+2),16);return b;}
}
