// Collapse lifecycle updates of the same tool call; preserve genuinely repeated calls.
function compactActivityEvents(events){
 const rows=[],pending=new Map();
 for(const event of events){
  let data;try{data=JSON.parse(event.detail);}catch{rows.push(event);continue;}
  const status=String(data.state||'').toUpperCase();
  if(!['ACTIVE','RUNNING','DONE','ERROR','FAILED'].includes(status)){rows.push(event);continue;}
  const key=String(event.kind)+'|'+JSON.stringify(data.id||data.tool_call_id||data.parameters||{}),index=pending.get(key);
  if(index!==undefined){rows[index]={...event,first_time:rows[index].first_time||rows[index].time};}
  else{rows.push(event);}
  if(['DONE','ERROR','FAILED'].includes(status))pending.delete(key);
  else pending.set(key,index===undefined?rows.length-1:index);
 }
 return rows;
}
// END_ACTIVITY_EVENTS
'use strict';
// Agent order everywhere: JARVIS, VISION, FRIDAY, EDITH, NOVA (quick questions), KAREN (free OpenRouter), then any custom role.
const AGENT_ORDER=['JARVIS','VISION','FRIDAY','EDITH','NOVA','KAREN'];
const agentRank=name=>{const i=AGENT_ORDER.indexOf(name);return i<0?AGENT_ORDER.length:i;};
// One colour per agent, the same one as on the agent card; used by the chat, the message rail and the voice settings.
const AGENT_COLORS={JARVIS:'#70d5e8',VISION:'#9bc7a6',FRIDAY:'#e8b760',EDITH:'#a99ee8',NOVA:'#f08a6b',KAREN:'#e9a3c0'};
function agentColor(name){
  const live=typeof state!=='undefined'&&state&&Array.isArray(state.agents)?state.agents.find(a=>a.name===name):null;
  return (live&&live.color)||AGENT_COLORS[name]||'#70d5e8';
}
// ChatGPT-style sidebar: navigation on top, your chats grouped by day below. The existing toggle collapses it to icons.
(()=>{
const rail=document.querySelector('.rail'),bottom=document.querySelector('.rail-bottom');
if(!rail||!bottom)return;
const box=document.createElement('div');box.id='sideChats';box.className='side-chats';box.setAttribute('aria-label',tr('Sohbetler','Chats'));
bottom.before(box);
const KEY='jarvisSidebar';
try{
  const saved=localStorage.getItem(KEY);
  if(saved==='open'||(saved===null&&innerWidth>=1100))document.body.classList.add('rail-expanded');
  else document.body.classList.remove('rail-expanded');
}catch{if(innerWidth>=1100)document.body.classList.add('rail-expanded');}
new MutationObserver(()=>{try{localStorage.setItem(KEY,document.body.classList.contains('rail-expanded')?'open':'closed');}catch{}}).observe(document.body,{attributes:true,attributeFilter:['class']});
function groupOf(chat){
  if(chat.pinned)return [0,tr('Sabitlenenler','Pinned')];
  const d=new Date(String(chat.last_at||chat.created_at||'').replace(' ','T'));
  if(isNaN(d))return [5,tr('Daha eski','Older')];
  const start=new Date();start.setHours(0,0,0,0);
  const days=(start-d)/864e5;
  if(days<=0)return [1,tr('Bugün','Today')];
  if(days<=1)return [2,tr('Dün','Yesterday')];
  if(days<=7)return [3,tr('Önceki 7 gün','Previous 7 days')];
  if(days<=30)return [4,tr('Önceki 30 gün','Previous 30 days')];
  return [5,tr('Daha eski','Older')];
}
// An "empty" chat is one nothing was ever sent in, with no project and no custom name. At most one is kept around.
const isEmptyChat=c=>!c.archived&&!c.user_messages&&!c.active_project&&!c.project_path&&!c.pinned&&c.title_mode!=='manual';
const stampOf=c=>String(c.last_at||c.created_at||'');
function emptyChat(){
  const list=(state.chats||[]).filter(isEmptyChat);
  return list.find(c=>c.id===state.active_chat)||list.sort((a,b)=>stampOf(b).localeCompare(stampOf(a)))[0]||null;
}
freshConversation=async function(){
  chatDrafts[state.active_chat]=$('#prompt').value;
  const target=emptyChat();
  if(target){
    if(target.id!==state.active_chat)await api('select-chat',{id:target.id});
    $('#prompt').value=chatDrafts[target.id]||'';
  }else{
    await api('new-chat');
    $('#prompt').value='';
  }
  $('#channel').value='common';$('#channel').dispatchEvent(new Event('change'));
  await view('mission');
  $('#prompt').focus();
};
let signature='';
function draw(){
  if(typeof state==='undefined'||!state||!state.chats)return;
  const chats=(state.chats||[]).filter(c=>!c.archived&&!isEmptyChat(c));
  const blank=emptyChat();
  const next=JSON.stringify([chats.map(c=>[c.id,c.title,c.pinned,c.last_at,c.created_at]),blank?blank.id:null,state.active_chat,state.language]);
  if(next===signature)return;signature=next;
  const sorted=[...chats].sort((a,b)=>String(b.last_at||b.created_at||'').localeCompare(String(a.last_at||a.created_at||'')));
  const groups=new Map();
  for(const chat of sorted){const [order,label]=groupOf(chat);if(!groups.has(order))groups.set(order,{label,chats:[]});groups.get(order).chats.push(chat);}
  const newLabel=tr('Yeni sohbet','New chat');
  const top=blank
    ?'<div class="side-chat side-new'+(blank.id===state.active_chat?' current':'')+'"><button type="button" class="open" data-side-chat="'+esc(blank.id)+'" title="'+esc(newLabel)+'">'+esc(newLabel)+'</button></div>'
    :'<div class="side-chat side-new"><button type="button" class="open" data-side-new="1" title="'+esc(newLabel)+'">'+esc(newLabel)+'</button></div>';
  box.innerHTML=top+[...groups.entries()].sort((a,b)=>a[0]-b[0]).map(([,g])=>
    '<div class="side-group">'+esc(g.label)+'</div>'+g.chats.map(c=>
      '<div class="side-chat'+(c.id===state.active_chat?' current':'')+'"><button type="button" class="open" data-side-chat="'+esc(c.id)+'" title="'+esc(c.title)+'">'+esc(c.title)+'</button><button type="button" class="more" data-history-menu="'+esc(c.id)+'" aria-label="'+esc(c.title)+' · '+tr('seçenekler','options')+'">⋯</button></div>'
    ).join('')).join('');
}
box.addEventListener('click',e=>{
  const more=e.target.closest('[data-history-menu]');
  if(more){showConversationMenu(more.dataset.historyMenu,more);return;}
  if(e.target.closest('[data-side-new]')){safe(freshConversation);return;}
  const open=e.target.closest('[data-side-chat]');
  if(!open)return;
  const id=open.dataset.sideChat;
  safe(async()=>{
    if(id!==state.active_chat){chatDrafts[state.active_chat]=$('#prompt').value;await api('select-chat',{id});$('#prompt').value=chatDrafts[id]||'';}
    await view('mission');
  });
});
const previous=renderWorkspace;renderWorkspace=function(){
  previous();
  document.querySelectorAll('.agent').forEach(card=>{card.style.order=String(agentRank(card.querySelector('h2')?.textContent||''));});
  const fresh=document.querySelector('.rail-btn[data-view="fresh-chat"] small');
  if(fresh)fresh.textContent=tr('Yeni sohbet','New chat');
  draw();
};
draw();
})();

// Profile menu at the bottom of the sidebar: history, archive, remaining quota and settings in one place.
(()=>{
const bottom=document.querySelector('.rail-bottom'),avatar=bottom?.querySelector('.avatar'),gear=bottom?.querySelector('.rail-btn[data-view="settings"]');
if(!bottom||!avatar)return;
const svg=d=>'<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>';
const icons={
  history:svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  archive:svg('<rect x="3.5" y="4.5" width="17" height="4" rx="1"/><path d="M5 8.5V18a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18V8.5M10 12.5h4"/>'),
  quota:svg('<path d="M4.5 16a7.5 7.5 0 1 1 15 0"/><path d="m12 16 3.5-4.5"/>'),
  settings:svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 14.5a1.6 1.6 0 0 0 .3 1.7l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.7.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.7.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.7-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.7v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z"/>'),
  chevron:svg('<path d="m9 6 6 6-6 6"/>')
};
const button=document.createElement('button');button.type='button';button.id='profileButton';button.className='profile-button';
button.setAttribute('aria-haspopup','menu');button.setAttribute('aria-expanded','false');button.setAttribute('aria-label',tr('Profil menüsü','Profile menu'));
button.innerHTML='<span class="profile-avatar">B</span><span class="profile-name">Berke</span>';
avatar.style.display='none';if(gear)gear.classList.add('profile-hidden');
bottom.append(button);
document.querySelector('.rail-btn[data-view="project"]')?.classList.add('profile-hidden');
const menu=document.createElement('div');menu.className='profile-menu hidden';menu.setAttribute('role','menu');document.body.append(menu);
let quotaOpen=false;
function quotaRows(){
  const rows=[...document.querySelectorAll('.agent')].filter(card=>card.style.display!=='none').sort((a,b)=>agentRank(a.querySelector('h2')?.textContent||'')-agentRank(b.querySelector('h2')?.textContent||'')).map(card=>{
    const name=card.querySelector('h2')?.textContent||'',value=card.querySelector('.agent-summary')?.textContent||'';
    return name&&value?'<div class="profile-quota"><span>'+esc(name)+'</span><b>'+esc(value)+'</b></div>':'';
  }).join('');
  return rows||'<div class="profile-quota"><span>'+esc(tr('Henüz kota bilgisi yok','No limit data yet'))+'</span></div>';
}
function render(){
  menu.innerHTML=
    '<div class="profile-head"><span class="profile-avatar big">B</span><div><b>Berke</b><small>'+esc(tr('JARVIS çalışma alanı','JARVIS workspace'))+'</small></div></div>'+
    '<div class="profile-sep"></div>'+
    '<button type="button" role="menuitem" class="profile-item" data-profile="quota" aria-expanded="'+quotaOpen+'">'+icons.quota+'<span>'+esc(tr('Kalan kota','Usage remaining'))+'</span><i class="profile-chevron'+(quotaOpen?' open':'')+'">'+icons.chevron+'</i></button>'+
    (quotaOpen?'<div class="profile-quotas">'+quotaRows()+'</div>':'')+
    '<button type="button" role="menuitem" class="profile-item" data-profile="history">'+icons.history+'<span>'+esc(tr('Sohbet geçmişi','Chat history'))+'</span></button>'+
    '<div class="profile-sep"></div>'+
    '<button type="button" role="menuitem" class="profile-item" data-profile="settings">'+icons.settings+'<span>'+esc(tr('Ayarlar','Settings'))+'</span><kbd>⌘,</kbd></button>';
}
function openMenu(){render();menu.classList.remove('hidden');button.setAttribute('aria-expanded','true');
  const r=button.getBoundingClientRect();menu.style.left=Math.max(8,r.left)+'px';menu.style.bottom=(innerHeight-r.top+8)+'px';}
function closeMenu(){menu.classList.add('hidden');button.setAttribute('aria-expanded','false');}
button.addEventListener('click',e=>{e.stopPropagation();menu.classList.contains('hidden')?openMenu():closeMenu();});
menu.addEventListener('click',e=>{
  e.stopPropagation();
  const item=e.target.closest('[data-profile]');if(!item)return;
  const act=item.dataset.profile;
  if(act==='quota'){quotaOpen=!quotaOpen;render();return;}
  closeMenu();
  if(act==='history')safe(()=>view('project'));
  else if(act==='archive')document.querySelector('.archive-list')?.click();
  else if(act==='settings')safe(()=>view('settings'));
});
document.addEventListener('click',e=>{if(!e.target.closest('.profile-menu,#profileButton'))closeMenu();});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&!menu.classList.contains('hidden'))closeMenu();
  if(e.metaKey&&e.key===','){e.preventDefault();safe(()=>view('settings'));}
});
})();

