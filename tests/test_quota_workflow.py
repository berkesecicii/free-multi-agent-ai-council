import copy,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Store
from claude_usage import parse_response,reset_timestamp,read_limits
from chat_workflow import detect
class RealQuotaTests(unittest.TestCase):
 def receipt(self):return dict(local_command='usage',type='result',is_error=False,num_turns=0,duration_api_ms=0,total_cost_usd=0,usage=dict(input_tokens=0,output_tokens=0),modelUsage={},result='Current session: 19% used · resets Nov 3 at 4:20am (America/Los_Angeles)\nCurrent week (all models): 14% used · resets Nov 9 at 4am (America/Los_Angeles)')
 def test_zero_turn_receipt_and_actual_windows(self):
  value=parse_response(self.receipt());self.assertEqual(value['primary']['used_percent'],19);self.assertEqual(value['secondary']['used_percent'],14);self.assertTrue(value['zero_model_turns']);self.assertIsNotNone(value['secondary']['resets_at'])
 def test_inference_or_wrong_command_never_accepted_as_quota(self):
  for change in ({'num_turns':1},{'duration_api_ms':100},{'total_cost_usd':.01},{'local_command':'chat'},{'usage':{'input_tokens':1}},{'modelUsage':{'some-model':{}}}):
   value=self.receipt();value.update(change)
   with self.assertRaises(ValueError):parse_response(value)
 def test_no_api_auth_fallback(self):
  with patch('claude_usage.binary',return_value='/fake'),patch('claude_usage.status',return_value={'signed_in':False}),patch('claude_usage.subprocess.Popen') as popen:
   self.assertEqual(read_limits()['status'],'error');popen.assert_not_called()
class ChatWorkflowTests(unittest.TestCase):
 def make(self,d):
  s=Store(d);s.integrations_enabled=True;s.state['jarvis_connector']='gemini'
  for a in s.state['agents']:
   if a['name'] in ('VISION','FRIDAY','EDITH'):a.update(connector='gemini',model='gemini-3.8-flash-low',enabled=True,in_common=True)
  return s
 def settle(self,s):
  end=time.time()+5
  while time.time()<end:
   run=s.state.get('chat_workflows',[])
   if run and run[-1]['status'] in ('done','error','paused','cancelled'):return
   time.sleep(.03)
  self.fail('workflow did not settle')
 def test_requested_order_preserved_outputs_and_final_presenter(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.make(d);calls=[]
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):calls.append(prompt);return ['Araştırma kaynağı https://example.com/research','Kod hazır','Elle kontrol; test çalıştırılmadı','Sonuç: kod hazır, çalıştırılmış test yok.'][len(calls)-1]
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'JARVIS, önce VISION kod yazacak ama EDITH araştırıp ona paslasın sonra FRIDAY test etsin sen sonucu sun.','channel':'common'});self.settle(s)
   self.assertEqual(s.state['chat_workflows'][-1]['steps'],['EDITH','VISION','FRIDAY']);self.assertEqual(len(calls),4)
   rows=[m for m in s.state['messages'] if m.get('workflow_id')];self.assertEqual([m['author'] for m in rows],['JARVIS','EDITH','VISION','FRIDAY','JARVIS']);self.assertTrue(rows[-1]['presentation']);self.assertIn('Araştırma kaynağı',rows[1]['text']);self.assertEqual(sum(m['author']=='YOU' for m in s.state['messages']),1)
   self.assertIn('Araştırma kaynağı',calls[-1]);self.assertIn('test çalıştırılmadı',calls[-1])
 def test_simple_question_does_not_fan_out(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.make(d);self.assertEqual(detect(s,'EDITH ve VISION farkı nedir?'),[]);self.assertEqual(detect(s,'@VISION bu kodu açıkla'),[]);self.assertEqual(detect(s,'EDITH ve VISION çağırma, sadece sen araştır'),[])
 def test_error_stops_sequence_and_preserves_prior_output(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.make(d);calls=[]
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):
     calls.append(prompt)
     if len(calls)>1:raise ValueError('quota exhausted')
     return 'Araştırma korundu.'
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'JARVIS EDITH araştırıp sonra VISION kod yazsın sen sun','channel':'common'});self.settle(s)
   self.assertEqual(len(calls),2);self.assertEqual(s.state['chat_workflows'][-1]['status'],'error');self.assertTrue(any(m['text']=='Araştırma korundu.' for m in s.state['messages']))
 def test_project_tools_only_in_explicit_attached_project_mode(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.integrations_enabled=True;s.state['active_project_path']=d;chat=s.state['chats'][0];seen=[]
   class Fake:
    def __init__(self,*args,project_tools=False):seen.append(project_tools)
    def run(self,*args):return 'Sadece verilen görev.'
    def close(self):pass
   with patch('app.CodexConversation',Fake):
    s.launch_model('Projeyi incele','common',speaker='FRIDAY');s.model_thread.join(2)
    chat['project_work']=True;s.launch_model('Projeyi incele','common',speaker='FRIDAY');s.model_thread.join(2)
   self.assertEqual(seen,[False,True])

class OrchestraTests(unittest.TestCase):
 make=ChatWorkflowTests.make
 settle=ChatWorkflowTests.settle
 def test_workers_are_isolated_and_lead_receives_summaries(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.make(d);calls=[]
   s.message('YOU','PRIVATE_OLD_CHAT_SENTINEL')
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):
     calls.append(prompt)
     return ['RESEARCH_ONLY_RESULT','TEST_ONLY_RESULT','LEAD_INTEGRATED_RESULT','Final brief'][len(calls)-1]
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'Orkestra yap, VISION lider olsun. EDITH: Python belgelerini araştır; FRIDAY: sınır durumlarını incele. Sonucu sun.','channel':'common'});self.settle(s)
   run=s.state['chat_workflows'][-1]
   self.assertEqual(set(run['steps'][:-1]),{'FRIDAY','EDITH'});self.assertEqual(run['steps'][-1],'VISION')
   self.assertEqual(run['leader'],'VISION');self.assertTrue(all(t['status']=='done' for t in run['subtasks']))
   self.assertEqual(len(calls),4)
   self.assertNotIn('PRIVATE_OLD_CHAT_SENTINEL',''.join(calls))
   self.assertNotIn('RESEARCH_ONLY_RESULT',calls[1])
   self.assertIn('RESEARCH_ONLY_RESULT',calls[2]);self.assertIn('TEST_ONLY_RESULT',calls[2]);self.assertIn('LEAD_INTEGRATED_RESULT',calls[3])
 def test_discussing_orchestra_does_not_call_workers(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(detect(self.make(d),'VISION EDITH orkestra modu nedir?'),[])

class IndependentNovaTests(unittest.TestCase):
 def test_nova_never_receives_coordinator_role_or_common_history(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.integrations_enabled=True
   nova=next(a for a in s.state['agents'] if a['name']=='NOVA');nova.update(connector='gemini',model='gemini-3.8-flash-low',enabled=True)
   s.message('YOU','COMMON_PRIVATE_SENTINEL','common');calls=[]
   class Fake:
    def __init__(self,*a):pass
    def run(self,prompt,image=None):calls.append(prompt);return 'Ben NOVA, bağımsız sohbet asistanıyım.'
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.launch_model('Merhaba','NOVA');s.model_thread.join(3)
   self.assertEqual(len(calls),1);self.assertIn('independent everyday chat assistant',calls[0]);self.assertNotIn('TEAM CHARTER',calls[0]);self.assertNotIn('COMMON_PRIVATE_SENTINEL',calls[0])
