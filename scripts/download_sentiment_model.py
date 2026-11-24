"""Fetch pinned model data during setup/build; runtime stays offline."""
import hashlib
import json
import os
from pathlib import Path
import time

import httpx


def download():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'backend/sentiment-model.json').read_text(encoding='utf8'))
    directory = Path(os.getenv('SENTIMENT_MODEL_DIR', str(root / 'models/sentiment')))
    directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=180) as client:
        for remote, expected in manifest['files'].items():
            path = directory / Path(remote).name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                continue
            temporary = path.with_suffix('.part')
            for attempt in range(3):
                try:
                    digest = hashlib.sha256()
                    url = f'https://huggingface.co/{manifest["repository"]}/resolve/{manifest["revision"]}/{remote}'
                    with client.stream('GET', url) as response:
                        response.raise_for_status()
                        with temporary.open('wb') as stream:
                            for block in response.iter_bytes(1024 * 1024):
                                stream.write(block); digest.update(block)
                    if digest.hexdigest() != expected:
                        raise ValueError('Model checksum mismatch')
                    temporary.replace(path)
                    break
                except (httpx.HTTPError, ValueError):
                    temporary.unlink(missing_ok=True)
                    if attempt == 2:
                        raise
                    time.sleep(1)
    print('Local sentiment model ready: pinned revision and checksums verified')


if __name__ == '__main__':
    download()