// This Mac: connection indicator at the top right with what JARVIS may use and shortcuts to the permission screens.
(()=>{
const btn=document.createElement('button');btn.type='button';btn.id='deviceButton';btn.className='device-button';
btn.setAttribute('aria-haspopup','dialog');btn.setAttribute('aria-expanded','false');
btn.innerHTML='<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4.5" y="5" width="15" height="10.5" rx="1.6"/><path d="M2.5 19h19"/></svg><i class="device-dot"></i>';
const pop=document.createElement('div');pop.className='device-pop hidden';pop.setAttribute('role','dialog');
document.body.append(pop);
const bottomBar=document.querySelector('.rail-bottom'),profileBtn=document.getElementById('profileButton');
if(bottomBar){const row=document.createElement('div');row.className='profile-row';if(profileBtn)row.append(profileBtn);row.append(btn);bottomBar.append(row);}else document.body.append(btn);
const known=p=>p&&typeof p.screen==='boolean'&&typeof p.accessibility==='boolean';
function status(){
  if(!nativeHost)return {level:'off',title:tr('Yalnızca tarayıcı','Browser only'),text:tr('JARVIS.app dışında açık. Mac dosya ve uygulama erişimi yok.','Opened outside JARVIS.app. No Mac file or app access.')};
  const p=state?.desktop_permissions;
  if(known(p)&&p.screen&&p.accessibility)return {level:'ok',title:tr('Bağlı','Connected'),text:tr('İzinler hazır. Kontrolü sohbetten başlatabilirsin.','Permissions ready. Start control from chat.')};
  if(known(p))return {level:'warn',title:tr('Mac izni gerekli','Mac permission needed'),text:tr('Kapalı iznin yanındaki Aç düğmesine bas.','Click Open beside the missing permission.')};
  return {level:'warn',title:tr('Bağlı · izinler kontrol ediliyor','Connected · checking permissions'),text:tr('Mac izin durumu okunuyor.','Reading Mac permission status.')};
}
const SHORT={codex:'Codex',gemini:'Gemini',claude_google:'Claude · Antigravity',claude_code:'Claude Code',openrouter:'OpenRouter',local:tr('Yerel','Local'),manual:tr('Manuel','Manual')};
const USAGE_KEY={codex:'FRIDAY',gemini:'EDITH',claude_code:'CLAUDE_PRO'};
let testing=false;const testErrors={};
function connAgents(){
  const list=[{name:'JARVIS',connector:state?.jarvis_connector||'gemini'}];
  for(const a of (state?.agents||[]))if(a.enabled!==false&&a.name!=='JARVIS')list.push({name:a.name,connector:a.connector});
  return list.sort((x,y)=>agentRank(x.name)-agentRank(y.name));
}
const testable=a=>!['manual','local'].includes(a.connector)&&!(a.connector==='openrouter'&&!state?.free_key_available);
function connRow(a){
  const rec=state?.connection_tests?.[a.name],usage=state?.provider_usage?.[USAGE_KEY[a.connector]];
  const clock=ts=>ts?new Date(ts*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'';
  let level='off',text=tr('Test edilmedi','Not tested');
  if(a.connector==='manual'){text=tr('Manuel rol','Manual role');}
  else if(a.connector==='openrouter'&&!state?.free_key_available){text=tr('Anahtar gerekli','Key required');}
  else if(testErrors[a.name]){level='bad';text=testErrors[a.name];}
  else if(rec?.status==='testing'){level='busy';text=tr('Test ediliyor…','Testing…');}
  else if(rec?.status==='ready'){level='ok';text=tr('Çalışıyor','Working')+' · '+clock(rec.checked_at);}
  else if(rec?.status==='error'){level='bad';text=String(rec.message||tr('Hata','Error')).slice(0,70);}
  else if(usage?.status==='live'){level='soft';text=tr('Bağlı · kota okunuyor','Linked · limits readable');}
  return '<div class="device-conn-row" title="'+esc(text)+'"><i class="device-dot inline" data-level="'+level+'"></i><b>'+esc(a.name)+'</b><span>'+esc(SHORT[a.connector]||a.connector)+'</span><em>'+esc(text)+'</em></div>';
}
async function runTests(){
  if(testing)return;testing=true;paint();
  for(const a of connAgents()){
    if(!testable(a))continue;
    delete testErrors[a.name];
    try{await api('test-agent',{name:a.name});}catch(error){testErrors[a.name]=String(error.message||error).slice(0,70);paint();continue;}
    const started=Date.now();
    while(Date.now()-started<150000){
      await new Promise(r=>setTimeout(r,1500));
      try{await refresh();}catch{}
      if(state?.connection_tests?.[a.name]?.status!=='testing')break;
    }
    paint();
  }
  testing=false;paint();
}
const mark=on=>'<b class="'+(on?'on':'off')+'">'+esc(on?tr('Açık','On'):tr('Kapalı','Off'))+'</b>';
function paint(){
  const s=status();btn.dataset.level=s.level;btn.setAttribute('aria-label',tr('Bu Mac','This Mac')+' · '+s.title);btn.title=tr('Bu Mac','This Mac')+' · '+s.title;
  if(pop.classList.contains('hidden'))return;
  const p=state?.desktop_permissions,session=state?.desktop_session;
  const html=
    '<div class="device-title">'+esc(tr('Bu Mac','This Mac'))+'</div>'+
    '<div class="device-status"><i class="device-dot inline" data-level="'+s.level+'"></i><span>'+esc(s.title)+'</span></div>'+
    '<p>'+esc(s.text)+'</p>'+
    (nativeHost&&known(p)?'<div class="device-rows"><div><span>'+esc(tr('Ekran kaydı','Screen recording'))+'</span>'+(p.screen?mark(true):'<button type="button" data-device="screen">'+esc(tr('Aç','Open'))+'</button>')+'</div><div><span>'+esc(tr('Erişilebilirlik','Accessibility'))+'</span>'+(p.accessibility?mark(true):'<button type="button" data-device="accessibility">'+esc(tr('Aç','Open'))+'</button>')+'</div></div>':'')+
    (session?'<div class="device-session">'+esc(tr('Kontrol oturumu açık','Control session active'))+(session.owner?' · '+esc(session.owner):'')+'</div>':'')+
    '<div class="device-conn"><div class="device-conn-head"><span>'+esc(tr('Bağlantılar','Connections'))+'</span><button type="button" data-device="test"'+(testing?' disabled':'')+'>'+esc(testing?tr('Test ediliyor…','Testing…'):tr('Hepsini test et','Test all'))+'</button></div>'+connAgents().map(connRow).join('')+'<small>'+esc(tr('Test, her bağlantıya tek kelimelik bir mesaj gönderir; çok az kota harcar.','The test sends a one-word message to each connection; it uses very little quota.'))+'</small></div>'+
    '<div class="device-actions">'+
    (nativeHost?'<button type="button" data-device="app">'+esc(tr('JARVIS’i Finder’da göster','Show JARVIS in Finder'))+'</button><button type="button" data-device="refresh">'+esc(tr('Kontrol et','Check'))+'</button>':'')+
    (session?'<button type="button" class="danger" data-device="stop">'+esc(tr('Kontrolü durdur','Stop control'))+'</button>':'')+
    '</div>';
  if(pop.dataset.html!==html){pop.dataset.html=html;pop.innerHTML=html;}
}
function open(){pop.classList.remove('hidden');btn.setAttribute('aria-expanded','true');if(nativeHost)nativeSend('desktop-status');paint();place();}
function place(){const r=btn.getBoundingClientRect();pop.style.left=Math.max(8,Math.min(r.left,innerWidth-pop.offsetWidth-8))+'px';pop.style.bottom=Math.max(8,innerHeight-r.top+8)+'px';pop.style.top='auto';}
function close(){pop.classList.add('hidden');btn.setAttribute('aria-expanded','false');}
btn.addEventListener('click',e=>{e.stopPropagation();pop.classList.contains('hidden')?open():close();});
pop.addEventListener('click',e=>{
  e.stopPropagation();
  const item=e.target.closest('[data-device]');if(!item)return;
  const act=item.dataset.device;
  if(act==='test'){runTests();return;}
  close();
  if(act==='screen'||act==='accessibility')requestMacPermission(act);
  else if(act==='app')nativeSend('reveal-jarvis-app');
  else if(act==='refresh')nativeSend('desktop-status');
  else if(act==='mac')showMacPermissionHelp();
  else if(act==='stop')document.querySelector('.computer-session button')?.click();
});
document.addEventListener('click',e=>{if(!e.target.closest('.device-pop,#deviceButton'))close();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();if(!pop.classList.contains('hidden'))place();};
if(nativeHost)setTimeout(()=>nativeSend('desktop-status'),1500);
paint();
})();

// One place for permissions: the shield in the chat opens a compact picker (like an approval dropdown).
// Project access is per chat and goes straight to the backend; Mac control stays a separate, time-limited session.
(()=>{
if(typeof permissionButton==='undefined')return;
const MODES=[
  ['read_only',()=>tr('Salt okunur','Read only'),()=>tr('Sohbet: proje dosyalarına dokunulmaz','Chat only: project files are never touched'),'calm'],
  ['ask',()=>tr('Her seferinde sor','Ask for approval'),()=>tr('Dosya düzenleme ve komutlar için önce sen onaylarsın','You approve every edit and command first'),'calm'],
  ['auto_files',()=>tr('Dosyaları düzenleyebilir','Edit files'),()=>tr('Seçili projede düzenleme sorulmaz; komutlar yine sorar','Edits in the selected project run without asking; commands still ask'),'write'],
  ['turbo',()=>tr('Tam erişim · Turbo','Full access · Turbo'),()=>tr('Düzenleme ve izinli testler sormadan çalışır. İnternet kapalı, klasör dışına çıkılmaz','Edits and allow-listed tests run without asking. Network off, nothing outside the folder'),'full']
];
const check='<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.2 4.2L19 7"/></svg>';
const menu=document.createElement('div');menu.className='perm-menu hidden';menu.setAttribute('role','menu');document.body.append(menu);
const currentMode=()=>{const chat=(state?.chats||[]).find(c=>c.id===state.active_chat);return chat?.work_permission||'ask';};
const modeOf=id=>MODES.find(m=>m[0]===id)||MODES[1];
function paintButton(){
  const [id,label,,tone]=modeOf(currentMode());
  let span=permissionButton.querySelector('.perm-label');
  if(!span){span=document.createElement('span');span.className='perm-label';permissionButton.append(span);}
  const text=label();if(span.textContent!==text)span.textContent=text;
  permissionButton.dataset.tone=tone;permissionButton.dataset.mode=id;
  permissionButton.title=tr('İzinler · ','Permissions · ')+text;permissionButton.setAttribute('aria-label',permissionButton.title);
  permissionButton.setAttribute('aria-haspopup','menu');
}
function render(){
  const now=currentMode();
  menu.innerHTML=
    '<div class="perm-head">'+esc(tr('Bu sohbette ajanlar projeye nasıl erişsin?','How may agents work on the project in this chat?'))+'</div>'+
    MODES.map(([id,label,note,tone])=>'<button type="button" role="menuitemradio" aria-checked="'+(id===now)+'" class="perm-item tone-'+tone+(id===now?' current':'')+'" data-mode="'+id+'"><span><b>'+esc(label())+'</b><small>'+esc(note())+'</small></span>'+(id===now?check:'')+'</button>').join('')+
    '<p class="perm-scope">'+esc(typeof projectScopeSummary==='function'?projectScopeSummary():'')+'</p>'+
    '<div class="perm-sep"></div>'+
    '<div class="perm-mac"><span><b>'+esc(tr('Mac kontrolü ayrı','Mac control is separate'))+'</b><small>'+esc(tr('Süreli oturum, her görevde sorulur; macOS izinlerini sen verirsin.','Time-limited session, asked per task; you grant the macOS permissions.'))+'</small></span><button type="button" data-perm="mac">'+esc(tr('Bu Mac','This Mac'))+'</button></div>'+
    '<details class="perm-agents"><summary>'+esc(tr('Ajan yetenekleri','Agent capabilities'))+'</summary>'+((state?.agents||[]).slice().sort((a,b)=>agentRank(a.name)-agentRank(b.name)).map(a=>'<p><b>'+esc(a.name)+'</b> · '+esc(typeof agentPermissionSummary==='function'?agentPermissionSummary(a):'')+'</p>').join(''))+'</details>';
}
function place(){const r=permissionButton.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(r.left,innerWidth-menu.offsetWidth-8))+'px';menu.style.bottom=Math.max(8,innerHeight-r.top+8)+'px';}
function open(){render();menu.classList.remove('hidden');place();permissionButton.setAttribute('aria-expanded','true');}
function close(){menu.classList.add('hidden');permissionButton.setAttribute('aria-expanded','false');}
permissionButton.onclick=e=>{e.stopPropagation();menu.classList.contains('hidden')?open():close();};
menu.addEventListener('click',e=>{
  e.stopPropagation();
  if(e.target.closest('[data-perm="mac"]')){close();document.getElementById('deviceButton')?.click();return;}
  const item=e.target.closest('[data-mode]');if(!item)return;
  close();
  if(item.dataset.mode!==currentMode())safe(()=>api('project-permission',{mode:item.dataset.mode}));
});
document.addEventListener('click',e=>{if(!e.target.closest('.perm-menu,.permission-button'))close();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
const previous=renderWorkspace;renderWorkspace=function(){previous();paintButton();if(!menu.classList.contains('hidden'))render();};
paintButton();
})();

// Agent colours in the chat: every reply carries its agent's accent (letter, name and a thin line), same colour as the card.
(()=>{
const list=document.getElementById('messages');
if(!list)return;
function paint(){
  list.querySelectorAll('.message').forEach(row=>{
    if(row.classList.contains('you'))return;
    const name=(row.querySelector('.message-meta')?.firstChild?.textContent||'').trim();
    if(!name)return;
    const color=agentColor(name);
    if(row.dataset.agent!==name)row.dataset.agent=name;
    if(row.style.getPropertyValue('--agent')!==color)row.style.setProperty('--agent',color);
  });
}
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();};
paint();
})();

// "+" opens a small menu right above the message box (like a tool picker) instead of a block at the top of the chat.
(()=>{
if(typeof tools==='undefined'||typeof toolsButton==='undefined')return;
document.body.append(tools);tools.classList.add('as-menu');tools.setAttribute('role','menu');
const icon=body=>'<svg class="tool-icon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+body+'</svg>';
const ICONS={
  photo:icon('<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="m4 17 5-4.5 4 3.5 3-2.5 4 3.5"/>'),
  folder:icon('<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>'),
  screen:icon('<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/>')
};
function decorate(){
  tools.querySelectorAll('.tools-main > button').forEach(button=>{
    const kind=button.id==='shareScreenFromChat'?'screen':/klasör|folder/i.test(button.textContent)?'folder':'photo';
    if(!button.querySelector('.tool-icon'))button.insertAdjacentHTML('afterbegin',ICONS[kind]);
    button.dataset.hint={photo:tr('Görsel, PDF, metin','Image, PDF, text'),folder:tr('Kod ve dosyalar','Code and files'),screen:tr('Ekranını göster','Show your screen')}[kind];
    button.setAttribute('role','menuitem');
  });
}
function place(){
  if(tools.classList.contains('hidden'))return;
  const r=toolsButton.getBoundingClientRect();
  tools.style.left=Math.max(8,Math.min(r.left-4,innerWidth-tools.offsetWidth-8))+'px';
  tools.style.bottom=Math.max(8,innerHeight-r.top+10)+'px';
}
new MutationObserver(()=>{decorate();place();}).observe(tools,{attributes:true,attributeFilter:['class']});
tools.addEventListener('click',e=>{if(e.target.closest('.tools-main > button'))setTimeout(()=>tools.classList.add('hidden'),0);});
document.addEventListener('click',e=>{if(!tools.classList.contains('hidden')&&!e.target.closest('#chatTools,#toolsButton'))tools.classList.add('hidden');});
window.addEventListener('resize',place);
const previous=renderWorkspace;renderWorkspace=function(){previous();decorate();place();};
decorate();
})();

// Agent voices: one local voice per agent (JARVIS female, VISION male, ...), chosen here and played by the Mac app.
(()=>{
const host=document.querySelector('.personal-preferences');
if(!host)return;
const VOICES=[
  ['F4',()=>tr('Kadın · parlak','Female · bright')],['F3',()=>tr('Kadın · yumuşak','Female · soft')],['F5',()=>tr('Kadın · sıcak','Female · warm')],
  ['F1',()=>tr('Kadın · dengeli','Female · balanced')],['F2',()=>tr('Kadın · alternatif','Female · alternative')],
  ['M3',()=>tr('Erkek · derin','Male · deep')],['M4',()=>tr('Erkek · sıcak','Male · warm')],['M5',()=>tr('Erkek · net','Male · clear')],
  ['M1',()=>tr('Erkek · dengeli','Male · balanced')],['M2',()=>tr('Erkek · alternatif','Male · alternative')]
];
let picks={JARVIS:'F4',VISION:'M3',FRIDAY:'M5',EDITH:'F3',NOVA:'F2',KAREN:'M2'};
const box=document.createElement('div');box.className='agent-voices';host.append(box);
let signature='';
const names=()=>{
  const live=(typeof state!=='undefined'&&state&&Array.isArray(state.agents)?state.agents.map(a=>a.name):[]).filter(n=>/^[A-Za-z][A-Za-z0-9_-]{0,19}$/.test(n));
  return [...new Set(['JARVIS',...live])].sort((a,b)=>agentRank(a)-agentRank(b));
};
function draw(force){
  const list=names(),key=list.join(',')+JSON.stringify(picks)+(typeof state!=='undefined'&&state?state.language:'');
  if(!force&&key===signature)return;signature=key;
  box.innerHTML='<h4>'+esc(tr('Ajan sesleri','Agent voices'))+'</h4><p class="muted">'+esc(tr('Her ajan kendi sesiyle konuşur. Sesler bu Mac’te üretilir, internet gerekmez.','Each agent speaks with its own voice. Voices are generated on this Mac, no internet needed.'))+'</p>'+
    list.map(n=>'<div class="agent-voice-row" data-voice-row="'+esc(n)+'"><span class="agent-voice-dot"></span><b>'+esc(n)+'</b><select aria-label="'+esc(n)+'" data-voice-agent="'+esc(n)+'">'+
      VOICES.map(([id,label])=>'<option value="'+id+'"'+(picks[n]===id||(!picks[n]&&id==='F4')?' selected':'')+'>'+esc(label())+'</option>').join('')+
    '</select><button type="button" class="button small" data-voice-test="'+esc(n)+'">'+esc(tr('Dinle','Listen'))+'</button></div>').join('');
  box.querySelectorAll('.agent-voice-row').forEach(row=>row.style.setProperty('--agent',agentColor(row.dataset.voiceRow)));
}
box.addEventListener('change',e=>{
  const select=e.target.closest('[data-voice-agent]');if(!select)return;
  const name=select.dataset.voiceAgent;picks[name]=select.value;signature='';
  nativeSend('preferences',{agentVoices:{[name]:select.value}});
});
box.addEventListener('click',e=>{
  const button=e.target.closest('[data-voice-test]');if(!button)return;
  const name=button.dataset.voiceTest,select=box.querySelector('[data-voice-agent="'+name+'"]');
  nativeSend('speak',{agent:name,voice:select?select.value:undefined,text:tr('Merhaba Berke, ben '+name+'. Sesim böyle; anladım, sonuçları sohbete gönderiyorum.','Hello Berke, I am '+name+'. This is my voice; understood, I am sending the results to the chat.')});
});
window.addEventListener('jarvis-native',e=>{
  if(e.detail.type==='agent-voices'&&e.detail.data&&e.detail.data.voices){picks={...picks,...e.detail.data.voices};draw(true);}
});
const previous=renderWorkspace;renderWorkspace=function(){previous();draw();};
draw(true);
if(nativeHost)setTimeout(()=>nativeSend('agent-voices'),1200);
})();

// Model picker next to the microphone (like a ChatGPT/Gemini model menu): you choose the model and its depth yourself;
// nothing switches automatically. Works for JARVIS and every agent of the open channel.
(()=>{
const mic=document.getElementById('micButton'),channelBox=document.getElementById('channel');
if(!mic||!channelBox)return;
const DEPTH={low:['Low',()=>tr('En hızlı, az düşünür','Fastest, thinks little')],medium:['Medium',()=>tr('Dengeli derinlik','Balanced depth')],high:['High',()=>tr('Daha çok düşünür','Extra thorough')],xhigh:['Extra high',()=>tr('Çok derin','Extra deep')],max:['Max',()=>tr('En derin','Maximum')]};
const TIER=/-(low|medium|high)$/;
const pill=document.createElement('button');pill.type='button';pill.id='modelPill';pill.className='model-pill';pill.setAttribute('aria-haspopup','menu');pill.setAttribute('aria-expanded','false');
mic.before(pill);
const menu=document.createElement('div');menu.className='model-menu hidden';menu.setAttribute('role','menu');document.body.append(menu);
const catalog=c=>((typeof state!=='undefined'&&state&&state.model_catalog)||{})[c]||[];
function groups(connector){
  const map=new Map();
  for(const m of catalog(connector)){
    const tier=(connector==='gemini'||connector==='claude_google')?(m.id.match(TIER)||[])[1]:null;
    const key=tier?m.id.replace(TIER,''):m.id;
    if(!map.has(key))map.set(key,{key,id:m.id,name:String(m.name||m.id||tr('Otomatik model','Automatic model')).replace(/\s*\((low|medium|high)\)\s*$/i,''),tiers:{},efforts:m.efforts||[]});
    if(tier)map.get(key).tiers[tier]=m.id;
  }
  return [...map.values()];
}
function current(){
  if(typeof state==='undefined'||!state)return null;
  const channel=channelBox.value||'common';
  const routed=channel==='common'&&state.jarvis_agent&&state.jarvis_agent!=='AUTO'?state.jarvis_agent:channel;
  if(routed==='common'){return {who:'JARVIS',jarvis:true,connector:state.jarvis_connector||'gemini',model:state.jarvis_model||'',effort:null,pinned:!!state.jarvis_model_pinned};}
  const a=(state.agents||[]).find(x=>x.name===routed);
  return a?{who:a.name,jarvis:false,connector:a.connector,model:a.model||'',effort:a.effort||null,pinned:true}:null;
}
const keyOf=(cur)=>cur.model.replace(TIER,'');
const tierOf=cur=>(cur.model.match(TIER)||[])[1]||null;
const depthOf=cur=>cur.connector==='gemini'||cur.connector==='claude_google'?tierOf(cur):cur.effort;
function short(name){return String(name).replace(/^Gemini\s+/,'').replace(/\s*·.*$/,'');}
function describe(cur){
  const group=groups(cur.connector).find(g=>g.key===keyOf(cur)||g.id===cur.model);
  const name=group?short(group.name):(cur.model||tr('Otomatik','Automatic'));
  const depth=depthOf(cur);
  return {name,depth:depth&&DEPTH[depth]?DEPTH[depth][0]:'',auto:cur.jarvis&&cur.connector==='gemini'&&!cur.pinned};
}
function paint(){
  const cur=current();
  pill.hidden=!cur;if(!cur)return;
  const d=describe(cur);
  const text=d.auto?tr('Otomatik','Automatic'):d.name+(d.depth?' · '+d.depth:'');
  if(pill.dataset.text!==text){pill.dataset.text=text;pill.innerHTML='<span>'+esc(text)+'</span><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';}
  pill.title=cur.who+' · '+text+(d.auto?'':tr(' · sabit, kendiliğinden değişmez',' · fixed, never switches by itself'));
  pill.setAttribute('aria-label',pill.title);
}
const check='<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.2 4.2L19 7"/></svg>';
function note(name){
  const n=name.toLowerCase();
  if(/lite/.test(n))return tr('En hızlı yanıtlar','Fastest answers');
  if(/flash/.test(n))return tr('Her iş için dengeli yardım','All-around help');
  if(/\bpro\b/.test(n))return tr('Gelişmiş akıl yürütme','Advanced reasoning');
  if(/opus/.test(n))return tr('En güçlü Claude','Most capable Claude');
  if(/sonnet/.test(n))return tr('Dengeli Claude','Balanced Claude');
  if(/haiku/.test(n))return tr('Hızlı Claude','Fast Claude');
  if(/gpt-oss/.test(n))return tr('OpenAI’nin açık modeli · Antigravity ile gelir','OpenAI’s open model · included with Antigravity');
  return '';
}
function render(){
  const cur=current();if(!cur){menu.innerHTML='';return;}
  const list=groups(cur.connector),sel=list.find(g=>g.key===keyOf(cur)||g.id===cur.model);
  const isGemini=cur.connector==='gemini'||cur.connector==='claude_google';
  const depths=sel?(isGemini?['low','medium','high'].filter(d=>sel.tiers[d]):sel.efforts.filter(d=>DEPTH[d])):[];
  const now=depthOf(cur);
  let html='<div class="mm-head">'+esc(cur.who)+'</div>';
  if(cur.jarvis&&cur.connector==='gemini')html+='<button type="button" role="menuitemradio" aria-checked="'+(!cur.pinned)+'" class="mm-item" data-auto="1"><span><b>'+esc(tr('Otomatik','Automatic'))+'</b><small>'+esc(tr('JARVIS mesaja göre derinliği kendi seçer','JARVIS picks the depth per message'))+'</small></span>'+(!cur.pinned?check:'')+'</button>';
  html+=list.map(g=>{const on=!!sel&&g===sel&&(cur.pinned||!cur.jarvis);return '<button type="button" role="menuitemradio" aria-checked="'+on+'" class="mm-item" data-model="'+esc(g.key)+'"><span><b>'+esc(short(g.name))+'</b><small>'+esc(note(g.name))+'</small></span>'+(on?check:'')+'</button>';}).join('');
  if(depths.length>1){
    html+='<div class="mm-sep"></div>'+depths.map(d=>'<button type="button" role="menuitemradio" aria-checked="'+(now===d)+'" class="mm-item" data-depth="'+d+'"><span><b>'+esc(DEPTH[d][0])+'</b><small>'+esc(DEPTH[d][1]())+'</small></span>'+(now===d?check:'')+'</button>').join('');
  }
  if(isGemini)html+='<p class="mm-foot">'+esc(tr('Bu liste Antigravity’den gelir. Google Pro veya Flash-Lite eklediğinde burada kendiliğinden görünür.','This list comes from Antigravity. When Google adds Pro or Flash-Lite there, they appear here by themselves.'))+'</p>';
  html+='<div class="mm-sep"></div><button type="button" role="menuitemcheckbox" aria-checked="'+(state.auto_effort!==false)+'" class="mm-item mm-toggle" data-auto-effort="1"><span><b>'+esc(tr('Derinliği kendiliğinden ayarla','Adjust depth automatically'))+'</b><small>'+esc(tr('Kapalıyken hiçbir ajan seçtiğin model ve derinliğin dışına çıkmaz','When off, no agent leaves the model and depth you picked'))+'</small></span>'+(state.auto_effort!==false?check:'')+'</button>';
  menu.innerHTML=html;
}
async function apply(cur,group,depth){
  const isGemini=cur.connector==='gemini'||cur.connector==='claude_google';
  if(isGemini){
    const id=group.tiers[depth]||group.tiers.medium||Object.values(group.tiers)[0]||group.id;
    if(cur.jarvis)await api('connection-settings',{jarvis_connector:cur.connector,jarvis_model:id,pin:true});
    else await api('update-agent',{name:cur.who,connector:cur.connector,model:id,effort:null});
    return;
  }
  const effort=depth&&group.efforts.includes(depth)?depth:(group.efforts.includes('medium')?'medium':(group.efforts[0]||null));
  if(cur.jarvis)await api('connection-settings',{jarvis_connector:cur.connector,jarvis_model:group.id,pin:true});
  else await api('update-agent',{name:cur.who,connector:cur.connector,model:group.id,effort});
}
function place(){const r=pill.getBoundingClientRect();menu.style.right=Math.max(8,innerWidth-r.right)+'px';menu.style.bottom=Math.max(8,innerHeight-r.top+8)+'px';}
function open(){render();menu.classList.remove('hidden');place();pill.setAttribute('aria-expanded','true');}
function close(){menu.classList.add('hidden');pill.setAttribute('aria-expanded','false');}
pill.addEventListener('click',e=>{e.stopPropagation();menu.classList.contains('hidden')?open():close();});
menu.addEventListener('click',e=>{
  e.stopPropagation();
  const cur=current();if(!cur)return;
  if(e.target.closest('[data-auto-effort]')){safe(()=>api('connection-settings',{auto_effort:state.auto_effort===false}));close();return;}
  if(e.target.closest('[data-auto]')){close();safe(()=>api('connection-settings',{jarvis_connector:'gemini',jarvis_model:'auto'}));return;}
  const list=groups(cur.connector),sel=list.find(g=>g.key===keyOf(cur)||g.id===cur.model);
  const modelItem=e.target.closest('[data-model]'),depthItem=e.target.closest('[data-depth]');
  if(modelItem){
    const group=list.find(g=>g.key===modelItem.dataset.model);if(!group)return;
    const want=depthOf(cur)||'medium';close();safe(()=>apply(cur,group,want));
  }else if(depthItem&&sel){close();safe(()=>apply(cur,sel,depthItem.dataset.depth));}
});
document.addEventListener('click',e=>{if(!e.target.closest('.model-menu,#modelPill'))close();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
window.addEventListener('resize',()=>{if(!menu.classList.contains('hidden'))place();});
channelBox.addEventListener('change',()=>{paint();if(!menu.classList.contains('hidden'))render();});
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();if(!menu.classList.contains('hidden'))render();};
paint();
})();

// Codex-style work line above an agent's answer. Running: "Komut çalıştırıyor 6 dk 47 sn ▸". Finished: "Web'de arama yaptı, 7 komut
// çalıştırdı ve 5 adım daha · 35 dk 46 sn ▸". Click it to see every step (command, search, file) with its details.
(()=>{
const list=document.getElementById('messages');
if(!list)return;
const keep=new Map();
const parse=s=>{const v=Date.parse(String(s||'').replace(' ','T'));return Number.isFinite(v)?v:null;};
const fmt=sec=>{sec=Math.max(0,Math.round(sec));const m=Math.floor(sec/60),s=sec%60;return m?m+tr(' dk ',' min ')+s+tr(' sn',' s'):s+tr(' sn',' s');};
const kindOf=a=>String(a&&a.kind||'');
const isResult=k=>/result|\/completed$/i.test(k);
const isSearch=k=>/search|web/i.test(k)&&!/read_url|browse|fetch/i.test(k);
const isReadUrl=k=>/read_url|browse|fetch/i.test(k);
const isCommand=k=>/project_command|project_test|(^|[^a-z])(bash|shell|exec)/i.test(k)&&!/result/i.test(k);
const isEdit=k=>/project_edit|write|(^|[^a-z])edit/i.test(k);
const isRead=k=>/project_read|project_list|read/i.test(k)&&!isReadUrl(k);
const capital=s=>s?s.charAt(0).toUpperCase()+s.slice(1):s;
function summary(acts){
  const steps=acts.filter(a=>!isResult(kindOf(a))),all=steps.length?steps:acts;
  const c={computer:0,search:0,command:0,edit:0,read:0};let counted=0;
  for(const a of all){const k=kindOf(a);if(/desktop|computer|screen_capture/i.test(k))c.computer++;else if(isSearch(k))c.search++;else if(isCommand(k))c.command++;else if(isEdit(k))c.edit++;else if(isReadUrl(k)||isRead(k))c.read++;}
  const make={
    computer:()=>tr('bilgisayarını kullandı','used your computer'),
    search:n=>tr(n>1?"web'de "+n+' arama yaptı':"web'de arama yaptı",n>1?'searched the web '+n+' times':'searched the web'),
    command:n=>tr(n+' komut çalıştırdı','ran '+n+(n>1?' commands':' command')),
    edit:n=>tr(n+' dosyayı düzenledi','edited '+n+(n>1?' files':' file')),
    read:n=>tr(n+' kaynak veya dosya okudu','read '+n+(n>1?' files or sources':' file or source'))
  };
  const shown=['computer','search','command','edit','read'].filter(k=>c[k]>0).slice(0,2);
  counted=shown.reduce((sum,k)=>sum+c[k],0);
  const parts=shown.map(k=>make[k](c[k]));
  const rest=all.length-counted;
  if(rest>0)parts.push(tr(rest+' adım daha',rest+' more '+(rest>1?'steps':'step')));
  if(!parts.length)return tr('Çalıştı','Worked');
  const text=parts.length===1?parts[0]:tr(parts.slice(0,-1).join(', ')+' ve '+parts[parts.length-1],parts.slice(0,-1).join(', ')+', and '+parts[parts.length-1]);
  return capital(text);
}
function liveLabel(a){
  const k=kindOf(a);
  try{if(['DONE','ERROR','FAILED'].includes(String(JSON.parse(a.detail).state).toUpperCase()))return tr('Sonucu değerlendiriyor','Reviewing the result');}catch{}
  if(isResult(k))return tr('Sonucu değerlendiriyor','Reviewing the result');
  if(/desktop_observe|screen_capture/i.test(k))return tr('Ekranı inceliyor','Looking at your screen');
  if(/desktop|computer/i.test(k))return tr('Bilgisayarda çalışıyor','Using your computer');
  if(isSearch(k))return tr("Web'de arama yapıyor",'Searching the web');
  if(isReadUrl(k))return tr('Kaynak okuyor','Reading a source');
  if(isCommand(k)||/command_result/i.test(k))return tr('Komut çalıştırıyor','Running a command');
  if(isEdit(k))return tr('Dosya düzenliyor','Editing a file');
  if(/project_list/i.test(k))return tr('Projeyi inceliyor','Browsing the project');
  if(isRead(k))return tr('Dosya okuyor','Reading a file');
  return tr('Çalışıyor','Working');
}
// One readable row per step: a short sentence, and a small triangle that opens the raw command, query or file.
const tri='<svg class="wl-tri" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 8 6-8 6z" fill="currentColor"/></svg>';
function queryOf(detail){try{const d=JSON.parse(detail),p=d.parameters||{};return String(p.query||p.search_query||p.url||'');}catch{return '';}}
function stepTitle(a){
  const k=kindOf(a),d=String(a.detail||'').trim(),first=d.split('\n')[0].slice(0,70);
  if(/desktop_observe|screen_capture/i.test(k))return tr('Ekranı inceledi','Looked at your screen');
  if(/desktop|computer/i.test(k))return tr('Bilgisayarını kullandı','Used your computer');
  if(isSearch(k)){const q=queryOf(d);return tr("Web'de aradı","Searched the web")+(q?': '+q.slice(0,70):'');}
  if(isReadUrl(k)){const q=queryOf(d);return tr('Kaynağı okudu','Read a source')+(q?': '+q.slice(0,70):'');}
  if(isCommand(k))return tr('Komut çalıştırdı','Ran a command');
  if(/result/i.test(k))return tr('Komut sonucu','Command result');
  if(isEdit(k))return tr('Dosyayı düzenledi','Edited a file')+(first?': '+first:'');
  if(/project_list/i.test(k))return tr('Projeyi inceledi','Browsed the project');
  if(isRead(k))return tr('Dosyayı okudu','Read a file')+(first?': '+first:'');
  if(/completed$/i.test(k))return tr('Adım bitti','Step finished');
  return (typeof logNames!=='undefined'&&logNames[k])||k||tr('Adım','Step');
}
window.jarvisStepTitle=stepTitle;
function stepRow(a){
  const k=kindOf(a),d=String(a.detail||'').trim(),title=stepTitle(a);
  const open=(isCommand(k)||/result/i.test(k)||d.includes('\n')||d.length>90)&&d;
  if(!open)return '<div class="wl-step"><span class="wl-st">'+esc(title)+'</span></div>';
  return '<details class="wl-step has"><summary><span class="wl-st">'+esc(title)+'</span>'+tri+'</summary><pre>'+esc(d.slice(0,800))+'</pre></details>';
}
// While the agent works, a ticker flips quickly through what it is searching, reading or running, with a running counter.
const ticks=new WeakMap();
function tickText(a){
  const k=kindOf(a),d=String(a.detail||'').trim();
  if(isSearch(k)||isReadUrl(k)){
    const q=queryOf(d);
    if(isReadUrl(k)){try{const u=new URL(q);return u.hostname.replace(/^www\./,'')+(u.pathname.length>1?u.pathname:'');}catch{}}
    return q||d.split('\n')[0].slice(0,70);
  }
  return d.split('\n')[0].slice(0,70);
}
function tickItems(acts){
  const steps=acts.filter(a=>!isResult(kindOf(a)));
  return steps.map((a,i)=>({n:i+1,total:steps.length,label:liveLabel(a),text:tickText(a)})).slice(-8);
}
function paintTick(line){
  const st=ticks.get(line);if(!st||!st.items.length)return;
  const it=st.items[st.i%st.items.length],box=line.querySelector('.wl-tick');if(!box)return;
  const label=line.querySelector('.wl-label');if(label)label.textContent=it.label;
  box.querySelector('b').textContent=it.n+'/'+it.total;box.querySelector('em').textContent=it.text;
  box.classList.remove('flip');void box.offsetWidth;box.classList.add('flip');
}
// Show the latest real action; never cycle old actions as if they are happening now.
const chevron='<svg class="wl-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';
function build(row,m){
  const acts=compactActivityEvents(m.activities||[]);
  let line=row.querySelector('.work-line');
  if(!acts.length){if(line)line.remove();return;}
  if(!line){
    line=document.createElement('details');line.className='work-line';
    const meta=row.querySelector('.message-meta');if(!meta)return;meta.after(line);
    line.open=Boolean(keep.get(m.id));line.addEventListener('toggle',()=>keep.set(m.id,line.open));
  }
  const running=m.status==='streaming',last=acts[acts.length-1];
  line.classList.toggle('running',running);
  const sig=JSON.stringify([m.status,acts.length,last.time,last.kind,last.detail,state.language]);
  if(line.dataset.sig!==sig){
    line.dataset.sig=sig;
    const names=typeof logNames!=='undefined'?logNames:{};
    line.style.setProperty('--work-accent',state.agents.find(a=>a.name===m.author)?.color||'#70d5e8');
    line.innerHTML='<summary><i class="wl-spin"></i><b class="wl-agent">'+esc(m.author)+'</b><span class="wl-label">'+esc(running?liveLabel(last):summary(acts))+'</span>'+(running?'<span class="wl-tick"><b></b><em></em></span>':'')+'<time class="wl-time"></time>'+chevron+'</summary><div class="wl-steps">'+
      acts.map(stepRow).join('')+'</div>';
    if(running){const items=tickItems(acts);ticks.set(line,{items,i:Math.max(0,items.length-1)});paintTick(line);}
    else ticks.delete(line);
  }
  const stamp=line.querySelector('.wl-time'),start=parse(m.time);
  let wf=row.querySelector('.worked-for'),took=0;
  if(running&&start){stamp.dataset.start=String(start);stamp.textContent=fmt((Date.now()-start)/1000);}
  else{
    delete stamp.dataset.start;
    const end=parse(last.time);
    took=!running&&start&&end&&end>=start?(end-start)/1000:0;
    stamp.textContent=took>0&&took<20?'· '+fmt(took):'';
  }
  // Long turns get a Codex-style divider above the answer: "Worked for 35m 46s ————".
  if(took>=20){
    if(!wf){wf=document.createElement('div');wf.className='worked-for';}
    if(wf.previousElementSibling!==line)line.after(wf);
    const label=tr('Çalıştı ','Worked for ')+fmt(took);if(wf.textContent!==label)wf.textContent=label;
  }else if(wf)wf.remove();
}
function paint(){
  if(typeof state==='undefined'||!state)return;
  const visible=state.messages.filter(m=>(m.channel||'common')===document.getElementById('channel').value);
  list.querySelectorAll('.message').forEach((row,i)=>{const m=visible[i];if(m&&m.author!=='YOU')build(row,m);});
}
setInterval(()=>{list.querySelectorAll('.wl-time[data-start]').forEach(el=>{el.textContent=fmt((Date.now()-Number(el.dataset.start))/1000);});},1000);
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();};
paint();
})();

// "Tamam, kontrolü al": the agent asks for control inside the chat. One tap per chat, no manual session setup.
(()=>{
const list=document.getElementById('messages'),channelBox=document.getElementById('channel');
if(!list||!channelBox)return;
const ICON='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/></svg>';
let switchedFor='';
function cardFor(row,m){
  const req=m.computer_request;
  let card=row.querySelector('.control-card');
  if(m.permission_help){
    if(!card){card=document.createElement('div');card.className='control-card';row.querySelector('.message-text').after(card);}
    const p=state.desktop_permissions||{},key=String(p.screen)+':'+String(p.accessibility)+':'+state.language;
    if(card.dataset.permKey!==key){card.dataset.permKey=key;
      card.innerHTML='<div class="cc-actions">'+(!p.screen?'<button type="button" class="cc-btn primary" data-mac-help="screen">'+esc(tr('Ekran izni ver','Allow screen access'))+'</button>':'')+(!p.accessibility?'<button type="button" class="cc-btn primary" data-mac-help="accessibility">'+esc(tr('Kontrol izni ver','Allow control access'))+'</button>':'')+'<button type="button" class="cc-btn" data-mac-help="app">'+esc(tr('Finder’da göster','Show in Finder'))+'</button><button type="button" class="cc-btn" data-mac-help="refresh">'+esc(tr('Kontrol et','Check'))+'</button></div>'+(p.screen&&p.accessibility?'<small>'+esc(tr('İzinler hazır. Görevi yeniden başlatabilirsin.','Permissions ready. You can restart the task.'))+'</small>':'');
    }
    return;
  }
  if(!req){if(card)card.remove();return;}
  const p=state.desktop_permissions||{},sig=[req.id,req.status,p.screen,p.accessibility,state.language].join('|');
  if(!card){card=document.createElement('div');card.className='control-card';const text=row.querySelector('.message-text');(text||row).after(card);}
  if(card.dataset.sig===sig)return;
  card.dataset.sig=sig;card.dataset.id=req.id;card.dataset.owner=req.owner;card.dataset.status=req.status;
  if(req.status==='approved'){card.innerHTML='<div class="cc-done">'+ICON+'<span>'+esc(tr('İzin verildi · bu sohbet · ','Allowed · this chat · ')+req.owner)+'</span></div>';return;}
  if(req.status==='denied'){card.innerHTML='<div class="cc-done muted">'+ICON+'<span>'+esc(tr('İzin verilmedi','Not allowed'))+'</span></div>';return;}
  const missing=!p.screen||!p.accessibility;
  const chip=(ok,label)=>'<span class="cc-chip '+(ok?'ok':'off')+'">'+(ok?'✓ ':'— ')+esc(label)+'</span>';
  const task=String(req.task||'').trim().replace(/\s+/g,' ');
  const line=(k,v)=>'<div><dt>'+esc(k)+'</dt><dd>'+v+'</dd></div>';
  card.innerHTML='<div class="cc-head">'+ICON+'<b>'+esc(req.owner+tr(' bilgisayarını kontrol etmek istiyor',' wants to control your computer'))+'</b></div>'+
    '<dl class="cc-rows">'+
    (task?line(tr('Görev','Task'),esc(task.length>180?task.slice(0,177)+'…':task)):'')+
    line(tr('Uygulamalar','Apps'),esc(tr('Görevin gerektirdiği uygulamalar. Terminal, parola alanları ve sistem izin pencereleri hariç.','Whatever apps the task needs. Not Terminal, password fields or system permission windows.')))+
    line(tr('Yapabilir','Can do'),esc(tr('Ekranı görür, tıklar ve yazar','See the screen, click and type')))+
    line(tr('Önce sorar','Asks first'),esc(tr('Mesaj gönderme, ödeme ve silme','Sending messages, payments and deleting')))+
    line(tr('Süre','Duration'),'<select class="cc-duration" aria-label="'+esc(tr('Kontrol izni süresi','Control access duration'))+'">'+[10,30,60,120].map(n=>'<option value="'+n+'"'+(n===(state.desktop_session_minutes||10)?' selected':'')+'>'+n+esc(tr(' dakika',' minutes'))+'</option>').join('')+'</select><span class="cc-sub">'+esc(tr('Durdur her an keser','Stop ends it any time'))+'</span>')+
    line(tr('Mac izinleri','Mac access'),chip(p.screen,tr('Ekran Kaydı','Screen Recording'))+chip(p.accessibility,tr('Erişilebilirlik','Accessibility'))+(missing?'<button type="button" class="cc-link" data-cc="perm">'+esc(tr('İzin ver','Allow'))+'</button>':''))+
    '</dl>'+
    '<p class="cc-note">'+esc(tr('Bu sohbet için tek seferlik izin. Süre, kesintisiz model çalışması veya sınırsız kota anlamına gelmez.','One-time permission for this chat. The duration does not mean uninterrupted model work or unlimited quota.'))+'</p>'+
    '<div class="cc-actions"><button type="button" class="cc-btn primary" data-cc="allow">'+esc(tr('Bu sohbette izin ver','Allow in this chat'))+'</button><button type="button" class="cc-btn" data-cc="deny">'+esc(tr('Şimdi değil','Not now'))+'</button></div>';
  if(typeof nativeHost!=='undefined'&&nativeHost&&typeof nativeSend==='function')nativeSend('desktop-status');
}
function paint(){
  if(typeof state==='undefined'||!state)return;
  const visible=state.messages.filter(m=>(m.channel||'common')===channelBox.value);
  list.querySelectorAll('.message').forEach((row,i)=>{const m=visible[i];if(m)cardFor(row,m);});
  // When an agent takes control, follow it: show that agent's channel so the work is visible.
  const ds=state.desktop_session;
  if(ds&&ds.chat_id===state.active_chat){
    const key=ds.owner+'|'+ds.expires;
    if(key!==switchedFor){switchedFor=key;const target=ds.channel||ds.owner;if(channelBox.value!==target&&[...channelBox.options].some(o=>o.value===target)){channelBox.value=target;channelBox.dispatchEvent(new Event('change'));}}
  }
}
list.addEventListener('click',e=>{
  const b=e.target.closest('[data-cc]');if(!b)return;
  const card=b.closest('.control-card'),id=card?.dataset.id;if(!id)return;
  if(b.dataset.cc==='perm'){requestMacPermission((state.desktop_permissions||{}).screen?'accessibility':'screen');return;}
  safe(()=>api('computer-grant',{id,allow:b.dataset.cc==='allow',minutes:Number(card.querySelector('.cc-duration')?.value||10)}));
});
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();};
paint();
})();

// Right-side activity panel in the Cowork style: "Adım N / M" pill in the header, Progress timeline, live Computer use frame,
// and a "Used in this session" list. Plus the chat "…" menu. Everything shown is real: steps, frames and tools that actually ran.
(()=>{
const workspace=document.querySelector('#mission .workspace'),conversation=document.querySelector('.conversation'),head=conversation&&conversation.querySelector(':scope>.panel-head');
if(!workspace||!conversation||!head)return;
const KEY='jarvisActivity';
let scopedState=null,scopedChannel='',scopedCache=[];
function chatRows(){const channel=document.getElementById('channel').value;if(scopedState!==state||scopedChannel!==channel){scopedState=state;scopedChannel=channel;scopedCache=(state.messages||[]).filter(m=>(m.channel||'common')===channel);}return scopedCache;}
function chatTasks(){const channel=document.getElementById('channel').value;return (state.tasks||[]).filter(t=>channel==='common'||t.owner===channel);}
const panel=document.createElement('aside');panel.id='activityPanel';panel.className='activity-panel hidden';panel.setAttribute('aria-label',tr('Etkinlik','Activity'));
workspace.append(panel);
const actions=document.createElement('div');actions.className='chat-head-actions';
const toggle=document.createElement('button');toggle.type='button';toggle.id='activityToggle';toggle.className='head-btn pill';toggle.setAttribute('aria-pressed','false');
toggle.title=tr('Etkinlik paneli · ⇧⌘E','Activity panel · ⇧⌘E');toggle.setAttribute('aria-label',toggle.title);
toggle.innerHTML='<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 3.5h7.5L19 8v12a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-16a.5.5 0 0 1 .5-.5z"/><path d="M14.5 3.5V8H19"/></svg><span class="ah-text"></span>';
// The chat's own name sits at the top with a small arrow, like the Claude and ChatGPT apps; the arrow opens the chat menu.
const dots=document.createElement('button');dots.type='button';dots.id='chatMenuBtn';dots.className='chat-title';dots.setAttribute('aria-haspopup','menu');
dots.innerHTML='<span class="ct-name"></span><svg class="ct-chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
const globe=document.createElement('button');globe.type='button';globe.id='activityGlobe';globe.className='head-btn';globe.hidden=true;
globe.innerHTML='<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.6 5.3 3.6 8.5s-1 6.1-3.6 8.5c-2.6-2.4-3.6-5.3-3.6-8.5s1-6.1 3.6-8.5z"/></svg>';
const share=document.createElement('button');share.type='button';share.id='activityShare';share.className='head-btn share';share.hidden=true;
share.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V4m0 0L8 8m4-4 4 4"/><path d="M5 12v6a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18v-6"/></svg><span class="sh-text"></span>';
actions.append(globe,toggle,share);head.append(dots,actions);
let userOpen=false;try{userOpen=localStorage.getItem(KEY)==='open';}catch{}
function setOpen(open){
  userOpen=open;panel.classList.toggle('hidden',!open);toggle.setAttribute('aria-pressed',String(open));
  try{localStorage.setItem(KEY,open?'open':'closed');}catch{}
  if(open)draw();
}
const isResult=k=>/result|\/completed$/i.test(k);
const kindClass=k=>/read_url|browse|fetch/i.test(k)?'web':/search|web/i.test(k)?'web':/desktop|computer|screen_capture/i.test(k)?'computer':/project_command|project_test|bash|shell|exec/i.test(k)?'cmd':/project_edit|write|edit/i.test(k)?'edit':/read|list/i.test(k)?'read':'other';
const ICONS={
  web:'<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.6 5.3 3.6 8.5s-1 6.1-3.6 8.5c-2.6-2.4-3.6-5.3-3.6-8.5s1-6.1 3.6-8.5z"/>',
  cmd:'<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="m7.5 10 3 2.5-3 2.5M12.5 15h4"/>',
  edit:'<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17z"/><path d="m14 8 3 3"/>',
  read:'<path d="M7 3.5h7.5L19 8v12a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-16a.5.5 0 0 1 .5-.5z"/><path d="M14.5 3.5V8H19"/>',
  upload:'<path d="m20 11.5-8 8a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.5 17a1.7 1.7 0 0 1-2.4-2.4L15 6.7"/>',
  agent:'<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c.6-3.6 3.4-5.5 7-5.5s6.4 1.9 7 5.5"/>',
  computer:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
  other:'<circle cx="12" cy="12" r="2.2"/>'
};
const ico=name=>'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(ICONS[name]||ICONS.other)+'</svg>';
const LABEL=c=>({web:tr('Web araması','Web search'),cmd:tr('Komut','Command'),edit:tr('Dosya düzenleme','File edit'),read:tr('Dosya okuma','File read'),computer:tr('Bilgisayar kullanımı','Computer use'),other:tr('Adım','Step')})[c];
function queryOf(detail){try{const d=JSON.parse(detail),p=d.parameters||{};return String(p.query||p.search_query||p.url||'');}catch{return '';}}
function brief(a){
  const d=String(a.detail||'').trim(),first=d.split('\n')[0];
  return (queryOf(d)||first).slice(0,60);
}
function lastTurn(){
  const rows=chatRows();let i=rows.length-1;while(i>=0&&rows[i].author!=='YOU')i--;
  return rows.slice(i+1).filter(m=>m.author!=='YOU');
}
// Every step of this chat, oldest first. The pill reads "Step N of M": M is the real total so far, N the step you picked (the latest by default).
let sel=-1,lastTotal=0,lastChat='',tlStick=true,tlAuto=0;
function stats(){
  const steps=[];
  for(const m of chatRows())for(const a of compactActivityEvents(m.activities||[]))if(!isResult(String(a.kind||'')))steps.push({a,m});
  const replies=lastTurn();
  const running=replies.some(m=>m.status==='streaming')||!!state.model_job;
  return {replies,steps,running};
}
// Progress reads like a task list, not a tool log: what Berke asked, then what each agent did in a few words ("EDITH · searched the web · 6 steps", "VISION · replied").
// The individual searches, commands and files stay in "Used in this session".
const shortText=(t,n)=>{t=String(t||'').replace(/\s+/g,' ').trim();return t.length>n?t.slice(0,n-1)+'…':t;};
function groupText(g){
  const verb={web:tr('webde araştırdı','searched the web'),cmd:tr('komut çalıştırdı','ran commands'),edit:tr('dosya düzenledi','edited files'),read:tr('dosya okudu','read files'),computer:tr('bilgisayarı kullandı','used your computer'),other:tr('çalıştı','worked')}[g.c]||tr('çalıştı','worked');
  return verb+(g.n>1?' · '+g.n+tr(' adım',' steps'):'');
}
function progress(){
  const out=[];
  for(const m of chatRows()){
    if(m.author==='YOU'||m.author==='SYSTEM')continue;
    const acts=compactActivityEvents(m.activities||[]).filter(a=>!isResult(String(a.kind||'')));
    let group=null;
    const flush=()=>{if(group){out.push({owner:m.author,text:groupText(group),now:m.status==='streaming'});group=null;}};
    for(const a of acts){const c=kindClass(String(a.kind||''));if(group&&group.c===c)group.n++;else{flush();group={c,n:1};}}
    flush();
    if(m.workflow_intro)out.push({owner:'JARVIS',text:shortText(m.text,180)});
    const handoff=String(m.text||'').match(/Paslama → ([A-Za-z][A-Za-z0-9_-]*)[^:]*:\s*([^\n]*)/);
    if(handoff)out.push({owner:m.author,text:handoff[1]+tr(' ajanına görevi aktarıyor: ',' · handing off: ')+shortText(handoff[2],110)});
    if(m.presentation)out.push({owner:'JARVIS',text:m.local_presentation?tr('Uzman çıktısını sundu','Presented the specialist output'):tr('Sonuçları birleştiriyor ve sunuyor','Combining and presenting the results'),now:m.status==='streaming'});
    else if(m.workflow_id&&!m.workflow_intro&&!acts.length)out.push({owner:m.author,text:m.status==='streaming'?tr('Verilen görev üzerinde çalışıyor','Working on the assigned task'):tr('Görev çıktısı hazır','Task output ready'),now:m.status==='streaming'});
  }
  return out.concat(planned());
}
// Work that is already planned but has not started: the rest of the team order (then JARVIS presents) and queued tasks.
// This is what makes the pill read "Step 9 of 20". With no plan the total just equals the steps so far; nothing is guessed.
function planned(){
  const out=[],runs=(state.chat_workflows||[]).filter(r=>r&&r.chat_id===state.active_chat&&document.getElementById('channel').value==='common'&&(r.status==='working'||r.status==='presenting'));
  const run=runs[runs.length-1];
  if(run){
    const stages=run.steps||[],from=run.status==='working'?Math.min((run.index||0)+1,stages.length):stages.length;
    for(const owner of stages.slice(from))out.push({owner,text:tr('Sırada','Up next'),future:true});
    if(run.status==='working')out.push({owner:'JARVIS',text:tr('Sonucu sunacak','Will present the result'),future:true});
  }
  for(const t of chatTasks())if(t.status==='queued'&&out.length<30)out.push({owner:t.owner,text:shortText(t.title,60),future:true});
  return out;
}
// Index of the latest step that has started (the plan after it is still ahead).
const cursor=items=>{let i=items.length-1;while(i>=0&&items[i].future)i--;return i;};
function pillText(items){
  const total=items.length;
  if(!total)return tr('Etkinlik','Activity');
  const n=sel>=0&&sel<total?sel+1:Math.max(1,cursor(items)+1);
  return tr('İş akışı '+n+' / '+total,'Workflow '+n+' of '+total);
}
function sources(){
  const out=[];
  for(const m of chatRows())for(const a of compactActivityEvents(m.activities||[]))for(const hit of String(a.detail||'').matchAll(/https?:\/\/[^\s"'<>}\\]+/g)){
    try{const u=new URL(hit[0]);const host=u.hostname.replace(/^www\./,'');if(!out.some(x=>x.host===host))out.push({host,href:u.href});}catch{}
  }
  return out;
}
// Everything that ran in this chat, oldest first: tool steps, uploads and the agents that were called.
function used(){
  const rows=[],seen=new Set();
  for(const m of chatRows()){
    for(const f of (m.attachments||[]))if(f&&f.name&&!seen.has('f'+f.name)){seen.add('f'+f.name);rows.push({icon:'upload',label:tr('Yüklenen','Uploads'),detail:f.name});}
    if(m.author!=='YOU'&&m.author!=='SYSTEM'&&!seen.has('a'+m.author)){seen.add('a'+m.author);rows.push({icon:'agent',label:m.author,detail:tr('Bu sohbete katıldı','Participated in this chat'),owner:m.author});}
    for(const a of compactActivityEvents(m.activities||[])){
      const k=String(a.kind||'');if(isResult(k))continue;
      const c=kindClass(k);rows.push({icon:c,label:LABEL(c),detail:brief(a),raw:String(a.detail||'').slice(0,6000),owner:m.author});
    }
  }
  return rows.slice(-40);
}
// Latest screen frame of a computer-control session, kept in memory only.
let frame=null;
window.addEventListener('jarvis-native',e=>{
  const d=e.detail;if(!d||d.type!=='desktop-result')return;
  const r=d.data&&d.data.result;
  if(r&&typeof r.image==='string'&&r.image.startsWith('data:image/jpeg')){frame={src:r.image,app:String(r.application||''),at:Date.now(),chat:(typeof state!=='undefined'&&state&&state.active_chat)||''};draw();}
});
const shot=document.createElement('img');shot.className='ap-shot';shot.alt=tr('Bilgisayar ekranı','Computer screen');
const section=(title,body,cls)=>'<section class="ap-sec'+(cls?' '+cls:'')+'"><h3>'+esc(title)+'</h3>'+body+'</section>';
function draw(){
  if(typeof state==='undefined'||!state)return;
  const {steps,running}=stats(),tasks=chatTasks(),doneTasks=tasks.filter(t=>t.status==='done').length;
  const items=progress(),total=items.length;
  const chat=(state.chats||[]).find(c=>c.id===state.active_chat),name=(chat&&String(chat.title||'').trim())||tr('Yeni sohbet','New chat');
  const nameEl=dots.querySelector('.ct-name');if(nameEl&&nameEl.textContent!==name)nameEl.textContent=name;
  dots.title=name;dots.setAttribute('aria-label',tr('Sohbet menüsü: ','Chat menu: ')+name);
  const scopeKey=state.active_chat+':'+document.getElementById('channel').value;
  if(scopeKey!==lastChat){lastChat=scopeKey;sel=-1;tlStick=true;}
  if(total!==lastTotal){lastTotal=total;sel=-1;tlStick=true;}
  const text=pillText(items),label=toggle.querySelector('.ah-text');if(label&&label.textContent!==text)label.textContent=text;
  toggle.classList.toggle('busy',running);
  const shareText=toggle.parentElement.querySelector('.sh-text');if(shareText)shareText.textContent=tr('Paylaş','Share');
  toggle.title=tr('Etkinlik paneli · ⇧⌘E','Activity panel · ⇧⌘E');globe.title=tr('Kaynaklar','Sources');share.title=tr('Sohbeti kopyala','Copy chat');
  // The pill only appears once this chat has something to show: steps, a plan, or a computer-control frame.
  const mine=frame&&frame.chat===state.active_chat?frame:null;
  const has=!!(steps.length||tasks.length||mine||(state.desktop_session&&state.desktop_session.chat_id===state.active_chat));
  toggle.hidden=!has&&panel.classList.contains('hidden');
  share.hidden=!has;globe.hidden=!(has&&sources().length);
  if(panel.classList.contains('hidden'))return;
  const title=(a)=>typeof jarvisStepTitle==='function'?jarvisStepTitle(a):String(a.kind||'');
  let prog='';
  if(tasks.length)prog+='<div class="ap-bar"><progress max="'+tasks.length+'" value="'+doneTasks+'"></progress><span>'+esc(tr('Görev ','Task ')+doneTasks+' / '+tasks.length)+'</span></div>'+
    '';
  const shown=items.slice(-200),base=total-shown.length,cur=Math.max(0,cursor(items)),picked=sel>=0&&sel<total?sel:cur;
  prog+=items.length?'<div class="ap-timeline" tabindex="0"><ul>'+shown.map((x,i)=>{const g=base+i,c=[x.now?'now':'',x.future?'future':'',g===cur&&!x.future?'cur':'',g===picked&&sel>=0?'sel':'',g>picked?'ahead':''].filter(Boolean).join(' ');return '<li data-i="'+g+'"'+(c?' class="'+c+'"':'')+' data-agent="'+esc(x.owner||'')+'">'+(x.owner?'<b class="ap-owner">'+esc(x.owner)+'</b>':'')+'<span>'+esc(x.text.slice(0,180))+'</span></li>';}).join('')+'</ul></div>':'<p class="ap-empty">'+esc(tr('Henüz adım yok. Bir iş başlayınca adımlar burada akar.','No steps yet. Steps stream here once work starts.'))+'</p>';
  let html=section(tr('Çalışma özeti','Work summary'),prog);
  const ds=state.desktop_session,live=!!(ds&&ds.chat_id===state.active_chat);
  if(live||mine){
    const who=live?ds.owner:'';
    html+=section(tr('Bilgisayar kullanımı','Computer use'),'<div class="ap-shot-slot"></div><div class="ap-live"><span class="ap-badge'+(live?' on':'')+'">'+esc(live?tr('Canlı','Live'):tr('Bitti','Ended'))+'</span><span>'+esc([tr('Arka planda','Background'),who,mine&&mine.app].filter(Boolean).join(' · '))+'</span>'+(live?'<button type="button" class="cc-btn" data-ap="stop">'+esc(tr('Durdur','Stop'))+'</button>':'')+'</div>');
  }
  const src=sources();
  if(src.length)html+=section(tr('Kaynaklar','Sources'),'<div class="ap-chips">'+src.slice(0,10).map(x=>'<button type="button" class="ap-chip" data-src="'+esc(x.href)+'" title="'+esc(x.href)+'"><b>'+esc(x.host[0].toUpperCase())+'</b>'+esc(x.host)+'</button>').join('')+'</div>','ap-sources');
  const rows=used();
  html+=section(tr('Bu oturumda kullanılanlar','Used in this session'),rows.length?'<ul class="ap-used">'+rows.map(r=>'<li><details class="ap-used-item"><summary>'+ico(r.icon)+'<span><b>'+esc(r.label)+'</b><small>'+esc([r.owner,r.detail].filter(Boolean).join(' · '))+'</small></span><i>›</i></summary><pre>'+esc(r.raw||r.detail||r.label)+'</pre></details></li>').join('')+'</ul>':'<p class="ap-empty">'+esc(tr('Araçlar, aramalar ve ekler burada listelenir.','Tools, searches and attachments are listed here.'))+'</p>');
  html='<div class="ap-head"><b>'+esc(tr('Etkinlik','Activity'))+'</b><button type="button" class="ap-close" data-ap="close" aria-label="'+esc(tr('Kapat','Close'))+'">×</button></div><div class="ap-body">'+html+'</div>';
  const sig=html+'|'+(mine?mine.at:0);
  const sig2=sig+'|'+sel;
  if(panel.dataset.html!==sig2){
    const old=panel.querySelector('.ap-timeline'),prevTop=old?old.scrollTop:0,bodyTop=(panel.querySelector('.ap-body')||{}).scrollTop||0;
    const expanded=new Set(Array.from(panel.querySelectorAll('.ap-used-item[open]'),d=>d.querySelector('summary').textContent));
    panel.dataset.html=sig2;panel.innerHTML=html;
    panel.querySelectorAll('[data-agent]').forEach(row=>row.style.setProperty('--agent',agentColor(row.dataset.agent)));
    panel.querySelectorAll('.ap-used-item').forEach(d=>{d.open=expanded.has(d.querySelector('summary').textContent);});
    const body=panel.querySelector('.ap-body');if(body)body.scrollTop=bodyTop;
    const slot=panel.querySelector('.ap-shot-slot');if(slot&&mine){if(shot.src!==mine.src)shot.src=mine.src;slot.append(shot);}
    const tl=panel.querySelector('.ap-timeline');
    if(tl){
      // Follow the step that is running; the planned ones below it stay out of the way until you scroll down.
      const at=tl.querySelector('li[data-i="'+picked+'"]');tlAuto=Date.now();
      tl.scrollTop=tlStick||!old?(at?Math.max(0,at.offsetTop+at.offsetHeight-tl.clientHeight+Math.round(at.offsetHeight*2.2)):tl.scrollHeight):prevTop;
    }
  }
}
toggle.addEventListener('click',e=>{e.stopPropagation();setOpen(panel.classList.contains('hidden'));});
globe.addEventListener('click',e=>{e.stopPropagation();setOpen(true);const sec=panel.querySelector('.ap-sources');if(sec)sec.scrollIntoView({block:'nearest'});});
share.addEventListener('click',e=>{e.stopPropagation();copyText(transcript()).then(ok=>toast(ok?tr('Sohbet panoya kopyalandı.','Chat copied.'):tr('Kopyalanamadı.','Could not copy.')));});
panel.addEventListener('scroll',e=>{const t=e.target;if(t.classList&&t.classList.contains('ap-timeline')&&Date.now()-tlAuto>200){const at=t.querySelector('li[data-i="'+Math.max(0,cursor(progress()))+'"]');tlStick=!!at&&at.offsetTop+at.offsetHeight-t.scrollTop-t.clientHeight<24&&t.scrollTop+t.clientHeight>=at.offsetTop;}},true);
panel.addEventListener('click',e=>{
  const li=e.target.closest('.ap-timeline li[data-i]');
  if(li){const g=Number(li.dataset.i),now=cursor(progress());sel=g>=now?-1:g;tlStick=false;draw();return;}
  const s=e.target.closest('[data-src]');if(s){if(typeof nativeSend==='function')nativeSend('open-task-site',{url:s.dataset.src});return;}
  const b=e.target.closest('[data-ap]');if(!b)return;
  if(b.dataset.ap==='close')setOpen(false);
  if(b.dataset.ap==='stop')safe(()=>api('desktop-stop'));
});
// "…" menu: the sidebar's chat menu, plus copy and the panel switch.
function transcript(){
  return chatRows().map(m=>(m.author==='YOU'?tr('Ben','Me'):m.author)+': '+String(m.text||'')).join('\n\n');
}
async function copyText(text){
  try{await navigator.clipboard.writeText(text);return true;}catch{}
  try{const t=document.createElement('textarea');t.value=text;t.setAttribute('readonly','');t.className='copy-sink';document.body.append(t);t.select();const ok=document.execCommand('copy');t.remove();return ok;}catch{return false;}
}
function openMenu(){
  if(typeof showConversationMenu!=='function'||!state.active_chat)return;
  showConversationMenu(state.active_chat,dots);
  const menu=document.querySelector('.conversation-menu');if(!menu)return;
  const at=dots.getBoundingClientRect();menu.style.left=Math.max(10,Math.min(innerWidth-240,at.left))+'px';
  const del=menu.querySelector('[data-history-action="delete"]');
  const extra=document.createElement('div');extra.className='cm-extra';
  extra.innerHTML='<div class="cm-sep"></div><button role="menuitem" data-history-action="x-copy">'+esc(tr('Sohbeti kopyala','Copy chat'))+'</button><button role="menuitem" data-history-action="x-panel">'+esc(panel.classList.contains('hidden')?tr('Paneli göster','Show panel'):tr('Paneli gizle','Hide panel'))+'<kbd>⇧⌘E</kbd></button>';
  if(del)del.before(extra);else menu.append(extra);
}
dots.addEventListener('click',e=>{e.stopPropagation();const menu=document.querySelector('.conversation-menu');if(menu&&!menu.classList.contains('hidden')){menu.classList.add('hidden');return;}openMenu();});
document.addEventListener('click',e=>{
  const b=e.target.closest('.conversation-menu [data-history-action^="x-"]');if(!b)return;
  const act=b.dataset.historyAction;
  if(act==='x-panel')setOpen(panel.classList.contains('hidden'));
  if(act==='x-copy')copyText(transcript()).then(ok=>toast(ok?tr('Sohbet panoya kopyalandı.','Chat copied.'):tr('Kopyalanamadı.','Could not copy.')));
},true);
document.addEventListener('keydown',e=>{
  if(!(e.metaKey&&e.shiftKey)||e.altKey||e.ctrlKey)return;
  const key=e.key.toLowerCase();
  if(key==='e'){e.preventDefault();setOpen(panel.classList.contains('hidden'));}
});
const previous=renderWorkspace;renderWorkspace=function(){previous();draw();};
setOpen(userOpen);draw();
})();

// Follow the conversation: stay pinned to the newest message while replies stream in, until the reader scrolls up.
// "Pinned" only changes when the reader scrolls (wheel, touch, keys, rail), never because content grew, so late-arriving rows can't break the follow.
(()=>{
const list=document.getElementById('messages'),pane=document.querySelector('.conversation');
if(!list||!pane)return;
let stick=true,userUntil=0,queued=false,lastYou=0,lastChat='';
const gap=()=>list.scrollHeight-list.scrollTop-list.clientHeight;
const jump=document.createElement('button');jump.type='button';jump.className='jump-latest hidden';
jump.innerHTML='<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14m0 0-6-6m6 6 6-6"/></svg><span></span>';
pane.append(jump);
function update(){
  const show=!stick&&gap()>120;
  jump.classList.toggle('hidden',!show);
  if(!show)return;
  const label=jump.querySelector('span'),text=tr('Son mesaja in','Jump to latest');if(label.textContent!==text)label.textContent=text;
  const lb=list.getBoundingClientRect(),pb=pane.getBoundingClientRect();
  jump.style.setProperty('bottom',Math.max(8,pb.bottom-lb.bottom+12)+'px');
}
function pin(){queued=false;if(stick)list.scrollTop=list.scrollHeight;update();}
function schedule(){if(queued)return;queued=true;requestAnimationFrame(pin);}
const touch=ms=>{userUntil=Math.max(userUntil,Date.now()+ms);};
['wheel','touchstart','touchmove','pointerdown'].forEach(t=>list.addEventListener(t,()=>touch(700),{passive:true}));
document.addEventListener('keydown',e=>{
  if(!['PageUp','PageDown','Home','End','ArrowUp','ArrowDown',' '].includes(e.key))return;
  const tag=(document.activeElement&&document.activeElement.tagName)||'';if(/INPUT|TEXTAREA|SELECT/.test(tag))return;
  touch(700);
});
document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('#msgRail'))touch(1600);},true);
let savedTop=0;
list.addEventListener('scroll',()=>{if(Date.now()<userUntil&&list.scrollHeight>list.clientHeight+1){stick=gap()<80;savedTop=list.scrollTop;}update();},{passive:true});
// Opening a step list or a block by hand means "I am reading this": stop following until the reader returns to the bottom.
list.addEventListener('toggle',e=>{if(e.target&&e.target.matches&&e.target.matches('details')&&Date.now()<userUntil)stick=false;update();},true);
jump.addEventListener('click',()=>{stick=true;pin();});
new MutationObserver(()=>{
  const you=list.querySelectorAll('.message.you').length,chat=(typeof state!=='undefined'&&state&&state.active_chat)||'';
  if(chat!==lastChat){lastChat=chat;stick=true;}else if(you>lastYou)stick=true;
  lastYou=you;
  // A re-render rebuilds the list; give a reader who scrolled up their place back.
  if(!stick&&savedTop>0&&Math.abs(list.scrollTop-savedTop)>2)list.scrollTop=savedTop;
  schedule();
}).observe(list,{childList:true,subtree:true,characterData:true});
if(typeof ResizeObserver==='function')new ResizeObserver(schedule).observe(list);
window.addEventListener('resize',schedule);
schedule();
})();

