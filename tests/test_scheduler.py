import sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Store
import scheduler as sc

def at(y,mo,d,h,mi):return time.mktime((y,mo,d,h,mi,0,0,0,-1))
def make(d):
 s=Store(d);s.launched=[]
 def fake(text,channel,**kw):
  s.launched.append((text,s.state['active_chat']))
  s.state['model_jobs'][s.state['active_chat']]={'id':'job'}
 s.launch_model=fake
 return s

class NextRunTests(unittest.TestCase):
 def test_daily_picks_today_or_tomorrow(self):
  item=dict(kind='daily',at='09:30')
  self.assertEqual(sc.next_run(item,at(2026,11,3,8,0)),at(2026,11,3,9,30))
  self.assertEqual(sc.next_run(item,at(2026,11,3,10,0)),at(2026,11,4,9,30))
 def test_weekdays_skip_the_weekend(self):
  item=dict(kind='weekdays',at='08:00')
  friday=at(2026,11,6,12,0)   # Friday 6 Nov 2026
  self.assertEqual(sc.next_run(item,friday),at(2026,11,9,8,0))
 def test_hourly_and_once(self):
  self.assertEqual(sc.next_run(dict(kind='hourly',every=3),1000.0),1000.0+3*3600)
  self.assertEqual(sc.next_run(dict(kind='once',at='2026-11-05T14:15'),0),at(2026,11,5,14,15))
 def test_bad_clock_is_rejected(self):
  for bad in ('25:00','9','ab:cd','10:61'):
   with self.assertRaises(ValueError):sc.parse_clock(bad)

