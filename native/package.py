#!/usr/bin/env python3
"""Package the signed Mac app while preserving dylib symlinks."""
from pathlib import Path
import os
import stat
import subprocess
import time
import zipfile

project=Path(__file__).resolve().parents[1]
root=project.parent
app=root/'JARVIS.app'
subprocess.run(['codesign','--verify','--deep',str(app)],check=True)
for path in app.rglob('*'):
    if path.name.startswith('._') or '__pycache__' in path.parts:
        raise SystemExit('Rebuild first: generated metadata must not enter the signed bundle.')
out=root/'JARVIS-Mac.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
    for directory in (app,project):
        for path in sorted(directory.rglob('*')):
            if '__pycache__' in path.parts or path.name=='.DS_Store' or path.name.startswith('._') or 'shared' in path.parts:continue
            name=str(path.relative_to(root))
            if path.is_symlink():
                info=zipfile.ZipInfo(name,time.localtime(path.lstat().st_mtime)[:6])
                info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
                archive.writestr(info,os.readlink(path))
            elif path.is_file():archive.write(path,name)
with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
    assert not any(name.endswith('state.json') for name in archive.namelist())
print(out)