// The J logo is a home button: go back to the main chat view without reloading the page (a reload can show a stale copy).
(()=>{
const logo=document.querySelector('.monogram');
if(!logo)return;
logo.removeAttribute('href');logo.setAttribute('role','button');logo.setAttribute('tabindex','0');
const go=e=>{e.preventDefault();const b=document.querySelector('.rail-btn[data-view="mission"]');if(b)b.click();const p=document.getElementById('prompt');if(p)p.focus();};
logo.addEventListener('click',go);
logo.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')go(e);});
})();

// Under the quota line every agent card says what the agent is for and which model and depth it runs: "Araştırma · 3.8 Flash · Medium".
(()=>{
const cap=t=>t?t.charAt(0).toUpperCase()+t.slice(1):t;
const role=name=>({JARVIS:tr('Koordinatör','Coordinator'),VISION:tr('Ana programcı','Lead developer'),FRIDAY:tr('Programcı · araştırma','Developer · research'),EDITH:tr('Araştırma','Research'),NOVA:tr('Hızlı sorular','Quick questions')})[name]||'';
function modelLabel(id,effort){
  const m=String(id||'').match(/^gemini-([\d.]+)-(flash-lite|flash|pro)(?:-(low|medium|high))?$/);
  if(m)return m[1]+' '+({'flash-lite':'Flash-Lite',flash:'Flash',pro:'Pro'})[m[2]]+(m[3]?' · '+cap(m[3]):'');
  const c=String(id||'').match(/^claude-(sonnet|opus|haiku)-([\d-]+)$/);
  if(c)return 'Claude '+cap(c[1])+' '+c[2].replace(/-/g,'.')+(['low','medium','high'].includes(effort)?' · '+cap(effort):'');
  const base=({sonnet:'Claude Sonnet',opus:'Claude Opus',haiku:'Claude Haiku'})[id]||(!id||id==='Codex varsayılanı'?tr('Otomatik model','Auto model'):id);
  return base+(['low','medium','high'].includes(effort)?' · '+cap(effort):'');
}
function paint(){
  if(typeof state==='undefined'||!state||!state.agents)return;
  document.querySelectorAll('.agent').forEach(card=>{
    const name=(card.querySelector('h2')||{}).textContent;if(!name)return;
    const a=state.agents.find(x=>x.name===name),isJarvis=name==='JARVIS';
    const id=isJarvis?state.jarvis_model:a&&a.model,effort=isJarvis?'':a&&a.effort;
    const text=[role(name)||(a&&a.role)||'',modelLabel(id,effort)].filter(Boolean).join(' · ');
    let sub=card.querySelector('.agent-sub');
    if(!sub){sub=document.createElement('span');sub.className='agent-sub';const anchor=card.querySelector('.agent-summary');if(anchor)anchor.after(sub);else card.append(sub);}
    if(sub.textContent!==text){sub.textContent=text;sub.title=text;}
  });
}
const previous=renderWorkspace;renderWorkspace=function(){previous();paint();};
paint();
})();

