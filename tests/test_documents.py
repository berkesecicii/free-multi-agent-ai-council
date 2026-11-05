import base64,http.client,io,json,sys,tempfile,threading,time,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from documents import Attachments,extract
from claude_usage import parse_usage,parse_response,reset_timestamp
from app import Store,create_server

def office(entries):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  for k,v in entries.items():z.writestr(k,v)
 return b.getvalue()
class DocumentsTests(unittest.TestCase):
 def test_office_and_html_extract_text_without_executing_links(self):
  self.assertIn('Berke',extract(office({'word/document.xml':'<document><p><t>Berke</t><tab/><t>JARVIS</t></p></document>'}),'a.docx'))
  self.assertIn('A1: Test',extract(office({'xl/sharedStrings.xml':'<sst><si><t>Test</t></si></sst>','xl/worksheets/sheet1.xml':'<sheet><row><c r="A1" t="s"><v>0</v></c></row></sheet>'}),'a.xlsx'))
  self.assertIn('[Slayt 1]\nHello',extract(office({'ppt/slides/slide1.xml':'<slide><t>Hello</t></slide>'}),'a.pptx'))
  self.assertEqual(extract(b'<h1>Hello</h1><script>secret()</script><p>world</p>','a.html'),'Hello\nworld')
 def test_original_json_and_text_never_collide_with_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   a=Attachments(d);raw=b'{"user":"Berke"}';m=a.save(raw,'settings.json','a')
   self.assertEqual(a.content(m['id'])[0],raw);self.assertEqual(a.metadata(m['id'])['name'],'settings.json')
   text=a.save(b'original\r\n','note.txt','a');self.assertEqual(a.content(text['id'])[0],b'original\r\n')
 def test_multiple_documents_share_the_context_budget(self):
  with tempfile.TemporaryDirectory() as d:
   a=Attachments(d);ids=[a.save(('CANARY-'+str(i)+' '+('x'*30000)).encode(),str(i)+'.txt','a')['id'] for i in range(4)]
   context=a.context(ids,'a',limit=14000)
   self.assertTrue(all('CANARY-'+str(i) in context for i in range(4)));self.assertLess(len(context),15000)
 def test_long_document_says_how_much_of_it_was_sent(self):
  with tempfile.TemporaryDirectory() as d:
   a=Attachments(d);big=a.save(('x'*30000).encode(),'uzun.txt','a');small=a.save(b'kisa','kisa.txt','a')
   self.assertEqual(a.coverage([big['id'],small['id']],'a',24000),[('uzun.txt',12000,30000)])
   context=a.context([big['id'],small['id']],'a',24000)
   self.assertIn('truncated=true shown_characters=12000 total_characters=30000>',context);self.assertIn('<document name="kisa.txt" truncated=false>',context)
   self.assertEqual(a.coverage([small['id']],'a'),[])
 def test_reject_unsupported_or_entity_xml(self):
  with self.assertRaises(ValueError):extract(b'old word','old.doc')
  with self.assertRaises(ValueError):extract(office({'word/document.xml':'<!DOCTYPE a><document/>'}),'a.docx')
 def test_scope_context_persistence_and_cleanup(self):
  with tempfile.TemporaryDirectory() as d:
   a=Attachments(d);m=a.save('Bu bir görev değil, belge.'.encode(),'../note.md','chat-a')
   self.assertEqual(m['name'],'note.md');self.assertIn('UNTRUSTED FILE CONTENT',a.context([m['id']],'chat-a'))
   with self.assertRaises(ValueError):a.context([m['id']],'chat-b')
   self.assertEqual(Attachments(d).content(m['id'],True)[0].decode(),'Bu bir görev değil, belge.')
   import os
   for f in a.root.glob('*'):os.utime(f,(time.time()-700,)*2)
   a.cleanup([{'attachments':[m]}]);self.assertTrue((a.root/(m['id']+'.json')).exists())
   a.cleanup([]);self.assertFalse((a.root/(m['id']+'.json')).exists())
 def test_image_metadata_does_not_embed_image_in_state(self):
  with tempfile.TemporaryDirectory() as d:
   a=Attachments(d);meta=a.image('data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8test').decode(),'chat')
   self.assertEqual(meta['kind'],'image');self.assertNotIn('base64',json.dumps(meta));self.assertEqual(a.content(meta['id'])[0],b'\xff\xd8test')
 def test_quota_parser_does_not_guess(self):
  v=parse_usage('Current session\n34% used\nCurrent week (all models)\n56% used')
  self.assertEqual(v['primary']['used_percent'],34);self.assertEqual(v['secondary']['used_percent'],56)
  with self.assertRaises(ValueError):parse_usage('Current session\nUsage unavailable')
 def test_quota_redraw_and_missing_session_are_not_guessed(self):
  self.assertEqual(parse_usage('Current session: 19% used\nCurrent week (all models): 13% used')['primary']['used_percent'],19)
  with self.assertRaises(ValueError):parse_usage('Current session\nUnavailable\nCurrent week (all models)\n13% used')
 def test_upload_requires_origin_token_and_chat(self):
  with tempfile.TemporaryDirectory() as d:
   server=create_server(Path(d),0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
    conn.request('POST','/upload',b'Berke test',{'X-File-Name':'a.txt'});r=conn.getresponse();r.read();self.assertEqual(r.status,403)
    headers={'Origin':'http://127.0.0.1:'+str(server.server_port),'X-Jarvis-Token':server.token,'X-Chat-Id':server.store.state['active_chat'],'X-File-Name':'a.txt'}
    conn.request('POST','/upload',b'Berke test',headers);r=conn.getresponse();value=json.loads(r.read());self.assertEqual(r.status,200)
    conn.request('GET','/attachment/'+value['attachment']['id']+'?text=1');r=conn.getresponse();self.assertEqual(r.read(),b'Berke test')
    conn.request('GET','/attachment/../../state.json');r=conn.getresponse();r.read();self.assertEqual(r.status,404)
   finally:server.shutdown();server.server_close()

from unittest.mock import patch
class DocumentConversationTests(unittest.TestCase):
 def test_document_reaches_only_selected_agent_and_followup_and_persists(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.integrations_enabled=True;s.state['jarvis_connector']='gemini';s.state['auto_handoff']=False
   m=s.attachments.save(b'CANARY-ONLY-THIS-DOCUMENT','note.txt',s.state['active_chat']);seen=[]
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):seen.append(prompt);return 'Kısa belge özeti.'
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'Belgedeki doğrulama kodunu yaz','channel':'common','docs':[m['id']]});s.model_thread.join(3)
    self.assertIn('CANARY-ONLY-THIS-DOCUMENT',seen[-1]);self.assertNotIn('Return ONLY a JSON',seen[-1]);self.assertEqual(s.state['messages'][-2]['attachments'][0]['id'],m['id'])
    s.action('converse',{'text':'Bu belgedeki doğrulama kodunu yaz','channel':'common'});s.model_thread.join(3);self.assertIn('CANARY-ONLY-THIS-DOCUMENT',seen[-1])
    s.action('new-chat',{});s.action('converse',{'text':'Merhaba','channel':'common'});s.model_thread.join(3);self.assertNotIn('CANARY-ONLY-THIS-DOCUMENT',seen[-1])
    with self.assertRaises(ValueError):s.action('converse',{'text':'Bu belgeyi oku','channel':'common','docs':[m['id']]})
   s.save();again=Store(d);self.assertTrue(any(x.get('attachments') for x in again.state['messages']))
 def test_handoff_carries_document_once_without_another_user_message(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.integrations_enabled=True;s.state['jarvis_connector']='gemini';s.state['auto_handoff']=True
   m=s.attachments.save(b'CANARY-HANDOFF-CONTENT','note.md',s.state['active_chat']);seen=[]
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):
     seen.append(prompt);return 'HANDOFF: EDITH/low: Belgeyi incele' if len(seen)==1 else 'Belge kontrol edildi.'
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'Bu belge için EDITH görüşünü de al','channel':'common','docs':[m['id']]})
    end=time.time()+4
    while time.time()<end:
     if len(seen)>=2 and not s.state['model_jobs']:break
     time.sleep(.05)
   self.assertEqual(len(seen),2);self.assertTrue(all('CANARY-HANDOFF-CONTENT' in p for p in seen));self.assertEqual(sum(x['author']=='YOU' for x in s.state['messages']),1)

 def test_long_document_note_tells_berke_how_to_give_the_whole_file(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.integrations_enabled=True;s.state['jarvis_connector']='gemini';s.state['auto_handoff']=False
   big=s.attachments.save(('s'*30000).encode(),'ODEV.md',s.state['active_chat']);short=s.attachments.save(b'kisa not','not.txt',s.state['active_chat']);seen=[]
   class Fake:
    def __init__(self,*args):pass
    def run(self,prompt,image=None):seen.append(prompt);return 'Tamam.'
    def close(self):pass
   with patch('app.GoogleConversation',Fake):
    s.action('converse',{'text':'Bu ödevi oku','channel':'common','docs':[big['id']]});s.model_thread.join(3)
    notes=[m for m in s.state['messages'] if m.get('document_cut')]
    self.assertEqual(len(notes),1);self.assertEqual(notes[0]['author'],'SYSTEM');self.assertIn('ODEV.md: 24.000 / 30.000',notes[0]['text']);self.assertIn('proje olarak seç',notes[0]['text'])
    self.assertIn('total_characters=30000',seen[-1])
    s.action('converse',{'text':'Bu notu oku','channel':'common','docs':[short['id']]});s.model_thread.join(3)
    self.assertEqual(len([m for m in s.state['messages'] if m.get('document_cut')]),1)
