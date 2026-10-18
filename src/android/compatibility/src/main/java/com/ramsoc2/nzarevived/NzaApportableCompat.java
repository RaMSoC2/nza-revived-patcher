package com.ramsoc2.nzarevived;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Arrays;

/** Private EXP-010 import fix; accepts only the verified trial-67 prepared engine. */
final class NzaApportableCompat {
    private static final String BEFORE = "407e82f755501d62403108d2c5e61bc4760bfa9746040dd308aaa9afcc4ca4a0";
    private static final String AFTER = "4de2a7a34adad6b724b2e69e6b0ceae6568c64a056c7efa3bfd47568c7a87482";
    private static final int OFFSET = 30418896;
    private static final int LENGTH = 168;

    private NzaApportableCompat() {}

    static void apply(File library) throws IOException {
        String before = digest(library);
        if (AFTER.equals(before)) return;
        if (!BEFORE.equals(before)) throw new IOException("Unrecognized NZA engine; SONAME fix refused");
        try (RandomAccessFile out = new RandomAccessFile(library, "rw")) {
            byte[] original = new byte[LENGTH];
            out.seek(OFFSET);
            out.readFully(original);
            byte[] changed = original.clone();
            // Remove DT_SONAME by shifting the entries through DT_NULL.
            // DT_NEEDED strings and entries remain byte-for-byte unchanged.
            System.arraycopy(original, 8, changed, 0, LENGTH - 8);
            Arrays.fill(changed, LENGTH - 8, LENGTH, (byte) 0);
            boolean verified = false;
            try {
                out.seek(OFFSET);
                out.write(changed);
                out.getFD().sync();
                if (!AFTER.equals(digest(library))) throw new IOException("NZA SONAME output hash mismatch");
                verified = true;
            } finally {
                if (!verified) {
                    out.seek(OFFSET);
                    out.write(original);
                    out.getFD().sync();
                }
            }
        }
        String report = "{\"patch\":\"remove self-colliding libGLESv2 SONAME\","
                + "\"before_sha256\":\"" + BEFORE + "\",\"after_sha256\":\"" + AFTER + "\"}\n";
        Files.write(new File(library.getParentFile(), "nza-soname-fix.json").toPath(),
                report.getBytes(StandardCharsets.UTF_8));
    }

    private static String digest(File file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (FileInputStream in = new FileInputStream(file)) {
                byte[] buffer = new byte[65536];
                int count;
                while ((count = in.read(buffer)) != -1) digest.update(buffer, 0, count);
            }
            byte[] hash = digest.digest();
            StringBuilder result = new StringBuilder(64);
            for (byte value : hash) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException error) {
            throw new IOException(error);
        }
    }
}