// Scheduled tasks (left menu) and the notification bell. JARVIS owns the data (state.scheduled, state.notifications);
// this layer only shows it. Mac banners go out through the native shell while the window is in the background.
(()=>{
const svg=d=>'<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>';
const clock=svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),bellIcon=svg('<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15L6 16.5Z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>');
const taskBtn=document.getElementById('taskDrawerButton'),deviceBtn=document.getElementById('deviceButton');
if(!taskBtn)return;
const lang=()=>(typeof state!=='undefined'&&state&&state.language==='en')?'en-US':'tr-TR';
const ok=fn=>{try{return fn();}catch{return undefined;}};
// --- left menu button + panel
const nav=document.createElement('button');nav.id='scheduleButton';nav.className='rail-btn';nav.setAttribute('aria-haspopup','dialog');
nav.innerHTML='<span>'+clock+'</span><small></small>';taskBtn.after(nav);
const backdrop=document.createElement('div');backdrop.className='sched-backdrop hidden';
const panel=document.createElement('section');panel.className='sched-panel hidden';panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');
document.body.append(backdrop,panel);
let open=false,formKind='daily',scheduleTab='yours',scheduleFilter='all';
const setOpen=v=>{open=v;panel.classList.toggle('hidden',!v);backdrop.classList.toggle('hidden',!v);nav.setAttribute('aria-expanded',String(v));if(v)drawPanel(true);};
nav.addEventListener('click',()=>setOpen(!open));
backdrop.addEventListener('click',()=>setOpen(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&open)setOpen(false);});
const kindText=(it)=>{
  if(it.kind==='daily')return tr('Her gün ','Every day ')+it.at;
  if(it.kind==='weekdays')return tr('Hafta içi ','Weekdays ')+it.at;
  if(it.kind==='hourly')return it.every===1?tr('Her saat','Every hour'):tr('Her '+it.every+' saatte','Every '+it.every+' hours');
  return tr('Bir kez','Once');
};
const when=ts=>ts?new Date(ts*1000).toLocaleString(lang(),{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
const owners=()=>['AUTO'].concat((state.agents||[]).filter(a=>a.enabled!==false).map(a=>a.name));
function scheduleStatus(it){if(it.running_chat)return 'working';if(it.last_status==='failed')return 'failed';if(!it.enabled)return it.runs?'completed':'paused';return it.next<Date.now()/1000?'waiting':'scheduled';}
const scheduleLabels=()=>({working:tr('Çalışıyor','Working'),waiting:tr('Bekliyor','Waiting'),scheduled:tr('Planlandı','Scheduled'),completed:tr('Tamamlandı','Completed'),paused:tr('Durduruldu','Paused'),failed:tr('Hata','Failed')});
const scheduleTemplates=()=>[
 [tr('Günlük özet','Daily briefing'),tr('Bu sohbetin son işlerini kısaca özetle.','Briefly summarise this chat’s recent work.')],
 [tr('Konu araştır','Research a topic'),tr('Belirttiğim konunun güncel resmî kaynaklarını araştır ve kısa özet sun.','Research current official sources for my topic and give a brief summary.')],
 [tr('Proje kontrolü','Project check-in'),tr('Proje hedeflerini ve açık işleri incele, sıradaki adımları öner.','Review project goals and open work; suggest next steps.')],
 [tr('Haftalık değerlendirme','Weekly review'),tr('Bu hafta yapılanları ve kalan işleri kısa maddelerle özetle.','Summarise completed and remaining work this week.')]
];
function rowHtml(it){
 const status=scheduleStatus(it),chat=it.running_chat||it.last_chat||it.source_chat||'';
 return '<li data-id="'+esc(it.id)+'" class="sp-card"><div class="sp-card-top"><b>'+esc(it.title)+'</b><span class="sp-status '+status+'">'+esc(scheduleLabels()[status])+'</span></div><p>'+esc(it.prompt)+'</p><small>'+esc([it.owner==='AUTO'?'JARVIS':it.owner,kindText(it),it.enabled&&it.next?when(it.next):''].filter(Boolean).join(' · '))+'</small><div class="sp-card-actions">'+(chat?'<button type="button" data-sp="chat" data-chat="'+esc(chat)+'">'+esc(tr('Sohbete git','Open chat'))+'</button>':'')+'<button type="button" data-sp="run">'+esc(tr('Şimdi çalıştır','Run now'))+'</button><label><input type="checkbox" data-sp="toggle"'+(it.enabled?' checked':'')+'>'+esc(tr('Etkin','Enabled'))+'</label><button type="button" data-sp="del" aria-label="'+esc(tr('Sil','Delete'))+'">×</button></div></li>';
}
function formHtml(){
  const kinds=[['daily',tr('Her gün','Every day')],['weekdays',tr('Hafta içi','Weekdays')],['hourly',tr('Saatlik','Hourly')],['once',tr('Bir kez','Once')]];
  const hours=Array.from({length:24},(_,i)=>'<option value="'+(i+1)+'">'+(i+1)+'</option>').join('');
  return '<form class="sp-form" autocomplete="off"><input name="title" maxlength="80" placeholder="'+esc(tr('Başlık (isteğe bağlı)','Title (optional)'))+'">'+
    '<textarea name="prompt" rows="3" maxlength="2000" placeholder="'+esc(tr('Ne yapılsın? Örn: Bugünkü işleri özetle ve öncelik sırala.','What should it do? e.g. Summarise today’s work and rank it.'))+'" required></textarea>'+
    '<div class="sp-row"><select name="owner" aria-label="'+esc(tr('Ajan','Agent'))+'">'+owners().map(n=>'<option value="'+esc(n)+'">'+esc(n==='AUTO'?tr('Otomatik ajan','Auto agent'):n)+'</option>').join('')+'</select>'+
    '<select name="kind" aria-label="'+esc(tr('Sıklık','Repeat'))+'">'+kinds.map(k=>'<option value="'+k[0]+'"'+(k[0]===formKind?' selected':'')+'>'+esc(k[1])+'</option>').join('')+'</select>'+
    '<input type="time" name="clock" value="09:00" class="sp-when" data-for="daily weekdays" aria-label="'+esc(tr('Saat','Time'))+'">'+
    '<input type="datetime-local" name="moment" class="sp-when" data-for="once" aria-label="'+esc(tr('Tarih ve saat','Date and time'))+'">'+
    '<label class="sp-when sp-every" data-for="hourly">'+esc(tr('Her','Every'))+' <select name="every">'+hours+'</select> '+esc(tr('saatte','h'))+'</label></div>'+
    '<div class="sp-foot"><span class="sp-err" role="alert"></span><button type="submit" class="sp-add">'+esc(tr('Ekle','Add'))+'</button></div></form>';
}
function syncWhen(){panel.querySelectorAll('.sp-when').forEach(el=>{el.hidden=!el.dataset.for.split(' ').includes(formKind);});}
function drawPanel(force){
  if(!open&&!force)return;
  const rows=(state.scheduled||[]).filter(it=>scheduleFilter==='all'||scheduleStatus(it)===scheduleFilter);
  const sig=JSON.stringify([rows,owners(),lang(),state.language,scheduleTab,scheduleFilter]);
  if(panel.dataset.sig===sig&&!force)return;
  // never rebuild while Berke is typing into the form
  if(!force&&panel.contains(document.activeElement)&&document.activeElement.closest('.sp-form'))return;
  panel.dataset.sig=sig;
  const keep=panel.querySelector('.sp-form');const draft=keep?Object.fromEntries(new FormData(keep)):{};
  panel.innerHTML='<div class="sp-head"><b>'+esc(tr('Zamanlanmış görevler','Scheduled tasks'))+'</b><button type="button" class="sp-x" data-sp="close" aria-label="'+esc(tr('Kapat','Close'))+'">×</button></div>'+
    '<p class="sp-note">'+esc(tr('JARVIS açıkken çalışır. Görev yeni bir sohbette başlar; bitince bildirim gelir.','Runs while JARVIS is open. A task starts in a new chat and you get a notification when it finishes.'))+'</p>'+
    '<div class="sp-toolbar"><button type="button" data-sp="yours" class="'+(scheduleTab==='yours'?'active':'')+'">'+esc(tr('Görevlerim','Yours'))+'</button><button type="button" data-sp="templates" class="'+(scheduleTab==='templates'?'active':'')+'">'+esc(tr('Şablonlar','Templates'))+'</button><select data-sp="filter" aria-label="'+esc(tr('Durum filtresi','Status filter'))+'"><option value="all">'+esc(tr('Tümü','All'))+'</option>'+Object.entries(scheduleLabels()).map(([v,l])=>'<option value="'+v+'"'+(scheduleFilter===v?' selected':'')+'>'+esc(l)+'</option>').join('')+'</select><button type="button" data-sp="create-chat">'+esc(tr('JARVIS ile oluştur','Create with JARVIS'))+'</button></div>'+
    (scheduleTab==='templates'?'<div class="sp-templates">'+scheduleTemplates().map(([title,prompt],i)=>'<button type="button" data-sp="template" data-template="'+i+'"><b>'+esc(title)+'</b><span>'+esc(prompt)+'</span></button>').join('')+'</div>':rows.length?'<ul class="sp-list">'+rows.map(rowHtml).join('')+'</ul>':'<p class="sp-empty">'+esc(tr('Bu görünümde görev yok. Sohbetten veya yeni görevle oluştur.','No tasks in this view. Create one in chat or add a new task.'))+'</p>')+'<details class="sp-manual"><summary>'+esc(tr('Yeni görev · elle ayarla','New task · set up manually'))+'</summary>'+formHtml()+'</details>';
  const form=panel.querySelector('.sp-form');
  for(const [k,v] of Object.entries(draft)){const el=form.elements[k];if(el&&typeof v==='string')el.value=v;}
  formKind=form.elements.kind.value;syncWhen();
}
panel.addEventListener('change',e=>{
  if(e.target.dataset.sp==='filter'){scheduleFilter=e.target.value;drawPanel(true);return;}
  if(e.target.name==='kind'){formKind=e.target.value;syncWhen();return;}
  if(e.target.dataset.sp==='toggle'){const li=e.target.closest('li');ok(()=>api('schedule-toggle',{id:li.dataset.id,enabled:e.target.checked}).catch(err=>{toast(err.message);drawPanel(true);}));}
});
panel.addEventListener('click',e=>{
  const b=e.target.closest('[data-sp]');if(!b||b.tagName==='INPUT')return;
  const li=b.closest('li');
  if(['yours','templates'].includes(b.dataset.sp)){scheduleTab=b.dataset.sp;drawPanel(true);return;}
  if(b.dataset.sp==='template'){const template=scheduleTemplates()[Number(b.dataset.template)];scheduleTab='yours';drawPanel(true);panel.querySelector('.sp-manual').open=true;panel.querySelector('[name=title]').value=template[0];panel.querySelector('[name=prompt]').value=template[1];return;}
  if(b.dataset.sp==='create-chat'){setOpen(false);view('mission');const prompt=document.getElementById('prompt');prompt.value=tr('Yarın saat 09:00 bu sohbetin işlerini özetlemeyi zamanla','Schedule a summary of this chat tomorrow at 09:00');prompt.focus();return;}
  if(b.dataset.sp==='chat'){api('select-chat',{id:b.dataset.chat}).then(()=>{setOpen(false);view('mission');}).catch(e=>toast(e.message));return;}
  if(b.dataset.sp==='close')setOpen(false);
  if(b.dataset.sp==='del'&&li)api('schedule-remove',{id:li.dataset.id}).then(()=>drawPanel(true)).catch(err=>toast(err.message));
  if(b.dataset.sp==='run'&&li)api('schedule-run',{id:li.dataset.id}).then(()=>{setOpen(false);toast(tr('Görev yeni sohbette başladı.','Task started in a new chat.'));}).catch(err=>toast(err.message));
});
panel.addEventListener('submit',e=>{
  e.preventDefault();const f=e.target,v=Object.fromEntries(new FormData(f)),err=f.querySelector('.sp-err');
  const body={title:v.title,prompt:v.prompt,owner:v.owner,kind:v.kind,every:Number(v.every||1),at:v.kind==='once'?v.moment:v.clock};
  if(v.kind==='once'&&!v.moment){err.textContent=tr('Tarih ve saat seç.','Pick a date and time.');return;}
  api('schedule-add',body).then(()=>{f.reset();err.textContent='';drawPanel(true);}).catch(x=>{err.textContent=x.message;});
});
// --- notification bell
const bell=document.createElement('button');bell.type='button';bell.id='bellButton';bell.className='device-button bell-btn';bell.setAttribute('aria-haspopup','dialog');
bell.innerHTML=bellIcon+'<b class="bell-badge" hidden></b>';
if(deviceBtn)deviceBtn.before(bell);else document.body.append(bell);
const pop=document.createElement('section');pop.className='bell-panel hidden';pop.setAttribute('role','dialog');document.body.append(pop);
let bellOpen=false;
const icon={done:'✓',permission:'!',quota:'%',schedule:'⏰',error:'×'};
const ago=ts=>{const s=Math.max(0,Date.now()/1000-ts);if(s<90)return tr('şimdi','now');if(s<5400)return Math.round(s/60)+tr(' dk',' min');if(s<86400)return Math.round(s/3600)+tr(' sa',' h');return new Date(ts*1000).toLocaleDateString(lang(),{day:'numeric',month:'short'});};
function drawBell(){
  const rows=(state.notifications||[]).slice().reverse(),unread=rows.filter(n=>!n.read).length;
  const badge=bell.querySelector('.bell-badge');badge.hidden=!unread;badge.textContent=unread>9?'9+':String(unread);
  const macState=bell.dataset.macNotificationStatus;
  const macHint=macState?({allowed:tr('Mac bildirimleri açık','Mac notifications allowed'),denied:tr('Mac bildirimleri kapalı','Mac notifications off'),'not-set':tr('Mac bildirim izni bekleniyor','Mac notification permission pending')})[macState]||tr('Mac bildirim durumu bilinmiyor','Mac notification status unknown'):'';
  bell.title=tr('Bildirimler','Notifications')+(macHint?' · '+macHint:'');bell.setAttribute('aria-label',tr('Bildirimler','Notifications')+(unread?' ('+unread+')':''));
  badge.parentElement.dataset.unread=unread?'1':'0';
  if(unread!==lastBadge){lastBadge=unread;if(typeof nativeSend==='function')ok(()=>nativeSend('badge',{count:unread}));}
  if(!bellOpen)return;
  const bellSig=JSON.stringify([rows.map(n=>[n.id,n.read,n.title,n.body,n.chat_id,Math.floor((Date.now()/1000-n.ts)/60)]),state.language,macState]);
  if(pop.dataset.signature===bellSig)return;pop.dataset.signature=bellSig;
  pop.innerHTML='<div class="bp-head"><b>'+esc(tr('Bildirimler','Notifications'))+'</b><span><button type="button" class="bp-link" data-bp="read">'+esc(tr('Okundu say','Mark read'))+'</button><button type="button" class="bp-link" data-bp="clear">'+esc(tr('Temizle','Clear'))+'</button></span></div>'+
    (rows.length?'<ul class="bp-list">'+rows.map(n=>'<li data-id="'+esc(n.id)+'" data-chat="'+esc(n.chat_id||'')+'" class="'+esc(n.kind)+(n.read?'':' unread')+'"><i>'+esc(icon[n.kind]||'•')+'</i><div><b>'+esc(n.title)+'</b>'+(n.body?'<span>'+esc(n.body)+'</span>':'')+'</div><time>'+esc(ago(n.ts))+'</time></li>').join('')+'</ul>':'<p class="bp-empty">'+esc(tr('Bildirim yok.','Nothing new.'))+'</p>')+((typeof nativeHost!=='undefined'&&nativeHost)?'<div class="bp-permission"><span>'+esc(macHint||tr('Mac bildirim durumu okunuyor','Reading Mac notification permission'))+'</span>'+(macState==='allowed'?'':'<button type="button" class="bp-link" data-bp="permission">'+esc(macState==='denied'?tr('Ayarları aç','Open settings'):tr('Bildirimleri aç','Enable notifications'))+'</button>')+'</div>':'');
}
let lastBadge=-1;
function placeBell(){const r=bell.getBoundingClientRect();pop.style.setProperty('left',Math.max(8,Math.min(innerWidth-336,r.left))+'px');pop.style.setProperty('bottom',Math.max(8,innerHeight-r.top+8)+'px');}
const setBell=v=>{bellOpen=v;pop.classList.toggle('hidden',!v);bell.setAttribute('aria-expanded',String(v));if(v){placeBell();drawBell();}};
bell.addEventListener('click',e=>{e.stopPropagation();setBell(!bellOpen);});
document.addEventListener('click',e=>{if(bellOpen&&!pop.contains(e.target)&&!bell.contains(e.target))setBell(false);});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&bellOpen)setBell(false);});
pop.addEventListener('click',async e=>{
  const act=e.target.closest('[data-bp]');
  if(act){if(act.dataset.bp==='permission'){nativeSend(bell.dataset.macNotificationStatus==='denied'?'open-notification-settings':'request-notifications');return;}if(act.dataset.bp==='read')ok(()=>api('notify-read',{}));if(act.dataset.bp==='clear')ok(()=>api('notify-clear',{}));return;}
  const li=e.target.closest('li[data-id]');if(!li)return;
  setBell(false);
  try{
    await api('notify-read',{ids:[li.dataset.id]});
    const notice=(state.notifications||[]).find(n=>n.id===li.dataset.id);
    if(notice?.action==='mac-permissions'){showMacPermissionHelp();return;}
    const chat=li.dataset.chat;
    if(chat&&chat!==state.active_chat&&(state.chats||[]).some(c=>c.id===chat)){await api('select-chat',{id:chat});}
    if(typeof view==='function')await view('mission');
  }catch(err){toast(err.message);}
});
// --- Mac banners: only while the window is in the background; the bell already shows everything when it is in front
const sentNow=new Set(),watching=new Map();
const brief=(t,n)=>{t=String(t||'').replace(/\s+/g,' ').trim();return t.length>n?t.slice(0,n-1)+'…':t;};
let nativeAppFocused=null;
window.addEventListener('jarvis-native',e=>{if(e.detail.type==='app-focus')nativeAppFocused=Boolean(e.detail.data.active);});
const away=()=>nativeAppFocused===false||document.hidden||!document.hasFocus();
function banners(){
  const fresh=(state.notifications||[]).filter(n=>!n.sent&&!sentNow.has(n.id));
  if(fresh.length){
    fresh.forEach(n=>sentNow.add(n.id));
    if(away()&&typeof nativeSend==='function')fresh.filter(n=>Date.now()/1000-n.ts<900).slice(-3).forEach(n=>ok(()=>nativeSend('notify',{title:n.title,body:n.body,chat_id:n.chat_id,kind:n.kind,action:n.action})));
    ok(()=>api('notify-sent',{ids:fresh.map(n=>n.id)}).catch(()=>{}));
  }
  // a single answer that finished while Berke was elsewhere (team and scheduled runs already have their own notification)
  for(const m of state.messages||[]){
    if(m.author==='YOU'||m.workflow_id)continue;
    if(m.status==='streaming'){watching.set(m.id,true);continue;}
    if(watching.delete(m.id)&&m.status==='done'&&away()&&typeof nativeSend==='function')ok(()=>nativeSend('notify',{title:m.author+tr(' yanıtladı',' replied'),body:brief(m.text,110),kind:'done'}));
  }
}
const before=renderWorkspace;renderWorkspace=function(){before();paint();};
function paint(){
  if(typeof state==='undefined'||!state)return;
  nav.querySelector('small').textContent=tr('Zamanlanmış','Scheduled');nav.setAttribute('aria-label',tr('Zamanlanmış görevler','Scheduled tasks'));
  drawPanel(false);drawBell();banners();
}
setInterval(()=>{if(bellOpen)drawBell();},30000);
paint();
})();

