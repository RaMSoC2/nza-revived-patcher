package com.ramsoc2.nzarevived;

import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Handler;
import android.os.Looper;
import android.view.PixelCopy;
import android.view.SurfaceView;
import android.view.View;
import android.view.ViewGroup;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** Diagnostic capture of the game's own SurfaceView, never a whole-phone screenshot. */
final class NzaFrameCapture {
    private static SurfaceView surface(View view) {
        if (view instanceof SurfaceView) return (SurfaceView)view;
        if (view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++) {
                SurfaceView found=surface(group.getChildAt(i));
                if(found!=null)return found;
            }
        }
        return null;
    }
    static void start(Activity activity) {
        String name=activity.getClass().getName();
        if(!name.startsWith("com.apportable.")&&!name.startsWith("com.booyah."))return;
        activity.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        Handler handler=new Handler(Looper.getMainLooper());
        for(int i=1;i<=3;i++) {
            final int index=i;
            handler.postDelayed(()->capture(activity,index,handler),i==1?3000:i==2?12000:30000);
        }
    }
    private static void capture(Activity activity,int index,Handler handler) {
        if(activity.isFinishing()||activity.isDestroyed()||!activity.hasWindowFocus())return;
        SurfaceView view=surface(activity.getWindow().getDecorView());
        if(view==null||view.getWidth()<=0||view.getHeight()<=0||!view.getHolder().getSurface().isValid())return;
        Bitmap bitmap=Bitmap.createBitmap(view.getWidth(),view.getHeight(),Bitmap.Config.ARGB_8888);
        File dir=activity.getFilesDir();
        String stem="nza-frame-"+android.os.Process.myPid()+"-"+index;
        PixelCopy.request(view,bitmap,result->new Thread(()->{
            try {
                if(result==PixelCopy.SUCCESS)try(FileOutputStream out=new FileOutputStream(new File(dir,stem+".png"))) {
                    bitmap.compress(Bitmap.CompressFormat.PNG,100,out);
                }
                try(FileOutputStream out=new FileOutputStream(new File(dir,stem+".txt"))) {
                    out.write(("PixelCopy result="+result+" activity="+activity.getClass().getName()
                        +" width="+bitmap.getWidth()+" height="+bitmap.getHeight()+"\n").getBytes(StandardCharsets.UTF_8));
                }
            } catch(Exception ignored) {} finally {bitmap.recycle();}
        },"nza-own-frame-writer").start(),handler);
    }
}
