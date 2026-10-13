#!/usr/bin/env python3
"""Run the three alternate native GRUB concepts on consecutive localhost ports."""
import argparse
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from variants import VARIANTS, preview_tag

BASE = Path(__file__).resolve().parent
CONCEPTS = ('carian', 'destined', 'farum')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8131, help='First of three consecutive ports')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65533:
        parser.error('Choose a first port between 1024 and 65533.')
    for index, variant in enumerate(CONCEPTS):
        iso = BASE/'previews'/preview_tag('1920x1080', variant)/'preview.iso'
        if not iso.exists():
            parser.error(f'First build this concept: python3 preview.py --variant {variant}')
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', args.port + index))
        except OSError:
            parser.error(f'Port {args.port + index} is in use; select a different --port.')
    children = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for index, variant in enumerate(CONCEPTS):
            port = args.port + index
            print(f'{VARIANTS[variant]["title"]}: localhost:{port}', flush=True)
            command = [sys.executable, str(BASE/'live-preview.py'), '--variant', variant, '--port', str(port)]
            if args.no_open:
                command.append('--no-open')
            children.append(subprocess.Popen(command, cwd=BASE))
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        raise RuntimeError('A concept preview exited; see its output above.')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            child.wait(timeout=15)


if __name__ == '__main__':
    main()
