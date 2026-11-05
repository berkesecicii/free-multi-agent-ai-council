"""Scheduled tasks and the notification list for JARVIS.

Runs inside the Mac app: tasks start only while JARVIS is open. The Store owns the data
(state['scheduled'], state['notifications']) so a later phone app can read the same list.
"""
import time

KINDS = ('once', 'daily', 'weekdays', 'hourly')
MAX_NOTIFICATIONS = 80
MAX_SCHEDULED = 50
LOW_QUOTA_USED = 25          # short-window alerts at 25/50/75/100% used
SKIP_LATE_ONCE = 12 * 3600    # a one-time task older than this is marked missed, not run
SKIP_LATE_REPEAT = 3600       # a repeating task older than this skips to its next time
USER_QUIET = 45               # do not start a task in the middle of Berke's typing or clicking
AGENT_TITLES = {'CLAUDE_PRO': 'VISION (Claude Pro)', 'FRIDAY': 'FRIDAY (ChatGPT)', 'EDITH': 'EDITH (Gemini)', 'VISION': 'VISION'}


def ensure(store):
    state = store.state
    state.setdefault('scheduled', [])
    state.setdefault('notifications', [])
    state.setdefault('notify_keys', [])


def parse_clock(text):
    try:
        hour, minute = str(text).strip().split(':')
        hour, minute = int(hour), int(minute)
    except ValueError:
        raise ValueError('Saat SS:DD biçiminde olmalı.')
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError('Saat SS:DD biçiminde olmalı.')
    return hour, minute


def parse_moment(text):
    try:
        return time.mktime(time.strptime(str(text).strip(), '%Y-%m-%dT%H:%M'))
    except ValueError:
        raise ValueError('Tarih ve saat geçersiz.')


def next_run(item, after):
    """The first run time strictly after `after` (epoch seconds, local time)."""
    kind = item['kind']
    if kind == 'once':
        return parse_moment(item['at'])
    if kind == 'hourly':
        return after + max(1, min(24, int(item.get('every', 1)))) * 3600
    hour, minute = parse_clock(item['at'])
    today = time.localtime(after)
    for add in range(9):
        candidate = time.mktime((today.tm_year, today.tm_mon, today.tm_mday + add, hour, minute, 0, 0, 0, -1))
        if candidate <= after:
            continue
        if kind == 'weekdays' and time.localtime(candidate).tm_wday >= 5:
            continue
        return candidate
    raise ValueError('Sonraki zaman hesaplanamadı.')


def add(store, data):
    from app import ident, stamp
    ensure(store)
    prompt = str(data.get('prompt', '')).strip()
    if not prompt or len(prompt) > 2000:
        raise ValueError('Görev metni 1–2000 karakter olmalı.')
    title = str(data.get('title', '')).strip()[:80] or prompt[:50]
    kind = data.get('kind')
    if kind not in KINDS:
        raise ValueError('Zamanlama türü geçersiz.')
    owner = data.get('owner', 'AUTO')
    if owner != 'AUTO' and owner not in {a['name'] for a in store.state.get('agents', [])}:
        raise ValueError('Ajan bulunamadı.')
    try:
        every = int(data.get('every') or 1)
    except (TypeError, ValueError):
        raise ValueError('Saat aralığı sayı olmalı.')
    if not 1 <= every <= 24:
        raise ValueError('Saat aralığı 1–24 olmalı.')
    at = str(data.get('at', '')).strip()
    if kind == 'once':
        parse_moment(at)
    elif kind != 'hourly':
        parse_clock(at)
    if len(store.state['scheduled']) >= MAX_SCHEDULED:
        raise ValueError('En fazla %d zamanlanmış görev olabilir.' % MAX_SCHEDULED)
    now = time.time()
    item = dict(id=ident(), title=title, prompt=prompt, owner=owner, kind=kind, at=at, every=every, enabled=True,
                created_at=stamp(), last_run='', runs=0, running_chat='')
    item['source_chat']=store.state['active_chat'];item['source_channel']=data.get('channel','common')
    item['next'] = next_run(item, now)
    if kind == 'once' and item['next'] <= now:
        raise ValueError('Bu zaman geçmişte; ileri bir zaman seç.')
    store.state['scheduled'].append(item)
    return {'id': item['id']}