// 5-hour quota warning: ONE dismissible banner above the chat, only when 25% or less is left, once per window.
// It is not a chat message, it is the same in every chat, and once dismissed it never comes back for that window.
(()=>{
const list=document.getElementById('messages');if(!list)return;
const banner=document.createElement('div');banner.className='quota-banner hidden';banner.setAttribute('role','status');list.before(banner);
const dismissed=new Set();let drawn='';
function openQuota(key){
 const name=key==='CLAUDE_PRO'?'VISION':key==='FRIDAY'?'FRIDAY':key==='EDITH'?'EDITH':'VISION';
 showAgentDetails(name);document.querySelector('[data-agent-tab="quota"]')?.click();
}
const labelOf=name=>name==='CLAUDE_PRO'?'VISION · Claude':name==='FRIDAY'?'FRIDAY · Codex':'Gemini';
function hits(){
 const out=[];
 for(const [name,u] of Object.entries(state.provider_usage||{}))if(u?.status==='live')for(const w of ['primary','secondary']){
  const p=u[w];if(p?.minutes!==300||typeof p.used_percent!=='number'||p.used_percent<75||p.used_percent>100)continue;
  const key=name+':'+w+':'+Math.floor(p.resets_at||0)+':75';
  if(dismissed.has(key)||(state.quota_milestones||[]).includes(key))continue;
  out.push({name,w,key,left:Math.max(0,Math.round(100-p.used_percent)),reset:p.resets_at});
 }
 return out.sort((x,y)=>x.left-y.left).slice(0,3);
}
function paint(){
 if(typeof state==='undefined'||!state)return;
 // receipts written by older versions stay in the history but are no longer shown
 document.querySelectorAll('#messages>.message').forEach(row=>{if(row.querySelector('.quota-open'))row.querySelector('.quota-open').remove();});
 const messages=state.messages.filter(m=>(m.channel||'common')===document.getElementById('channel').value);
 document.querySelectorAll('#messages>.message').forEach((row,i)=>{if(messages[i]?.quota_notice)row.classList.add('hidden');});
 const rows=hits(),sig=rows.map(r=>r.key+':'+r.left).join('|')+'|'+state.language;
 if(sig===drawn)return;drawn=sig;
 banner.classList.toggle('hidden',!rows.length);
 banner.innerHTML=rows.map(r=>{
  const when=r.reset?new Date(r.reset*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false}):'';
  return '<div class="qb-row" data-key="'+esc(r.key)+'" data-provider="'+esc(r.name)+'"><span class="qb-text"><b>'+esc(labelOf(r.name))+'</b> · '+esc(tr('5 saatlik kota: %'+r.left+' kaldı','5-hour limit: '+r.left+'% left'))+(when?'<span class="qb-sub">'+esc(tr(when+'’de sıfırlanır','Resets at '+when))+'</span>':'')+'</span><button type="button" class="qb-open" data-qb="open">'+esc(tr('Kota ayrıntıları','Usage details'))+'</button><button type="button" class="qb-x" data-qb="x" aria-label="'+esc(tr('Kapat','Dismiss'))+'">×</button></div>';
 }).join('');
}
banner.addEventListener('click',e=>{
 const row=e.target.closest('.qb-row');if(!row)return;
 if(e.target.closest('[data-qb="x"]')){
  const key=row.dataset.key,parts=key.split(':');dismissed.add(key);drawn='';
  api('quota-note',{provider:parts[0],window:parts[1]}).catch(()=>{});
  paint();
 }else if(e.target.closest('[data-qb="open"]'))openQuota(row.dataset.provider);
});
const prior=renderWorkspace;renderWorkspace=function(){prior();paint();};
})();

