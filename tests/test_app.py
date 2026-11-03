import http.client
import json
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store, create_server

class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def test_one_owner_and_dedup(self):
        first = self.store.action('task', {'text':'Depolama seçeneklerini araştır'})
        repeated = self.store.action('task', {'text':'  Depolama   seçeneklerini araştır  ', 'owner':'VISION'})
        self.assertTrue(repeated['duplicate'])
        self.assertEqual(first['task_id'], repeated['task_id'])
        self.assertEqual(len(self.store.state['tasks']), 1)
        self.assertEqual(self.store.state['tasks'][0]['owner'], 'EDITH')
    def test_cache_hit_expiry_persistence_and_files(self):
        task = self.store.action('task', {'text':'Mac depolama araştır'})
        self.store.action('result', {'id':task['task_id'], 'text':'Kaynak: https://example.com — manuel bulgu'})
        self.store.save()
        reopened = Store(self.tmp.name)
        reopened.action('task', {'text':'Mac depolama araştır'})
        self.assertTrue(reopened.state['tasks'][-1]['cache_hit'])
        reopened.state['settings']['cache_hours'] = 0
        reopened.action('task', {'text':'Mac depolama araştır'})
        self.assertEqual(reopened.state['tasks'][-1]['status'], 'queued')
        self.assertIn('https://example.com', (Path(self.tmp.name)/'research.md').read_text())
        self.assertTrue((Path(self.tmp.name)/'tasks.json').exists())
        self.assertTrue((Path(self.tmp.name)/'decisions.md').exists())
    def test_handoff_quota(self):
        task = self.store.task({'text':'Uygulama geliştir'})
        self.store.state['settings']['daily_handoffs'] = 1
        packet = self.store.action('handoff', {'id':task['task_id']})
        self.assertIn('sole owner', packet['packet'])
        with self.assertRaises(ValueError):
            self.store.action('handoff', {'id':task['task_id']})
        self.assertEqual(self.store.state['usage']['handoffs'], 1)
    def test_command_needs_approval_single_use_and_allowlist(self):
        with patch('app.subprocess.run') as run:
            self.store.action('propose', {'command':'python-version'})
            self.assertFalse(run.called)
            command = self.store.state['commands'][-1]
            run.return_value.returncode = 0
            run.return_value.stdout = 'Python test'
            run.return_value.stderr = ''
            self.store.action('approve', {'id':command['id']})
            self.assertEqual(run.call_count, 1)
            self.assertFalse(run.call_args.kwargs['shell'])
            with self.assertRaises(ValueError):
                self.store.action('approve', {'id':command['id']})
            with self.assertRaises(ValueError):
                self.store.action('propose', {'command':'rm -rf /'})
    def test_real_approved_readonly_command(self):
        self.store.action('propose', {'command':'python-version'})
        command = self.store.state['commands'][-1]
        self.store.action('approve', {'id':command['id']})
        self.assertEqual(command['status'],'done')
        self.assertIn('Python',command['output'])
    def test_rejected_and_expired_commands_never_run(self):
        with patch('app.subprocess.run') as run:
            for action in ['reject', 'approve']:
                self.store.action('propose', {'command':'python-version'})
                command = self.store.state['commands'][-1]
                command['expires'] = 0
                self.store.action(action, {'id':command['id']})
            self.assertFalse(run.called)
    def test_budget_validation_and_manual_result_immutability(self):
        for value in [-1,float('nan'),float('inf'),True]:
            with self.assertRaises(ValueError):
                self.store.action('settings', dict(daily_usd=value,task_usd=0,daily_handoffs=20,cache_hours=24))
        task = self.store.task({'text':'Test görevi'})
        self.store.action('result', {'id':task['task_id'],'text':'Tamamlandı'})
        with self.assertRaises(ValueError):
            self.store.action('result', {'id':task['task_id'],'text':'Değiştirme'})
    def test_agents_transfer_and_checkpoint_preserve_single_owner(self):
        self.store.action('add-agent', {'name':'TEST_AGENT','provider':'Local manual tool','role':'Developer'})
        task = self.store.task({'text':'Devam eden uygulama'})
        self.store.action('transfer', {'id':task['task_id'],'owner':'TEST_AGENT','checkpoint':'Login tamam. Kalan: testler.'})
        row = self.store.state['tasks'][0]
        self.assertEqual(row['owner'], 'TEST_AGENT')
        self.assertEqual(row['previous_owners'], ['FRIDAY'])
        packet = self.store.action('handoff', {'id':row['id']})['packet']
        self.assertIn('Login tamam', packet)
        self.assertEqual(len(self.store.state['tasks']), 1)
        with self.assertRaises(ValueError):
            self.store.action('add-agent', {'name':'TEST_AGENT','provider':'duplicate','role':'x'})
    def test_chat_channels_and_local_conversation(self):
        self.store.action('converse', {'text':'Merhaba'})
        self.assertIn('Berke', self.store.state['messages'][-1]['text'])
        self.store.action('converse', {'text':'Bu kodu incele','channel':'FRIDAY'})
        self.assertEqual(self.store.state['messages'][-1]['channel'], 'FRIDAY')
        packet = self.store.action('chat-packet', {'channel':'FRIDAY'})['packet']
        self.assertIn('Bu kodu incele',packet)
        self.store.action('chat-result', {'channel':'FRIDAY','text':'Manuel yanıt'})
        self.assertEqual(self.store.state['messages'][-1]['author'],'FRIDAY')
        self.assertEqual(len(self.store.state['tasks']),0)
    def test_common_context_reaches_all_agents_without_private_channel_leak(self):
        self.store.action('chat', {'text':'Ortak istek: mavi renkli bir Mac uygulaması.'})
        self.store.action('converse', {'text':'FRIDAY özel kanal notu', 'channel':'FRIDAY'})
        packet = self.store.action('chat-packet', {'channel':'VISION'})['packet']
        self.assertNotIn('mavi renkli',packet)
        self.assertNotIn('FRIDAY özel kanal notu',packet)
        task=self.store.task({'text':'Uygulama tasarla','owner':'EDITH'})
        self.assertIn('mavi renkli',self.store.packet(self.store.find('tasks',task['task_id'])))
        self.store.save()
        self.assertIn('mavi renkli',(Path(self.tmp.name)/'conversation.md').read_text())
    def test_team_plan_is_sequential_and_deduplicated(self):
        self.store.action('brief', {'text':'Mavi bir Mac uygulaması geliştir'})
        self.store.action('organize', {})
        self.assertEqual([t['owner'] for t in self.store.state['tasks']],['FRIDAY','VISION'])
        first,second=self.store.state['tasks']
        self.assertEqual(second['depends_on'],[first['id']])
        with self.assertRaises(ValueError):self.store.action('handoff',{'id':second['id']})
        self.store.action('result',{'id':first['id'],'text':'Kod ve doğrulama sonucu'})
        self.assertIn('shared_context',self.store.action('handoff',{'id':second['id']})['packet'])
        self.store.action('organize', {})
        self.assertEqual(len(self.store.state['tasks']),2)
    def test_organizer_does_not_make_project_from_small_talk(self):
        self.store.action('chat',{'text':'Mikrofon yok ki senin'})
        self.store.action('organize',{})
        self.assertEqual(self.store.state['tasks'],[])
        self.assertIn('hangi projede',self.store.state['messages'][-1]['text'])
    def test_live_model_updates_persisted_message(self):
        captured=[]
        class FakeConversation:
            def __init__(self,directory,on_delta,cancelled):self.delta=on_delta
            def run(self,prompt,image=None):
                captured.append(prompt);self.delta('Gerçek ');return 'Bağlama göre model yanıtı'
            def close(self):pass
        self.store.action('chat',{'text':'Berke ortak bağlamı'})
        self.store.integrations_enabled=True
        self.store.state['chat_mode']='codex'
        with patch('app.CodexConversation',FakeConversation):
            self.store.action('converse',{'text':'Devam et','channel':'FRIDAY'})
            self.store.model_thread.join(timeout=3)
        self.assertNotIn('Berke ortak bağlamı',captured[0])
        self.assertEqual(self.store.state['messages'][-1]['text'],'Bağlama göre model yanıtı')
        self.assertEqual(self.store.state['messages'][-1]['status'],'done')
        self.assertIsNone(self.store.state['model_job'])
    def test_live_failure_does_not_fake_answer_or_fallback(self):
        class FailingConversation:
            def __init__(self,*args):raise ValueError('Abonelik kotası dolu')
        self.store.integrations_enabled=True
        self.store.state['chat_mode']='codex'
        with patch('app.CodexConversation',FailingConversation):
            self.store.action('converse',{'text':'Bir soru'})
            self.store.model_thread.join(timeout=3)
        row=self.store.state['messages'][-1]
        self.assertEqual(row['status'],'error')
        self.assertEqual(row['text'],'Abonelik kotası dolu')
        self.assertEqual(self.store.state['usage']['api_usd'],0)
    def test_invalid_image_rejected_before_model_start(self):
        self.store.integrations_enabled=True
        for image in ['https://evil.example/image','data:image/jpeg;base64,bm90LWEtanBlZw==']:
            with self.assertRaises(ValueError):self.store.action('converse',{'text':'Ekrana bak','image':image})
        self.assertIsNone(self.store.state['model_job'])
    def test_automatic_router_and_explicit_local_image_limit(self):
        self.assertEqual(self.store.route_engine('Nasılsın bugün?','common'),'gemini')
        self.assertEqual(self.store.route_engine('Bu projeyi debug et','common'),'gemini')
        self.assertEqual(self.store.route_engine('Merhaba','FRIDAY'),'codex')
        self.store.state['chat_mode']='local'
        with self.assertRaises(ValueError):self.store.route_engine('Ekrana bak','common','image')
    def test_common_never_spends_coding_quota_implicitly(self):
        for text in ['write python code','internetten güncel araştır','debug this project','x'*900]:
            self.assertEqual(self.store.route_engine(text,'common'),'gemini')
        for a in self.store.state['agents']:
            if a['connector']=='gemini':a['in_common']=False
        with self.assertRaises(ValueError):self.store.route_engine('hello','common')
        self.assertEqual(self.store.route_engine('hello','FRIDAY'),'codex')
    def test_simple_arithmetic_and_status_do_not_use_models(self):
        with patch.object(self.store,'launch_model') as model:
            self.store.integrations_enabled=True
            self.store.action('converse',{'text':'2 + 3 * 4'})
            self.assertEqual(self.store.state['messages'][-1]['text'],'14')
            self.store.action('converse',{'text':'team status'})
            self.assertIn('active tasks',self.store.state['messages'][-1]['text'])
            model.assert_not_called()
    def test_local_chat_never_calls_codex_and_reuses_safe_cache(self):
        self.store.integrations_enabled=True
        self.store.state['chat_mode']='local'
        with patch.object(self.store.local,'run',return_value='A star is a luminous object.') as local,patch('app.CodexConversation') as codex:
            for _ in range(2):
                self.store.action('converse',{'text':'What is a star?'})
                self.store.model_thread.join(timeout=3)
            self.assertEqual(local.call_count,1)
            codex.assert_not_called()
            self.assertEqual(self.store.state['messages'][-1]['provider'],'local')
            self.assertTrue(self.store.state['messages'][-1]['cache_hit'])
    def test_local_failure_never_falls_back_to_subscription(self):
        self.store.integrations_enabled=True
        self.store.state['chat_mode']='local'
        with patch.object(self.store.local,'run',side_effect=ValueError('Local unavailable')),patch('app.CodexConversation') as codex:
            self.store.action('converse',{'text':'Hello there'})
            self.store.model_thread.join(timeout=3)
            codex.assert_not_called()
            self.assertEqual(self.store.state['messages'][-1]['status'],'error')
    def test_language_and_optional_context_persist(self):
        self.store.action('chat',{'text':'Shared-only detail'})
        self.store.action('connection-settings',{'language':'en','speech_language':'en-GB','share_context':False})
        self.assertNotIn('Shared-only detail',self.store.shared_context())
        self.store.save()
        reopened=Store(self.tmp.name)
        self.assertEqual(reopened.state['language'],'en')
        self.assertFalse(reopened.state['share_context'])
        with self.assertRaises(ValueError):reopened.action('connection-settings',{'language':'invalid'})
    def test_command_request_in_chat_creates_approval_without_execution(self):
        self.store.integrations_enabled=True
        with patch('app.subprocess.run') as run:
            self.store.action('converse',{'text':'python sürümünü kontrol et'})
            self.assertEqual(self.store.state['commands'][-1]['status'],'pending')
            run.assert_not_called()
            self.assertIsNone(self.store.state['model_job'])
    def test_restart_never_replays_running_command(self):
        self.store.action('propose', {'command':'python-version'})
        self.store.state['commands'][-1]['status']='running'
        self.store.save()
        self.assertEqual(Store(self.tmp.name).state['commands'][-1]['status'],'interrupted')

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = create_server(cls.tmp.name, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self, method, path, payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port)
        connection.request(method, path, json.dumps(payload) if payload is not None else None, headers or {})
        response = connection.getresponse()
        body=response.read()
        status=response.status
        connection.close()
        return status, body
    def test_static_and_state(self):
        for path in ['/', '/style.css', '/app.js','/api/state','/api/files','/native.js']:
            self.assertEqual(self.request('GET', path)[0],200)
        self.assertEqual(self.request('GET', '/shared/state.json')[0],404)
        self.assertEqual(self.request('GET', '/../../app.py')[0],404)
    def test_origin_token_host_and_roundtrip(self):
        payload={'text':'Gerçek HTTP görevi'}
        url=f'http://127.0.0.1:{self.port}'
        good={'Origin':url,'X-Jarvis-Token':self.server.token,'Content-Type':'application/json'}
        self.assertEqual(self.request('POST','/api/task',payload)[0],403)
        self.assertEqual(self.request('POST','/api/task',payload,dict(good,Origin='https://evil.example'))[0],403)
        self.assertEqual(self.request('POST','/api/task',payload,dict(good,Host='evil.example'))[0],403)
        self.assertEqual(self.request('POST','/api/task',payload,good)[0],200)
        status,body=self.request('GET','/api/state')
        self.assertEqual(json.loads(body)['tasks'][0]['owner'],'FRIDAY')

