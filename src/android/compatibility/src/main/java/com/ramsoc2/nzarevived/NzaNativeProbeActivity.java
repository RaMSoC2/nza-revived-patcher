package com.ramsoc2.nzarevived;
import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.widget.TextView;
import com.zettabridge.core.ZBridge;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.json.JSONObject;
public final class NzaNativeProbeActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView status = new TextView(this);
        status.setTextSize(18); status.setPadding(24,24,24,24);
        status.setText("ARM64 host / ARM32 guest test running..."); setContentView(status);
        new Thread(() -> {
            JSONObject report = new JSONObject();
            try {
                boolean dynamic = getIntent().getBooleanExtra("dynamic",false);
                boolean ashmem = getIntent().getBooleanExtra("ashmem",false);
                boolean inotify = getIntent().getBooleanExtra("inotify",false);
                report.put("dynamic",dynamic);
                report.put("ashmem",ashmem);
                report.put("inotify",inotify);
                report.put("host_is_64_bit",android.os.Process.is64Bit());
                report.put("android_api",Build.VERSION.SDK_INT);
                report.put("game_loading_validated",false);
                RuntimeBundle.install(this);
                String name = inotify ? "nza_probe_inotify" : ashmem ? "nza_probe_ashmem" : dynamic ? "nza_probe_dynamic" : "nza_probe_static";
                File elf = new File(getFilesDir(),name);
                try (InputStream in = getAssets().open("nza-probe/"+name);
                     OutputStream out = new FileOutputStream(elf)) {
                    byte[] b = new byte[65536]; int n;
                    while ((n = in.read(b)) >= 0) out.write(b,0,n);
                }
                File marker = new File(getFilesDir(),name+"-marker.txt");
                if (marker.exists() && !marker.delete()) throw new IOException("Cannot reset own probe marker");
                int code = ZBridge.runExecutable(new File(getFilesDir(),"zb/sysroot").getAbsolutePath(),
                    new String[]{elf.getAbsolutePath(),marker.getAbsolutePath()},
                    new String[]{"PATH=/system/bin","LANG=C"});
                String value = marker.exists() ? new String(Files.readAllBytes(marker.toPath()),StandardCharsets.US_ASCII) : "";
                report.put("guest_exit",code); report.put("marker",value);
                report.put("passed",android.os.Process.is64Bit() && code==0 && value.equals(
                    inotify ? "NZA_INOTIFY_EVENT_OK\n" : ashmem ? "NZA_ASHMEM_REAL_MAPPING_OK\n" : "NZA_ARM32_EXEC_OK\n"));
            } catch (Throwable failure) {
                try { report.put("passed",false); report.put("error",failure.toString()); } catch(Exception ignored){}
            }
            String text = report.toString();
            try (FileOutputStream out = new FileOutputStream(new File(getFilesDir(),"nza-native-probe.json"))) {
                out.write(text.getBytes(StandardCharsets.UTF_8));
            } catch (IOException ignored) {}
            runOnUiThread(() -> status.setText(text));
        },"nza-native-smoke").start();
    }
}
