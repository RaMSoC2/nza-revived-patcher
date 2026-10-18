package com.apportable.app;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Matrix;
import android.util.Log;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.ImageView;
import com.ramsoc2.nzarevived.NzaAdaptiveScreen;
import java.io.InputStream;

/** Scoped compatibility adapter; original splash pixels, proportional fit, no crop. */
public final class SplashScreen {
    private static ImageView image;
    private static Bitmap bitmap;
    private SplashScreen() {}
    public static void show(FrameLayout root) {
        NzaAdaptiveScreen.attach(root);
        if(image!=null)return;
        try(InputStream input=root.getContext().getAssets().open("Default.png")) {
            Bitmap original=BitmapFactory.decodeStream(input);
            if(original==null)throw new IllegalStateException("Original splash cannot decode");
            Matrix rotate=new Matrix();rotate.postRotate(-90);
            bitmap=Bitmap.createBitmap(original,0,0,original.getWidth(),original.getHeight(),rotate,true);
            if(bitmap!=original)original.recycle();
            image=new ImageView(root.getContext());
            image.setBackgroundColor(Color.BLACK);
            image.setScaleType(ImageView.ScaleType.FIT_CENTER);
            image.setImageBitmap(bitmap);
            root.addView(image,new FrameLayout.LayoutParams(-1,-1,Gravity.CENTER));
            Log.i("NzaScreen","Original splash fit="+bitmap.getWidth()+"x"+bitmap.getHeight());
        } catch(Exception failure) {Log.e("NzaScreen","Splash adapter failed",failure);}
    }
    public static void hide(FrameLayout root) {
        if(image!=null) {root.removeView(image);image.setImageDrawable(null);image=null;}
        if(bitmap!=null) {bitmap.recycle();bitmap=null;}
    }
}