// Read-only system notification permission: no toggle or permission click on Berke's behalf.
(()=>{
 let checked=false;
 window.addEventListener('jarvis-native',e=>{
  if(e.detail.type==='app-focus'&&e.detail.data.active&&typeof nativeHost!=='undefined'&&nativeHost){nativeSend('notification-status');return;}
  if(e.detail.type!=='notification-status')return;
  const b=document.getElementById('bellButton');if(!b)return;
  b.dataset.macNotificationStatus=e.detail.data.status;
  if(typeof renderWorkspace==='function'&&typeof state!=='undefined'&&state)renderWorkspace();
  b.setAttribute('aria-description',({allowed:tr('Mac bildirimleri açık','Mac notifications allowed'),denied:tr('Mac bildirimleri kapalı; Sistem Ayarları’ndan Berke açabilir','Mac notifications off; Berke can enable them in System Settings'),'not-set':tr('Mac bildirim izni henüz seçilmedi','Mac notification permission not yet chosen')})[e.detail.data.status]||tr('Mac bildirim durumu bilinmiyor','Mac notification status unknown'));
 });
 const prior=renderWorkspace;renderWorkspace=function(){prior();if(!checked&&typeof nativeHost!=='undefined'&&nativeHost){checked=true;nativeSend('notification-status');}};
})();

