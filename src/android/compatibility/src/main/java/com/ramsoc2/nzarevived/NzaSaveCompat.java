package com.ramsoc2.nzarevived;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;

/** Private, hash-guarded correction of the original atomic-file commit helper. */
final class NzaSaveCompat {
    private static final String BEFORE="4de2a7a34adad6b724b2e69e6b0ceae6568c64a056c7efa3bfd47568c7a87482";
    private static final String AFTER="5bd39aa97d496e36e3a27f84911ee4298caac74324a0cb38a093d509a18d7d6e";
    private static final long OFFSET=0x1b57194L;

    static void apply(File library) throws IOException {
        String before=digest(library);
        if(AFTER.equals(before))return;
        if(!BEFORE.equals(before))throw new IOException("Unknown engine; atomic-save correction refused");
        boolean writable=library.canWrite();
        if(!writable&&!library.setWritable(true,true))throw new IOException("Cannot prepare own working engine");
        try(RandomAccessFile file=new RandomAccessFile(library,"rw")) {
            file.seek(OFFSET);
            if(file.readInt()!=0x0900001a)throw new IOException("Atomic-save instruction guard failed");
            boolean verified=false;
            try {
                // BNE -> B: call POSIX rename for existing AND new destinations.
                // The legacy missing-destination path unlinks the nonexistent target
                // and returns failure before rename. Keep the original rename,
                // EINTR retry, result handling and all serialized bytes unchanged.
                file.seek(OFFSET);file.writeInt(0x090000ea);file.getFD().sync();
                if(!AFTER.equals(digest(library)))throw new IOException("Atomic-save output hash mismatch");
                verified=true;
            } finally {
                if(!verified){file.seek(OFFSET);file.writeInt(0x0900001a);file.getFD().sync();}
            }
        } finally {
            if(!writable&&!library.setReadOnly())throw new IOException("Cannot restore working engine protection");
        }
        String report="{\"patch\":\"original atomic rename for new destinations\",\"offset\":\"0x1b57194\","
            +"\"before_sha256\":\""+BEFORE+"\",\"after_sha256\":\""+AFTER+"\"}\n";
        Files.write(new File(library.getParentFile(),"nza-save-fix.json").toPath(),report.getBytes(StandardCharsets.UTF_8));
    }
    private static String digest(File file) throws IOException {
        try {
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(FileInputStream in=new FileInputStream(file)) {
                byte[] buffer=new byte[65536];int count;
                while((count=in.read(buffer))!=-1)digest.update(buffer,0,count);
            }
            StringBuilder text=new StringBuilder();
            for(byte value:digest.digest())text.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
            return text.toString();
        } catch(java.security.NoSuchAlgorithmException failure){throw new IOException(failure);}
    }
}
