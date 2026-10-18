"""Strict local preparation of separately acquired, pinned runtime sources."""
from pathlib import Path, PurePosixPath
import hashlib
import re
import shutil
import zipfile


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def checked_archive(path,expected):
    if not Path(path).is_file():raise ValueError('Missing separately acquired archive: '+str(path))
    if sha256(path)!=expected:raise ValueError('Archive SHA-256 mismatch: '+Path(path).name)


def extract_zip(path,destination,strip_root=True,include=None):
    """No traversal, symlinks, duplicate Windows paths or implicit overwrites."""
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(path) as archive:
        files=[entry for entry in archive.infolist() if not entry.is_dir()]
        roots={PurePosixPath(entry.filename).parts[0] for entry in files}
        if strip_root and len(roots)!=1:raise ValueError('Expected one archive root')
        if sum(entry.file_size for entry in files)>4*1024**3:raise ValueError('Archive exceeds extraction bound')
        seen=set()
        for entry in files:
            relative=PurePosixPath(entry.filename)
            if relative.is_absolute() or '..' in relative.parts or '\\' in entry.filename or ':' in entry.filename:
                raise ValueError('Unsafe archive path')
            if (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink refused')
            parts=relative.parts[1:] if strip_root else relative.parts
            if not parts:raise ValueError('Empty archive path')
            if include is not None and not any('/'.join(parts).startswith(prefix) for prefix in include):continue
            normalized='/'.join(parts).casefold()
            if normalized in seen:raise ValueError('Duplicate archive path')
            seen.add(normalized)
            target=destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination):raise ValueError('Archive escaped destination')
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(entry) as source,target.open('xb') as out:shutil.copyfileobj(source,out)


def apply_unified_patch(root,patch):
    """Apply only exact text hunks. No fuzz, subprocess, Git or path guessing."""
    root=Path(root).resolve()
    lines=Path(patch).read_text(encoding='utf8').splitlines(keepends=True)
    index=0;changed=[]
    while index<len(lines):
        if not lines[index].startswith('--- '):index+=1;continue
        old=lines[index][4:].strip().split('\t')[0]
        index+=1
        if index>=len(lines) or not lines[index].startswith('+++ '):raise ValueError('Missing patch target')
        new=lines[index][4:].strip().split('\t')[0];index+=1
        if not old.startswith('a/') or new!='b/'+old[2:]:raise ValueError('Only edits to existing files are supported')
        relative=PurePosixPath(old[2:])
        if relative.is_absolute() or '..' in relative.parts or ':' in old or '\\' in old:raise ValueError('Unsafe patch path')
        target=root.joinpath(*relative.parts)
        if not target.resolve().is_relative_to(root):raise ValueError('Patch escaped source root')
        original=target.read_text(encoding='utf8').splitlines(keepends=True)
        result=[];cursor=0;found=False
        while index<len(lines) and lines[index].startswith('@@ '):
            header=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',lines[index])
            if not header:raise ValueError('Invalid patch hunk')
            start=int(header[1])-1;old_count=int(header[2] or 1);new_count=int(header[4] or 1)
            if start<cursor:raise ValueError('Overlapping patch hunks')
            result.extend(original[cursor:start]);cursor=start;index+=1
            before=[];after=[]
            while index<len(lines) and lines[index][:1] in (' ','+','-') and not lines[index].startswith(('--- ','+++ ')):
                line=lines[index];index+=1
                if line[0] in ' -':before.append(line[1:])
                if line[0] in ' +':after.append(line[1:])
            if len(before)!=old_count or len(after)!=new_count:raise ValueError('Patch hunk count mismatch: '+str(relative))
            if original[cursor:cursor+old_count]!=before:raise ValueError('Patch context mismatch: '+str(relative))
            result.extend(after);cursor+=old_count;found=True
        if not found:raise ValueError('No hunks for '+str(relative))
        result.extend(original[cursor:]);target.write_text(''.join(result),encoding='utf8',newline='\n')
        changed.append(relative.as_posix())
    if not changed:raise ValueError('Empty patch')
    return changed
