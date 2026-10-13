"""Install the fixed inference assets into a portable working directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
from .io import sha


def install_asset(spec, destination, local=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha(destination) != spec['sha256']:
            raise ValueError(f'Existing asset has wrong SHA256: {destination.name}')
        return
    if local is None and not spec.get('url'):
        raise ValueError('Release download URL is not configured; supply --weights-dir')
    fd, name = tempfile.mkstemp(prefix='.download-', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        if local is not None:
            shutil.copyfile(local, temporary)
        else:
            if not spec['url'].startswith('https://'):
                raise ValueError('Weight downloads require HTTPS')
            with urllib.request.urlopen(spec['url'], timeout=60) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
        if sha(temporary) != spec['sha256']:
            raise ValueError(f'Asset checksum mismatch: {destination.name}')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--weights-dir', type=Path)
    args = parser.parse_args()
    data = Path(__file__).parent / 'data'
    registry = json.loads((data/'model_registry.json').read_text())
    for spec in registry.values():
        install_asset(spec, args.out/'models'/spec['filename'],
                      args.weights_dir/spec['filename'] if args.weights_dir else None)
    for folder in ['configs', 'references']:
        for source in (data/folder).iterdir():
            target = args.out/folder/source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(f'Refusing to overwrite modified {folder}/{source.name}')
            shutil.copyfile(source, target)
    print(f'Fixed models and configuration ready in {args.out}')
