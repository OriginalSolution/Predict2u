#!/usr/bin/env python3
"""Post Predict2U daily codes / settled results to Telegram.

Reads TELEGRAM_BOT_TOKEN from the environment (required to post).
Reads channel from TELEGRAM_CHANNEL env, else telegram.conf CHANNEL=.
Skips cleanly (exit 0) when token or channel is unset — never prints the token.
"""
from __future__ import annotations
import json, os, sys, datetime as dt, urllib.parse, urllib.request

FEED = os.path.dirname(os.path.abspath(__file__))
REPO = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else os.environ.get('REPO_DIR', '/workspace/Predict2u')
CONF = os.path.join(FEED, 'telegram.conf')
STATE = os.path.join(FEED, 'private', 'telegram-state.json')
API = 'https://api.telegram.org/bot{token}/{method}'

BOOKS = [
  ('sportybet', 'SportyBet'), ('msport', 'MSport'), ('betika', 'Betika'),
  ('footballcom', 'football.com'), ('betpawa', 'Betpawa'),
]

def load_conf():
  ch = (os.environ.get('TELEGRAM_CHANNEL') or os.environ.get('TELEGRAM_CHAT_ID') or '').strip()
  if not ch and os.path.exists(CONF):
    for line in open(CONF):
      line = line.strip()
      if not line or line.startswith('#') or '=' not in line: continue
      k, v = line.split('=', 1)
      if k.strip().upper() == 'CHANNEL':
        ch = v.strip().strip('"').strip("'")
  if ch and not ch.startswith('@') and not ch.startswith('-') and not ch.lstrip('-').isdigit():
    ch = '@' + ch
  return ch

def token():
  return (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()

def load_state():
  try: return json.load(open(STATE))
  except Exception: return {}

def save_state(st):
  os.makedirs(os.path.dirname(STATE), exist_ok=True)
  json.dump(st, open(STATE, 'w'), indent=1)

def api(tok, method, payload):
  url = API.format(token=tok, method=method)
  data = json.dumps(payload).encode('utf-8')
  req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
  with urllib.request.urlopen(req, timeout=30) as r:
    return json.loads(r.read().decode('utf-8'))

def send(tok, chat, text):
  return api(tok, 'sendMessage', {
    'chat_id': chat, 'text': text, 'disable_web_page_preview': True,
  })

def slip_label(s):
  risk = (s.get('risk') or '').lower()
  name = s.get('name') or s.get('label') or 'Slip'
  if risk == 'safe' or 'safe slip' in name.lower(): return '🟢 Safe'
  if risk == 'medium' or 'medium slip' in name.lower(): return '🟡 Medium'
  if s.get('banker') or 'banker' in name.lower(): return '🔴 Banker'
  if 'hot' in name.lower(): return '🔥 Hot'
  return '⚪ ' + name[:40]

def format_codes(day_doc=None, picks_doc=None):
  day = dt.datetime.now(dt.timezone.utc).strftime('%d %b %Y')
  lines = [f'Predict2U — {day} codes', '']
  slips = []
  if day_doc:
    slips = [s for s in (day_doc.get('slips') or []) if not s.get('earlier') and (s.get('codes') or {})]
  if not slips and picks_doc:
    slips = [s for s in (picks_doc.get('slips') or []) if s.get('house') and (s.get('codes') or {})]
  # Prefer risk order
  order = {'safe': 0, 'medium': 1, 'high': 2}
  slips = sorted(slips, key=lambda s: (order.get(s.get('risk'), 3), -(s.get('totalOdds') or 0)))
  # Dedupe by sportybet code
  seen = set(); out = []
  for s in slips:
    c = (s.get('codes') or {}).get('sportybet') or s.get('code')
    if not c or c in seen: continue
    seen.add(c); out.append(s)
  if not out:
    return None
  for s in out[:8]:
    codes = s.get('codes') or {}
    odds = (s.get('bookOdds') or {}).get('sportybet') or s.get('totalOdds')
    n = (s.get('bookPicks') or {}).get('sportybet') or s.get('picks') or len(s.get('legs') or [])
    lines.append(f"{slip_label(s)}  @{odds:g} · {n} picks" if isinstance(odds, (int, float)) else f"{slip_label(s)} · {n} picks")
    bits = []
    for k, lab in BOOKS:
      if codes.get(k): bits.append(f"{lab} `{codes[k]}`")
    if bits: lines.append(' · '.join(bits))
    lines.append('')
  lines += [
    'Board: https://predict2u.com/bankers.html',
    'Track record: https://predict2u.com/record.html',
    '',
    '18+ | Bet responsibly',
  ]
  # Telegram parse_mode none — strip backticks for plain text
  return '\n'.join(lines).replace('`', '')

def format_results(ledger, since_ids):
  settled = [e for e in ledger.values()
             if e.get('status') in ('won', 'lost') and f"{e.get('book')}:{e.get('code')}" not in since_ids]
  if not settled: return None, []
  # Prefer distinct by name+date+total, sportybet first
  uniq = {}
  for e in settled:
    key = (e.get('date'), e.get('name'), e.get('total'))
    if key not in uniq or e.get('book') == 'sportybet':
      uniq[key] = e
  rows = sorted(uniq.values(), key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''), reverse=True)[:15]
  day = dt.datetime.now(dt.timezone.utc).strftime('%d %b %Y')
  lines = [f'Predict2U — results ({day})', '']
  for e in rows:
    mark = '✅' if e['status'] == 'won' else '❌'
    odds = e.get('odds')
    od = f" @{odds:g}" if isinstance(odds, (int, float)) else ''
    lines.append(f"{mark} {e.get('name') or e.get('code')}{od} · {e.get('hit')}/{e.get('total')} legs · {e.get('status').upper()}")
  lines += ['', 'Full record: https://predict2u.com/record.html', '', '18+ | Bet responsibly']
  ids = [f"{e.get('book')}:{e.get('code')}" for e in settled]
  return '\n'.join(lines), ids

