#!/usr/bin/env python3
"""Install only procd-ujail's verified binary/metadata from a trusted local IPK."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


def ar_members(data):
    if not data.startswith(b'!<arch>\n'):
        raise ValueError('input is not an ar/IPK archive')
    pos=8; out={}
    while pos < len(data):
        if pos+60>len(data):
            raise ValueError('truncated ar member header')
        header=data[pos:pos+60]
        if header[58:60] != b'`\n':
            raise ValueError('invalid ar member header')
        name=header[:16].decode().strip().rstrip('/')
        size=int(header[48:58].decode().strip())
        start=pos+60; end=start+size
        if end>len(data):
            raise ValueError(f'truncated ar member {name}')
        if name not in ('debian-binary','control.tar.gz','data.tar.gz'):
            raise ValueError(f'unexpected IPK member {name}')
        out[name]=data[start:end]
        pos=end+(size&1)
    if set(out)!={'debian-binary','control.tar.gz','data.tar.gz'}:
        raise ValueError(f'unexpected IPK members: {sorted(out)}')
    return out


def tar_files(data):
    result={}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('./')
            if not name or member.isdir():
                continue
            if member.issym() or member.islnk() or not member.isfile():
                raise ValueError(f'non-regular package payload is forbidden: {name}')
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError(f'unsafe package path: {name}')
            source=archive.extractfile(member)
            if source is None:
                raise ValueError(f'cannot read package member: {name}')
            result[name]=(member.mode,source.read())
    return result


def fields(data):
    out={}
    for line in data.decode().splitlines():
        if not line or line[0].isspace():
            continue
        key,sep,value=line.partition(': ')
        if not sep:
            raise ValueError(f'malformed control field: {line}')
        out[key]=value
    return out


def write_atomic(path,data,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.wayne-tmp')
    temp.write_bytes(data);temp.chmod(mode);temp.replace(path)


def install(ipk_path,root):
    package = ipk_path.read_bytes()
    if package.startswith(b'!<arch>\n'):
        ar = ar_members(package)
    else:
        ar = {name: data for name, (_, data) in tar_files(package).items()}
    if set(ar) != {'debian-binary', 'control.tar.gz', 'data.tar.gz'} or ar['debian-binary'] != b'2.0\n':
        raise ValueError('Unexpected IPK archive format')
    control=tar_files(ar['control.tar.gz'])
    if 'control' not in control:
        raise ValueError('IPK control.tar.gz missing control file')
    meta=fields(control['control'][1])
    if meta.get('Package')!='procd-ujail':
        raise ValueError(f"unexpected package {meta.get('Package')}")
    if not meta.get('Version','').endswith('-r2'):
        raise ValueError(f"expected locally rebuilt release r2, got {meta.get('Version')}")
    payload=tar_files(ar['data.tar.gz'])
    if set(payload)!={'sbin/ujail'}:
        raise ValueError(f"refusing unexpected payload: {sorted(payload)}")
    executable=payload['sbin/ujail'][1]
    if len(executable)<4096 or b'kernel does not support capability %d; skipping' not in executable:
        raise ValueError('patched ujail marker absent from binary')
    info=root/'usr/lib/opkg/info'
    # Replace only the old procd-ujail package record and file list.
    status_path=root/'usr/lib/opkg/status'
    paragraphs=status_path.read_text().strip().split('\n\n')
    build_info = root / 'etc/wayne-build.json'
    provenance = json.loads(build_info.read_text())
    provenance['ujail'] = {
        'version': meta['Version'],
        'binary_sha256': hashlib.sha256(executable).hexdigest(),
        'package_sha256': hashlib.sha256(package).hexdigest(),
    }
    paragraphs=[p for p in paragraphs if not any(l=='Package: procd-ujail' for l in p.splitlines())]
    record=dict(meta);record['Status']='install user installed'
    paragraphs.append('\n'.join(f'{k}: {v}' for k,v in record.items()))
    write_atomic(root/'sbin/ujail',executable,0o755)
    write_atomic(status_path,('\n\n'.join(paragraphs)+'\n\n').encode())
    write_atomic(info/'procd-ujail.control',control['control'][1])
    write_atomic(info/'procd-ujail.list',b'/sbin/ujail\n')
    write_atomic(build_info, (json.dumps(provenance, indent=2) + '\n').encode())
    return {'package':meta['Package'],'version':meta['Version'],'binary_bytes':len(executable)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('ipk',type=Path);p.add_argument('root',type=Path);a=p.parse_args()
    print(install(a.ipk,a.root))
