"""Visit extraction and explainable property matching; no external dependencies."""
import re
from datetime import datetime, timedelta

FIELDS = ('needs', 'budget', 'currency', 'zones', 'likes', 'objections', 'questions', 'interest', 'offer', 'agreements', 'nextStep', 'followUp')

def clean(value):
    return str(value or '').strip()

def unique(items):
    return list(dict.fromkeys(clean(x) for x in items if clean(x)))

def amount(text):
    m = re.search(r'(?<!\d)(\d+(?:[.,]\d+)*)\s*(mill[oó]n(?:es)?|mil)?', text, re.I)
    if not m:
        return None
    raw = m.group(1).strip().replace(' ', '')
    unit = (m.group(2) or '').lower()
    if unit:
        raw = raw.replace(',', '.')
        if raw.count('.') > 1: raw = raw.replace('.', '')
    else:
        raw = re.sub(r'[.,](?=\d{3}(?:\D|$))', '', raw).replace(',', '.')
    try:
        n = float(raw) * (1000000 if unit.startswith('mill') else 1000 if unit == 'mil' else 1)
        return round(n, 2) if n > 0 else None
    except ValueError:
        return None

def extract_visit(text, now=None):
    now = now or datetime.now()
    text = clean(text)
    parts = [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+|;', text) if x.strip()]
    result = {k: [] if k in ('needs', 'zones', 'likes', 'objections', 'questions', 'agreements') else None for k in FIELDS}
    needs = re.compile(r'\b(necesita|necesito|busca|busco|requiere|quiero|queremos|preferimos|prefiere|imprescindible)\b', re.I)
    objection = re.compile(r'no\s+(?:le\s+)?gust[oó]|no\s+me\s+gusta|descart[aó]|demasiado|muy\s+(?:caro|pequeño|lejos)|falta|pero|sin\s+(?:garaje|estacionamiento|ascensor)|ruido|no\s+(?:tiene|cumple)|fuera\s+del\s+presupuesto', re.I)
    like = re.compile(r'(?<!no )(?<!no le )\b(?:le gust[oó]|me gust[aó]|nos gust[aó]|encant[aó]|valora|buena ubicaci[oó]n|le interesa)\b', re.I)
    for part in parts:
        if needs.search(part): result['needs'].append(part)
        if objection.search(part): result['objections'].append(part)
        if like.search(part):
            # Retain the positive clause only when the sentence has a later objection.
            positive = re.split(r'\bpero\b', part, maxsplit=1, flags=re.I)[0].strip(' ,')
            if not re.search(r'\bno\s+(?:le\s+|me\s+|nos\s+)?gust', positive, re.I): result['likes'].append(positive)
        if '?' in part or re.search(r'\b(pregunt[aó]|consult[aó]|pendiente de confirmar|hay que confirmar)\b', part, re.I): result['questions'].append(part)
        if re.search(r'\b(acordamos|acordaron|quedamos|se acord[oó]|acept[oó]|se comprometi[oó])\b', part, re.I): result['agreements'].append(part)
        if re.search(r'\b(llamar|llamarle|enviar|mandar|contactar|coordinar|programar|volver|seguimiento)\b', part, re.I): result['nextStep'] = part
        if re.search(r'\b(presupuesto|hasta|m[aá]ximo|tope|dispone de|busca algo de|busca algo hasta)\b', part, re.I):
            marker = re.search(r'\b(?:presupuesto(?: de)?|hasta|m[aá]ximo(?: de)?|tope(?: de)?|dispone de)\s*[:$]?\s*(.*)', part, re.I)
            value = amount(marker.group(1)) if marker else None
            if value: result['budget'] = value
        if re.search(r'\b(ofrece|ofert[aó]|oferta de|propon[eé] pagar)\b', part, re.I):
            m = re.search(r'\b(?:ofrece|ofert[aó]|oferta de|propone pagar)\s*[:$]?\s*(.*)', part, re.I)
            result['offer'] = amount(m.group(1)) if m else None
        for z in re.findall(r'(?:zona|barrio|sector)\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+){0,2})', part): result['zones'].append(z)
    if result['budget'] or result['offer']:
        result['currency'] = 'BOB' if re.search(r'\b(bolivianos|bs\.?|bob)\b', text, re.I) else 'USD' if re.search(r'\b(d[oó]lares|usd)\b|\$', text, re.I) else None
    m = re.search(r'\binter[eé]s\s+(alto|medio|bajo)\b', text, re.I)
    if m: result['interest'] = m.group(1).capitalize()
    for phrase, offset in [('pasado mañana', 2), ('mañana', 1), ('hoy', 0)]:
        if result['nextStep'] and phrase in result['nextStep'].lower():
            result['followUp'] = (now + timedelta(days=offset)).strftime('%Y-%m-%d')
            break
    iso = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', result['nextStep'] or '')
    if iso:
        try: datetime.strptime(iso.group(1), '%Y-%m-%d'); result['followUp'] = iso.group(1)
        except ValueError: pass
    for k in ('needs', 'zones', 'likes', 'objections', 'questions', 'agreements'): result[k] = unique(result[k])
    result['summary'] = ' '.join(parts[:3])[:700]
    return result

def matching(client, properties):
    """Each score comes with observable reasons and unmet requirements."""
    results = []
    preferences = ' '.join(client.get('needs', [])).lower()
    budget = float(client.get('budget') or 0)
    for p in properties:
        if p.get('status') != 'Disponible': continue
        reasons, missing, score, total = [], [], 0, 0
        checks = []
        if client.get('intent'): checks.append((p.get('operation') == client['intent'], 'Operación: ' + client['intent'], 'La operación es distinta'))
        if budget:
            same = (client.get('currency') or 'USD') == p.get('currency', 'USD')
            checks.append((same and float(p.get('price') or 0) <= budget, 'Dentro del presupuesto', 'Supera el presupuesto' if same else 'Moneda distinta; requiere conversión'))
        if client.get('zones'):
            zones = [z.lower() for z in client['zones']]
            checks.append((any(z in p.get('zone', '').lower() or p.get('zone', '').lower() in z for z in zones), 'Zona buscada: ' + p.get('zone', ''), 'Otra zona'))
        if client.get('propertyType'): checks.append((p.get('type') == client['propertyType'], 'Tipo: ' + p.get('type', ''), 'Otro tipo de inmueble'))
        if client.get('bedrooms'): checks.append((int(p.get('bedrooms') or 0) >= int(client['bedrooms']), 'Dormitorios suficientes', 'Faltan dormitorios'))
        if re.search(r'estacionamiento|garaje|parqueo', preferences): checks.append((bool(p.get('parking')), 'Tiene estacionamiento', 'Falta estacionamiento'))
        for ok, yes, no in checks:
            total += 1
            if ok: score += 1; reasons.append(yes)
            else: missing.append(no)
        results.append({'property': p, 'score': round(score / total * 100) if total else None, 'reasons': reasons, 'missing': missing})
    return sorted(results, key=lambda r: (-1 if r['score'] is None else -r['score'], float(r['property'].get('price') or 0)))
