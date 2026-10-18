"""Maintainer-only build from explicitly supplied, locally prepared runtime inputs.

Runtime redistribution remains blocked. No input game binaries enter templates.
Requires JDK21, Android build-tools35/platform35, NDK29 and the recorded runtime.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='com.ramsoc2.nzarevived'
PLACES=PACKAGE+'.places'


def renamed(text):
    return text.replace('com.ramsoc2.nza.places',PLACES).replace('com.zettabridge.launcher',PACKAGE)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('host-source','host-manifest','native-bundle','prepared-engine','jdk','build-tools','android-jar','hidden-api','ndk'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--replace-existing-local',action='store_true',help='Back up and rebuild local templates')
    parser.add_argument('--destination',type=Path,default=ROOT/'.dependencies/templates')
    parser.add_argument('--version-code',type=int,default=3)
    parser.add_argument('--version-name',default='0.2.1-local')
    a=parser.parse_args()
    for k,v in vars(a).items():
        if isinstance(v,Path):setattr(a,k,v.resolve())
    out=ROOT/'work'/('templates-'+__import__('uuid').uuid4().hex[:8]);out.mkdir(parents=True)
    destination=a.destination;destination.mkdir(parents=True,exist_ok=True)
    if (destination/'game.apk').exists():
        if not a.replace_existing_local:raise ValueError('Preserve existing templates or explicitly use --replace-existing-local')
        previous=out/'previous-templates';previous.mkdir()
        for p in destination.iterdir():
            if p.is_file():p.rename(previous/p.name)
    log=(out/'build.log').open('w',encoding='utf8')
    def run(cmd):
        subprocess.run([str(v) for v in cmd],stdout=log,stderr=subprocess.STDOUT,check=True)
        log.flush()
    sources=out/'src';shutil.copytree(a.host_source,sources)
    # Own Android sources are canonical; supplied runtime contributes only its integration classes.
    for folder in ('launcher','compatibility','places-helper'):
        for source in (ROOT/'src/android'/folder).rglob('*.java'):
            text=source.read_text(encoding='utf8');old_name=source.name
            prior=list(sources.rglob(old_name))
            if len(prior)>1:raise ValueError('Duplicate runtime class '+old_name)
            target=prior[0] if prior else sources/old_name
            target.write_text(text,encoding='utf8')
    for source in sources.rglob('*.java'):
        source.write_text(renamed(source.read_text(encoding='utf8')),encoding='utf8')
    application_source=next(sources.rglob('ZbApplication.java'))
    value=application_source.read_text(encoding='utf8')
    needle='        super.onCreate();'
    if value.count(needle)!=1:raise ValueError('Application startup hook changed')
    value=value.replace(needle,needle+'\n        if (!processName().endsWith(":places") && !NzaNetworkGuard.install(this)) return;')
    application_source.write_text(value,encoding='utf8')
    switch=next(sources.rglob('PluginSwitchActivity.java'))
    value=switch.read_text(encoding='utf8')
    old_gate='        if (NzaLocationPermission.request(this, packageName)) return;'
    if value.count(old_gate)!=1:raise ValueError('Legacy permission hook changed')
    switch.write_text(value.replace(old_gate,'        // Permission is requested by the visible NzaGameActivity.'),encoding='utf8')
    instrumentation=next(sources.rglob('GuestInstrumentation.java'))
    value=instrumentation.read_text(encoding='utf8')
    needle='    public void callActivityOnDestroy(Activity activity) {'
    if value.count(needle)!=1 or 'void callActivityOnResume(' in value:raise ValueError('Resume hook changed')
    value=value.replace(needle,'    public void callActivityOnResume(Activity activity) {\n'
        '        base.callActivityOnResume(activity);\n'
        '        NzaNearbyCache.start(activity);\n    }\n\n    @Override\n'+needle)
    instrumentation.write_text(value,encoding='utf8')
    manifest=out/'AndroidManifest.xml'
    tree=ET.ElementTree(ET.fromstring(renamed(a.host_manifest.read_text(encoding='utf8'))))
    ns='http://schemas.android.com/apk/res/android';ET.register_namespace('android',ns)
    application=tree.getroot().find('application');application.set('{'+ns+'}debuggable','false')
    application.set('{'+ns+'}usesCleartextTraffic','false')
    for entry in application.findall('activity'):
        if entry.get('{'+ns+'}name','').endswith('NzaGameActivity'):
            # The permission controller must not destroy a noHistory requester.
            entry.attrib.pop('{'+ns+'}noHistory',None)
    root=tree.getroot()
    for child in list(root):
        if child.tag=='queries' or (child.tag=='uses-permission' and child.get('{'+ns+'}name','').endswith('.READ_NEARBY')):
            root.remove(child)
    if not any(p.get('{'+ns+'}name')=='android.permission.INTERNET' for p in root.findall('uses-permission')):
        ET.SubElement(root,'uses-permission',{'{'+ns+'}name':'android.permission.INTERNET'})
    ET.SubElement(application,'provider',{
        '{'+ns+'}name':PLACES+'.NzaPlacesProvider','{'+ns+'}authorities':PACKAGE+'.nearby',
        '{'+ns+'}exported':'false','{'+ns+'}process':':places'})
    ET.SubElement(application,'activity',{
        '{'+ns+'}name':PLACES+'.NzaPlacesInfoActivity','{'+ns+'}exported':'true',
        '{'+ns+'}process':':places','{'+ns+'}theme':'@android:style/Theme.Material.Light.NoActionBar'})
    # Isolated CPU probes and library selection are not entry points of this single-game app.
    for child in application.findall('activity'):
        if child.get('{'+ns+'}name','').endswith('NzaNativeProbeActivity'):
            application.remove(child)
    tree.write(manifest,encoding='utf-8',xml_declaration=True)
    def compile_sources(folder,name,hidden=False):
        classes=out/(name+'-classes');classes.mkdir()
        response=out/(name+'-javac.args')
        args=['--release','17','-encoding','UTF-8','-classpath',str(a.android_jar)+(';' +str(a.hidden_api) if hidden else ''),'-d',str(classes)]
        args += [str(p) for p in sorted(folder.rglob('*.java'))]
        response.write_text('\n'.join('"'+v.replace('\\','/')+'"' for v in args),encoding='utf8')
        run([a.jdk/'bin/javac.exe','@'+str(response)])
        jar=out/(name+'.jar')
        with zipfile.ZipFile(jar,'w') as z:
            for p in sorted(classes.rglob('*.class')):z.write(p,p.relative_to(classes).as_posix())
        dex=out/(name+'-dex');dex.mkdir()
        run([a.jdk/'bin/java.exe','-cp',a.build_tools/'lib/d8.jar','com.android.tools.r8.D8',
             '--release','--min-api','26','--lib',a.android_jar,'--output',dex,jar,*([a.hidden_api] if hidden else [])])
        return dex
    dex=compile_sources(sources,'game',True)
    # A fully transparent placeholder contains no game pixels; replaced from the user's APK.
    res=out/'res/drawable';res.mkdir(parents=True)
    from PIL import Image
    Image.new('RGBA',(48,48),(0,0,0,0)).save(res/'nza_original_icon.png')
    compiled=out/'resources.zip'
    run([a.build_tools/'aapt2.exe','compile','--dir',res.parent,'-o',compiled])
    game=destination/'game.apk'
    run([a.build_tools/'aapt2.exe','link','-I',a.android_jar,'--manifest',manifest,
         '--min-sdk-version','26','--target-sdk-version','35','--version-code',str(a.version_code),'--version-name',a.version_name,
         '-o',game,compiled])
    native=out/'libnza_host_fault.so'
    run([a.ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe',
         '--target=aarch64-linux-android26','-shared','-fPIC','-O2','-Wall','-DNZA_SINGLE_CPU',
         '-DJava_com_zettabridge_launcher_NzaHostFaultCapture_configure=Java_com_ramsoc2_nzarevived_NzaHostFaultCapture_configure',
         ROOT/'src/android/runtime/nza_host_fault.c','-o',native])
    guard=out/'libnza_network_guard.so'
    run([a.ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe',
         '--target=aarch64-linux-android26','-shared','-fPIC','-O2','-Wall',
         ROOT/'src/android/runtime/nza_network_guard.c','-o',guard])
    guard_test=out/'nza-network-guard-test'
    run([a.ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe',
         '--target=aarch64-linux-android26','-O2','-Wall','-DNZA_GUARD_TEST',
         ROOT/'src/android/runtime/nza_network_guard.c','-o',guard_test])
    sys.path.insert(0,str(ROOT/'src/android/patches'))
    from nearby import make_patch
    _,recipe=make_patch(a.prepared_engine.read_bytes(),a.prepared_engine)
    with zipfile.ZipFile(game,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(dex.glob('*.dex')):archive.write(p,p.name)
        for p in sorted((a.native_bundle/'assets').rglob('*')):
            if p.is_file():archive.write(p,'assets/'+p.relative_to(a.native_bundle/'assets').as_posix())
        for p in sorted((a.native_bundle/'jniLibs').rglob('*.so')):
            if p.name!='libnza_host_fault.so':archive.write(p,'lib/'+p.relative_to(a.native_bundle/'jniLibs').as_posix())
        archive.write(native,'lib/arm64-v8a/libnza_host_fault.so')
        archive.write(guard,'lib/arm64-v8a/libnza_network_guard.so')
        archive.writestr('assets/nza-probe/nearby-engine.json',json.dumps(recipe,separators=(',',':')).encode())
        archive.write(ROOT/'src/android/runtime/ZettaBridge-LICENSE.txt','assets/nza-probe/ZettaBridge-LICENSE.txt')
        for name in ('Boost-LICENSE.txt','Dynarmic-LICENSE.txt'):
            archive.write(ROOT/'src/android/runtime'/name,'assets/nza-probe/'+name)
        # Explicitly no embedded APK, original icon, save, cache or test fixtures.
    log.close()
    with zipfile.ZipFile(game) as archive:
        icon=next(n for n in archive.namelist() if n.startswith('res/') and n.endswith('/nza_original_icon.png'))
        if any(n.endswith('.apk') for n in archive.namelist()):raise ValueError('Template contains a game APK')
    (destination/'metadata.json').write_text(json.dumps({'icon_entry':icon,'package':PACKAGE,'places_authority':PACKAGE+'.nearby',
        'places_integrated':True,'places_default_enabled':True,'legacy_socket_guard':'seccomp-tsync',
        'nearby_output_engine_sha256':recipe['after_sha256'],'runtime_commit':'d6066b9b9e61de27041ba6e1f3c499c080c9e2b7',
        'contains_game_payload':False,'public_release_allowed':False},indent=2)+'\n',encoding='utf8')
    print('Game-free templates built:',destination)


if __name__=='__main__':main()
