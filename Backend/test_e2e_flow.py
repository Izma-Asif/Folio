import urllib.request
import json
import time
import sys

BASE = 'http://localhost:8000'

def req(url, method='GET', data=None, timeout=60):
    headers = {'Content-Type': 'application/json'}
    body = json.dumps(data).encode('utf-8') if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            content = resp.read()
            try:
                return resp.status, json.loads(content.decode('utf-8'))
            except Exception:
                return resp.status, content
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        return e.code, err_body
    except Exception as e:
        return 0, str(e)

print('=== 1. CREATE USER ===', flush=True)
st, u_res = req(f'{BASE}/api/users', 'POST', {
    'interests': ['Tech', 'Politics', 'AI'],
    'language': 'en',
    'calm_mode': False,
    'visual_mode': 'visual'
})
print(f'Status: {st}, Res: {u_res}', flush=True)
if st != 200 or not isinstance(u_res, dict):
    print("Failed to create user!", flush=True)
    sys.exit(1)
uid = u_res['user_id']

print('\n=== 2. FETCH ARTICLES ===', flush=True)
t0 = time.time()
st, f_res = req(f'{BASE}/api/fetch', 'POST', timeout=45)
print(f'Fetch completed in {time.time()-t0:.1f}s. Status: {st}, Res: {f_res}', flush=True)

print('\n=== 3. SCORE ARTICLES ===', flush=True)
t0 = time.time()
st, s_res = req(f'{BASE}/api/score', 'POST', timeout=60)
print(f'Score completed in {time.time()-t0:.1f}s. Status: {st}, Res: {s_res}', flush=True)

print('\n=== 4. GENERATE FIRST EDITION ===', flush=True)
t0 = time.time()
st, ed1 = req(f'{BASE}/api/editions/generate?user_id={uid}', 'POST', timeout=60)
print(f'Generate completed in {time.time()-t0:.1f}s. Status: {st}', flush=True)
if isinstance(ed1, dict):
    ed1_id = ed1.get('id')
    print(f'Edition 1 ID: {ed1_id}, Masthead: {ed1.get("masthead")}', flush=True)
    lead = ed1.get('lead') or {}
    print(f'Lead title: {lead.get("title")}, Lead topic: {lead.get("topic")}', flush=True)
    print(f'Changes in ed1: {ed1.get("changes")}', flush=True)
    lead_art_id = lead.get('id')
else:
    print('Failed ed1:', ed1, flush=True)
    sys.exit(1)

print('\n=== 5. SKIP A TOPIC ===', flush=True)
st, ev_res = req(f'{BASE}/api/events', 'POST', {
    'user_id': uid,
    'article_id': lead_art_id,
    'type': 'skip',
    'reason': 'not_interested'
})
print(f'Status: {st}, Event Res: {ev_res}', flush=True)

print('\n=== 6. SEND EDITOR NOTE ("less politics, more startups") ===', flush=True)
st, en_res = req(f'{BASE}/api/users/{uid}/editor-note', 'POST', {
    'text': 'less politics, more startups'
})
print(f'Status: {st}, Note Res: {en_res}', flush=True)

print('\n=== 7. REGENERATE EDITION ===', flush=True)
# Ensure we bypass or allow cache to clear if needed
time.sleep(2)
st, ed2 = req(f'{BASE}/api/editions/generate?user_id={uid}', 'POST', timeout=60)
print(f'Regenerate Status: {st}', flush=True)
if isinstance(ed2, dict):
    ed2_id = ed2.get('id')
    print(f'Edition 2 ID: {ed2_id}', flush=True)
    print(f'Changes card in ed2: {ed2.get("changes")}', flush=True)
    print(f'Lead in ed2: {(ed2.get("lead") or {}).get("title")}', flush=True)
else:
    print('Failed ed2:', ed2, flush=True)

print('\n=== 8. DOWNLOAD PDF ===', flush=True)
target_ed_id = ed2_id if isinstance(ed2, dict) and ed2.get('id') else ed1_id
t0 = time.time()
st, pdf_data = req(f'{BASE}/api/editions/{target_ed_id}/pdf', timeout=60)
print(f'PDF Download completed in {time.time()-t0:.1f}s. Status: {st}', flush=True)
if isinstance(pdf_data, bytes):
    print(f'Length: {len(pdf_data)} bytes', flush=True)
    print(f'Starts with %PDF: {pdf_data.startswith(b"%PDF")}', flush=True)
    with open('test_downloaded.pdf', 'wb') as f:
        f.write(pdf_data)
    print('Saved PDF to test_downloaded.pdf', flush=True)
else:
    print('PDF response is not bytes:', str(pdf_data)[:300], flush=True)

print('\n=== END TO END TEST COMPLETE ===', flush=True)
