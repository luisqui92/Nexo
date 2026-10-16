#!/usr/bin/env python3
"""Create the first administrator locally, without passwords in arguments or logs."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import accounts
import server


def create_first_admin(data):
    with server.LOCK, server.db() as conn:
        if accounts.has_users(conn):
            raise ValueError('Ya existen cuentas. El administrador inicial no se reemplaza.')
        return accounts.create_user(conn, data, 'admin', server.now())


def main():
    with server.db() as conn:
        if accounts.has_users(conn):
            raise ValueError('Ya existen cuentas. El administrador inicial no se reemplaza.')
    if not sys.stdin.isatty():
        raise ValueError('Ejecutá este comando en una terminal interactiva; la contraseña no se pasa por argumentos.')
    name = input('Nombre de gerencia: ').strip()
    username = input('Usuario: ').strip()
    password = getpass.getpass('Contraseña (al menos 10 caracteres): ')
    repeated = getpass.getpass('Repetí la contraseña: ')
    if password != repeated:
        raise ValueError('Las contraseñas no coinciden.')
    user = create_first_admin({'name': name, 'username': username, 'password': password})
    print('Administrador creado:', user['username'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyboardInterrupt, EOFError) as error:
        raise SystemExit(str(error) or 'Cancelado; no se creó la cuenta.')