// All connected private channels use their own chat; only manual connectors show export tools.
(()=>{const prior=renderWorkspace;renderWorkspace=function(){prior();const channel=$('#channel').value,a=state.agents.find(a=>a.name===channel);$('#directTools').classList.toggle('hidden',channel==='common'||a?.connector!=='manual');};})();

// "Used your computer ▸ [shot][shot] +3": small thumbnails of the screens an agent really looked at, in the chat work line.
// Frames come only from real computer-control results, stay in memory (never saved), and a click opens them larger.
(()=>{
const list=document.getElementById('messages'),channelBox=document.getElementById('channel');
if(!list||!channelBox)return;
const DESKTOP=/desktop|computer|screen_capture/i,KEEP=12,MESSAGES=6;
const pending={},owned={};
const same=(a,b)=>Boolean(a&&b&&a.src.length===b.src.length&&a.src.slice(-96)===b.src.slice(-96));
function computerUse(m){
  const ds=typeof state!=='undefined'&&state&&state.desktop_session;
  if(m.status==='streaming'&&ds&&ds.chat_id===state.active_chat)return true;
  return (m.activities||[]).some(a=>DESKTOP.test(String(a.kind||'')));
}
function trim(){const ids=Object.keys(owned);ids.slice(0,Math.max(0,ids.length-MESSAGES)).forEach(id=>delete owned[id]);}
window.addEventListener('jarvis-native',e=>{
  const d=e.detail;if(!d||d.type!=='desktop-result')return;
  const r=d.data&&d.data.result;
  if(!r||typeof r.image!=='string'||!r.image.startsWith('data:image/jpeg'))return;
  const ds=typeof state!=='undefined'&&state&&state.desktop_session;
  const chat=(ds&&ds.chat_id)||(typeof state!=='undefined'&&state&&state.active_chat)||'';
  const rows=pending[chat]=pending[chat]||[],frame={src:r.image,app:String(r.application||''),at:Date.now()};
  if(same(rows[rows.length-1],frame))return;
  rows.push(frame);if(rows.length>40)rows.shift();
  decorate();
});
function decorate(){
  if(typeof state==='undefined'||!state||!Array.isArray(state.messages))return;
  const chat=state.active_chat,visible=state.messages.filter(m=>(m.channel||'common')===channelBox.value),rows=list.querySelectorAll('.message');
  let target=null;
  visible.forEach((m,i)=>{if(m.author!=='YOU'&&rows[i]&&computerUse(m))target=m;});
  if(target&&(pending[chat]||[]).length){
    const mine=owned[target.id]||[];
    pending[chat].splice(0).forEach(f=>{if(!same(mine[mine.length-1],f))mine.push(f);});
    owned[target.id]=mine.slice(-KEEP);trim();
  }
  visible.forEach((m,i)=>{
    const row=rows[i];if(!row||m.author==='YOU')return;
    const frames=owned[m.id],head=row.querySelector('.work-line>summary');
    let strip=head&&head.querySelector('.wl-shots');
    if(!frames||!frames.length||!head){if(strip)strip.remove();return;}
    const sig=frames.length+':'+frames[frames.length-1].at+':'+state.language;
    if(strip&&strip.dataset.sig===sig)return;
    if(!strip){
      strip=document.createElement('span');strip.className='wl-shots';strip.setAttribute('role','group');
      head.insertBefore(strip,head.querySelector('.wl-time')||head.querySelector('.wl-chev'));
    }
    strip.dataset.sig=sig;strip.dataset.mid=m.id;strip.textContent='';
    strip.setAttribute('aria-label',tr('Ekran görüntüleri','Screenshots'));strip.title=tr('Ekran görüntülerini aç','Open the screenshots');
    const shown=frames.slice(-3),first=frames.length-shown.length;
    shown.forEach((f,k)=>{const img=document.createElement('img');img.className='wl-shot';img.alt=tr('Ekran görüntüsü ','Screenshot ')+(first+k+1);img.dataset.k=String(first+k);img.src=f.src;strip.appendChild(img);});
    if(first>0){const more=document.createElement('span');more.className='wl-more';more.textContent='+'+first;strip.appendChild(more);}
  });
}
let box=null,at=0,set=[];
function closeBox(){if(box){box.remove();box=null;document.removeEventListener('keydown',keys,true);}}
function keys(e){
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeBox();}
  else if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();e.stopPropagation();show(at+(e.key==='ArrowRight'?1:-1));}
}
function show(index){
  if(!box||!set.length)return;
  at=(index+set.length)%set.length;const f=set[at];
  box.querySelector('img').src=f.src;
  box.querySelector('.sl-cap').textContent=(f.app?f.app+' · ':'')+(at+1)+' / '+set.length;
}
function open(frames,index){
  closeBox();set=frames.slice();
  box=document.createElement('div');box.className='shot-lightbox';box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');box.setAttribute('aria-label',tr('Bilgisayar ekranı','Computer screen'));
  const img=document.createElement('img'),cap=document.createElement('div'),close=document.createElement('button');
  cap.className='sl-cap';close.type='button';close.className='sl-close';close.textContent='×';close.setAttribute('aria-label',tr('Kapat','Close'));
  img.alt=tr('Bilgisayar ekranı','Computer screen');
  box.append(img,cap,close);document.body.appendChild(box);
  box.addEventListener('click',e=>{if(e.target===img){show(at+1);return;}closeBox();});
  document.addEventListener('keydown',keys,true);
  show(index);close.focus();
}
list.addEventListener('click',e=>{
  const strip=e.target.closest('.wl-shots');if(!strip)return;
  e.preventDefault();e.stopPropagation();
  const frames=owned[strip.dataset.mid];if(!frames||!frames.length)return;
  const k=e.target.closest('.wl-shot');open(frames,k?Number(k.dataset.k):frames.length-1);
},true);
const before=renderWorkspace;renderWorkspace=function(){before();decorate();};
decorate();
})();

