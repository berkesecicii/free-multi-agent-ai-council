#!/usr/bin/env python3
"""Fetch the Supertonic voice presets (F1-F5, M1-M5) that the bundled runtime does not have yet.

Only small JSON preset files from the model's official repository are downloaded. Each file is checked against the
preset that already works (same keys, same tensor dimensions) before it is kept. Nothing here is executable.
A failure is never fatal: the app falls back to the macOS voice for a missing preset. Usage: fetch_voice_styles.py <voice_styles dir>
"""
import json,subprocess,sys,tempfile
from pathlib import Path

REPOS=('supertone-oss-archive/supertonic-3','Supertone/supertonic-3')
IDS=['F1','F2','F3','F4','F5','M1','M2','M3','M4','M5']

def shape_ok(new,ref):
    if not isinstance(new,dict) or set(new)!=set(ref):return False
    for key,value in ref.items():
        if isinstance(value,dict) and 'dims' in value and (not isinstance(new[key],dict) or new[key].get('dims')!=value['dims']):return False
    return True

def main():
    dest=Path(sys.argv[1])
    if not dest.is_dir():print('voice_styles klasörü yok:',dest);return
    refs=[json.loads(p.read_text()) for p in sorted(dest.glob('*.json'))[:1]]
    ref=refs[0] if refs else None
    for voice in IDS:
        target=dest/(voice+'.json')
        if target.exists() and target.stat().st_size>1000:print(voice,'zaten var');continue
        done=False
        for repo in REPOS:
            url='https://huggingface.co/'+repo+'/resolve/main/voice_styles/'+voice+'.json'
            with tempfile.NamedTemporaryFile(suffix='.json') as tmp:
                run=subprocess.run(['curl','-fsSL','--max-time','40','-o',tmp.name,url],capture_output=True,text=True)
                if run.returncode:print(voice,'indirilemedi',repo,run.returncode);continue
                try:data=json.loads(Path(tmp.name).read_text())
                except ValueError:print(voice,'geçersiz JSON',repo);continue
                if ref is not None and not shape_ok(data,ref):print(voice,'şekil uyuşmuyor',repo);continue
                target.write_text(json.dumps(data));print(voice,'indirildi',repo);done=True;break
        if not done:print(voice,'ATLANDI')

if __name__=='__main__':
    try:main()
    except Exception as error:print('ses indirme hatası:',error)
