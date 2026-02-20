#!/usr/bin/env python3
"""
GRANT HUNTER AGENT
Searches for new grants daily. Scores fit. AI drafts + sends applications.
Never applies to the same grant twice. Fully autonomous.
"""
import os, json, re, smtplib, requests
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SERP_KEY    = os.environ.get('SERPAPI_KEY', '')
OR_KEY      = os.environ.get('OPENROUTER_KEY', '')
GMAIL_PASS  = os.environ.get('GMAIL_APP_PASSWORD', '')
GMAIL_USER  = 'mickowood86@gmail.com'
GALLERY     = 'https://meekotharaccoon-cell.github.io/gaza-rose-gallery'
GITHUB      = 'https://github.com/meekotharaccoon-cell'
FOUND_LOG   = 'data/grants_found.json'
APPLIED_LOG = 'data/grants_applied.json'

SEARCH_QUERIES = [
    'open grant application 2025 digital art humanitarian no nonprofit required',
    'microgrant open source technology humanitarian rolling deadline 2025',
    'artist grant 2025 digital media solo artist open application now',
    'fellowship digital art technology social impact 2025 stipend apply',
    'emergency grant artist 2025 open rolling no deadline',
    'grant funding open source project humanitarian 2025',
]

POSITIVE_KW = ['open source','humanitarian','digital art','technology','solo artist',
    'no nonprofit','individual','rolling','microgrant','stipend','fellowship',
    'palestine','international','free software','open application']
NEGATIVE_KW = ['501c3 required','nonprofit only','corporation','university only',
    'closed','deadline passed','employees only']

def search(query):
    if not SERP_KEY: return []
    try:
        r = requests.get('https://serpapi.com/search',
            params={'q': query, 'api_key': SERP_KEY, 'num': 10, 'tbs': 'qdr:m'},
            timeout=15)
        return [{'title': x.get('title',''), 'url': x.get('link',''),
                 'snippet': x.get('snippet','')} for x in r.json().get('organic_results',[])]
    except: return []

def score(result):
    text = (result['title'] + ' ' + result['snippet']).lower()
    s = sum(2 for kw in POSITIVE_KW if kw in text)
    s -= sum(3 for kw in NEGATIVE_KW if kw in text)
    return s

def ai_eval(grant):
    if not OR_KEY: return None
    prompt = f"""Evaluate this grant for Gaza Rose Gallery (open source humanitarian art, 70% to PCRF).
Grant: {grant['title']}\nURL: {grant['url']}\nDesc: {grant['snippet']}
Respond JSON only:
{{"worth_applying":bool,"reason":"one sentence","contact_email":"email or null",
"estimated_amount":"range or unknown","application_email":"full email body or null"}}
If writing email: be genuine, mention gallery ({GALLERY}) and code ({GITHUB}).
Sign as Meeko, mickowood86@gmail.com."""
    try:
        r = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization':f'Bearer {OR_KEY}','Content-Type':'application/json'},
            json={'model':'openai/gpt-4o-mini','messages':[{'role':'user','content':prompt}],
                  'max_tokens':600,'temperature':0.3},timeout=30)
        text = re.sub(r'```json|```','',r.json()['choices'][0]['message']['content']).strip()
        return json.loads(text)
    except: return None

def load_json(p):
    try:
        with open(p) as f: return json.load(f)
    except: return {}

def save_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p,'w') as f: json.dump(d, f, indent=2)

def send_email(to, subject, body):
    if not GMAIL_PASS: print(f'[Email] Would send to {to}'); return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f'Meeko / Gaza Rose Gallery <{GMAIL_USER}>'
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body,'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com',465) as s:
            s.login(GMAIL_USER, GMAIL_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f'[Email] Failed: {e}'); return False

def run():
    found = load_json(FOUND_LOG)
    applied = load_json(APPLIED_LOG)
    new = applied_count = 0
    for query in SEARCH_QUERIES:
        for result in search(query):
            url = result['url']
            if url in found: continue
            s = score(result)
            found[url] = {'title':result['title'],'score':s,
                'found_at':datetime.now(timezone.utc).isoformat()}
            new += 1
            if s >= 3 and url not in applied:
                ev = ai_eval(result)
                if ev and ev.get('worth_applying') and ev.get('application_email') and ev.get('contact_email'):
                    if send_email(ev['contact_email'],
                        'Grant Application — Gaza Rose Gallery (Humanitarian Art)',
                        ev['application_email']):
                        applied[url] = {'title':result['title'],'to':ev['contact_email'],
                            'amount':ev.get('estimated_amount','?'),
                            'applied_at':datetime.now(timezone.utc).isoformat()}
                        applied_count += 1
                        print(f'APPLIED: {ev["contact_email"]}')
    save_json(FOUND_LOG, found)
    save_json(APPLIED_LOG, applied)
    print(f'Done. New: {new}, Applied: {applied_count}, Total tracked: {len(found)}')

if __name__ == '__main__': run()
