"""OpenAI/AssemblyAI configuration and recorded-audio HTTP requests (stdlib)."""
import json
import os
import re
import secrets
import urllib.request
from pathlib import Path

TEXT_MODELS = ('gpt-4.1-mini', 'gpt-4o-mini')
AUDIO_MODELS = ('gpt-4o-mini-transcribe', 'gpt-transcribe', 'gpt-4o-transcribe-diarize')
MAX_OPENAI_AUDIO = 25 * 1024 * 1024

def settings(data):
    try:
        value=json.loads((data/'ai-settings.json').read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError): return {}

def openai_key(data):
    return os.environ.get('OPENAI_API_KEY') or settings(data).get('openai_key','')

def text_model(data):
    return os.environ.get('OPENAI_MODEL') or settings(data).get('text_model','gpt-4.1-mini')

def audio_model(data):
    value=os.environ.get('OPENAI_TRANSCRIBE_MODEL') or settings(data).get('audio_model','gpt-4o-mini-transcribe')
    if value not in AUDIO_MODELS: raise ValueError('Modelo de transcripción no admitido')
    return value

def provider(data, assembly_key):
    value=os.environ.get('NEXO_TRANSCRIPTION_PROVIDER') or settings(data).get('provider')
    if value in ('openai','assemblyai'): return value
    return 'openai' if openai_key(data) or not assembly_key else 'assemblyai'

def configured(data, assembly_key):
    return bool(openai_key(data) if provider(data,assembly_key)=='openai' else assembly_key)

def checked_key(value):
    if not isinstance(value,str): raise ValueError('Ingresá una clave válida')
    value=value.strip()
    if value and (not 16<=len(value)<=512 or re.search(r'\s',value)):
        raise ValueError('La clave debe tener entre 16 y 512 caracteres, sin espacios')
    return value

def save(data, body, save_assembly):
    chosen=body.get('provider')
    if chosen not in ('openai','assemblyai'): raise ValueError('Elegí OpenAI o AssemblyAI')
    key=checked_key(body.get('key',''))
    value=settings(data)
    if chosen=='openai':
        model=body.get('audioModel',value.get('audio_model','gpt-4o-mini-transcribe'))
        if model not in AUDIO_MODELS: raise ValueError('Modelo de transcripción inválido')
        value['audio_model']=model
        if key:
            if os.environ.get('OPENAI_API_KEY'): raise ValueError('La clave OpenAI está definida en el entorno del servidor')
            value['openai_key']=key
            value.pop('verifiedAt',None)
        if not (os.environ.get('OPENAI_API_KEY') or value.get('openai_key')): raise ValueError('Ingresá tu clave de OpenAI')
    elif key:
        if os.environ.get('ASSEMBLYAI_API_KEY'): raise ValueError('La clave AssemblyAI está definida en el entorno del servidor')
        save_assembly(key)
    value['provider']=chosen
    path=data/'ai-settings.json'
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.chmod(0o600)
    os.replace(temporary,path)

def transcribe(audio, filename, mime, key, model):
    if not audio or len(audio)>MAX_OPENAI_AUDIO:
        raise ValueError('OpenAI admite hasta 25 MB por archivo. Dividí el audio en grabaciones más cortas.')
    boundary='Nexo-'+secrets.token_hex(16)
    fields={'model':model,'response_format':'diarized_json' if model=='gpt-4o-transcribe-diarize' else 'json'}
    if model=='gpt-transcribe': fields['languages[]']='es'
    elif model=='gpt-4o-transcribe-diarize': fields['chunking_strategy']='auto'
    else: fields['language']='es'
    parts=[]
    for name,value in fields.items():
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode())
    filename=re.sub(r'[^\w.\-]','_',Path(filename).name)[:120] or 'visita.webm'
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode())
    parts.extend([audio,f'\r\n--{boundary}--\r\n'.encode()])
    request=urllib.request.Request('https://api.openai.com/v1/audio/transcriptions',data=b''.join(parts),headers={'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(request,timeout=180) as response: result=json.load(response)
    text=result.get('text','')
    if not isinstance(text,str): raise ValueError('El servicio no devolvió una transcripción válida')
    if len(text)>150000: raise ValueError('La transcripción es demasiado extensa para una sola hoja')
    return text.strip()