if __name__ == '__main__':
    unittest.main()

class ConversationIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_chat_scope_and_reopen(self):
        self.store.message('YOU','Private alpha topic')
        task=self.store.action('task',{'text':'Private alpha project'})
        self.store.action('brief',{'text':'Secret alpha brief'})
        self.store.action('new-chat',{})
        self.assertEqual(self.store.client_state()['messages'],[])
        self.assertEqual(self.store.client_state()['tasks'],[])
        self.assertNotIn('alpha',self.store.shared_context())
        self.store.message('YOU','Beta topic')
        self.assertEqual(self.store.state['chats'][0]['title'],'Beta topic')
        self.store.action('select-chat',{'id':'main'})
        self.assertEqual(self.store.state['project_brief'],'Secret alpha brief')
        self.assertNotIn('Beta',self.store.shared_context())
        self.store.save();reopened=Store(self.tmp.name)
        self.assertEqual(len(reopened.state['chats']),2)
        self.assertEqual(reopened.client_state()['tasks'][0]['id'],task['task_id'])
    def test_task_cache_and_packet_do_not_cross_chats(self):
        first=self.store.action('task',{'text':'research alpha','owner':'EDITH'})
        self.store.action('result',{'id':first['task_id'],'text':'Private alpha research'})
        self.store.action('new-chat',{})
        second=self.store.action('task',{'text':'research alpha','owner':'EDITH'})
        self.assertFalse(self.store.state['tasks'][-1]['cache_hit'])
        self.store.save()
        self.assertNotIn('Private alpha research',self.store.packet(self.store.find('tasks',second['task_id'])))
        self.assertNotIn('Private alpha research',self.store.action('chat-packet',{'channel':'EDITH'})['packet'])
    def test_local_context_does_not_cross_chats(self):
        self.store.state['chat_mode']='local'
        self.store.message('YOU','Private alpha context')
        self.store.action('new-chat',{})
        self.store.integrations_enabled=True
        def run(messages,on_delta,cancelled):
            self.assertNotIn('Private alpha context',str(messages));return 'Hello'
        with patch.object(self.store.local,'run',side_effect=run):
            self.store.action('converse',{'text':'Hello','channel':'common'})
            self.store.model_thread.join(3)
        self.assertEqual(self.store.state['messages'][-1]['status'],'done')
    def test_rules_never_claim_unavailable_actions(self):
        with patch.object(self.store.local,'run') as run:
            self.store.action('converse',{'text':'Yarın 9 için hatırlatıcı kur.'})
            self.assertFalse(run.called)
        self.assertIn('gerçekleştiremiyorum',self.store.state['messages'][-1]['text'])
    def test_expired_pending_command_is_not_replayed(self):
        self.store.action('propose',{'command':'python-version'})
        self.store.state['commands'][-1]['expires']=0;self.store.save()
        reopened=Store(self.tmp.name)
        self.assertEqual(reopened.state['commands'][-1]['status'],'expired')
    def test_connected_specialist_routes(self):
        self.assertEqual(self.store.route_engine('hello','EDITH'),'gemini')
        self.assertEqual(self.store.route_engine('review this','VISION'),'claude_google')
        self.assertEqual(self.store.route_engine('write code','FRIDAY'),'codex')

class ParallelChatTests(unittest.TestCase):
    def test_different_providers_run_independently_and_stop_is_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.integrations_enabled=True;store.state['chat_mode']='local'
            local_started=threading.Event();google_started=threading.Event();release=threading.Event()
            def local_run(messages,on_delta,cancelled):
                local_started.set();cancelled.wait(3)
                if cancelled.is_set():raise ValueError('stopped local')
                return 'local answer'
            class FakeGoogle:
                def __init__(self,*args):self.cancelled=args[2]
                def run(self,*args):google_started.set();release.wait(3);return 'Google beta answer'
                def close(self):pass
            with patch.object(store.local,'run',side_effect=local_run),patch('app.GoogleConversation',FakeGoogle):
                store.action('converse',{'text':'Hello alpha'})
                self.assertTrue(local_started.wait(1));alpha_thread=store.model_thread
                beta=store.action('new-chat',{})['chat_id']
                store.action('converse',{'text':'Hello beta','channel':'EDITH'})
                self.assertTrue(google_started.wait(1));beta_thread=store.model_thread
                try:
                    self.assertEqual(len(store.state['model_jobs']),2)
                    self.assertEqual(store.client_state()['model_job']['provider'],'gemini')
                    store.action('select-chat',{'id':'main'})
                    store.action('stop-model',{})
                    alpha_thread.join(2)
                    self.assertEqual(len(store.state['model_jobs']),1)
                    self.assertIsNone(store.client_state()['model_job'])
                    self.assertEqual(store.state['model_jobs'][beta]['provider'],'gemini')
                finally:release.set();beta_thread.join(3);store.cancel_model.set();alpha_thread.join(3)
                self.assertNotIn('Google beta answer',str(store.client_state()['messages']))
                store.action('select-chat',{'id':beta})
                self.assertEqual(store.client_state()['messages'][-1]['text'],'Google beta answer')
    def test_chat_selected_agent_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.action('chat-agent',{'channel':'EDITH'});store.save()
            reopened=Store(tmp)
            self.assertEqual(reopened.state['chats'][0]['agent'],'EDITH')
            with self.assertRaises(ValueError):reopened.action('chat-agent',{'channel':'NO-SUCH-AGENT'})

class TaskExecutionTests(unittest.TestCase):
    def test_model_output_waits_for_review_and_is_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.integrations_enabled=True
            task_id=store.task({'text':'Python selamlama kodu öner','owner':'FRIDAY'})['task_id']
            class FakeCodex:
                def __init__(self,*args):pass
                def run(self,*args):return '```python\nprint("Hello")\n```'
                def close(self):pass
            with patch('app.CodexConversation',FakeCodex):
                store.action('run-task',{'id':task_id});store.model_thread.join(3)
            task=store.find('tasks',task_id)
            self.assertEqual(task['status'],'review')
            self.assertEqual(store.state['active_chat'],task['assistant_chat'])
            self.assertEqual(len(store.client_state()['tasks']),1)
            self.assertIn('print',task['result'])
            store.action('reject-task-output',{'id':task_id})
            self.assertEqual(task['status'],'queued')
            self.assertIn('print',task['past_outputs'][0])
            with patch('app.CodexConversation',FakeCodex):
                store.action('run-task',{'id':task_id});store.model_thread.join(3)
            store.action('confirm-task-output',{'id':task_id})
            self.assertEqual(task['status'],'done')
            self.assertEqual(len(store.state['chats']),2)
    def test_dependency_does_not_start_before_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.integrations_enabled=True
            a=store.task({'text':'Review A','owner':'VISION'})['task_id']
            b=store.task({'text':'Code B','owner':'FRIDAY'})['task_id']
            store.find('tasks',b)['depends_on']=[a]
            with patch.object(store,'launch_model') as model:
                with self.assertRaises(ValueError):store.action('run-task',{'id':b})
                model.assert_not_called()
    def test_duplicate_command_proposal_has_one_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp)
            store.action('propose',{'command':'python-version'})
            duplicate=store.action('propose',{'command':'python-version'})
            self.assertTrue(duplicate['duplicate'])
            self.assertEqual(len(store.state['commands']),1)
            store.action('reject',{'id':duplicate['command_id']})
            self.assertFalse(any(c['status']=='pending' for c in store.state['commands']))