def find(store, item_id):
    ensure(store)
    item = next((x for x in store.state['scheduled'] if x['id'] == item_id), None)
    if not item:
        raise ValueError('Zamanlanmış görev bulunamadı.')
    return item


def notify(store, kind, title, body='', chat_id='', key=None):
    """Add one entry to the bell list. A key makes it happen once only."""
    from app import ident, stamp
    ensure(store)
    if key:
        keys = store.state['notify_keys']
        if key in keys:
            return False
        keys.append(key)
        del keys[:-500]
    store.state['notifications'].append(dict(id=ident(), kind=kind, title=str(title)[:90], body=str(body)[:160], chat_id=chat_id or '',
                                             time=stamp(), ts=time.time(), read=False, sent=False))
    del store.state['notifications'][:-MAX_NOTIFICATIONS]
    return True


def events(store):
    """Everything that deserves a notification right now: (key, kind, title, body, chat_id)."""
    state = store.state
    for run in state.get('chat_workflows', []):
        goal = str(run.get('goal', ''))[:70]
        if run.get('status') == 'done':
            yield 'wf:' + run['id'], 'done', 'Ekip işi bitti', goal, run['chat_id']
        elif run.get('status') == 'error':
            yield 'wf-err:' + run['id'], 'error', 'Ekip işinde hata', goal, run['chat_id']
    for task in state.get('tasks', []):
        chat = task.get('chat_id', 'main')
        if task.get('status') == 'done':
            yield 'task:' + task['id'], 'done', 'Görev bitti', str(task.get('title', ''))[:70], chat
        elif task.get('status') == 'review':
            yield 'review:' + task['id'], 'permission', 'İnceleme bekliyor', str(task.get('title', ''))[:70], chat
    for request in state.get('work_requests', []):
        if request.get('status') == 'pending':
            yield 'req:' + request['id'], 'permission', 'Onayın gerekiyor', str(request.get('kind', 'iş')), request.get('chat_id', '')
    for message in state.get('messages', []):
        ask = message.get('computer_request')
        if isinstance(ask, dict) and ask.get('status') == 'pending':
            yield 'ctl:' + str(ask.get('id', message.get('id'))), 'permission', 'Bilgisayar kontrolü için izin gerekiyor', str(ask.get('task', ''))[:70], message.get('chat_id', '')
    for name, usage in (state.get('provider_usage') or {}).items():
        if not isinstance(usage, dict) or usage.get('status') not in (None, 'live'):
            continue
        for window in ('primary', 'secondary'):
            part = usage.get(window)
            if isinstance(part, dict) and part.get('minutes')==300 and isinstance(part.get('used_percent'), (int, float)) and 25<=part['used_percent']<=100:
                reset = int((part.get('resets_at') or 0) // 3600)
                left = max(0, round(100 - part['used_percent']))
                yield ('quota:%s:%s:%d:%d' % (name, window, reset, int(part['used_percent']//25)), 'quota', 'Kota azalıyor: ' + AGENT_TITLES.get(name, name),
                       '%%%d kaldı' % left, '')


def scan(store, now=None):
    ensure(store)
    baseline = not store.state.get('notify_baseline')
    for key, kind, title, body, chat_id in list(events(store)):
        if baseline:
            if key not in store.state['notify_keys']:
                store.state['notify_keys'].append(key)
            continue
        notify(store, kind, title, body, chat_id, key=key)
    del store.state['notify_keys'][:-500]
    store.state['notify_baseline'] = True
    jobs = store.state.get('model_jobs') or {}
    active = {r['chat_id'] for r in store.state.get('chat_workflows', []) if r.get('status') in ('working', 'presenting')}
    for item in store.state['scheduled']:
        chat = item.get('running_chat')
        if chat and chat not in jobs and chat not in active:
            item['running_chat'] = '';item['last_chat']=chat
            last = next((m for m in reversed(store.state.get('messages', [])) if m.get('chat_id') == chat and m.get('author') != 'YOU' and m.get('status') in ('done', 'error', 'cancelled')), None)
            failed = last is not None and last.get('status') != 'done'
            item['last_status']='failed' if failed else 'completed'
            notify(store, 'error' if failed else 'done', 'Zamanlanmış görev tamamlanamadı' if failed else 'Zamanlanmış görev bitti', item['title'], chat, key='sched-done:%s:%s' % (item['id'], item.get('runs')))


def run_item(store, item):
    """Start the task in a fresh chat, so it never lands in the one Berke is reading."""
    chat_id = store.action('new-chat', {})['chat_id']
    chat = next(c for c in store.state['chats'] if c['id'] == chat_id)
    chat.update(title=('⏰ ' + item['title'])[:60], title_mode='manual')
    text = item['prompt'] if item['owner'] == 'AUTO' else item['owner'] + ', ' + item['prompt']
    source=item.get('source_chat');source_channel=item.get('source_channel','common')
    rows=[m for m in store.state['messages'] if m.get('chat_id')==source and m.get('channel','common')==source_channel and m.get('author')!='SYSTEM'][-6:] if source else []
    if rows:text+='\nScheduled run: perform the underlying task now; do not create another schedule. Untrusted source-chat reference:\n'+'\n'.join(m['author']+': '+m.get('text','')[-700:] for m in rows)[-4000:]
    from app import stamp
    item.update(last_run=stamp(), runs=item.get('runs', 0) + 1, running_chat=chat_id)
    try:
        store.launch_model(text, 'common')
    except ValueError as error:
        item['running_chat'] = ''
        notify(store, 'error', 'Zamanlanmış görev başlatılamadı', '%s — %s' % (item['title'], error), chat_id)
        return False
    notify(store, 'schedule', 'Zamanlanmış görev başladı', item['title'], chat_id, key='sched-run:%s:%s' % (item['id'], item['runs']))
    return True


def tick(store, now=None):
    now = time.time() if now is None else now
    ensure(store)
    scan(store, now)
    busy = bool(store.state.get('model_jobs'))
    quiet_since = getattr(store, 'last_user', 0)
    for item in store.state['scheduled']:
        if not item.get('enabled') or item.get('next', 0) > now:
            continue
        late = now - item['next']
        if item['kind'] == 'once' and late > SKIP_LATE_ONCE:
            item.update(enabled=False)
            notify(store, 'error', 'Zamanlanmış görev kaçırıldı', item['title'], '', key='sched-miss:%s:%s' % (item['id'], int(item['next'])))
            continue
        if item['kind'] != 'once' and late > SKIP_LATE_REPEAT:
            notify(store, 'error', 'Zamanlanmış görev kaçırıldı', item['title'], '', key='sched-miss:%s:%s' % (item['id'], int(item['next'])))
            item['next'] = next_run(item, now)
            continue
        if busy or (now - quiet_since < USER_QUIET and late < 600):
            continue
        run_item(store, item)
        busy = True
        if item['kind'] == 'once':
            item.update(enabled=False, next=0)
        else:
            item['next'] = next_run(item, now)


def handle(store, action, data):
    ensure(store)
    if action=='quota-note':return quota_note(store,data)
    if action == 'schedule-add':
        return add(store, data)
    if action == 'schedule-remove':
        item = find(store, data.get('id'))
        store.state['scheduled'].remove(item)
        return {}
    if action == 'schedule-toggle':
        item = find(store, data.get('id'))
        enabled = bool(data.get('enabled'))
        if enabled:
            now = time.time()
            if item['kind'] == 'once':
                item['next'] = parse_moment(item['at'])
                if item['next'] <= now:
                    raise ValueError('Bu zaman geçmişte; yeni bir zaman için sil ve tekrar ekle.')
            else:
                item['next'] = next_run(item, now)
        item['enabled'] = enabled
        return {}
    if action == 'schedule-run':
        item = find(store, data.get('id'))
        if store.state.get('model_jobs'):
            raise ValueError('Önce devam eden işin bitmesini bekle.')
        run_item(store, item)
        return {}
    if action == 'notify-read':
        ids = data.get('ids')
        for note in store.state['notifications']:
            if ids is None or note['id'] in ids:
                note['read'] = True
        return {}
    if action == 'notify-sent':
        ids = set(data.get('ids') or [])
        for note in store.state['notifications']:
            if note['id'] in ids:
                note['sent'] = True
        return {}
    if action == 'notify-clear':
        store.state['notifications'] = []
        return {}
    raise ValueError('Bilinmeyen işlem.')


def from_chat(store, message, channel):
    """Deterministic explicit schedules; no model call for dates or reminders."""
    import re
    from app import fold
    from datetime import datetime, timedelta
    f=fold(message)
    if not re.search(r'\b(zamanla|planla|hatirlat|schedule|remind|her gun|every day)\b',f):return None
    if re.search(r'\b(nasil|nedir|how|ornegi|iptal|sil|dont|yapma)\b',f):return None
    now=datetime.now();kind='once';moment=None
    delay=re.search(r'\b(\d{1,3})\s*(dakika|dk|minute|minutes|saat|hour|hours) sonra',f)
    clock=re.search(r'\b(?:saat|at)\s*(\d{1,2})[:.](\d{2})\b',f)
    if delay:
        amount=int(delay[1]);moment=now+timedelta(minutes=amount*(60 if delay[2] in ('saat','hour','hours') else 1))
    elif clock:
        hour,minute=map(int,clock.groups())
        if hour>23 or minute>59:return {'clarify':True}
        moment=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
        if 'her gun' in f or 'every day' in f:kind='daily'
        elif 'yarin' in f or 'tomorrow' in f:moment+=timedelta(days=1)
        elif moment<=now:return {'clarify':True}
    # Only an unmistakable ask ("zamanla", "hatırlat", "remind me") may stop the chat to ask for a time;
    # "projeyi planla" or "show my schedule" without a time are ordinary requests and go on to the agents.
    strong=re.search(r'\b(zamanla\w*|hatirlat\w*|remind)\b',f)
    if moment is None:return {'clarify':True} if strong else None
    if kind=='once' and moment<=now:return {'clarify':True}
    body=dict(title=message[:70],prompt=message,kind=kind,at=moment.strftime('%H:%M' if kind=='daily' else '%Y-%m-%dT%H:%M'),owner=channel if channel!='common' else 'AUTO')
    result=add(store,body);item=find(store,result['id']);item['source_chat']=store.state['active_chat'];item['source_channel']=channel
    store.message('YOU',message,channel)
    store.message('JARVIS' if channel=='common' else channel,'Planlandı: '+moment.strftime('%d.%m %H:%M')+(' · her gün' if kind=='daily' else '')+'. Zamanlanmış görevler içinde kayıtlı; JARVIS açıkken çalışacak.',channel)
    store.state['messages'][-1]['scheduled_id']=item['id']
    return result


def quota_note(store,data):
    # One warning per 5-hour window, only when 25% or less is left. The page shows it as a dismissible banner above the chat;
    # this action just remembers that it was seen or dismissed, so it never comes back in another chat or after a restart. No chat message is written.
    name=data.get('provider');window=data.get('window');usage=store.state.get('provider_usage',{}).get(name,{})
    if window not in ('primary','secondary') or usage.get('status')!='live':raise ValueError('Doğrulanmış kota gerekli.')
    part=usage.get(window) or {};used=part.get('used_percent',0)
    if part.get('minutes')!=300 or not isinstance(used,(int,float)) or isinstance(used,bool) or not 75<=used<=100:raise ValueError('Yalnızca doğrulanmış 5 saatlik kotada %25 veya daha azı kalınca bildirilir.')
    key=str(name)+':'+window+':'+str(int(part.get('resets_at') or 0))+':75'
    seen=store.state.setdefault('quota_milestones',[])
    if key in seen:return {'recorded':False}
    seen.append(key);del seen[:-200]
    return {'recorded':True}