class ScheduleTests(unittest.TestCase):
 def test_add_validates_and_lists_in_client_state(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d)
   with self.assertRaises(ValueError):sc.add(s,dict(prompt='',kind='daily',at='09:00'))
   with self.assertRaises(ValueError):sc.add(s,dict(prompt='x',kind='nope'))
   with self.assertRaises(ValueError):sc.add(s,dict(prompt='x',kind='once',at='2020-01-01T10:00'))
   with self.assertRaises(ValueError):sc.add(s,dict(prompt='x',kind='daily',at='09:00',owner='GHOST'))
   sc.add(s,dict(title='Sabah özeti',prompt='Bugünün işlerini özetle',kind='daily',at='09:00',owner='EDITH'))
   rows=s.client_state()['scheduled'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['owner'],'EDITH');self.assertTrue(rows[0]['next']>time.time())
 def test_due_task_runs_in_a_new_chat_once(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);first=s.state['active_chat']
   sc.add(s,dict(title='Rapor',prompt='Rapor yaz',kind='hourly',every=1,owner='NOVA'))
   item=s.state['scheduled'][0];item['next']=time.time()-5
   sc.tick(s)
   self.assertEqual(len(s.launched),1);self.assertTrue(s.launched[0][0].startswith('NOVA, '))
   self.assertNotEqual(s.launched[0][1],first)
   chat=next(c for c in s.state['chats'] if c['id']==s.launched[0][1]);self.assertTrue(chat['title'].startswith('⏰'))
   self.assertTrue(item['next']>time.time()+3000);self.assertEqual(item['runs'],1)
   sc.tick(s);self.assertEqual(len(s.launched),1)
 def test_one_time_task_turns_itself_off(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.add(s,dict(prompt='tek sefer',kind='once',at=time.strftime('%Y-%m-%dT%H:%M',time.localtime(time.time()+3600))))
   item=s.state['scheduled'][0];item['next']=time.time()-1;sc.tick(s)
   self.assertEqual(len(s.launched),1);self.assertFalse(item['enabled'])
 def test_busy_or_typing_defers_and_old_tasks_are_marked_missed(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.add(s,dict(prompt='x',kind='daily',at='09:00'));item=s.state['scheduled'][0]
   item['next']=time.time()-5;s.state['model_jobs']['c']={'id':'j'};sc.tick(s);self.assertEqual(len(s.launched),0)
   s.state['model_jobs']={};s.last_user=time.time();sc.tick(s);self.assertEqual(len(s.launched),0)
   s.last_user=0;item['next']=time.time()-2*3600;sc.tick(s)
   self.assertEqual(len(s.launched),0);self.assertTrue(item['next']>time.time())
   self.assertTrue(any(n['title']=='Zamanlanmış görev kaçırıldı' for n in s.state['notifications']))
 def test_finished_scheduled_run_notifies_once(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.add(s,dict(prompt='x',kind='hourly',every=2));item=s.state['scheduled'][0]
   item['next']=time.time()-1;sc.tick(s);chat=item['running_chat'];self.assertTrue(chat)
   s.state['model_jobs']={};sc.tick(s);sc.tick(s)
   done=[n for n in s.state['notifications'] if n['title']=='Zamanlanmış görev bitti'];self.assertEqual(len(done),1);self.assertEqual(done[0]['chat_id'],chat)
 def test_toggle_remove_run_now(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.add(s,dict(prompt='x',kind='daily',at='07:05'));ident=s.state['scheduled'][0]['id']
   sc.handle(s,'schedule-toggle',dict(id=ident,enabled=False));self.assertFalse(s.state['scheduled'][0]['enabled'])
   sc.handle(s,'schedule-toggle',dict(id=ident,enabled=True));self.assertTrue(s.state['scheduled'][0]['enabled'])
   sc.handle(s,'schedule-run',dict(id=ident));self.assertEqual(len(s.launched),1)
   with self.assertRaises(ValueError):sc.handle(s,'schedule-run',dict(id=ident))
   sc.handle(s,'schedule-remove',dict(id=ident));self.assertEqual(s.state['scheduled'],[])

class NotificationTests(unittest.TestCase):
 def test_first_scan_is_silent_then_new_events_notify_once(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);chat=s.state['active_chat']
   s.state['chat_workflows']=[dict(id='w0',chat_id=chat,goal='eski',steps=[],index=0,status='done',results=[],docs=[])]
   sc.scan(s);self.assertEqual(s.state['notifications'],[])
   s.state['chat_workflows'].append(dict(id='w1',chat_id=chat,goal='Python listesi araştır',steps=['EDITH'],index=1,status='done',results=[],docs=[]))
   sc.scan(s);sc.scan(s)
   rows=s.state['notifications'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'Ekip işi bitti');self.assertEqual(rows[0]['chat_id'],chat);self.assertFalse(rows[0]['read'])
 def test_permission_requests_and_low_quota_notify(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.scan(s)
   s.state['work_requests'].append(dict(id='r1',chat_id=s.state['active_chat'],kind='command',status='pending'))
   s.state['messages'].append(dict(id='m1',author='VISION',text='',chat_id=s.state['active_chat'],computer_request=dict(id='cr1',status='pending',task='Safari aç')))
   s.state['provider_usage']['CLAUDE_PRO']=dict(status='live',primary=dict(used_percent=93.0,resets_at=1800000000,minutes=300),secondary=dict(used_percent=40.0,resets_at=1800500000))
   sc.scan(s);sc.scan(s)
   titles=sorted(n['title'] for n in s.state['notifications'])
   self.assertEqual(titles,['Bilgisayar kontrolü için izin gerekiyor','Kota azalıyor: VISION (Claude Pro)','Onayın gerekiyor'])
   quota=next(n for n in s.state['notifications'] if n['kind']=='quota');self.assertIn('%7',quota['body'])
 def test_read_sent_clear_and_cap(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d)
   for i in range(100):sc.notify(s,'done','t%d'%i,'b')
   self.assertEqual(len(s.state['notifications']),sc.MAX_NOTIFICATIONS)
   ids=[n['id'] for n in s.state['notifications'][:2]]
   sc.handle(s,'notify-sent',dict(ids=ids));sc.handle(s,'notify-read',dict(ids=ids))
   self.assertEqual(sum(n['sent'] for n in s.state['notifications']),2);self.assertEqual(sum(n['read'] for n in s.state['notifications']),2)
   sc.handle(s,'notify-read',dict());self.assertTrue(all(n['read'] for n in s.state['notifications']))
   sc.handle(s,'notify-clear',dict());self.assertEqual(s.state['notifications'],[])
 def test_actions_are_wired_through_the_store_and_the_http_allowlist(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);s.action('schedule-add',dict(prompt='x',kind='daily',at='06:00'));self.assertEqual(len(s.client_state()['scheduled']),1)
  src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
  for name in ('schedule-add','schedule-run','notify-read','notify-sent'):self.assertIn("'"+name+"'",src)
  self.assertIn('scheduler.py',(Path(__file__).resolve().parents[1]/'native'/'build.sh').read_text(encoding='utf-8'))
  self.assertIn('scheduler.py',(Path(__file__).resolve().parents[1]/'Guncelle.command').read_text(encoding='utf-8'))

class FailureStatusTests(unittest.TestCase):
 def test_failed_answer_is_not_announced_as_success(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.scan(s);sc.add(s,dict(prompt='test',kind='hourly',every=2))
   item=s.state['scheduled'][0];sc.run_item(s,item);chat=item['running_chat']
   s.state['messages'].append(dict(id='failed-reply',chat_id=chat,author='JARVIS',status='error',text='quota exhausted'))
   s.state['model_jobs']={};sc.scan(s)
   self.assertEqual(s.state['notifications'][-1]['kind'],'error')
   self.assertEqual(s.state['notifications'][-1]['title'],'Zamanlanmış görev tamamlanamadı')
 def test_rejected_past_once_stays_disabled(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);sc.add(s,dict(prompt='test',kind='once',at=time.strftime('%Y-%m-%dT%H:%M',time.localtime(time.time()+3600))))
   item=s.state['scheduled'][0];item.update(enabled=False,at='2020-01-01T10:00')
   with self.assertRaises(ValueError):sc.handle(s,'schedule-toggle',dict(id=item['id'],enabled=True))
   self.assertFalse(item['enabled'])

class ChatCreationTests(unittest.TestCase):
 def test_chat_request_creates_real_schedule_and_unclear_time_does_not(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d)
   result=s.action('converse',dict(text='10 dakika sonra bu sohbeti özetlemeyi zamanla',channel='common'))
   self.assertTrue(result.get('id'));self.assertEqual(len(s.state['scheduled']),1)
   self.assertEqual(s.state['scheduled'][0]['source_chat'],s.state['active_chat'])
   s.action('converse',dict(text='Bunu zamanla',channel='common'))
   self.assertEqual(len(s.state['scheduled']),1);self.assertIn('Hangi gün',s.state['messages'][-1]['text'])
 def test_quota_warning_is_remembered_once_per_window_and_never_written_into_a_chat(self):
  with tempfile.TemporaryDirectory() as d:
   s=make(d);s.state['provider_usage']['FRIDAY']=dict(status='live',primary=dict(used_percent=83,resets_at=123,minutes=300))
   before=len(s.state['messages'])
   self.assertTrue(s.action('quota-note',dict(provider='FRIDAY',window='primary'))['recorded'])
   self.assertFalse(s.action('quota-note',dict(provider='FRIDAY',window='primary'))['recorded'])   # dismissing twice changes nothing
   self.assertEqual(len(s.state['messages']),before);self.assertFalse([m for m in s.state['messages'] if m.get('quota_notice')])
   self.assertEqual(s.state['quota_milestones'],['FRIDAY:primary:123:75'])
   # more usage in the same window is not a new warning
   s.state['provider_usage']['FRIDAY']['primary']['used_percent']=100
   self.assertFalse(s.action('quota-note',dict(provider='FRIDAY',window='primary'))['recorded'])
   # a new 5-hour window can warn again
   s.state['provider_usage']['FRIDAY']['primary'].update(used_percent=80,resets_at=999)
   self.assertTrue(s.action('quota-note',dict(provider='FRIDAY',window='primary'))['recorded'])
   # more than 25% left, unverified providers and weekly windows are refused
   s.state['provider_usage']['FRIDAY']['primary'].update(used_percent=60,resets_at=1500)
   with self.assertRaises(ValueError):s.action('quota-note',dict(provider='FRIDAY',window='primary'))
   with self.assertRaises(ValueError):s.action('quota-note',dict(provider='UNVERIFIED',window='primary'))
   s.state['provider_usage']['FRIDAY']['primary'].update(used_percent=90,minutes=10080)
   with self.assertRaises(ValueError):s.action('quota-note',dict(provider='FRIDAY',window='primary'))



class ChatScheduleTests(unittest.TestCase):
    def test_only_explicit_timed_asks_become_schedules(self):
        import tempfile
        from app import Store
        from scheduler import from_chat
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            for text in ('bu projeyi planla', 'planla ve ekibe dağıt', 'show my schedule', 'Python nasıl zamanlanır'):
                self.assertIsNone(from_chat(store, text, 'common'), text)
            self.assertEqual(from_chat(store, 'bana bunu hatırlat', 'common'), {'clarify': True})
            made = from_chat(store, 'yarın saat 09:00 raporu hazırla ve zamanla', 'common')
            self.assertIn('id', made)
            self.assertEqual(len(store.state['scheduled']), 1)
            self.assertEqual(store.state['scheduled'][0]['kind'], 'once')
            daily = from_chat(store, 'her gün saat 08:30 haberleri özetle', 'common')
            self.assertIn('id', daily)
            self.assertEqual(store.state['scheduled'][1]['kind'], 'daily')
