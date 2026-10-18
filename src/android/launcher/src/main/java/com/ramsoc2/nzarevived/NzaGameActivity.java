package com.ramsoc2.nzarevived;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;
import android.net.Uri;
import java.io.*;

/** Single-game entry point. Preparation is automatic and never reimports an existing installation. */
public final class NzaGameActivity extends Activity {
    private boolean permissionPending;
    private boolean preparing;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        NzaPlacesShortcut.install(this);
        TextView message=new TextView(this);message.setGravity(Gravity.CENTER);
        message.setText("No Zombies Allowed");message.setTextColor(0xffffffff);
        message.setBackgroundColor(0xff000000);setContentView(message);
        permissionPending=state!=null&&state.getBoolean("location-pending");
    }

    @Override protected void onPostResume() {
        super.onPostResume();
        if (permissionPending || preparing) return;
        // Use the visible, opaque entry activity, before import/task switching.
        permissionPending=true;
        if (!NzaLocationPermission.request(this,"com.booyah.zombie")) {
            permissionPending=false;
            prepareGame();
        }
    }

    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==NzaLocationPermission.REQUEST) {
            permissionPending=false;
            NzaLocationPermission.complete(this,results);
            prepareGame(); // Denial keeps the game available offline.
        }
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("location-pending",permissionPending);
        super.onSaveInstanceState(state);
    }

    private void prepareGame() {
        if(preparing || isFinishing() || isDestroyed())return;
        preparing=true;
        new Thread(()->{
            try {
                NzaNetworkGuard.requireReady();
                PluginRecord record=PluginStore.find(this,"com.booyah.zombie");
                if(record==null) {
                    File input=new File(getCacheDir(),"nza-first-install.apk");
                    try(InputStream in=getAssets().open("nza-probe/trial-67.apk");OutputStream out=new FileOutputStream(input)) {
                        byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1)out.write(bytes,0,n);
                    }
                    record=PluginStore.importApk(this,Uri.fromFile(input));
                }
                if(!record.isLaunchable())throw new IOException("The game could not be prepared.");
                runOnUiThread(()->{startActivity(PluginSwitchActivity.intent(this,"com.booyah.zombie"));finish();});
            } catch(Exception failure) {
                android.util.Log.e("NzaGame","Game preparation failed",failure);
                runOnUiThread(()->new AlertDialog.Builder(this).setTitle("No Zombies Allowed")
                    .setMessage("Não foi possível abrir o jogo. Sua partida foi preservada.")
                    .setPositiveButton("Fechar",(d,w)->finish()).show());
            }
        },"nza-game-start").start();
    }
}
