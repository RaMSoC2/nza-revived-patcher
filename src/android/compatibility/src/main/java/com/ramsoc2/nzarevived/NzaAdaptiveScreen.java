package com.ramsoc2.nzarevived;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Rect;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.FrameLayout;

/** Fit the entire legacy canvas across the current usable window; independent X/Y scale, no crop. */
public final class NzaAdaptiveScreen {
    private static final String TAG="NzaScreen";
    private static Dialog lastDialog;
    private static String lastGeometry="";

    private NzaAdaptiveScreen() {}

    public static void attach(FrameLayout root) {
        if (!(root.getContext() instanceof Activity))
            throw new IllegalStateException("NZA root has no activity");
        Activity activity=(Activity)root.getContext();
        if (!activity.getClass().getName().startsWith("com.apportable."))
            throw new IllegalStateException("Not the NZA activity");
        root.setBackgroundColor(Color.BLACK);
        activity.getWindow().getDecorView().setBackgroundColor(Color.BLACK);
        immersive(activity.getWindow());
        fit(activity,root);
        root.getViewTreeObserver().addOnGlobalLayoutListener(()->fit(activity,root));
        root.getViewTreeObserver().addOnWindowFocusChangeListener(focus->{
            if(focus) {immersive(activity.getWindow());fit(activity,root);}
        });
        Handler handler=new Handler(Looper.getMainLooper());
        handler.post(new Runnable() {
            public void run() {
                if(activity.isFinishing()||activity.isDestroyed())return;
                fit(activity,root);
                try {
                    Class<?> type=activity.getClassLoader().loadClass("com.apportable.ui.Window");
                    Dialog dialog=(Dialog)type.getMethod("getKeyWindowDialog").invoke(null);
                    if(dialog!=null&&dialog.isShowing()) {
                        if(dialog!=lastDialog) {
                            lastDialog=dialog;
                            // Apportable creates UIKit's Dialog on its GL looper. Its own
                            // decor handler, rather than Android's main handler, must mutate it.
                            dialog.getWindow().getDecorView().post(()->{
                                immersive(dialog.getWindow());
                                dialog.getWindow().getDecorView().getViewTreeObserver()
                                    .addOnWindowFocusChangeListener(focus->{
                                        if(focus) {immersive(dialog.getWindow());fitDialog(activity,dialog);}
                                    });
                                fitDialog(activity,dialog);
                            });
                        }
                        dialog.getWindow().getDecorView().post(()->fitDialog(activity,dialog));
                    }
                } catch(ReflectiveOperationException failure) {
                    Log.w(TAG,"UIKit window lookup failed",failure);
                    return;
                }
                handler.postDelayed(this,300);
            }
        });
    }

    private static Rect safe(Activity activity) {
        if(Build.VERSION.SDK_INT>=30) {
            android.view.WindowMetrics metrics=activity.getWindowManager().getCurrentWindowMetrics();
            Rect bounds=new Rect(metrics.getBounds());
            // Reserve navigation even when hidden, so a transient bar cannot cover controls.
            Insets insets=metrics.getWindowInsets().getInsetsIgnoringVisibility(
                WindowInsets.Type.navigationBars()|WindowInsets.Type.displayCutout());
            bounds.inset(insets.left,insets.top,insets.right,insets.bottom);
            return bounds;
        }
        android.util.DisplayMetrics metrics=new android.util.DisplayMetrics();
        activity.getWindowManager().getDefaultDisplay().getMetrics(metrics);
        return new Rect(0,0,metrics.widthPixels,metrics.heightPixels);
    }

    private static Rect viewport(Activity activity) {
        return safe(activity);
    }

    private static void fit(Activity activity,FrameLayout root) {
        Rect rect=viewport(activity);
        if(rect.width()<1||rect.height()<1)return;
        ViewGroup.LayoutParams old=root.getLayoutParams();
        if(!(old instanceof FrameLayout.LayoutParams))return;
        FrameLayout.LayoutParams params=(FrameLayout.LayoutParams)old;
        int[] origin=new int[2];
        if(root.getParent() instanceof View)((View)root.getParent()).getLocationOnScreen(origin);
        int left=rect.left-origin[0],top=rect.top-origin[1];
        int logicalWidth=rect.height()*3/2,logicalHeight=rect.height();
        root.setPivotX(0);root.setPivotY(0);
        root.setScaleX(rect.width()/(float)logicalWidth);root.setScaleY(1);
        if(params.width!=logicalWidth||params.height!=logicalHeight||params.leftMargin!=left
            ||params.topMargin!=top||params.gravity!=(Gravity.TOP|Gravity.LEFT)) {
            params.width=logicalWidth;params.height=logicalHeight;
            params.gravity=Gravity.TOP|Gravity.LEFT;params.leftMargin=left;params.topMargin=top;
            root.setLayoutParams(params);
        }
        String geometry="safe="+safe(activity)+" viewport="+rect;
        if(!geometry.equals(lastGeometry)) {lastGeometry=geometry;Log.i(TAG,geometry);}
    }

    private static void fitDialog(Activity activity,Dialog dialog) {
        Window window=dialog.getWindow();if(window==null)return;
        Rect rect=viewport(activity);
        // Keep UIKit in the same legacy coordinates as the GL surface. Android's
        // view transforms invert touch coordinates, so no manual touch remapping is used.
        View content=window.findViewById(android.R.id.content);
        if(content instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)content;
            int logicalWidth=rect.height()*3/2;
            for(int i=0;i<group.getChildCount();i++) {
                View child=group.getChildAt(i);
                ViewGroup.LayoutParams old=child.getLayoutParams();
                if(!(old instanceof FrameLayout.LayoutParams))continue;
                FrameLayout.LayoutParams size=(FrameLayout.LayoutParams)old;
                if(size.width!=logicalWidth||size.height!=rect.height()||size.gravity!=(Gravity.TOP|Gravity.LEFT)) {
                    size.width=logicalWidth;size.height=rect.height();size.gravity=Gravity.TOP|Gravity.LEFT;
                    size.leftMargin=0;size.topMargin=0;child.setLayoutParams(size);
                }
                child.setPivotX(0);child.setPivotY(0);
                child.setScaleX(rect.width()/(float)logicalWidth);child.setScaleY(1);
            }
        }
        Rect full=Build.VERSION.SDK_INT>=30
            ?activity.getWindowManager().getCurrentWindowMetrics().getBounds()
            :new Rect(0,0,activity.getWindow().getDecorView().getWidth(),activity.getWindow().getDecorView().getHeight());
        WindowManager.LayoutParams params=window.getAttributes();
        int x=rect.centerX()-full.centerX(),y=rect.centerY()-full.centerY();
        if(params.width!=rect.width()||params.height!=rect.height()||params.x!=x||params.y!=y
            ||params.gravity!=Gravity.CENTER) {
            params.width=rect.width();params.height=rect.height();
            params.gravity=Gravity.CENTER;params.x=x;params.y=y;
            window.setAttributes(params);
            Log.i(TAG,"UIKit viewport="+rect+" window="+params.width+"x"+params.height);
        }
    }

    private static void immersive(Window window) {
        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        if(Build.VERSION.SDK_INT>=30) {
            window.setDecorFitsSystemWindows(false);
            WindowInsetsController controller=window.getInsetsController();
            if(controller!=null) {
                controller.hide(WindowInsets.Type.systemBars());
                controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        }
    }
}
