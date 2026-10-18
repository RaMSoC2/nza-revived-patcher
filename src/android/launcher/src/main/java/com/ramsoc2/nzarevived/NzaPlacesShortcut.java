package com.ramsoc2.nzarevived;

/** Settings access through a long press on the single game icon. */
final class NzaPlacesShortcut {
    static void install(android.app.Activity activity) {
        try {
            android.content.pm.ShortcutManager manager=activity.getSystemService(android.content.pm.ShortcutManager.class);
            android.content.Intent intent=new android.content.Intent(android.content.Intent.ACTION_VIEW)
                .setClassName(activity,"com.ramsoc2.nzarevived.places.NzaPlacesInfoActivity");
            android.content.pm.ShortcutInfo info=new android.content.pm.ShortcutInfo.Builder(activity,"nearby-settings")
                .setShortLabel("Lugares reais")
                .setIcon(android.graphics.drawable.Icon.createWithResource(activity,android.R.drawable.ic_menu_mylocation))
                .setActivity(new android.content.ComponentName(activity,NzaGameActivity.class))
                .setIntent(intent).build();
            manager.setDynamicShortcuts(java.util.Collections.singletonList(info));
        } catch(RuntimeException failure) {
            android.util.Log.w("NZA-Places","Launcher shortcut unavailable");
        }
    }
}
