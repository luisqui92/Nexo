#!/usr/bin/env python3
"""Run an isolated demo on localhost; never reads the real data/ workspace."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['NEXO_DATA_DIR']=str(ROOT/'data_presentacion')
os.environ['NEXO_PRESENTATION']='1'

def main():
    import server
    from presentation_demo import prepare_demo
    if server.DATA != (ROOT/'data_presentacion').resolve():
        raise SystemExit('Reiniciá el intérprete de Python antes de abrir presentar.py. No se modificó tu espacio habitual.')
    credentials=prepare_demo(server)
    print('\nNEXO — PRESENTACIÓN CON DATOS FICTICIOS',flush=True)
    print('Tus datos de data/ se conservan. Esta demo utiliza data_presentacion/.',flush=True)
    print('\nAccesos de esta demo local (no usar estas cuentas en producción):',flush=True)
    for user in credentials['accounts']:
        print(f"  {user['name']}: usuario {user['username']} | contraseña {user['password']}",flush=True)
    port=int(os.environ.get('PORT','8080'))
    print(f'\nSistema: http://127.0.0.1:{port}',flush=True)
    print(f'Diapositivas: http://127.0.0.1:{port}/presentacion.html',flush=True)
    print('Mantené este proceso abierto. Para salir, detené la ejecución en Pydroid o Ctrl+C.',flush=True)
    try: server.ThreadingHTTPServer(('127.0.0.1',port),server.Handler).serve_forever()
    except OSError as error:
        if getattr(error,'errno',None) in (48,98,10048):
            raise SystemExit('El puerto ya está ocupado. Detené server.py antes de ejecutar presentar.py.')
        raise

if __name__=='__main__': main()
