import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Store
ROOT=Path(__file__).resolve().parents[1]
class SidebarTests(unittest.TestCase):
 def test_chat_list_has_last_activity_for_day_groups(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);first=s.state['active_chat'];s.state['messages']=[]
   next(c for c in s.state['chats'] if c['id']==first)['created_at']='2026-10-01 09:00:00'
   s.state['messages'].append(dict(id='a',author='YOU',text='x',time='2026-11-03 01:00:00',channel='common',chat_id=first))
   chats={c['id']:c for c in s.client_state()['chats']}
   self.assertEqual(chats[first]['last_at'],'2026-11-03 01:00:00')
 def test_empty_chat_falls_back_to_creation_time(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.state['messages']=[]
   chat=s.client_state()['chats'][0]
   self.assertEqual(chat['last_at'],chat['created_at'])
 def test_sidebar_and_rail_files_are_wired(self):
  html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
  self.assertIn('/sidebar.js',html);self.assertIn('/rail.js',html)
  self.assertIn("'/sidebar.js':'sidebar.js'",(ROOT/'app.py').read_text(encoding='utf-8'))
  self.assertIn('static/sidebar.js',(ROOT/'Guncelle.command').read_text(encoding='utf-8'))
  self.assertTrue((ROOT/'static'/'sidebar.js').exists())

class AgentSetupTests(unittest.TestCase):
 def test_pick_gemini_prefers_pro_medium_and_falls_back(self):
  from model_catalog import pick_gemini
  base=[{'id':'gemini-3.8-flash-high','name':'Gemini 3.8 Flash (High)'},{'id':'gemini-3.8-flash-medium','name':'Gemini 3.8 Flash (Medium)'},{'id':'gemini-3.8-flash-low','name':'Gemini 3.8 Flash (Low)'},{'id':'gpt-oss-120b-medium','name':'GPT-OSS 120B (Medium)'}]
  self.assertEqual(pick_gemini(base,'pro','medium'),'')
  self.assertEqual(pick_gemini(base,'flash','medium'),'gemini-3.8-flash-medium')
  self.assertEqual(pick_gemini(base,'flash','low'),'gemini-3.8-flash-low')
  self.assertEqual(pick_gemini(base,'lite','low'),'')
  more=base+[{'id':'gemini-3.1-pro-high','name':'Gemini 3.1 Pro (High)'},{'id':'gemini-3.1-pro-medium','name':'Gemini 3.1 Pro (Medium)'},{'id':'gemini-3.5-flash-lite','name':'Gemini 3.5 Flash-Lite'}]
  self.assertEqual(pick_gemini(more,'pro','medium'),'gemini-3.1-pro-medium')
  self.assertEqual(pick_gemini(more,'pro','high'),'gemini-3.1-pro-high')
  self.assertEqual(pick_gemini(more,'lite','low'),'gemini-3.5-flash-lite')
  self.assertEqual(pick_gemini(more,'flash','low'),'gemini-3.8-flash-low')
 def existing_install(self,d):
  s=Store(d);s.state.pop('agent_models_v8',None);s.save()
  return Store(d)
 def test_existing_install_gets_fixed_models_and_nova(self):
  with tempfile.TemporaryDirectory() as d:
   st=self.existing_install(d).state
   self.assertTrue(st['agent_models_v8']);self.assertFalse(st['auto_effort']);self.assertTrue(st['jarvis_model_pinned'])
   agents={a['name']:a for a in st['agents']}
   self.assertEqual(agents['NOVA']['connector'],'gemini');self.assertEqual(agents['NOVA']['model'],'gemini-3.8-flash-low')
   self.assertFalse(agents['NOVA']['in_common']);self.assertEqual(agents['KAREN']['connector'],'openrouter')
   self.assertEqual(st['jarvis_model'],agents['EDITH']['model'])
 def test_fresh_install_keeps_automatic_defaults(self):
  with tempfile.TemporaryDirectory() as d:
   st=Store(d).state
   self.assertTrue(st['agent_models_v8']);self.assertTrue(st.get('auto_effort',True))
   self.assertEqual([a['name'] for a in st['agents'] if a.get('connector')=='openrouter'],['NOVA'])
 def test_migration_runs_once_and_keeps_later_choices(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.existing_install(d);s.state['jarvis_model']='gemini-3.8-flash-high';s.state['auto_effort']=True;s.save()
   again=Store(d)
   self.assertEqual(again.state['jarvis_model'],'gemini-3.8-flash-high');self.assertTrue(again.state['auto_effort'])
   self.assertEqual([a['name'] for a in again.state['agents']].count('NOVA'),1)
 def test_voice_and_ui_files_are_wired(self):
  js=(ROOT/'static'/'native.js').read_text(encoding='utf-8')
  self.assertNotIn('Ayrıntılar sohbette',js);self.assertIn('agent:m.author',js)
  swift=(ROOT/'native'/'Jarvis.swift').read_text(encoding='utf-8')
  for key in ('agentVoice(','emitAgentVoices','voiceIDs','"voice":voiceID'):self.assertIn(key,swift)
  worker=(ROOT/'native'/'voice_worker.py').read_text(encoding='utf-8')
  self.assertIn("voice_styles",worker);self.assertIn('sys.exit(3)',worker)
  ui=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8')
  for key in ('function agentColor','as-menu','agent-voices','model-pill','work-line'):self.assertIn(key,ui)

class ControlAndSettingsTests(unittest.TestCase):
 def store(self,d,perms=True):
  s=Store(d);s.state['messages']=[]
  if perms:s.state['desktop_permissions']={'screen':True,'accessibility':True}
  self.launched=[]
  def fake(text,channel,*a,**k):self.launched.append((text,channel,k));return {}
  s.launch_model=fake
  return s
 def test_control_phrases_and_negations(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d)
   for yes in ('Tamam kontrolü al','tamam KONTROLU AL ve safariyi aç','bilgisayarı kontrol et','Mac’imi kullan','take control of my screen','Control my Mac please'):
    self.assertTrue(s.is_control_request(yes),yes)
   for no in ('kontrolü alma','bilgisayarı kontrol etme','don’t take control','Python sürümünü kontrol et','kontrol listesi hazırla'):
    self.assertFalse(s.is_control_request(no),no)
 def test_owner_choice(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d)
   for a in s.state['agents']:
    if a['name']=='VISION':a['connector']='claude_code'
    if a['name']=='FRIDAY':a['connector']='codex'
   claude='VISION';codex='FRIDAY'
   self.assertEqual(s.control_owner('tamam kontrolü al','common'),claude)
   self.assertEqual(s.control_owner(codex.lower()+' kontrolü al','common'),codex)
   self.assertEqual(s.control_owner('chatgpt kontrolü al','common'),codex)
   self.assertEqual(s.control_owner('kontrolü al',codex),codex)
 def test_request_then_one_tap_grant_then_instant_start(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d);chat=s.state['active_chat']
   s.action('converse',{'text':'tamam kontrolü al','channel':'common'})
   self.assertEqual(self.launched,[])
   last=s.state['messages'][-1];req=last['computer_request']
   self.assertEqual(req['status'],'pending');self.assertEqual(last['author'],'JARVIS')
   s.action('computer-grant',{'id':req['id'],'allow':True})
   self.assertEqual(req['status'],'approved');self.assertIn(chat,s.computer_grants)
   text,channel,kw=self.launched[-1]
   self.assertEqual(channel,'common');self.assertEqual(kw['speaker'],req['owner']);self.assertTrue(kw['computer_work'])
   self.assertTrue(s.desktop_session['auto_actions']);self.assertEqual(s.desktop_session['chat_id'],chat)
   s.desktop_session=None
   s.action('converse',{'text':'bilgisayarı kontrol et, notları aç','channel':'common'})
   self.assertEqual(len(self.launched),2)
   self.assertNotIn('computer_request',s.state['messages'][-1]) 
   self.assertEqual(len([m for m in s.state['messages'] if m.get('computer_request')]),1)
 def test_grant_needs_mac_permissions_and_stays_pending(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d,perms=False)
   s.action('converse',{'text':'kontrolü al','channel':'common'})
   req=s.state['messages'][-1]['computer_request']
   with self.assertRaises(ValueError):s.action('computer-grant',{'id':req['id'],'allow':True})
   self.assertEqual(req['status'],'pending');self.assertEqual(self.launched,[])
 def test_deny_and_stop_revoke(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d)
   s.action('converse',{'text':'kontrolü al','channel':'common'})
   req=s.state['messages'][-1]['computer_request']
   s.action('computer-grant',{'id':req['id'],'allow':False})
   self.assertEqual(req['status'],'denied');self.assertEqual(self.launched,[])
   with self.assertRaises(ValueError):s.action('computer-grant',{'id':req['id'],'allow':True})
   s.computer_grants.add(s.state['active_chat']);s.action('desktop-stop',{})
   self.assertFalse(s.computer_grants)
 def test_the_chat_grant_survives_a_restart_and_stop_takes_back_only_that_chat(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.store(d)
   s.action('converse',{'text':'kontrolü al','channel':'common'})
   req=s.state['messages'][-1]['computer_request']
   s.action('computer-grant',{'id':req['id'],'allow':True})
   chat=s.state['active_chat'];s.desktop_session=None
   self.assertTrue(next(c for c in s.state['chats'] if c['id']==chat)['computer_granted'])
   again=Store(d);self.assertIn(chat,again.computer_grants)   # a new app run does not ask again
   other='other-chat';again.computer_grants.add(other)
   again.action('desktop-stop',{})
   self.assertNotIn(chat,again.computer_grants);self.assertIn(other,again.computer_grants)
   self.assertNotIn(chat,Store(d).computer_grants)
 def test_agent_settings_win_over_hints(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d)
   s.state['auto_effort']=True
   agents={a['name']:a for a in s.state['agents']}
   self.assertFalse(s.honors_settings('EDITH'))
   s.state['auto_effort']=False
   self.assertTrue(s.honors_settings('EDITH'))
   s.state['auto_effort']=True
   edith=agents['EDITH'];model=next(m['id'] for m in s.state['model_catalog']['gemini'] if m['id'].endswith('-medium'))
   s.action('update-agent',{'name':'EDITH','connector':'gemini','model':model,'effort':None})
   self.assertTrue(edith['pinned']);self.assertTrue(s.honors_settings('EDITH'));self.assertEqual(s.depth_label('EDITH'),'medium')
   s.state['jarvis_model_pinned']=False;self.assertFalse(s.honors_settings(None))
   s.action('connection-settings',{'jarvis_connector':'gemini','jarvis_model':model,'pin':True})
   self.assertTrue(s.honors_settings(None))
 def test_existing_agents_become_pinned_once(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.state.pop('agent_pins_v9',None);s.state['starter_free_added']=True
   for a in s.state['agents']:a.pop('pinned',None)
   s.save();st=Store(d).state
   self.assertTrue(st['agent_pins_v9']);self.assertTrue(all(a.get('pinned') for a in st['agents']))
 def test_ui_wiring(self):
  js=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8')
  for needle in ('computer-grant','control-card','data-cc','showMacPermissionHelp','worked-for','stepRow','pin:true'):self.assertIn(needle,js)
  self.assertIn("gemini:'Gemini · Antigravity',claude_google:'Claude · Google'",(ROOT/'static'/'refine.js').read_text(encoding='utf-8'))

class LanguageTests(unittest.TestCase):
 def test_detects_the_language_berke_writes(self):
  from app import detect_language
  for text,want in (('Python dilinde liste ters çevir','tr'),('kanka sen bunu fix et','tr'),('yapmisin sanirim devam et','tr'),('Please fix the bug in the login page','en'),('Hello there, what is next?','en'),('ok',None),('x = [1,2,3]\nprint(x)',None),('```python\nprint(1)\n```',None)):
   self.assertEqual(detect_language(text),want,text)
 def test_agents_follow_the_message_language_not_the_interface_language(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);chat=s.state['active_chat'];s.state['messages']=[]
   s.state['language']='en'
   self.assertEqual(s.reply_language('tamam kanka devam et'),'tr')
   s.state['language']='tr'
   self.assertEqual(s.reply_language('Please explain what this function does and why'),'en')
   self.assertEqual(s.reply_language('Cevabı ingilizce cevap ver'),'en')
   self.assertEqual(s.state['language'],'tr')
 def test_short_messages_keep_the_conversation_language(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);chat=s.state['active_chat'];s.state['language']='tr'
   s.state['messages']=[dict(id='a',author='YOU',text='Please explain what this function does and why',time='2026-11-03 01:00:00',channel='common',chat_id=chat)]
   self.assertEqual(s.reply_language('ok'),'en')
   s.state['messages']=[]
   self.assertEqual(s.reply_language('ok'),'tr')
 def test_converse_never_changes_the_interface_language(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.state['messages']=[];s.state['language']='tr';s.launch_model=lambda *a,**k:{}
   try:s.action('converse',{'text':'Please explain what this function does and why','channel':'common'})
   except Exception:pass
   self.assertEqual(s.state['language'],'tr')
   s.action('connection-settings',{'language':'en'});self.assertEqual(s.state['language'],'en')
 def test_research_rules_are_global_and_answer_in_his_language(self):
  from app import language_rules
  r=language_rules('tr',True)
  self.assertIn('search globally',r);self.assertIn('English',r);self.assertIn('specific to Turkey',r);self.assertIn('Turkish',r)
  self.assertNotIn('RESEARCH SCOPE',language_rules('en',False));self.assertIn('English',language_rules('en',False))
  simple=(ROOT/'static'/'simple.js').read_text(encoding='utf-8')
  self.assertNotIn('language_mode',simple)

class ArchiveGoneTests(unittest.TestCase):
 def test_old_archived_chats_return_to_the_history_list_once(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d);s.state['chats'][0]['archived']=True;s.state.pop('archive_gone_v10',None);s.save()
   s2=Store(d);self.assertFalse(any(c.get('archived') for c in s2.state['chats']))
   s2.state['chats'][0]['archived']=True;s2.save()
   s3=Store(d);self.assertTrue(s3.state['chats'][0]['archived'])
 def test_archive_entry_points_are_gone_from_the_ui(self):
  side=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8');clar=(ROOT/'static'/'clarity.js').read_text(encoding='utf-8')
  self.assertNotIn('data-profile="archive"',side);self.assertNotIn("'archive',tr(",clar)

class PlannedTotalTests(unittest.TestCase):
 def test_step_pill_counts_planned_work_not_only_finished_steps(self):
  js=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8')
  # the plan comes from the running team order and queued tasks, and the pill reads "Step N of M" with M including them
  self.assertIn('function planned()',js);self.assertIn("r.status==='working'||r.status==='presenting'",js)
  self.assertIn("t.status==='queued'",js);self.assertIn('future:true',js);self.assertIn('const cursor=',js)
  self.assertIn('function pillText(items)',js);self.assertIn('cursor(items)+1',js)
  css=(ROOT/'static'/'focus.css').read_text(encoding='utf-8')
  self.assertIn('.ap-timeline li.future',css);self.assertIn('.ap-timeline li.cur',css)

class ActivityLifecycleTests(unittest.TestCase):
 def test_tool_lifecycle_is_counted_once_but_repeated_calls_remain(self):
  import shutil,subprocess,json
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  source=(Path(__file__).resolve().parents[1]/'static/sidebar.js').read_text().split('// END_ACTIVITY_EVENTS')[0]
  def event(state):return dict(kind='search_web',time=state,detail=json.dumps(dict(state=state,parameters=dict(query='Python docs'))))
  events=[event('ACTIVE'),event('RUNNING'),event('DONE'),event('ACTIVE'),event('DONE'),dict(kind='project_command',detail='python3 -m unittest')]
  result=subprocess.run([node,'-e',source+';console.log(JSON.stringify(compactActivityEvents(JSON.parse(process.argv[1]))))',json.dumps(events)],check=True,capture_output=True,text=True)
  rows=json.loads(result.stdout)
  self.assertEqual(len(rows),3);self.assertEqual(rows[0]['first_time'],'ACTIVE');self.assertEqual(rows[-1]['kind'],'project_command')

class NaturalControlTests(unittest.TestCase):
 def test_notes_request_is_control_not_english_negation(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d)
   for text in ('not defterimi acip yeni sayfaya selam berke yazabilir misin','Notes uygulamasını aç ve selam yaz','TextEdit aç'):
    self.assertTrue(s.is_control_request(text),text)
   for text in ('not defteri nasıl açılır','not defterini açma','do not open notes','Python kodu yaz'):
    self.assertFalse(s.is_control_request(text),text)
 def test_build_requests_that_mention_the_browser_are_not_control(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(d)
   for text in ('Tarayıcıda açılan küçük bir yılan oyunu yapın, skor göstersin','Chrome’da çalışan bir hesap makinesi sitesi oluştur','Safari uyumlu bir uygulama geliştir','tarayıcı için açıklama yazılımı hazırla'):
    self.assertFalse(s.is_control_request(text),text)
   for text in ('Chrome’u aç','Safari aç ve haberlere bak','Notes uygulamasını aç ve selam yaz','Takvimi aç ve yarına bak','Open Calculator','Xcode aç'):
    self.assertTrue(s.is_control_request(text),text)
   # The words of a macOS permission dialog quoted in the request do not cancel it; a real refusal still does.
   self.assertTrue(s.is_control_request('FRIDAY, bilgisayarımı kullanarak Safari’yi aç; izin penceresindeki (Allow / Don’t Allow) düğmelerine dokunma'))
   self.assertFalse(s.is_control_request('bilgisayarımı kullanma, Safari’yi açma'))
   self.assertTrue(s.is_control_request('FRIDAY, bilgisayarını kullanarak Notlar’ı aç'))
   self.assertTrue(s.is_control_request('VISION, ekranını kontrol et ve Safari’yi aç'))
   self.assertFalse(s.is_control_request('bilgisayarını kullanma, Safari’yi açma'))
   self.assertFalse(s.is_control_request('Don’t use my computer, just explain'))
   # VS Code is opened with the project tool, and a project chat never turns a build request into screen control.
   self.assertFalse(s.is_control_request('Tarayıcıda oynanan bir oyun yap, sonra projeyi Visual Studio Code ile aç'))
   self.assertTrue(s.is_control_request('FRIDAY, bilgisayarımı kullanarak Visual Studio Code’u aç'))
   s.state['active_project_path']='/tmp/proje';next(c for c in s.state['chats'] if c['id']==s.state['active_chat'])['project_work']=True
   self.assertFalse(s.is_control_request('Safari aç ve haberlere bak'));self.assertTrue(s.is_control_request('Safari aç; bilgisayarımı kullanarak haberlere bak'))

class ComputerShotsTests(unittest.TestCase):
 def test_work_line_shows_real_screen_frames_only(self):
  root=Path(__file__).resolve().parents[1]
  script=(root/'static/sidebar.js').read_text();css=(root/'static/focus.css').read_text()
  self.assertIn("type!=='desktop-result'",script)
  self.assertIn("startsWith('data:image/jpeg')",script)   # frames come from real computer-control results
  self.assertIn("used your computer",script)
  self.assertNotIn('localStorage.setItem(\'jarvis-shots',script)  # never persisted
  for selector in ('.wl-shots','.wl-shot','.wl-more','.shot-lightbox'):self.assertIn(selector,css)
  card=(root/'static/native.js').read_text()
  self.assertIn("api('agent-chat'",card)   # top agent cards open their own chat

 def test_agent_chat_keeps_its_channel_after_restart(self):
  root=Path(__file__).resolve().parents[1]
  card=(root/'static/native.js').read_text()
  # rebuilding the channel list on first render must fall back to the active chat's agent, not to the shared channel
  self.assertIn("$('#channel').value||state.chats.find(c=>c.id===state.active_chat)?.agent||'common'",card)

 def test_computer_control_overlay_is_driven_by_the_session_and_stop_pill_reaches_the_server(self):
  clar=(ROOT/'static'/'clarity.js').read_text(encoding='utf-8')
  # the page tells the Mac app when a control session starts or ends, only when it changes, with the agent's colour; the app does the drawing (no model tokens)
  self.assertIn("nativeSend('desktop-overlay'",clar);self.assertIn("overlayOwner!==lastOverlay",clar);self.assertIn("agentColor(overlayOwner)",clar)
  self.assertIn("{active:false}",clar)
  # glow strength is a page setting sent with the start message, so tuning it needs no new app build
  self.assertIn("const GLOW_LEVEL=0.62,GLOW_DEPTH=44;",clar);self.assertIn("intensity:GLOW_LEVEL,depth:GLOW_DEPTH",clar)
  # the Stop pill of the overlay comes back as an event and stops the session
  self.assertIn("desktop-stop-request')safe(()=>api('desktop-stop'))",clar)
  progress=(ROOT/'static'/'focus.css').read_text(encoding='utf-8')
  self.assertIn('.message.is-progress',progress)

class MacPermissionButtonTests(unittest.TestCase):
 def test_permission_buttons_open_the_settings_page_when_macos_shows_no_prompt(self):
  clar=(ROOT/'static'/'clarity.js').read_text(encoding='utf-8');side=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8')
  # one helper: ask macOS first, and when the permission is still off a moment later, open that Settings page (the app already has this action)
  self.assertIn("function requestMacPermission(kind){",clar);self.assertIn("nativeSend('open-mac-permission',{page:kind})",clar)
  self.assertIn("!(state.desktop_permissions||{})[kind]",clar)
  # every permission button goes through it: the chat message, the This Mac popover and the Mac access link of the control card
  self.assertIn("requestMacPermission(action)",clar);self.assertIn("requestMacPermission(act)",side);self.assertIn("b.dataset.cc==='perm'){requestMacPermission(",side)
  self.assertNotIn("nativeSend('desktop-permissions')",side)
 def test_native_app_has_the_settings_action_for_both_pages(self):
  swift=(ROOT/'native'/'Jarvis.swift').read_text(encoding='utf-8')
  self.assertIn('case "open-mac-permission"',swift);self.assertIn('"screen":"Privacy_ScreenCapture"',swift);self.assertIn('"accessibility":"Privacy_Accessibility"',swift)

class BootSplashTests(unittest.TestCase):
 def test_unfinished_page_layers_stay_hidden_behind_a_quiet_splash_until_the_first_data_is_in(self):
  html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
  self.assertIn('<html lang="tr" class="booting">',html);self.assertIn('html.booting body{visibility:hidden}',html);self.assertIn('html.booting::before{content:"JARVIS"',html)
  # shown again after the first state arrives (jarvis-ready), and never stuck: a timer lifts the splash even when the first request fails
  self.assertIn('window.addEventListener("jarvis-ready"',html);self.assertIn('classList.remove("booting")',html);self.assertIn('setTimeout(done,5000)',html)
  self.assertLess(html.index('/sidebar.js'),html.index('classList.remove("booting")'))

class BackgroundWindowAndTextTests(unittest.TestCase):
 def swift(self):return (ROOT/'native'/'Jarvis.swift').read_text(encoding='utf-8')
 def test_agent_looks_at_the_window_the_app_itself_treats_as_current(self):
  swift=self.swift()
  # a new document or window the agent just opened must be the one it sees, not the app's biggest old window
  self.assertIn('func preferredWindow(',swift);self.assertIn('kAXFocusedWindowAttribute',swift);self.assertIn('kAXMainWindowAttribute',swift)
  self.assertIn('self.preferredWindow(windows,pid:pid) ?? windows.max',swift);self.assertIn('"window_title":window.title',swift)
 def test_click_remembers_the_text_field_it_focused_for_apps_that_report_no_focus_in_the_background(self):
  swift=self.swift()
  self.assertIn('var bgText:(pid:pid_t,element:AXUIElement)?',swift);self.assertIn('func textTarget(',swift);self.assertIn('func textElement(under',swift)
  click=swift[swift.index('func backgroundClick('):swift.index('func backgroundKey(')]
  # text element on the way up first, then hidden beside the visible lines, only then press/select, and a posted click as the last resort
  self.assertLess(click.index('backgroundTextRoles.contains'),click.index('textElement(under'));self.assertLess(click.index('textElement(under'),click.index('kAXPressAction'));self.assertLess(click.index('kAXPressAction'),click.index('postMouseClick'))
  self.assertIn('"hit_path":how.path',swift)
  # code editors (Monaco) keep the real input beside the painted lines: found through the editor container's CSS class
  self.assertIn('domClasses($0).contains("monaco-editor")',swift);self.assertIn('func anyTextElement(under',swift);self.assertIn('"AXDOMClassList"',swift)
  action=swift[swift.index('func performBackgroundAction('):swift.index('func captureDesktopTarget(') if swift.index('func captureDesktopTarget(')>swift.index('func performBackgroundAction(') else len(swift)]
  self.assertIn('textTarget(app,pid:t.pid)',action);self.assertIn('elementLooksLikeTerminal(focused)',action)
 def test_typing_tries_selection_insert_then_value_splice_then_process_keys(self):
  swift=self.swift()
  action=swift[swift.index('case "desktop_type":'):swift.index('case "desktop_key":')]
  self.assertLess(action.index('insertText(focused,text)'),action.index('replaceValue(focused,inserting:text)'));self.assertLess(action.index('replaceValue('),action.index('postText('))
  self.assertIn('AXSecureTextField',action)

class QuotaBannerTests(unittest.TestCase):
 def test_quota_warning_is_one_dismissible_banner_only_below_25_percent_left(self):
  side=(ROOT/'static'/'sidebar.js').read_text(encoding='utf-8');css=(ROOT/'static'/'focus.css').read_text(encoding='utf-8')
  block=side[side.index('// 5-hour quota warning'):side.index('// Read-only system notification permission')]
  self.assertIn("banner.className='quota-banner hidden'",block);self.assertIn("list.before(banner)",block)   # above the chat, not inside it
  self.assertIn("p.used_percent<75",block);self.assertIn("p?.minutes!==300",block)                           # 5-hour window, 25% or less left
  self.assertIn("(state.quota_milestones||[]).includes(key)",block);self.assertIn("api('quota-note'",block)    # dismissed once, gone everywhere
  self.assertIn('data-qb="x"',block);self.assertIn("slice(0,3)",block)
  self.assertNotIn("limit-chip",block);self.assertNotIn("state.messages.some(m=>m.author==='YOU')",block)       # no per-chat chip, no receipt written into chats
  self.assertIn(".quota-banner .qb-x",css)

class LaunchGreetingTests(unittest.TestCase):
 def source(self):
  text=(ROOT/'static'/'native.js').read_text(encoding='utf-8')
  start=text.index('// LAUNCH_GREETINGS');end=text.index('// END_LAUNCH_GREETINGS')
  return text,text[start:end]
 def run_js(self,body):
  import shutil,subprocess
  node=shutil.which('node')
  if not node:self.skipTest('Node unavailable')
  text,block=self.source()
  prelude="const store={};global.localStorage={getItem:k=>store[k]===undefined?null:store[k],setItem:(k,v)=>{store[k]=String(v)}};"
  done=subprocess.run([node,'-e',prelude+block+';'+body],check=True,capture_output=True,text=True)
  return json.loads(done.stdout)
 def test_many_lines_in_both_languages_and_a_few_for_each_time_of_day(self):
  rows=self.run_js("console.log(JSON.stringify(LAUNCH_GREETINGS))")
  self.assertGreaterEqual(len(rows),24);self.assertEqual(len({r[2] for r in rows}),len(rows))
  for r in rows:self.assertTrue(r[2] and r[3] and r[1] in ('any','morning','day','evening','night'),r)
  for when in ('morning','day','evening','night'):self.assertGreaterEqual(len([r for r in rows if r[1]==when]),2,when)
 def test_never_the_same_line_twice_in_a_row_and_time_of_day_lines_only_fit_their_hour(self):
  out=self.run_js("const seen=[];for(let i=0;i<300;i++)seen.push(pickLaunchGreeting(false,Math.random,i%24));"
                  "let repeats=0;for(let i=1;i<seen.length;i++)if(seen[i]===seen[i-1])repeats++;"
                  "const night=[];for(let i=0;i<200;i++)night.push(pickLaunchGreeting(false,Math.random,3));"
                  "const morning=LAUNCH_GREETINGS.filter(r=>r[1]==='morning').map(r=>r[2]);"
                  "console.log(JSON.stringify({repeats,distinct:new Set(seen).size,nightHasMorning:night.some(t=>morning.includes(t)),english:pickLaunchGreeting(true,()=>0,9)}))")
  self.assertEqual(out['repeats'],0);self.assertGreaterEqual(out['distinct'],20);self.assertFalse(out['nightHasMorning'])
  self.assertTrue(out['english'].isascii())
 def test_launch_speaks_a_varied_line_once_per_app_run_replacing_the_fixed_one(self):
  text,_=self.source()
  self.assertIn("nativeSend('ready');",text);self.assertIn("sessionStorage.getItem('jarvis-launch-greeted')!=='1'",text)
  self.assertIn("nativeSend('speak',{text:pickLaunchGreeting(",text)
  # the Mac app's own fixed line stays the fallback and is replaced because speak() stops the running voice first
  swift=(ROOT/'native'/'Jarvis.swift').read_text(encoding='utf-8')
  self.assertIn('listenWanted=false;stopListening(deliver:false);stopSpeech(notify:false)',swift)
