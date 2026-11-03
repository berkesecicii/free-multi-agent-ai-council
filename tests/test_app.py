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
