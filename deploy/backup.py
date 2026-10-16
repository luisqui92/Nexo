#!/usr/bin/env python3
"""Stopped-service backup: the database and its uploads stay consistent."""
import datetime
import os
from pathlib import Path
import subprocess
import sys

DEPLOY = Path(__file__).resolve().parent
COMPOSE = ['docker', 'compose', '--project-directory', str(DEPLOY), '-f', str(DEPLOY / 'compose.yaml')]


def run(*arguments, **kwargs):
    return subprocess.run([*COMPOSE, *arguments], check=True, **kwargs)


def main():
    os.umask(0o077)
    # Refuse to change service state unless it is currently running.
    status = run('ps', '--status', 'running', '--services', stdout=subprocess.PIPE, text=True)
    if 'app' not in status.stdout.splitlines():
        raise SystemExit('Nexo no está en ejecución. Revisá el servidor antes del respaldo.')
    folder = DEPLOY / 'backups'
    folder.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = folder / ('nexo-' + stamp + '.tar.gz')
    temporary = target.with_suffix('.part')
    stopped = False
    try:
        # No mutations or transcription jobs can write during the snapshot.
        run('stop', '-t', '240', 'app')
        stopped = True
        with temporary.open('xb') as output:
            run('run', '--rm', '--no-deps', '-T', '--entrypoint', 'tar', 'app',
                'czf', '-', '-C', '/app/data', '.', stdout=output)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
        if stopped:
            run('start', 'app')
    print('Respaldo creado:', target)
    print('Contiene datos y claves privadas. Guardalo cifrado fuera del servidor.')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError:
        sys.exit('Falló un comando de Docker; revisá el estado del servicio y el mensaje anterior.')