// Spoken replies are a per-chat choice: each chat remembers on/off; a chat without a choice follows the saved default.
(function(){
  let syncedChat=null;
  const hush=()=>{if(nativeHost)nativeSend('stop-speech');};
  const chatOf=id=>(state.chats||[]).find(c=>c.id===id)||{};
  function wanted(){
    const own=chatOf(state.active_chat).voice_replies;
    if(own==='on')return true;
    if(own==='off')return false;
    try{return localStorage.getItem('jarvis-spoken-replies')!=='off';}catch(error){return true;}
  }
  function sync(){
    if(typeof liveConversation!=='undefined'&&liveConversation)return;
    const changed=syncedChat!==state.active_chat;
    if(changed&&syncedChat!==null)hush();
    syncedChat=state.active_chat;
    const want=wanted();
    if(want!==voiceEnabled||changed){const was=voiceEnabled;voiceEnabled=want;if(was&&!want)hush();setVoiceState(want?'MAC SES MOTORU HAZIR':'YAZILI SOHBET HAZIR');}
  }
  $('#speakerButton').onclick=()=>{
    sound();
    const next=!voiceEnabled;voiceEnabled=next;
    if(!next)hush();else if(nativeHost)nativeSend('speak',{text:'Merhaba Berke. Seni dinliyorum.'});
    setVoiceState(next?'MAC SES MOTORU HAZIR':'YAZILI SOHBET HAZIR');
    safe(()=>api('chat-voice',{id:state.active_chat,mode:next?'on':'off'}));
  };
  const earlier=renderWorkspace;renderWorkspace=function(){sync();earlier.apply(this,arguments);};
})();

// Message footer, like the Claude app: a time on every message (always visible on SYSTEM cards, on hover elsewhere),
// and on your own messages Edit / Copy / new reply. Assistant replies get "new reply" next to Copy.
(function(){
  const host=document.getElementById('messages');
  if(!host)return;
  const parse=value=>{const m=String(value||'').match(/^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d)(?::(\d\d))?/);return m?new Date(+m[1],m[2]-1,+m[3],+m[4],+m[5],+(m[6]||0)):null;};
  const locale=()=>state.language==='en'?'en-GB':'tr-TR';
  function label(value){
    const d=parse(value);if(!d)return '';
    const now=new Date(),minutes=Math.floor((now-d)/60000);
    const clock=d.toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'});
    if(d.toDateString()===now.toDateString()){
      if(minutes<1)return clock+' · '+tr('şimdi','just now');
      if(minutes<60)return clock+' · '+tr(minutes+' dk önce',minutes+' min ago');
      return clock;
    }
    const yesterday=new Date(now);yesterday.setDate(now.getDate()-1);
    if(d.toDateString()===yesterday.toDateString())return tr('Dün ','Yesterday ')+clock;
    return d.toLocaleDateString(locale(),{day:'numeric',month:'short'})+' '+clock;
  }
  function stamp(el,value){el.dataset.ts=value;el.title=value;el.textContent=label(value);}
  function button(kind,text){const b=document.createElement('button');b.type='button';b.dataset.foot=kind;b.textContent=text;return b;}
  function precedingYou(m){
    const rows=state.messages.filter(x=>(x.channel||'common')===(m.channel||'common'));
    const at=rows.findIndex(x=>String(x.id)===String(m.id));
    for(let i=at-1;i>=0;i--)if(rows[i].author==='YOU')return rows[i];
    return null;
  }
  function decorate(){
    for(const el of host.querySelectorAll(':scope > .message[data-message-id]')){
      const m=state.messages.find(x=>String(x.id)===el.dataset.messageId);
      if(!m)continue;
      el.classList.toggle('is-system',m.author==='SYSTEM');
      el.classList.toggle('is-progress',Boolean(m.progress));
      el.classList.toggle('is-joined',Boolean(m.joined));
      el.classList.toggle('is-finished',Boolean(m.finished));
      const capsule=m.joined||m.finished;
      if(capsule&&typeof agentColor==='function'){const tint=agentColor(capsule);if(el.style.getPropertyValue('--agent')!==tint)el.style.setProperty('--agent',tint);}
      const finished=m.status!=='streaming'&&m.status!=='queued';
      if(m.author==='YOU'){
        if(!finished||el.querySelector('.you-foot'))continue;
        const foot=document.createElement('div');foot.className='you-foot';
        const t=document.createElement('time');stamp(t,m.time);foot.append(t,button('edit',tr('Düzenle','Edit')),button('copy',tr('Kopyala','Copy')),button('retry',tr('Yeni yanıt','New reply')));
        el.querySelector('.message-content').append(foot);
        continue;
      }
      const time=el.querySelector('.message-meta time');
      if(time&&time.dataset.ts!==m.time)stamp(time,m.time);
      const actions=el.querySelector('.reply-actions');
      if(finished&&actions&&!actions.querySelector('[data-foot]')&&m.author!=='SYSTEM'&&!m.progress&&precedingYou(m))actions.append(button('retry',tr('Yeni yanıt','New reply')));
    }
  }
  // Edit and "new reply" work in place, like the Claude app: the message is replaced and the replies after it are generated again.
  function replace(id,text){
    if(busy||state.model_job){toast(tr('Yanıt hazırlanıyor. Durdur düğmesiyle kesebilirsin.','A reply is in progress. Use Stop to cancel it.'));return;}
    busy=true;
    safe(async()=>{try{await api('edit-message',{id,text});}finally{busy=false;}});
  }
  function startEdit(el,m){
    if(busy||state.model_job){toast(tr('Yanıt hazırlanıyor. Durdur düğmesiyle kesebilirsin.','A reply is in progress. Use Stop to cancel it.'));return;}
    if(el.classList.contains('editing'))return;
    const shown=el.querySelector('.message-text');
    el.classList.add('editing');shown.hidden=true;
    const box=document.createElement('div');box.className='msg-edit';
    const area=document.createElement('textarea');area.value=m.text;area.rows=Math.min(10,Math.max(2,m.text.split('\n').length));area.setAttribute('aria-label',tr('Mesajı düzenle','Edit message'));
    const hint=document.createElement('p');hint.className='msg-edit-hint';hint.textContent=tr('Kaydedersen bu mesajdan sonraki yanıtlar silinir ve yeniden üretilir.','If you save, the replies after this message are removed and generated again.');
    const row=document.createElement('div');row.className='msg-edit-actions';
    const save=button('save',tr('Kaydet ve gönder','Save and send')),cancel=button('cancel',tr('Vazgeç','Cancel'));
    save.classList.add('primary');row.append(cancel,save);box.append(area,hint,row);shown.after(box);
    const close=()=>{box.remove();shown.hidden=false;el.classList.remove('editing');};
    const commit=()=>{const value=area.value.trim();if(!value)return;if(value===m.text.trim()){close();return;}replace(m.id,value);};
    cancel.onclick=close;save.onclick=commit;
    area.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}else if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();commit();}});
    area.focus();area.setSelectionRange(area.value.length,area.value.length);
  }
  host.addEventListener('click',e=>{
    const b=e.target.closest('[data-foot]');if(!b)return;
    const el=b.closest('.message[data-message-id]');if(!el)return;
    const m=state.messages.find(x=>String(x.id)===el.dataset.messageId);if(!m)return;
    sound();
    if(b.dataset.foot==='copy')return copyReply(m.text);
    if(b.dataset.foot==='edit'){startEdit(el,m);return;}
    if(b.dataset.foot==='retry'){
      const source=m.author==='YOU'?m:precedingYou(m);
      if(source)replace(source.id,source.text);
    }
  });
  setInterval(()=>{if(document.hidden)return;host.querySelectorAll('time[data-ts]').forEach(t=>{t.textContent=label(t.dataset.ts);});},30000);
  const earlier=renderWorkspace;renderWorkspace=function(){earlier.apply(this,arguments);decorate();};
  decorate();
})();

// A question from an agent gets its own answer box right under it. The reply continues that topic and goes to whoever asked,
// so Berke does not have to type into the main "Message JARVIS" field as if he were starting something new.
(function(){
  const host=document.querySelector('#messages');
  if(!host)return;
  const drafts=new Map(),focused=new Set();let sending=false;
  function target(){
    if(typeof state==='undefined'||!state||state.model_job)return null;
    const channel=document.querySelector('#channel');
    if(channel&&channel.value&&channel.value!=='common')return null;
    const rows=state.messages.filter(x=>(x.channel||'common')==='common'&&x.author!=='SYSTEM');
    const last=rows[rows.length-1];
    return last&&last.asks&&last.author!=='YOU'&&last.status!=='streaming'?last:null;
  }
  function build(m){
    const form=document.createElement('form');form.className='ask-box';form.dataset.for=String(m.id);
    if(typeof agentColor==='function')form.style.setProperty('--agent',agentColor(m.author));
    const label=document.createElement('label');label.className='ask-label';label.textContent=tr('↳ '+m.author+' sorusuna yanıtın','↳ Your answer to '+m.author);
    const area=document.createElement('textarea');area.rows=1;area.maxLength=4000;area.placeholder=tr('Yanıtını buraya yaz…','Type your answer here…');area.setAttribute('aria-label',label.textContent);
    area.value=drafts.get(String(m.id))||'';
    const send=document.createElement('button');send.type='submit';send.className='ask-send';send.textContent=tr('Gönder','Send');
    const row=document.createElement('div');row.className='ask-row';row.append(area,send);
    form.append(label,row);
    const fit=()=>{area.rows=Math.min(6,Math.max(1,area.value.split('\n').length));};
    area.addEventListener('input',()=>{drafts.set(String(m.id),area.value);fit();});
    area.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit();}});
    form.addEventListener('submit',e=>{
      e.preventDefault();
      const text=area.value.trim();
      if(!text||sending)return;
      sending=true;send.disabled=true;
      if(typeof sound==='function')sound();
      safe(async()=>{try{await api('converse',{text,channel:'common',reply_to:m.id});drafts.delete(String(m.id));}finally{sending=false;send.disabled=false;}});
    });
    fit();
    return form;
  }
  function sync(){
    const want=target();
    host.querySelectorAll('.ask-box').forEach(box=>{if(!want||box.dataset.for!==String(want.id))box.remove();});
    if(!want)return;
    const el=host.querySelector(':scope > .message[data-message-id="'+(window.CSS&&CSS.escape?CSS.escape(String(want.id)):String(want.id))+'"]');
    const content=el&&el.querySelector('.message-content');
    if(!content||content.querySelector('.ask-box'))return;
    const box=build(want);content.appendChild(box);
    if(!focused.has(String(want.id))){
      focused.add(String(want.id));
      const prompt=document.querySelector('#prompt'),active=document.activeElement;
      if(!active||active===document.body||(active===prompt&&!prompt.value))box.querySelector('textarea').focus({preventScroll:true});
    }
  }
  const earlier=renderWorkspace;renderWorkspace=function(){earlier.apply(this,arguments);sync();};
  sync();
})();
