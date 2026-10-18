package com.apportable.utils;

import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.os.MessageQueue;
import android.util.Log;
import java.lang.reflect.Method;

/** Private experiment adapter for Apportable's manual queue dispatch on modern Android. */
public final class RunLoop {
    private static Handler sHandler;
    private static boolean unified;
    private static int STOP_MESSAGE=2727301;
    private static Method recycler;
    private static boolean recyclerChecked;
    private static boolean warned;
    private static native Message nativeNext(MessageQueue queue);

    public static void prepare() {
        Looper.prepare();
        sHandler=new Handler(Looper.myLooper());
        unified=true;
        Looper.myQueue().addIdleHandler(()->{
            if(!sHandler.hasMessages(STOP_MESSAGE))sHandler.sendEmptyMessage(STOP_MESSAGE);
            return true;
        });
    }
    public static boolean isUnifiedThreadModel(){return unified;}
    public static void processMessages() {
        Message message=nativeNext(Looper.myQueue());
        if(message==null)return;
        try {
            if(message.what!=STOP_MESSAGE)message.getTarget().dispatchMessage(message);
        } finally {
            // MessageQueue.next marks the dequeued message in use. The framework's
            // Looper recycles it internally; public recycle rejects it on modern API.
            try {
                if(!recyclerChecked) {
                    recyclerChecked=true;
                    recycler=Message.class.getDeclaredMethod("recycleUnchecked");
                    recycler.setAccessible(true);
                }
                if(recycler!=null)recycler.invoke(message);
            } catch(ReflectiveOperationException|RuntimeException failure) {
                // An unpooled message can be collected. Never recycle an active message
                // through the public API or hide a dispatch exception.
                if(!warned){warned=true;Log.w("NZA-RunLoop","Queue recycle unavailable; messages remain unpooled",failure);}
            }
        }
    }
}
