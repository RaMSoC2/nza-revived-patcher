package com.ramsoc2.nzarevived;
import android.content.Context;
import android.location.Address;
import java.util.*;

/** Prevent legacy reverse-geocoding from sending coordinates through an OS network service. */
public final class NzaOfflineGeocoder {
    public NzaOfflineGeocoder(Context context){}
    public NzaOfflineGeocoder(Context context,Locale locale){}
    public static boolean isPresent(){return false;}
    public List<Address> getFromLocation(double latitude,double longitude,int max){return Collections.emptyList();}
    public List<Address> getFromLocationName(String name,int max){return Collections.emptyList();}
    public List<Address> getFromLocationName(String name,int max,double a,double b,double c,double d){return Collections.emptyList();}
}
