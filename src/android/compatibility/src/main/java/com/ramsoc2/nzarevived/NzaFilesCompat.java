package com.ramsoc2.nzarevived;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

/** Existing app-owned directory alias for Apportable's /data/data/ disk prefix. */
final class NzaFilesCompat {
    private static boolean logged;
    static File alias(File files) {
        String modern="/data/user/0/com.ramsoc2.nzarevived/";
        String path=files.getAbsolutePath();
        if(!path.startsWith(modern))return files;
        File legacy=new File("/data/data/com.ramsoc2.nzarevived/"+path.substring(modern.length()));
        try {
            if(!Files.isSameFile(files.toPath(),legacy.toPath()))
                throw new IOException("Legacy data alias does not refer to the same directory");
        } catch(IOException error){throw new IllegalStateException("NZA storage alias refused",error);}
        if(!logged) {
            logged=true;
            android.util.Log.i("NZA-Files","Verified same-directory legacy alias: "+path+" -> "+legacy);
        }
        return legacy;
    }
}