def main():
  args = [a for a in sys.argv[1:] if a.startswith('--')]
  mode = 'results' if '--results' in args else 'codes'
  dry = '--dry-run' in args
  tok = token(); chat = load_conf()
  if not tok:
    print('telegram: TELEGRAM_BOT_TOKEN unset — skip'); return 0
  if not chat:
    print('telegram: CHANNEL unset (set TELEGRAM_CHANNEL or telegram.conf) — skip'); return 0

  text = None; new_ids = []
  if mode == 'codes':
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    rf = os.path.join(os.environ.get('RESEARCH_DIR', os.path.join(os.path.dirname(__file__), '..', 'data')), day + '.json')
    home = os.path.join(REPO, 'home-picks.json')
    day_doc = json.load(open(rf)) if os.path.exists(rf) else None
    picks = json.load(open(home)) if os.path.exists(home) else None
    # home-picks often has the slips; research may too
    if picks and picks.get('slips'): day_doc = picks
    text = format_codes(day_doc, None)
    _free = False
    try:
      sys.path.insert(0, os.path.dirname(os.path.dirname(FEED))); from engine.premium import free_mode; _free = free_mode(REPO)
    except Exception: _free = False
    if text and not _free:  # premium slips: never post their codes (paid mode only)
      import re as _re; sys.path.insert(0, FEED); import lock_codes
      text = _re.sub(r'`?P2ULOCK-[a-z]+-\d{8}-[a-z]+\d*`?', '🔒 unlock on predict2u.com', lock_codes.mask_text(text))
    if not text:
      print('telegram: no codes to post — skip'); return 0
  else:
    led_path = os.path.join(FEED, 'code-ledger.json')
    led = json.load(open(led_path)) if os.path.exists(led_path) else {}
    st = load_state()
    posted = set(st.get('postedResults') or [])
    text, new_ids = format_results(led, posted)
    if not text:
      print('telegram: no new results — skip'); return 0

  print('telegram: prepared', mode, 'to', chat, 'chars', len(text))
  if dry:
    print('---DRY---'); print(text); print('---END---'); return 0
  try:
    send(tok, chat, text)
  except Exception as e:
    print('telegram: send failed', type(e).__name__, str(e)[:160]); return 1
  st = load_state()
  if mode == 'codes':
    st['lastCodesAt'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
  else:
    st['postedResults'] = list(set(st.get('postedResults') or []) | set(new_ids))[-500:]
    st['lastResultsAt'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
  save_state(st)
  print('telegram: posted', mode)
  return 0

if __name__ == '__main__':
  sys.exit(main())
