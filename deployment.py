"""Checks for the HTTPS reverse-proxy deployment; local Android mode is unchanged."""
import os
import re


def enabled():
    return os.environ.get('NEXO_DEPLOYMENT') == '1'


def domain():
    value = os.environ.get('NEXO_DOMAIN', '').strip().lower()
    if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value) or '.' not in value:
        raise ValueError('NEXO_DOMAIN debe ser un dominio, sin https:// ni rutas.')
    return value


def validate_startup(host, has_admin):
    if enabled():
        domain()
        if os.environ.get('NEXO_HTTPS') != '1':
            raise ValueError('El despliegue requiere NEXO_HTTPS=1 y un proxy HTTPS.')
        if not has_admin:
            raise ValueError('Creá primero el administrador con scripts/create_admin.py.')
        if os.environ.get('NEXO_PRESENTATION') == '1':
            raise ValueError('Usá datos de producción separados de la presentación.')
    elif host not in ('127.0.0.1', 'localhost') and not os.environ.get('APP_PASSWORD'):
        raise ValueError('Definí APP_PASSWORD antes de habilitar acceso desde otras máquinas.')


def request_allowed(headers, method):
    if not enabled():
        return True
    expected = domain()
    if headers.get('Host', '').lower() != expected:
        return False
    # Browser mutations must use the canonical HTTPS origin. CLI tools have no Origin.
    origin = headers.get('Origin')
    return method == 'GET' or not origin or origin == 'https://' + expected