class InstanceOwnershipTests(unittest.TestCase):
    def test_two_backends_cannot_overwrite_one_state_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=create_server(tmp,0)
            try:
                with self.assertRaises(BlockingIOError):create_server(tmp,0)
            finally:first.server_close()
            second=create_server(tmp,0);second.server_close()

class GoogleTelemetryTests(unittest.TestCase):
    def test_official_usage_is_read_without_model_turn(self):
        from providers import read_google_limits
        from unittest.mock import MagicMock
        value={'num_turns':0,'command':{'name':'usage','data':{'groups':[{'buckets':[{'id':'gemini-weekly','remaining_fraction':.95,'reset_time':'2026-11-09T14:00:00Z'},{'id':'3p-weekly','remaining_fraction':.98,'reset_time':'2026-11-09T14:00:00Z'}]}]}}}
        process=MagicMock();process.communicate.return_value=(json.dumps(value),None);process.returncode=0;process.poll.return_value=0
        with patch('google_chat.binary',return_value='/fake/agy'),patch('providers.subprocess.Popen',return_value=process) as popen,patch.dict('os.environ',{'GOOGLE_API_KEY':'must-not-pass'}):
            data=read_google_limits()
        self.assertAlmostEqual(data['EDITH']['primary']['used_percent'],5)
        self.assertAlmostEqual(data['VISION']['primary']['used_percent'],2)
        self.assertNotIn('GOOGLE_API_KEY',popen.call_args.kwargs['env'])
        self.assertEqual(popen.call_args.args[0][-1],'/usage')
        args=popen.call_args.args[0]
        self.assertFalse(json.loads(args[args.index('--settings')+1])['useG1Credits'])
        value['num_turns']=1;process.communicate.return_value=(json.dumps(value),None)
        with patch('google_chat.binary',return_value='/fake/agy'),patch('providers.subprocess.Popen',return_value=process):
            with self.assertRaises(ValueError):read_google_limits()

