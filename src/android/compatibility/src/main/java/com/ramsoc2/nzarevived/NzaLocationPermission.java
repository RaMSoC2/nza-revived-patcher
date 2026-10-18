package com.ramsoc2.nzarevived;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.util.Log;

/** Foreground-only permission gate, before the legacy engine starts requesting GPS. */
public final class NzaLocationPermission {
    public static final int REQUEST = 6201;
    private static final String COMPLETED = "permission-result-v021";

    static boolean request(Activity activity, String plugin) {
        if (!"com.booyah.zombie".equals(plugin)) return false;
        if (activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED) {
            report(activity);
            return false;
        }
        // Migrate the old latch: v0.2 marked "requested" before Android answered.
        // Only a completed request suppresses another automatic prompt.
        android.content.SharedPreferences prefs = activity.getSharedPreferences("nza-location", 0);
        if (prefs.getBoolean(COMPLETED, false)) {
            report(activity);
            return false;
        }
        requestExplicit(activity);
        return true;
    }

    public static void requestExplicit(Activity activity) {
        activity.requestPermissions(new String[] {
            Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION
        }, REQUEST);
    }

    public static void complete(Activity activity, int[] results) {
        // An interrupted/cancelled request returns an empty result; allow a retry.
        if (results.length > 0) activity.getSharedPreferences("nza-location", 0)
                .edit().putBoolean(COMPLETED, true).apply();
        report(activity);
    }

    static void report(Activity activity) {
        boolean fine = activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
        boolean coarse = activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
        // Never log a location, address, or list of the user's nearby places.
        Log.i("NZA-Location", "foreground permission fine=" + fine + " coarse=" + coarse);
    }
}
