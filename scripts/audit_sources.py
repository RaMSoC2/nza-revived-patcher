"""Audit Git candidates, excluding ignored private artifacts. No license clearance implied."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
    files=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z']).decode('utf8').split('\0')
    failures=[]
    for name in filter(None,files):
        p=Path(name)
        if p.suffix.lower() in {'.apk','.ipa','.dex','.so','.dll','.exe','.jar','.jks','.keystore','.key','.p12','.zip'} or any(n in p.parts for n in ('signing','saves','.dependencies','input','output','work','originals','decompiled')):
            failures.append(name)
        if p.suffix in ('.py','.java','.json','.cmd','.md'):
            data=(ROOT/p).read_text(encoding='utf-8-sig')
            if any(marker in data for marker in ('D:'+chr(92)+'Projetos'+chr(92),'C'+':/Users/','C:'+chr(92)+'Users'+chr(92),'reverse'+'-engineering/')):
                failures.append(name+' (private path)')
    if failures:print('\n'.join(failures));return 1
    print('Source audit OK. Publication gate remains blocked.');return 0
if __name__=='__main__':raise SystemExit(main())