class BillingAndRoomGuardTests(unittest.TestCase):
    def test_exhausted_google_quota_does_not_launch_or_create_empty_room(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.integrations_enabled=True
            task=store.task({'text':'A concise proposal','owner':'EDITH'})['task_id']
            store.state['provider_usage']['EDITH']={'status':'live','primary':{'used_percent':100}}
            with patch('app.GoogleConversation') as google:
                with self.assertRaises(ValueError):store.action('run-task',{'id':task})
                google.assert_not_called()
            self.assertEqual(store.state['active_chat'],'main')
            self.assertEqual(len(store.state['chats']),1)
            self.assertEqual(store.find('tasks',task)['status'],'queued')
    def test_late_message_cannot_land_in_another_room(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=create_server(tmp,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            origin='http://127.0.0.1:'+str(server.server_port)
            try:
                server.store.action('new-chat',{})
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                body=json.dumps({'chat_id':'main','text':'Should stay private'})
                connection.request('POST','/api/converse',body,{'Origin':origin,'X-Jarvis-Token':server.token,'Content-Type':'application/json'})
                response=connection.getresponse();response.read();connection.close()
                self.assertEqual(response.status,400)
                self.assertFalse(any('Should stay private' in m['text'] for m in server.store.state['messages']))
            finally:server.shutdown();server.server_close();thread.join(2)

class ChatManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_archive_and_restore_preserves_messages(self):
        store=self.store;old=store.state['active_chat'];store.message('YOU','Keep this')
        store.action('archive-chat',{'id':old})
        self.assertNotEqual(store.state['active_chat'],old)
        self.assertTrue(next(c for c in store.state['chats'] if c['id']==old)['archived'])
        store.action('restore-chat',{'id':old});store.action('select-chat',{'id':old})
        self.assertTrue(any(m['text']=='Keep this' for m in store.client_state()['messages']))
    def test_delete_removes_only_target_and_creates_backup(self):
        store=self.store;old=store.state['active_chat'];store.message('YOU','Remove me');store.action('new-chat',{})
        current=store.state['active_chat'];store.message('YOU','Keep me');store.action('delete-chat',{'id':old})
        self.assertEqual(store.state['active_chat'],current)
        self.assertTrue((Path(self.tmp.name)/'backups'/('deleted-chat-'+old+'.json')).exists())
        self.assertFalse(any(m['text']=='Remove me' for m in store.state['messages']))
        self.assertTrue(any(m['text']=='Keep me' for m in store.state['messages']))
    def test_agent_connector_color_and_common_exclusion(self):
        store=self.store;store.action('add-agent',{'name':'TEST_AGENT','provider':'Local','role':'Helper','connector':'local','color':'#ffaacc'})
        self.assertEqual(store.route_engine('Hello','TEST_AGENT'),'local')
        store.action('update-agent',{'name':'FRIDAY','in_common':False})
        self.assertNotEqual(store.route_engine('write python code','common'),'codex') if store.state['google_status']['verified'] else None
        store.action('update-agent',{'name':'TEST_AGENT','enabled':False})
        with self.assertRaises(ValueError):store.route_engine('Hello','TEST_AGENT')
        store.action('delete-agent',{'name':'TEST_AGENT'});self.assertNotIn('TEST_AGENT',store.agent_names)
    def test_free_quota_error_never_retries_a_paid_model(self):
        import free_chat,urllib.error
        from unittest.mock import MagicMock
        opener=MagicMock();opener.open.side_effect=urllib.error.HTTPError('https://openrouter.ai/api/v1/chat/completions',429,'quota',{},None)
        with patch.object(free_chat,'key',return_value='dummy-test-key'),patch.object(free_chat.urllib.request,'build_opener',return_value=opener):
            with self.assertRaises(ValueError):free_chat.FreeConversation(lambda text:None,threading.Event()).run('Test')
        self.assertEqual(opener.open.call_count,1)
        sent=json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(sent['model'],'openrouter/free')
        self.assertEqual(sent['provider']['max_price'],{'prompt':0,'completion':0})
        self.assertNotIn('models',sent)

class ModelSettingsAndTitlesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_title_evolves_without_model_and_manual_name_is_preserved(self):
        store=self.store;chat=store.state['active_chat']
        store.message('YOU','Merhaba')
        store.message('YOU','Mac uygulaması için ses motorunu geliştirelim')
        self.assertIn('ses motorunu',next(c for c in store.state['chats'] if c['id']==chat)['title'])
        store.action('rename-chat',{'id':chat,'title':'Benim projem'})
        store.message('YOU','Başka bir proje tasarımı hakkında konuşalım')
        self.assertEqual(next(c for c in store.state['chats'] if c['id']==chat)['title'],'Benim projem')
        store.action('auto-title',{'id':chat})
        self.assertNotEqual(next(c for c in store.state['chats'] if c['id']==chat)['title'],'Benim projem')
    def test_configured_agent_model_reaches_google_transport(self):
        store=self.store;store.integrations_enabled=True;captured=[]
        class FakeGoogle:
            def __init__(self,cwd,delta,cancelled,model):captured.append(model);self.delta=delta
            def run(self,prompt,image=None):return 'HAZIR'
            def close(self):pass
        store.action('update-agent',{'name':'EDITH','model':'gemini-3.8-flash-high'})
        store.action('connection-settings',{'jarvis_agent':'EDITH'})
        with patch('app.GoogleConversation',FakeGoogle):
            store.action('converse',{'text':'Kısa bir açıklama rica ediyorum','channel':'common'});store.model_thread.join(3)
        self.assertEqual(captured,['gemini-3.8-flash-high'])
        self.assertEqual(store.state['messages'][-1]['provider'],'gemini')
        self.assertIn('gemini-3.8-flash-high',store.state['messages'][-1]['model'])
    def test_paid_free_model_and_unknown_model_are_rejected(self):
        store=self.store
        with self.assertRaises(ValueError):store.action('update-agent',{'name':'EDITH','model':'invented-model'})
        free=next(a for a in store.state['agents'] if a['connector']=='openrouter')
        with self.assertRaises(ValueError):store.action('update-agent',{'name':free['name'],'model':'openai/paid-model'})
        self.assertFalse(free['in_common'])
    def test_connection_inventory_is_local_and_consistent(self):
        with patch.object(self.store,'launch_model') as model:
            self.store.action('converse',{'text':'Jarvis sen hangi ailara bağlandın neler yapabiliyorsun','channel':'common'})
        self.assertIn('FRIDAY',self.store.state['messages'][-1]['text'])
        self.assertIn('VISION',self.store.state['messages'][-1]['text'])
        model.assert_not_called()

class ProjectToolsTests(unittest.TestCase):
    def setUp(self):
        from project_bridge import ProjectBridge
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'project';self.root.mkdir();self.cancelled=threading.Event()
        self.bridge=ProjectBridge(self.root,Path(self.tmp.name)/'backups',lambda kind,payload:False,lambda *args:None,self.cancelled)
    def tearDown(self):self.tmp.cleanup()
    def test_outside_paths_and_secret_files_are_refused(self):
        for path in ('../secret.txt','/etc/passwd','.env','nested/.env.local'):
            with self.assertRaises(ValueError):self.bridge.invoke({'tool':'project_read','arguments':{'path':path}})
    def test_declined_edit_never_writes_and_approved_edit_has_backup(self):
        target=self.root/'hello.txt';target.write_text('before')
        args={'tool':'project_edit','arguments':{'path':'hello.txt','content':'after','reason':'Test'}}
        self.assertFalse(self.bridge.invoke(args)['saved']);self.assertEqual(target.read_text(),'before')
        self.bridge.approve=lambda *args:True
        self.assertTrue(self.bridge.invoke(args)['saved']);self.assertEqual(target.read_text(),'after')
        self.assertTrue(list((Path(self.tmp.name)/'backups').glob('agent-edit-*.json')))
    def test_concurrent_file_change_is_not_overwritten(self):
        target=self.root/'hello.txt';target.write_text('before')
        def approve(*args):target.write_text('someone else');return True
        self.bridge.approve=approve
        with self.assertRaises(ValueError):self.bridge.invoke({'tool':'project_edit','arguments':{'path':'hello.txt','content':'after','reason':'Test'}})
        self.assertEqual(target.read_text(),'someone else')
    def test_commands_require_approval_and_use_workspace_network_restriction(self):
        from unittest.mock import MagicMock
        self.bridge.client=MagicMock();args={'tool':'project_command','arguments':{'argv':['python3','-c','print(123)'],'reason':'Test'}}
        self.assertFalse(self.bridge.invoke(args)['ran']);self.bridge.client.rpc.assert_not_called()
        self.bridge.approve=lambda *args:True;self.bridge.client.rpc.return_value={'exitCode':0,'stdout':'123'}
        self.assertTrue(self.bridge.invoke(args)['ran'])
        params=self.bridge.client.rpc.call_args.args[1]
        self.assertEqual(params['cwd'],str(self.root.resolve()));self.assertFalse(params['sandboxPolicy']['networkAccess'])
        self.assertEqual(params['sandboxPolicy']['writableRoots'],[str(self.root.resolve())])


class PermissionAndContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_read_only_permission_stops_project_mode(self):
        self.store.action('project-context',{'name':'test','path':self.tmp.name})
        self.store.action('project-work',{'enabled':True})
        self.store.action('project-permission',{'mode':'read_only'})
        chat=next(c for c in self.store.state['chats'] if c['id']==self.store.state['active_chat'])
        self.assertFalse(chat['project_work'])
        with self.assertRaises(ValueError):self.store.action('project-work',{'enabled':True})
    def test_manual_agent_can_become_real_connector(self):
        self.store.action('add-agent',{'name':'CUSTOM','provider':'manual','connector':'manual','role':'Helper'})
        self.store.action('update-agent',{'name':'CUSTOM','connector':'gemini','model':'gemini-3.8-flash-medium'})
        self.assertEqual(self.store.route_engine('Hello','CUSTOM'),'gemini')
        self.assertEqual(self.store.selected_model('gemini','CUSTOM'),'gemini-3.8-flash-medium')
    def test_disabled_history_is_not_sent_to_google(self):
        self.store.integrations_enabled=True;captured=[]
        self.store.message('YOU','UNSHARED_PRIVATE_CONTEXT')
        self.store.action('connection-settings',{'share_context':False,'jarvis_agent':'EDITH'})
        class FakeGoogle:
            def __init__(self,*args):pass
            def run(self,prompt,image=None):captured.append(prompt);return 'Cevap'
            def close(self):pass
        with patch('app.GoogleConversation',FakeGoogle):
            self.store.action('converse',{'text':'Sadece bu soruyu cevapla','channel':'common'});self.store.model_thread.join(3)
        self.assertNotIn('UNSHARED_PRIVATE_CONTEXT',captured[0])

class TeamIsolationTests(unittest.TestCase):
    def test_explicit_team_uses_only_goal_and_task_outputs(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);store.integrations_enabled=True;store.message('YOU','PRIVATE_OLD_CHAT_CANARY');captured=[]
            class Fake:
                def __init__(self,*args,**kwargs):pass
                def run(self,prompt,image=None):captured.append(prompt);return 'Göreve ait kısa sonuç'
                def close(self):pass
            with patch('app.CodexConversation',Fake),patch('app.GoogleConversation',Fake):
                store.action('team-start',{'text':'Basit not uygulamasının tasarımını ve örnek kodunu hazırla'})
                deadline=time.monotonic()+4
                while store.state['teams'][0]['status']=='working' and time.monotonic()<deadline:time.sleep(.02)
            store.team_threads[store.state['teams'][0]['id']].join(4)
            self.assertEqual(store.state['teams'][0]['status'],'review')
            self.assertEqual(len(captured),3)
            self.assertTrue(all('PRIVATE_OLD_CHAT_CANARY' not in prompt for prompt in captured))
            self.assertEqual(store.state['messages'][-1]['author'],'JARVIS')
            self.assertIn('Birleşik ekip raporu',store.state['messages'][-1]['text'])

class BudgetPlanTests(unittest.TestCase):
    def test_jarvis_brain_is_independent_of_worker_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-low'})
            s.action('update-agent',{'name':'EDITH','enabled':False,'model':'gemini-3.8-flash-high'})
            self.assertEqual(s.route_engine('write code','common'),'gemini')
            self.assertEqual(s.selected_model('gemini','common'),'gemini-3.8-flash-low')
            self.assertEqual(s.route_engine('hi','FRIDAY'),'codex')
    def test_plan_is_validated_and_does_not_start_workers(self):
        from team_runner import parse_plan,save_plan
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);item={}
            answer=json.dumps({'summary':'Tek geliştirici yeterli','steps':[{'owner':'FRIDAY','kind':'build','instruction':'Bir sayaç fonksiyonu yaz.'}]})
            save_plan(s,item,answer,s.state['active_chat'],'Sayaç geliştir')
            self.assertEqual(len(s.state['chats'][0]['pending_team_plan']['steps']),1)
            self.assertEqual(s.state['model_jobs'],{})
            self.assertEqual(s.state['tasks'],[])
            for bad in [answer.replace('FRIDAY','UNKNOWN'),json.dumps({'summary':'bad','steps':[{'owner':'FRIDAY','kind':'shell','instruction':'do it'}]}),json.dumps({'summary':'bad','steps':[{'owner':'FRIDAY','kind':'build','instruction':'one'}]*2})]:
                with self.assertRaises(ValueError):parse_plan(bad,s.state['agents'])
    def test_plan_uses_one_coordinator_call_and_waits_for_review(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.integrations_enabled=True
            s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-low'})
            captured=[]
            class FakeGoogle:
                def __init__(self,*args):captured.append(args[-1])
                def run(self,*args):return json.dumps({'summary':'Araştırma yeterli','steps':[{'owner':'EDITH','kind':'design','instruction':'Verilen seçenekleri karşılaştır.'}]})
                def close(self):pass
            with patch('app.GoogleConversation',FakeGoogle),patch('app.CodexConversation') as codex:
                s.action('team-plan',{'text':'Seçenekleri karşılaştır'});s.model_thread.join(3)
                self.assertEqual(captured,['gemini-3.8-flash-low']);codex.assert_not_called()
            self.assertEqual(s.state['messages'][-1]['status'],'done')
            self.assertEqual(s.state['tasks'],[])
            self.assertTrue(s.state['messages'][-1]['team_plan_id'])

class ClaudeConnectorTests(unittest.TestCase):
    def test_subscription_only_environment_and_no_call_before_signin(self):
        import os
        from claude_chat import environment,ClaudeConversation
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test-secret','CLAUDE_CODE_OAUTH_TOKEN':'test-secret','KEEP_TEST':'yes'}):
            env=environment();self.assertNotIn('ANTHROPIC_API_KEY',env);self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN',env);self.assertEqual(env['KEEP_TEST'],'yes')
        with patch('claude_chat.status',return_value={'signed_in':False}),patch('claude_chat.subprocess.Popen') as spawn:
            c=ClaudeConversation('.',lambda _:None,threading.Event())
            with self.assertRaises(ValueError):c.run('hello')
            spawn.assert_not_called()
    def test_claude_model_and_project_tools_catalog(self):
        from claude_project_mcp import process
        tools=process({'method':'tools/list'})['tools']
        self.assertEqual({t['name'] for t in tools},{'project_list','project_read','project_edit'})
        with self.assertRaises(ValueError):process({'method':'tools/call','params':{'name':'project_command'}})
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.action('update-agent',{'name':'VISION','connector':'claude_code','model':'sonnet'})
            self.assertEqual(s.route_engine('write code','VISION'),'claude_code')
            self.assertEqual(s.selected_model('claude_code','VISION'),'sonnet')
    def test_claude_tool_endpoint_is_session_scoped(self):
        from project_bridge import ProjectBridge
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';root.mkdir();(root/'hello.txt').write_text('hello')
            server=create_server(Path(tmp)/'state',0,False)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            server.store.tool_sessions['test-session']=ProjectBridge(root,Path(tmp)/'backup',lambda *args:False,lambda *args:None,threading.Event())
            def request(token,tool,args={}):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port)
                c.request('POST','/claude-tool',json.dumps({'tool':tool,'arguments':args}),{'Content-Type':'application/json','X-Jarvis-Project-Token':token});r=c.getresponse();value=json.loads(r.read());c.close();return r.status,value
            try:
                self.assertEqual(request('wrong','project_list')[0],403)
                self.assertEqual(request('test-session','project_read',{'path':'hello.txt'})[1]['text'],'hello')
                self.assertEqual(request('test-session','project_read',{'path':'../outside'})[0],400)
                self.assertEqual(request('test-session','project_command')[0],400)
                server.store.tool_sessions.clear();self.assertEqual(request('test-session','project_list')[0],403)
            finally:server.store.shutdown.set();server.shutdown();server.server_close();thread.join(2)

class ContextBudgetTests(unittest.TestCase):
    def test_independent_question_omits_irrelevant_history_and_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.message('YOU','Secret unrelated submarine design CANARY-731')
            s.state['project_brief']='Unrelated confidential project notes'
            context=s.shared_context('Kediler neden mırlar?')
            self.assertNotIn('CANARY-731',context);self.assertNotIn('confidential',context)
            self.assertEqual(s.relevant_chat('Kediler neden mırlar?'),[])
    def test_followup_keeps_local_context_without_cross_agent_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.message('YOU','Design a green button','FRIDAY');s.message('FRIDAY','Use emerald','FRIDAY')
            s.message('YOU','Private other-agent canary','EDITH')
            self.assertIn('green',str(s.relevant_chat('Make this larger','FRIDAY')))
            self.assertNotIn('canary',str(s.relevant_chat('Make this larger','FRIDAY')))

class DesktopSessionTests(unittest.TestCase):
    def test_no_session_no_actions_and_no_parallel_owner(self):
        from desktop_bridge import DesktopBridge
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);called=[];bridge=DesktopBridge(s,'main','VISION',lambda *a:called.append(a),lambda *a:None,threading.Event())
            with self.assertRaises(ValueError):bridge.invoke({'tool':'desktop_click','arguments':{'x':1,'y':2}})
            self.assertEqual(called,[]);self.assertEqual(s.native_requests,{})
            s.desktop_session={'owner':'FRIDAY','chat_id':'main','expires':time.time()+60}
            with self.assertRaises(ValueError):bridge.invoke({'tool':'desktop_observe'})
    def test_observation_response_is_ephemeral_and_stop_revokes(self):
        from desktop_bridge import DesktopBridge
        import time
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.desktop_session={'owner':'VISION','chat_id':'main','expires':time.time()+60};bridge=DesktopBridge(s,'main','VISION',lambda *a:True,lambda *a:None,threading.Event());answers=[]
            t=threading.Thread(target=lambda:answers.append(bridge.invoke({'tool':'desktop_observe'})));t.start()
            deadline=time.time()+2
            while not s.native_requests and time.time()<deadline:threading.Event().wait(.01)
            request=next(iter(s.native_requests));s.action('desktop-result',{'id':request,'result':{'image':'data:image/jpeg;base64,test','width':100,'height':100}});t.join(2)
            self.assertTrue(answers[0]['image']);self.assertEqual(s.native_requests,{})
            s.save();self.assertNotIn('base64,test',s.path.read_text())
            s.action('desktop-stop',{})
            with self.assertRaises(ValueError):bridge.invoke({'tool':'desktop_click','arguments':{'x':1,'y':2}})
    def test_actions_require_fresh_observation_and_valid_arguments(self):
        from desktop_bridge import DesktopBridge
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.desktop_session={'owner':'VISION','chat_id':'main','expires':time.time()+60,'auto_actions':True};bridge=DesktopBridge(s,'main','VISION',lambda *a:True,lambda *a:None,threading.Event())
            for tool,args in [('desktop_click',{'x':float('nan'),'y':2}),('desktop_key',{'key':'cmd+space'}),('desktop_open_url',{'url':'file:///etc/passwd'}),('desktop_type',{'text':'hi'})]:
                with self.assertRaises(ValueError):bridge.invoke({'tool':tool,'arguments':args})
    def test_small_question_does_not_plan_team(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            for question in ['Kediler neden mırlar?','Python nedir?','Nasıl site yapılır?','What is a compiler?']:
                self.assertFalse(s.is_execution_request(question))
            self.assertTrue(s.is_execution_request('Bir not uygulaması yapalım'))

class InterruptedHandoffTests(unittest.TestCase):
    def test_handoff_is_explicit_and_contains_only_selected_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.message('YOU','UNRELATED_PRIVATE_CANARY','EDITH');s.message('YOU','Write a counter function','FRIDAY');s.message('FRIDAY','Quota exhausted','FRIDAY');item=s.state['messages'][-1];item.update(status='error',model='test',provider='codex')
            with patch.object(s,'launch_model',return_value={'model_started':True}) as launch:
                s.action('continue-with-agent',{'message_id':item['id'],'owner':'VISION'})
                self.assertIn('counter function',launch.call_args.args[0]);self.assertNotIn('CANARY',launch.call_args.args[0]);self.assertNotIn('Quota exhausted',launch.call_args.args[0]);self.assertEqual(launch.call_args.args[1],'VISION')
            item['status']='done'
            with self.assertRaises(ValueError):s.action('continue-with-agent',{'message_id':item['id'],'owner':'VISION'})

class CostDefaultsTests(unittest.TestCase):
    def test_escalation_helper_is_conservative(self):
        from model_catalog import escalate_model,cheapest_flash
        offered={'gemini-3.8-flash-low','gemini-3.8-flash-medium','gemini-3.8-flash-high'}
        self.assertEqual(escalate_model('gemini-3.8-flash-low',offered,web_research=True),'gemini-3.8-flash-medium')
        self.assertEqual(escalate_model('gemini-3.8-flash-low',offered),'gemini-3.8-flash-low')
        self.assertEqual(escalate_model('gemini-3.8-flash-low',offered,planning=False,web_research=False),'gemini-3.8-flash-low')
        self.assertEqual(escalate_model('gemini-3.8-flash-low',{'gemini-3.8-flash-low'},web_research=True),'gemini-3.8-flash-low')
        self.assertEqual(escalate_model('gemini-3.8-flash-high',offered,web_research=True),'gemini-3.8-flash-high')
        self.assertEqual(escalate_model('gpt-oss-120b-medium',offered,web_research=True),'gpt-oss-120b-medium')
        self.assertEqual(escalate_model('',offered,web_research=True),'')
        self.assertEqual(cheapest_flash('gemini-3.8-flash-high'),'gemini-3.8-flash-low')
        self.assertEqual(cheapest_flash('gemini-3.8-flash-medium'),'gemini-3.8-flash-low')
        self.assertEqual(cheapest_flash('claude-sonnet-4-6'),'claude-sonnet-4-6')
        self.assertEqual(cheapest_flash(''),'')
    def test_one_time_migration_lowers_saved_flash_tier_but_respects_later_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            s.state['jarvis_model']='gemini-3.8-flash-high'
            edith=next(a for a in s.state['agents'] if a['name']=='EDITH');edith.update(model='gemini-3.8-flash-high',effort='high')
            s.state.pop('cost_defaults_v071');s.save()
            second=Store(tmp)
            self.assertEqual(second.state['jarvis_model'],'gemini-3.8-flash-low')
            edith=next(a for a in second.state['agents'] if a['name']=='EDITH')
            self.assertEqual((edith['model'],edith['effort']),('gemini-3.8-flash-low','low'))
            self.assertTrue(second.state['cost_defaults_v071'])
            second.state['jarvis_model']='gemini-3.8-flash-high';second.save()
            self.assertEqual(Store(tmp).state['jarvis_model'],'gemini-3.8-flash-high')
    def test_version_bump_keeps_existing_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);chats=[c['id'] for c in s.state['chats']];s.save()
            again=Store(tmp)
            self.assertEqual(again.state['version'],'0.7.4')
            self.assertEqual([c['id'] for c in again.state['chats']],chats)
    def test_live_research_steps_up_once_and_plain_chat_stays_cheap(self):
        from unittest.mock import patch
        for research,expected in ((False,'gemini-3.8-flash-low'),(True,'gemini-3.8-flash-medium')):
            with tempfile.TemporaryDirectory() as tmp:
                s=Store(tmp);s.integrations_enabled=True
                s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-low'})
                captured=[]
                class FakeGoogle:
                    def __init__(self,*args):captured.append(args[-1])
                    def run(self,*args):return 'tamam'
                    def close(self):pass
                with patch('app.GoogleConversation',FakeGoogle):
                    s.launch_model('Kısa bir konuyu özetle','common',web_research=research);s.model_thread.join(3)
                self.assertEqual(captured,[expected])
    def test_auto_effort_can_be_switched_off(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.integrations_enabled=True;s.state['auto_effort']=False
            s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-low'})
            captured=[]
            class FakeGoogle:
                def __init__(self,*args):captured.append(args[-1])
                def run(self,*args):return 'tamam'
                def close(self):pass
            with patch('app.GoogleConversation',FakeGoogle):
                s.launch_model('Kısa bir konuyu özetle','common',web_research=True);s.model_thread.join(3)
            self.assertEqual(captured,['gemini-3.8-flash-low'])

class RobustnessTests(unittest.TestCase):
    def test_missing_or_hung_keychain_means_no_key_not_a_crash(self):
        import subprocess
        from unittest.mock import patch
        import free_chat
        for failure in (FileNotFoundError('security'),subprocess.TimeoutExpired('security',8)):
            with patch('free_chat.subprocess.run',side_effect=failure):
                self.assertEqual(free_chat.key(),'');self.assertFalse(free_chat.has_key())
    def test_unexpected_errors_are_logged_and_log_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            try:raise RuntimeError('canary-failure')
            except RuntimeError:s.log_error('/api/test')
            log=Path(tmp)/'server-errors.log'
            self.assertIn('canary-failure',log.read_text());self.assertIn('/api/test',log.read_text())
            log.write_text('x'*250000);s.log_error('/api/again')
            self.assertLess(log.stat().st_size,150000)

class ClaudeStatusRefreshTests(unittest.TestCase):
    def test_signed_in_state_is_read_in_background_after_restart(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.integrations_enabled=True
            self.assertFalse(s.state['claude_status']['signed_in'])
            with patch('claude_chat.status',return_value={'installed':True,'signed_in':True,'plan':'pro'}):
                s.action('connection-status',{})
                deadline=time.monotonic()+3
                while s.claude_status_busy and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(s.state['claude_status']['signed_in']);self.assertIn('checked_at',s.state['claude_status'])
    def test_status_is_not_polled_again_within_ten_minutes_and_not_when_integrations_off(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            with patch.object(s,'refresh_claude_status') as refresh:
                s.action('connection-status',{});refresh.assert_not_called()
                s.integrations_enabled=True;s.state['claude_status']['checked_at']=time.time()
                s.action('connection-status',{});refresh.assert_not_called()
                s.state['claude_status']['checked_at']=time.time()-700
                s.action('connection-status',{});refresh.assert_called_once()


class TeamCallHelpers:
    def make(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        s=Store(tmp.name);s.integrations_enabled=True
        s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-low'})
        return s
    def settle(self,s,timeout=6):
        end=time.time()+timeout;stable=0
        while time.time()<end:
            busy=bool(s.state['model_jobs']) or any(m.get('status')=='streaming' for m in s.state['messages'])
            stable=0 if busy else stable+1
            if stable>=8:return
            time.sleep(.05)
        self.fail('model jobs did not settle')
    def fakes(self,google_replies,codex_replies=()):
        calls=[]
        google=list(google_replies);codex=list(codex_replies)
        class FakeGoogle:
            def __init__(self,directory,on_delta,cancelled,model=''):self.model=model
            def run(self,prompt,image=None):
                calls.append(('google',self.model,prompt));return google.pop(0) if google else 'Tamam.'
            def close(self):pass
        self.efforts=[]
        efforts=self.efforts
        class FakeCodex:
            def __init__(self,directory,on_delta,cancelled,project_tools=False):pass
            def run(self,prompt,image=None):
                calls.append(('codex','',prompt));efforts.append(getattr(self,'effort',None));return codex.pop(0) if codex else 'Tamam.'
            def close(self):pass
        return calls,patch('app.GoogleConversation',FakeGoogle),patch('app.CodexConversation',FakeCodex)
    def shared(self,s):return [m for m in s.state['messages'] if m.get('channel','common')=='common']

class TeamCallTests(TeamCallHelpers,unittest.TestCase):
    """JARVIS and Berke can call agents into the same chat; they see the chat and may hand work on (capped)."""
    def test_named_agent_answers_in_the_same_chat_and_sees_it(self):
        s=self.make()
        s.message('YOU','Önce şu fikri konuşalım: mavi bahçe');s.message('JARVIS','Fikir güzel: mavi bahçe');s.state['messages'][-1]['model']='x'
        calls,g,c=self.fakes(['EDITH yanıtı'])
        with g,c:
            s.action('converse',{'text':'EDITH’i çağır, bir şey eklesin','channel':'common'});self.settle(s)
        last=self.shared(s)[-1]
        self.assertEqual((last['author'],last['status'],last['text'],last['chat_id']),('EDITH','done','EDITH yanıtı',s.state['active_chat']))
        self.assertEqual(sum(m['text'].startswith('EDITH’i çağır') for m in self.shared(s)),1)
        self.assertEqual(len(calls),1);self.assertIn('mavi bahçe',calls[0][2]);self.assertIn('EDITH',calls[0][2]);self.assertNotIn('You are the JARVIS persona',calls[0][2])

    def test_bare_mentions_and_negations_are_not_calls(self):
        s=self.make()
        for text in ('EDITH nedir?','Bana EDITH hakkında bilgi ver','EDITH’i çağırma','Do not call FRIDAY','FRIDAY çok iyi bir isim'):
            self.assertEqual(s.parse_agent_calls(text),[],text)
        self.assertEqual(s.parse_agent_calls('FRIDAY’e sor'),['FRIDAY'])
        self.assertEqual(s.parse_agent_calls('call edith please'),['EDITH'])
        self.assertEqual(s.parse_agent_calls('@EDITH ve @FRIDAY bakın'),['EDITH','FRIDAY'])
        self.assertEqual(s.parse_agent_calls('FRIDAY, bunu yap'),['FRIDAY'])
        self.assertTrue(set(s.parse_agent_calls('ekibi çağır')))
        s.state['agents'][[a['name'] for a in s.state['agents']].index('EDITH')]['enabled']=False
        self.assertEqual(s.parse_agent_calls('EDITH’i çağır'),[])

    def test_two_named_agents_answer_in_order_and_second_sees_first(self):
        s=self.make()
        calls,g,c=self.fakes(['EDITH araştırdı'],['FRIDAY kodu yazdı'])
        with g,c:
            s.action('converse',{'text':'FRIDAY ve EDITH’i çağır, birlikte bir fikir üretin','channel':'common'});self.settle(s)
        rows=[m for m in self.shared(s) if m.get('model')]
        self.assertEqual([m['author'] for m in rows],['FRIDAY','EDITH'])
        self.assertEqual([c_[0] for c_ in calls],['codex','google'])
        self.assertIn('FRIDAY kodu yazdı',calls[1][2])
        self.assertEqual(sum(m['author']=='YOU' for m in s.state['messages']),1)

    def test_autonomous_handoff_is_followed_stripped_and_capped(self):
        s=self.make()
        calls,g,c=self.fakes(['İlk yanıt\nHANDOFF: FRIDAY: Kaynakları ara','Gözden geçirdim\nHANDOFF: FRIDAY: tekrar'],['Kaynaklar bulundu\nHANDOFF: EDITH: gözden geçir'])
        with g,c:
            s.action('converse',{'text':'Bu konuda güncel bilgiye ihtiyacım var, araştırıp kısa özet çıkar','channel':'common'});self.settle(s)
        rows=[m for m in self.shared(s) if m.get('model')]
        self.assertEqual([m['author'] for m in rows],['JARVIS','FRIDAY','EDITH'])
        self.assertTrue(all('HANDOFF:' not in m['text'] for m in rows))
        self.assertIn('Paslama → FRIDAY',rows[0]['text']);self.assertIn('Paslama → EDITH',rows[1]['text']);self.assertNotIn('Paslama',rows[2]['text'])
        self.assertEqual(len(calls),3)
        self.assertIn('HANDOFF: NAME',calls[0][2]);self.assertIn('İlk yanıt',calls[1][2]);self.assertIn('TASK HANDED OVER',calls[1][2]);self.assertNotIn('HANDOFF: NAME',calls[2][2])

    def test_handoff_difficulty_sets_the_called_agents_effort(self):
        s=self.make()
        calls,g,c=self.fakes(['Tamam\nHANDOFF: FRIDAY/high: Zor bir iş'],['Bitti'])
        with g,c:
            s.action('converse',{'text':'Bu konuda uzun bir değerlendirme yapar mısın lütfen','channel':'common'});self.settle(s)
        self.assertEqual(self.efforts,['high'])
        rows=[m for m in self.shared(s) if m.get('model')]
        self.assertIn('Paslama → FRIDAY (high)',rows[0]['text']);self.assertIn('effort high',rows[1]['model'])
        s=self.make()
        calls,g,c=self.fakes(['Tamam\nHANDOFF: EDITH/high: Zor bir araştırma','EDITH yanıtı'])
        with g,c:
            s.action('converse',{'text':'Bu konuda uzun bir değerlendirme yapar mısın lütfen','channel':'common'});self.settle(s)
        self.assertEqual(calls[1][1],'gemini-3.8-flash-high')
        s=self.make()
        calls,g,c=self.fakes(['Tamam\nHANDOFF: FRIDAY: Rating yok'],['Bitti'])
        with g,c:
            s.action('converse',{'text':'Bu konuda uzun bir değerlendirme yapar mısın lütfen','channel':'common'});self.settle(s)
        self.assertEqual(self.efforts,[None])

    def test_plan_steps_carry_valid_effort_only(self):
        from team_runner import parse_plan
        agents=[{'name':'FRIDAY','connector':'codex'},{'name':'EDITH','connector':'gemini'}]
        plan=parse_plan('{"summary":"x","steps":[{"owner":"FRIDAY","kind":"build","effort":"high","instruction":"a"},{"owner":"EDITH","kind":"research","effort":"extreme","instruction":"b"}]}',agents)
        self.assertEqual(plan['steps'][0]['effort'],'high');self.assertNotIn('effort',plan['steps'][1])

    def test_auto_handoff_off_unknown_and_self_targets_do_nothing(self):
        for setup,reply in ((lambda s:s.state.update(auto_handoff=False),'Bitti\nHANDOFF: FRIDAY: yap'),(lambda s:None,'Bitti\nHANDOFF: GHOST: yap'),(lambda s:None,'Bitti\nHANDOFF: JARVIS: yap')):
            s=self.make();setup(s)
            calls,g,c=self.fakes([reply])
            with g,c:
                s.action('converse',{'text':'Bu konuda uzun bir değerlendirme yapar mısın lütfen','channel':'common'});self.settle(s)
            rows=[m for m in self.shared(s) if m.get('model')]
            self.assertEqual((len(calls),len(rows),rows[0]['text']),(1,1,'Bitti'))

    def test_followup_is_skipped_with_a_note_when_the_chat_changed(self):
        s=self.make();calls=[]
        origin=s.state['active_chat']
        class FakeGoogle:
            def __init__(self,directory,on_delta,cancelled,model=''):pass
            def run(self,prompt,image=None):
                s.action('new-chat',{});return 'Bitti\nHANDOFF: FRIDAY: yap'
            def close(self):pass
        with patch('app.GoogleConversation',FakeGoogle),patch('app.CodexConversation') as codex:
            s.launch_model('Bu konuda uzun bir değerlendirme yapar mısın lütfen','common')
            s.model_thread.join(5);self.settle(s)
            codex.assert_not_called()
        notes=[m for m in s.state['messages'] if m['chat_id']==origin and m['text'].startswith('Paslama yapılmadı')]
        self.assertEqual(len(notes),1)

    def test_calls_need_live_chat(self):
        s=self.make();s.integrations_enabled=False
        calls,g,c=self.fakes(['x'])
        with g,c:
            s.action('converse',{'text':'EDITH’i çağır','channel':'common'})
        self.assertEqual(calls,[])

    def test_coordinator_tier_helper(self):
        from model_catalog import coordinator_tier,with_tier
        offered={'gemini-3.8-flash-low','gemini-3.8-flash-medium','gemini-3.8-flash-high'}
        self.assertEqual(coordinator_tier('Selam'),'low')
        self.assertEqual(coordinator_tier('Bu iki yaklaşımı karşılaştırır mısın?'),'medium')
        self.assertEqual(coordinator_tier('x '*200),'high')
        self.assertEqual(coordinator_tier('Selam',planning=True),'high')
        self.assertEqual(coordinator_tier('Selam',delegation=True),'high')
        self.assertEqual(with_tier('gemini-3.8-flash-high','low',offered),'gemini-3.8-flash-low')
        self.assertEqual(with_tier('gemini-3.8-flash-low','high',{'gemini-3.8-flash-low','gemini-3.8-flash-medium'}),'gemini-3.8-flash-medium')
        self.assertEqual(with_tier('claude-sonnet-4-6','high',offered),'claude-sonnet-4-6')

    def test_unpinned_coordinator_picks_tier_per_message_and_pinned_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.integrations_enabled=True
            self.assertEqual(s.state['jarvis_model'],'gemini-3.8-flash-high');self.assertFalse(s.state.get('jarvis_model_pinned'))
            s.state['jarvis_connector']='gemini'
            calls,g,c=self.fakes([])
            with g,c:
                for text,planning in (('Selam',False),('Bu iki yaklaşımı karşılaştırıp hangisinin neden daha iyi olduğunu açıklar mısın lütfen',False),('Bir not uygulaması yapalım',True)):
                    s.launch_model(text,'common',planning=planning);s.model_thread.join(3);self.settle(s)
                self.assertEqual([c_[1] for c_ in calls],['gemini-3.8-flash-low','gemini-3.8-flash-medium','gemini-3.8-flash-high'])
                s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'gemini-3.8-flash-medium'})
                self.assertTrue(s.state['jarvis_model_pinned']);calls.clear()
                s.launch_model('Selam','common');s.model_thread.join(3);self.settle(s)
                self.assertEqual(calls[0][1],'gemini-3.8-flash-medium')
                s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':'auto'})
                self.assertFalse(s.state['jarvis_model_pinned']);self.assertEqual(s.state['jarvis_model'],'gemini-3.8-flash-high')

    def test_migration_gives_the_coordinator_the_strongest_tier_unless_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.state['jarvis_model']='gemini-3.8-flash-low';s.state.pop('coordinator_tier_v072');s.save()
            self.assertEqual(Store(tmp).state['jarvis_model'],'gemini-3.8-flash-high')
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);s.state.update(jarvis_model='gemini-3.8-flash-low',jarvis_model_pinned=True);s.state.pop('coordinator_tier_v072');s.save()
            self.assertEqual(Store(tmp).state['jarvis_model'],'gemini-3.8-flash-low')


class CodeRoutingTests(TeamCallHelpers,unittest.TestCase):
    """Small code asks go straight to a code agent; JARVIS only announces it."""
    def test_code_request_heuristic(self):
        s=self.make()
        for text in ('Python’da hello world yazdıran komut ver','Bana bir bash script yaz','JavaScript fonksiyon lazım, iki sayıyı toplasın','write a python function that reverses a string'):
            self.assertTrue(s.code_request(text),text)
        for text in ('Python nedir?','Nasıl Python öğrenirim','Bir not uygulaması yapalım, kod yazalım','Merhaba','Bu kodu anlat','x '*200):
            self.assertFalse(s.code_request(text),text)

    def test_code_agent_prefers_claude_then_codex_and_skips_exhausted(self):
        s=self.make()
        vision=next(a for a in s.state['agents'] if a['name']=='VISION')
        vision['connector']='claude_google';self.assertEqual(s.code_agent(),'FRIDAY')
        vision['connector']='claude_code';self.assertEqual(s.code_agent(),'FRIDAY')
        s.state['claude_status']={'installed':True,'signed_in':True};self.assertEqual(s.code_agent(),'VISION')
        vision['enabled']=False;self.assertEqual(s.code_agent(),'FRIDAY')
        s.state['provider_usage']['FRIDAY']={'status':'live','primary':{'used_percent':100}};self.assertIsNone(s.code_agent())
        vision['enabled']=True;self.assertEqual(s.code_agent(),'VISION')

    def test_simple_code_ask_is_routed_without_a_coordinator_call(self):
        s=self.make()
        calls,g,c=self.fakes(['print("Merhaba")'],['print("Merhaba")'])
        with g,c:
            s.action('converse',{'text':'Python’da hello world yazdıran komut ver','channel':'common'});self.settle(s)
        rows=self.shared(s)
        self.assertEqual([m['author'] for m in rows if m['author']!='YOU'][-2:],['JARVIS','FRIDAY'])
        self.assertEqual(rows[-2]['provider'],'rules');self.assertIn('FRIDAY',rows[-2]['text'])
        self.assertEqual(rows[-1]['text'],'print("Merhaba")')
        self.assertEqual(len(calls),1);self.assertIn('JARVIS routed',calls[0][2])
        self.assertEqual(self.efforts,['low']);self.assertIn('effort low',rows[-1]['model'])
        self.assertEqual(sum(m['author']=='YOU' for m in s.state['messages']),1)

    def test_harder_code_ask_goes_through_the_coordinator_who_rates_it(self):
        s=self.make()
        calls,g,c=self.fakes(['Tamam\nHANDOFF: FRIDAY/high: Thread kullanan hızlı karşılaştırma komutu'],['Kod hazır'])
        with g,c:
            s.action('converse',{'text':'Python’da iki büyük dosyayı thread kullanarak karşılaştıran ve test eden hızlı bir komut ver','channel':'common'});self.settle(s)
        self.assertEqual([c_[0] for c_ in calls],['google','codex']);self.assertEqual(self.efforts,['high'])
        self.assertEqual([m['author'] for m in self.shared(s) if m.get('model')],['JARVIS','FRIDAY'])

    def test_code_ask_falls_to_chatgpt_when_claude_is_off_and_stays_with_jarvis_when_handoff_is_off(self):
        s=self.make();next(a for a in s.state['agents'] if a['name']=='VISION')['enabled']=False
        calls,g,c=self.fakes([],['codex kodu'])
        with g,c:
            s.action('converse',{'text':'Bana bir bash script yaz, dosyaları saysın','channel':'common'});self.settle(s)
        self.assertEqual([c_[0] for c_ in calls],['codex']);self.assertEqual(self.shared(s)[-1]['author'],'FRIDAY')
        s=self.make();s.state['auto_handoff']=False
        calls,g,c=self.fakes(['JARVIS cevabı'])
        with g,c:
            s.action('converse',{'text':'Bana bir bash script yaz, dosyaları saysın','channel':'common'});self.settle(s)
        self.assertEqual([c_[0] for c_ in calls],['google']);self.assertEqual(self.shared(s)[-1]['author'],'JARVIS')


class TeamCharterTests(TeamCallHelpers,unittest.TestCase):
    """Every agent is taught the same team structure inside its own prompt."""
    def test_roles_migration_updates_old_defaults_but_keeps_custom_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp)
            roles={a['name']:a['role'] for a in s.state['agents']}
            self.assertIn('baş',roles['VISION']);self.assertIn('Yardımcı yazılımcı',roles['FRIDAY']);self.assertIn('Araştırmacı',roles['EDITH'])
            for a in s.state['agents']:
                if a['name']=='VISION':a['role']='Ana geliştirici · kod ve dosya düzenleme'
                if a['name']=='FRIDAY':a['role']='Benim özel rolüm'
            s.state.pop('roles_v073');s.save()
            again={a['name']:a['role'] for a in Store(tmp).state['agents']}
            self.assertIn('baş',again['VISION']);self.assertEqual(again['FRIDAY'],'Benim özel rolüm')
    def test_charter_names_roles_and_reaches_called_agents_and_coordinator(self):
        s=self.make()
        charter=s.team_charter('EDITH')
        for word in ('Berke owns','JARVIS (Gemini) is the coordinator','VISION','FRIDAY','EDITH','You are EDITH'):self.assertIn(word,charter)
        calls,g,c=self.fakes(['EDITH yanıtı','JARVIS yanıtı'])
        with g,c:
            s.action('converse',{'text':'EDITH’i çağır, kendini tanıtsın','channel':'common'});self.settle(s)
            s.action('converse',{'text':'Bugün hangi işleri planlıyoruz, bana kısa bir özet ver lütfen','channel':'common'});self.settle(s)
        self.assertIn('You are EDITH',calls[0][2]);self.assertIn('TEAM CHARTER',calls[1][2]);self.assertIn('You are JARVIS',calls[1][2])
    def test_planning_prompt_carries_the_charter(self):
        from team_runner import planning_prompt
        s=self.make();self.assertIn('TEAM CHARTER',planning_prompt(s,'Bir uygulama yapalım',''))


class TurboPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(self.tmp.name)
    def pending(self,kind,chat_id=None):
        chat_id=chat_id or self.store.state['active_chat'];event=threading.Event()
        self.store.state['work_requests'].append(dict(id='r-'+kind,chat_id=chat_id,kind=kind,status='pending',expires=time.time()+60,reason='x'))
        self.store.work_events['r-'+kind]=event;return event
    def chat(self):return next(c for c in self.store.state['chats'] if c['id']==self.store.state['active_chat'])
    def test_turbo_auto_approves_edits_and_tests_but_never_computer_control(self):
        s=self.store
        for kind in ('file','test'):self.assertTrue(s.auto_approved('turbo',kind))
        self.assertFalse(s.auto_approved('turbo','desktop'))
        self.assertTrue(s.auto_approved('auto_files','file'));self.assertFalse(s.auto_approved('auto_files','test'))
        for kind in ('file','test','desktop'):self.assertFalse(s.auto_approved('ask',kind));self.assertFalse(s.auto_approved('read_only',kind))
    def test_permission_modes_include_turbo_and_reject_unknown(self):
        self.store.action('project-permission',{'mode':'turbo'});self.assertEqual(self.chat()['work_permission'],'turbo')
        with self.assertRaises(ValueError):self.store.action('project-permission',{'mode':'root'})
        self.assertEqual(self.chat()['work_permission'],'turbo')
    def test_always_allow_upgrades_this_chat_once_and_only_for_edits_and_tests(self):
        event=self.pending('file')
        self.store.action('work-decision',{'id':'r-file','decision':'approved','always':True})
        self.assertTrue(event.is_set());self.assertEqual(self.chat()['work_permission'],'turbo')
        self.assertEqual(next(r for r in self.store.state['work_requests'] if r['id']=='r-file')['status'],'approved')
        self.store.action('project-permission',{'mode':'ask'});self.pending('desktop')
        self.store.action('work-decision',{'id':'r-desktop','decision':'approved','always':True})
        self.assertEqual(self.chat()['work_permission'],'ask')
    def test_rejecting_or_read_only_chats_never_upgrade(self):
        self.pending('test');self.store.action('work-decision',{'id':'r-test','decision':'rejected','always':True})
        self.assertNotEqual(self.chat().get('work_permission'),'turbo')
        self.store.action('project-permission',{'mode':'read_only'});self.pending('file')
        self.store.action('work-decision',{'id':'r-file','decision':'approved','always':True})
        self.assertEqual(self.chat()['work_permission'],'read_only')


class PhotoRoutingTests(TeamCallHelpers,unittest.TestCase):
    """Photos and video contact sheets are JPEGs; only Codex can read them, so the shared chat hands them to FRIDAY."""
    JPEG='data:image/jpeg;base64,'+__import__('base64').b64encode(b'\xff\xd8\xff\xe0'+b'0'*40).decode()
    def codex(self,seen):
        class FakeCodex:
            def __init__(self,directory,on_delta,cancelled,project_tools=False):pass
            def run(self,prompt,image=None):seen.append((prompt,image));return 'Fotoğrafta bir masa var.'
            def close(self):pass
        return patch('app.CodexConversation',FakeCodex)
    def test_photo_in_common_chat_is_answered_by_the_codex_agent(self):
        s=self.make();seen=[]
        with self.codex(seen):
            s.action('converse',{'text':'Bu fotoğrafta ne var?','channel':'common','image':self.JPEG});self.settle(s)
        rows=[m for m in self.shared(s) if m.get('model')]
        self.assertEqual(rows[-1]['author'],'FRIDAY');self.assertEqual(rows[-1]['text'],'Fotoğrafta bir masa var.')
        self.assertEqual([image for _,image in seen],[self.JPEG])
        self.assertTrue(any(m['author']=='JARVIS' and 'FRIDAY' in m['text'] and 'görsel' in m['text'].lower() for m in self.shared(s)))
        user=[m for m in self.shared(s) if m['author']=='YOU'][-1];self.assertIn('Görsel eklendi',user['text']);self.assertNotIn(self.JPEG,json.dumps(s.state['messages']))
    def test_photo_without_an_available_codex_agent_says_why(self):
        s=self.make()
        s.state['agents'][[a['name'] for a in s.state['agents']].index('FRIDAY')]['enabled']=False
        with self.assertRaises(ValueError) as caught:s.action('converse',{'text':'Bu nedir?','channel':'common','image':self.JPEG})
        self.assertIn('FRIDAY',str(caught.exception))
    def test_photo_keeps_the_normal_route_when_jarvis_already_is_codex(self):
        s=self.make();s.state['jarvis_connector']='codex'
        self.assertIsNone(s.image_agent('Bu nedir?'))
    def test_non_jpeg_images_are_still_refused(self):
        s=self.make()
        with self.assertRaises(ValueError):s.action('converse',{'text':'Bu nedir?','channel':'common','image':'data:image/png;base64,AAAA'})

    def test_reader_writes_a_visual_note_prompt_and_followups_reuse_the_photo(self):
        s=self.make();seen=[]
        with self.codex(seen):
            s.action('converse',{'text':'Bu ekran görüntüsündeki hatayı anla','channel':'common','image':self.JPEG});self.settle(s)
            s.action('converse',{'text':'FRIDAY’e sor, fotoğraftaki hatayı bir daha açıklasın','channel':'common'});self.settle(s)
            s.action('converse',{'text':'FRIDAY’e sor, bugün hava nasıl olur','channel':'common'});self.settle(s)
        self.assertIn('Visual note',seen[0][0]);self.assertEqual(seen[0][1],self.JPEG)
        self.assertEqual(seen[1][1],self.JPEG)
        self.assertIsNone(seen[2][1])
        self.assertNotIn('data:image',json.dumps(s.state))
    def test_remembered_photo_is_only_for_codex_agents_and_expires(self):
        s=self.make();seen=[]
        s.remember_image(s.state['active_chat'],self.JPEG)
        self.assertEqual(s.recent_image('fotoğrafa bak'),self.JPEG);self.assertIsNone(s.recent_image('bugün plan yapalım'))
        s.chat_images[s.state['active_chat']]=(self.JPEG,time.time()-3000)
        self.assertIsNone(s.recent_image('fotoğrafa bak'))
        s.remember_image(s.state['active_chat'],self.JPEG)
        calls,g,c=self.fakes(['EDITH yanıtı'])
        with g,c:
            s.action('converse',{'text':'EDITH’i çağır, fotoğrafı yorumlasın','channel':'common'});self.settle(s)
        self.assertEqual(len(calls),1)


class ActiveWorkTests(TeamCallHelpers,unittest.TestCase):
    """The bottom bubble lists every running agent, in this chat and in other chats/projects."""
    def test_running_agents_are_listed_with_summary_chat_and_project(self):
        s=self.make();gate=threading.Event();seen=[]
        class SlowGoogle:
            def __init__(self,directory,on_delta,cancelled,model=''):pass
            def run(self,prompt,image=None):gate.wait(5);return 'Tamam.'
            def close(self):pass
        first=s.state['active_chat'];s.state['chats'][0]['active_project']='Mavi Bahçe'
        with patch('app.GoogleConversation',SlowGoogle):
            s.action('converse',{'text':'EDITH’i çağır, internetten güncel haberleri araştırsın','channel':'common'})
            rows=s.state_view()['active_work'] if hasattr(s,'state_view') else s.active_work()
            self.assertEqual(len(rows),1)
            row=rows[0]
            self.assertEqual((row['agent'],row['mode'],row['current'],row['project'],row['chat_id']),('EDITH','research',True,'Mavi Bahçe',first))
            self.assertIn('araştırsın',row['summary']);self.assertFalse(row['writing']);self.assertTrue(row['started_at'])
            s.action('new-chat',{})
            self.assertTrue(all(r['current'] is False for r in s.active_work()))
            self.assertEqual(s.active_work()[0]['chat_id'],first)
            gate.set();self.settle(s,8)
        self.assertEqual(s.active_work(),[])
    def test_team_run_without_a_running_job_shows_one_row(self):
        s=self.make();parent=s.state['active_chat']
        s.state['teams'].append(dict(id='t1',parent_chat=parent,goal='Bir uygulama yapalım',status='working',stage='Plan hazırlanıyor',children=[],outputs=[]))
        rows=s.active_work();self.assertEqual([(r['agent'],r['mode'],r['activity']) for r in rows],[('JARVIS','team','Plan hazırlanıyor')])
        s.state['teams'][0]['status']='review';self.assertEqual(s.active_work(),[])


class GeminiPictureTests(TeamCallHelpers,unittest.TestCase):
    """Gemini (JARVIS) looks at pictures through the CLI's file tool, but only after the self-test proved it works."""
    JPEG=PhotoRoutingTests.JPEG
    def fake_agy(self,response='zorgblat_7'):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        script=root/'agy'
        script.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > '+str(root/'args.txt')+'\nls -1 > '+str(root/'ls.txt')+'\n'
            'case "$*" in *stream-json*)\n'
            'echo \'{"event":"step_update","step_update":{"step_type":"tool","state":"DONE","tool_name":"read_file","tool_info":{"parameters":{}}}}\'\n'
            'echo \'{"event":"result","result":{"status":"SUCCESS","response":"'+response+'"}}\';;\n'
            '*) echo \'{"status":"SUCCESS","response":"'+response+'"}\';;\nesac\n')
        script.chmod(0o755);return root,script
    def test_cli_gets_a_private_read_allowed_copy_that_is_deleted_afterwards(self):
        from google_chat import GoogleConversation
        root,script=self.fake_agy()
        with patch('google_chat.binary',return_value=str(script)):
            client=GoogleConversation(str(root),lambda _:None,threading.Event());answer=client.run('Ne yazıyor?',self.JPEG)
        self.assertEqual(answer,'zorgblat_7');self.assertEqual(client.tools_used,['read_file'])
        args=(root/'args.txt').read_text().split('\n')
        settings=json.loads(args[args.index('--settings')+1])
        self.assertNotIn('read_file(*)',settings['permissions']['deny']);self.assertIn('write_file(*)',settings['permissions']['deny'])
        name=[a for a in settings['permissions']['allow'] if a.startswith('read_file(')][0]
        self.assertIn('attachment-',name);self.assertEqual(args[args.index('--output-format')+1],'stream-json')
        self.assertIn('attachment-',(root/'ls.txt').read_text())
        self.assertEqual(list((root/'google-chat-workspace').glob('attachment-*')),[])
        self.assertIn('Open that one file',args[args.index('-p')+1])
    def test_without_a_picture_file_reading_stays_denied(self):
        from google_chat import GoogleConversation
        root,script=self.fake_agy('Merhaba')
        with patch('google_chat.binary',return_value=str(script)):
            GoogleConversation(str(root),lambda _:None,threading.Event()).run('Selam')
        args=(root/'args.txt').read_text().split('\n');settings=json.loads(args[args.index('--settings')+1])
        self.assertIn('read_file(*)',settings['permissions']['deny']);self.assertEqual(args[args.index('--output-format')+1],'json')
    def test_non_jpeg_pictures_are_refused_before_the_cli_starts(self):
        from google_chat import GoogleConversation
        root,script=self.fake_agy()
        with patch('google_chat.binary',return_value=str(script)):
            with self.assertRaises(ValueError):GoogleConversation(str(root),lambda _:None,threading.Event()).run('x','data:image/png;base64,AAAA')
        self.assertFalse((root/'args.txt').exists())
    def probe(self,s,answer):
        class FakeGoogle:
            tools_used=['read_file']
            def __init__(self,directory,on_delta,cancelled,model=''):pass
            def run(self,prompt,image=None):return answer
            def close(self):pass
        with patch('app.GoogleConversation',FakeGoogle):
            s.action('vision-test',{})
            end=time.time()+5
            while s.state['vision']['status']=='testing' and time.time()<end:time.sleep(.05)
        return s.state['vision']
    def test_self_test_enables_vision_only_when_the_unique_token_is_read(self):
        s=self.make();self.assertEqual(s.state['vision']['status'],'unknown')
        self.assertEqual(self.probe(s,'Cevap: bilmiyorum, görseli göremiyorum')['status'],'no')
        self.assertFalse(s.jarvis_can_see())
        self.assertEqual(self.probe(s,'zorgblat_7')['status'],'ok');self.assertTrue(s.jarvis_can_see());self.assertEqual(s.state['vision']['variant'],'review')
    def test_self_test_tries_the_permission_variants_and_remembers_the_one_that_works(self):
        s=self.make();seen=[]
        class FakeGoogle:
            tools_used=['read_file'];debug='result/status=SUCCESS'
            def __init__(self,directory,on_delta,cancelled,model=''):pass
            def run(self,prompt,image=None):
                seen.append(self.picture_mode)
                if self.picture_mode!='strict':raise ValueError('Antigravity boş yanıt döndürdü.')
                return 'zorgblat_7'
            def close(self):pass
        with patch('app.GoogleConversation',FakeGoogle):
            s.action('vision-test',{});end=time.time()+5
            while s.state['vision']['status']=='testing' and time.time()<end:time.sleep(.05)
        self.assertEqual(seen,['review','strict']);self.assertEqual((s.state['vision']['status'],s.state['vision']['variant']),('ok','strict'))
        self.assertIn('review: Antigravity boş yanıt',s.state['vision']['message'])
    def photo_run(self,s,text,vision):
        s.state['vision']={'status':vision};seen={'google':[],'codex':[]}
        class FakeGoogle:
            def __init__(self,directory,on_delta,cancelled,model=''):self.model=model
            def run(self,prompt,image=None):seen['google'].append((self.model,image,prompt));return 'Gemini yanıtı'
            def close(self):pass
        class FakeCodex:
            def __init__(self,directory,on_delta,cancelled,project_tools=False):pass
            def run(self,prompt,image=None):seen['codex'].append(image);return 'Codex yanıtı'
            def close(self):pass
        with patch('app.GoogleConversation',FakeGoogle),patch('app.CodexConversation',FakeCodex):
            s.action('converse',{'text':text,'channel':'common','image':self.JPEG});self.settle(s)
        return seen
    def test_jarvis_answers_a_screenshot_itself_once_gemini_can_see(self):
        s=self.make();seen=self.photo_run(s,'Bu ekran görüntüsünde ne yazıyor?','ok')
        self.assertEqual(len(seen['google']),1);self.assertEqual(seen['google'][0][1],self.JPEG);self.assertEqual(seen['codex'],[])
        self.assertIn('answer it directly',seen['google'][0][2])
        rows=[m for m in self.shared(s) if m.get('model')];self.assertEqual(rows[-1]['author'],'JARVIS')
    def test_screenshot_goes_to_the_codex_agent_while_gemini_cannot_see(self):
        for state in ('unknown','no','error'):
            s=self.make();seen=self.photo_run(s,'Bu ekran görüntüsünde ne yazıyor?',state)
            self.assertEqual(seen['google'],[],state);self.assertEqual(seen['codex'],[self.JPEG],state)
    def test_a_named_gemini_agent_receives_the_picture_only_when_it_can_see(self):
        s=self.make();seen=self.photo_run(s,'EDITH’i çağır, bu ekran görüntüsüne baksın','ok')
        self.assertEqual([(m,i) for m,i,_ in seen['google']][:1],[(seen['google'][0][0],self.JPEG)]);self.assertEqual(seen['codex'],[])
        self.assertEqual([m['author'] for m in self.shared(s) if m.get('model')][-1],'EDITH')
        s=self.make();seen=self.photo_run(s,'EDITH’i çağır, bu ekran görüntüsüne baksın','no')
        self.assertEqual(seen['codex'],[self.JPEG])
