package com.ramsoc2.nzarevived.places;

/** In-game shortcut settings; the user requested enabled-by-default place queries. */
public final class NzaPlacesInfoActivity extends android.app.Activity {
    private android.widget.TextView locationStatus;
    @Override public void onCreate(android.os.Bundle state) {
        super.onCreate(state);
        android.widget.LinearLayout layout=new android.widget.LinearLayout(this);
        layout.setOrientation(android.widget.LinearLayout.VERTICAL);
        int padding=(int)(24*getResources().getDisplayMetrics().density);
        layout.setPadding(padding,padding,padding,padding);
        android.widget.TextView text=new android.widget.TextView(this);
        text.setTextSize(18);
        text.setText(android.text.Html.fromHtml("<h2>NZA Places</h2>"
            +"<p>A busca de lugares reais está integrada ao jogo e começa ativada.</p>"
            +"<p>Com a permissão de localização do Android, ela envia uma posição aproximada, arredondada para cerca de 1 km, "
            +"ao serviço Overpass para consultar estabelecimentos próximos. Os resultados ficam em cache por 24 horas.</p>"
            +"<p>Você pode desativar as consultas aqui a qualquer momento. O cliente antigo permanece bloqueado para rede.</p>"
            +"<p>Dados © <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap contributors</a>, ODbL. "
            +"A cobertura depende dos lugares mapeados.</p>",0));
        text.setMovementMethod(android.text.method.LinkMovementMethod.getInstance());
        layout.addView(text);
        android.widget.Switch enabled=new android.widget.Switch(this);
        enabled.setText("Permitir busca de lugares reais");
        android.content.SharedPreferences preferences=getSharedPreferences("privacy",0);
        enabled.setChecked(preferences.getBoolean("enabled",true));
        enabled.setOnCheckedChangeListener((button,checked)->{
            preferences.edit().putBoolean("enabled",checked).apply();
            android.widget.Toast.makeText(this,checked?"Busca ativada. Volte ao jogo.":"Consultas desativadas.",android.widget.Toast.LENGTH_LONG).show();
        });
        layout.addView(enabled);
        locationStatus=new android.widget.TextView(this);
        layout.addView(locationStatus);
        android.widget.Button permission=new android.widget.Button(this);
        permission.setText("Autorizar localização");
        permission.setOnClickListener(v->com.ramsoc2.nzarevived.NzaLocationPermission.requestExplicit(this));
        layout.addView(permission);
        android.widget.Button settings=new android.widget.Button(this);
        settings.setText("Permissões nas configurações do Android");
        settings.setOnClickListener(v->startActivity(new android.content.Intent(
            android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            android.net.Uri.parse("package:"+getPackageName()))));
        layout.addView(settings);
        android.widget.ScrollView scroll=new android.widget.ScrollView(this);scroll.addView(layout);setContentView(scroll);
    }
    @Override protected void onResume(){super.onResume();updateLocationStatus();}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==com.ramsoc2.nzarevived.NzaLocationPermission.REQUEST){
            com.ramsoc2.nzarevived.NzaLocationPermission.complete(this,results);
            updateLocationStatus();
        }
    }
    private void updateLocationStatus(){
        boolean granted=checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)
            ==android.content.pm.PackageManager.PERMISSION_GRANTED;
        locationStatus.setText(granted?"Localização autorizada. Reabra o jogo para atualizar os lugares.":
            "Localização não autorizada no Android. Ativar a busca, sozinho, não concede essa permissão.");
    }
}
