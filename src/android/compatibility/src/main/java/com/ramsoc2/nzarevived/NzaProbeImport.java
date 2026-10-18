package com.ramsoc2.nzarevived;
import android.app.Activity;
import android.app.AlertDialog;
import android.net.Uri;
import java.io.*;
import java.util.function.Consumer;
final class NzaProbeImport {
    static void start(Activity activity, Consumer<Uri> imported) {
        new Thread(() -> {
            try {
                File target = new File(activity.getCacheDir(), "nza-trial-67.apk");
                try (InputStream in = activity.getAssets().open("nza-probe/trial-67.apk");
                     OutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[65536]; int n;
                    while ((n = in.read(buffer)) >= 0) out.write(buffer, 0, n);
                }
                activity.runOnUiThread(() -> imported.accept(Uri.fromFile(target)));
            } catch (Exception e) {
                activity.runOnUiThread(() -> new AlertDialog.Builder(activity)
                    .setMessage("NZA import failed: " + e).setPositiveButton("OK", null).show());
            }
        }, "nza-private-import").start();
    }
}
