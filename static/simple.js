'use strict';
// One conversation, contextual tools, optional project pane. No separate memory/screen/approval destinations.
document.querySelectorAll('.rail-btn[data-view="memory"],.rail-btn[data-view="screen"],.rail-btn[data-view="approvals"]').forEach(b=>b.remove());
$('.page-heading .eyebrow').innerHTML='BERKE’S WORKSPACE <span>/</span> <b id="buildBadge">v0.7.6</b>';
$('#pageTitle').textContent='Merhaba Berke.';$('#pageSubtitle').textContent='Bir sohbet. Bütün ekip.';
$('.page-footer').innerHTML='<span>JARVIS <b>MARK IV · v0.7.6</b></span><span>MAC · LOCAL FIRST</span>';
$('.memory-mini').classList.add('hidden');
const railLabels={mission:['Sohbet','◌'],project:['Proje','⌥'],settings:['Ayarlar','⚙']};
document.querySelectorAll('.rail-btn').forEach(b=>{const [label,icon]=railLabels[b.dataset.view];b.innerHTML='<span>'+icon+'</span><small>'+label+'</small>';b.setAttribute('aria-label',label);});
const tools=document.createElement('section');tools.id='chatTools';tools.className='chat-tools hidden';tools.innerHTML='<div class="tools-heading"><h3>Sohbet araçları</h3><button id="closeTools" class="icon-btn" aria-label="Kapat">×</button></div><div class="tool-actions"><button id="hostHandoff" class="button primary">ChatGPT’ye devret ↗</button><button id="watchHost" class="button">ChatGPT penceresini izle</button><button id="stopHost" class="button danger hidden">İzlemeyi durdur</button></div><p class="muted">Aktif bilgisayar/site işini ChatGPT’nin kendi uygulamasına taşı. Görev paketini orada gönderip izinleri ver; seçtiğin pencereyi burada canlı izle.</p><div id="hostMirror" class="hidden"><img id="hostFrame" alt="Seçilen ChatGPT penceresinin canlı görüntüsü"><p id="hostStatus" class="micro"></p></div><div class="tool-actions"><button id="shareScreenFromChat" class="button">Ekranla sesli konuş</button><button id="endScreenFromChat" class="button danger hidden">Ekran paylaşımını bitir</button></div><p class="muted">Bu uygulamadaki ekranlı sohbet, her sorunda güncel kareyi modele iletir; ChatGPT’nin fare/klavye araçlarından ayrıdır.</p><div class="site-helper"><input id="siteURL" type="url" placeholder="İncelediğin site: https://…" aria-label="Site adresi"><button id="openTaskSite" class="button">Siteyi aç ↗</button></div>';
$('.conversation .panel-head').after(tools);
const toolsButton=document.createElement('button');toolsButton.type='button';toolsButton.className='voice-btn';toolsButton.id='toolsButton';toolsButton.textContent='+ Araçlar';$('.voice-bar').prepend(toolsButton);
toolsButton.onclick=()=>tools.classList.toggle('hidden');$('#closeTools').onclick=()=>tools.classList.add('hidden');
$('#shareScreenFromChat').onclick=()=>$('#screenVoice').click();$('#endScreenFromChat').onclick=stopLiveScreenSharing;
$('#openTaskSite').onclick=()=>{try{const url=new URL($('#siteURL').value);if(!['http:','https:'].includes(url.protocol))throw new Error();nativeSend('open-task-site',{url:url.href});}catch{toast('Geçerli bir http/https adresi gir.');}};
$('#hostHandoff').onclick=()=>safe(async()=>{
 const channel=$('#channel').value;
 const latest=state.messages.filter(m=>m.author==='YOU'&&(m.channel||'common')===channel).slice(-1)[0];
 const instruction=$('#prompt').value.trim()||(latest?latest.text:'');
 if(!instruction){toast('Önce ne yapmasını istediğini yaz. Gönderilmeden görev paketi hazırlanır.');return;}
 const shared=state.share_context?state.messages.filter(m=>(m.channel||'common')==='common'&&m.author==='YOU').slice(-8).map(m=>m.text).join('\n'):'';
 const prompt='Berke için aktif bilgisayar/tarayıcı görevi.\n\n'+instruction+'\n\nOrtak bağlam (referans):\n'+shared+'\n\nÖnce hedef uygulamayı/siteyi doğrula. Hassas işlemlerde kendi onay akışını uygula. Sonunda yapılanları ve açık kalan işleri kısaca bildir.';
 nativeSend('handoff-chatgpt',{text:prompt});
});
$('#watchHost').onclick=()=>nativeSend('watch-chatgpt');$('#stopHost').onclick=()=>nativeSend('stop-host-watch');
const engine=document.createElement('select');engine.id='engineMode';engine.setAttribute('aria-label','Yanıt motoru');engine.innerHTML='<option value="auto">Otomatik · ekonomik</option><option value="local">Yerel · ücretsiz</option><option value="codex">Codex · güçlü</option>';
$('.compose-controls').prepend(engine);engine.onchange=()=>safe(()=>api('connection-settings',{chat_mode:engine.value}));
const context=document.createElement('label');context.className='switch-label context-toggle';context.innerHTML='<input id="shareContextToggle" type="checkbox"> Proje bağlamı';$('.compose-controls').append(context);
$('#shareContextToggle').onchange=()=>safe(()=>api('connection-settings',{share_context:$('#shareContextToggle').checked}));
const approvals=document.createElement('div');approvals.id='inlineApprovals';approvals.className='inline-approvals';$('#messages').after(approvals);
function renderInlineApprovals(){
 const pending=state.commands.filter(c=>c.status==='pending');
 approvals.innerHTML=pending.map(c=>`<article class="approval-message"><div class="approval-icon">◇</div><div><b>JARVIS onayını bekliyor</b><p>Bu komut yalnızca Python sürümünü okur.</p><code>${esc(c.argv.join(' '))}</code><div class="approval-actions"><button class="button" data-inline-command="${c.id}" data-decision="reject">Reddet</button><button class="button primary" data-inline-command="${c.id}" data-decision="approve">Bu komutu çalıştır</button></div></div></article>`).join('');
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-inline-command]');if(b)safe(async()=>{const id=b.dataset.inlineCommand,decision=b.dataset.decision;b.disabled=true;try{await api(decision,{id});renderInlineApprovals();sound(decision==='approve'?'approve':'send');}finally{if(b.isConnected)b.disabled=false;}});});
// Put advanced settings in a drawer over the conversation, rather than another primary destination.
const oldView=view;
view=async function(name){
 if(['settings','memory','screen','approvals'].includes(name)){
  if(name==='screen'){tools.classList.remove('hidden');return;}
  if(name==='approvals'){tools.classList.add('hidden');$('#messages').scrollTop=$('#messages').scrollHeight;return;}
  if(name==='memory'){name='settings';}
  const panel=$('#settings');panel.classList.remove('hidden');panel.classList.add('settings-drawer');
  Object.entries(state.settings).forEach(([key,value])=>$('#'+key).value=value);
  if(!$('#closeSettings')){const close=document.createElement('button');close.id='closeSettings';close.className='icon-btn';close.textContent='×';close.setAttribute('aria-label','Kapat');close.onclick=()=>{panel.classList.add('hidden');document.body.classList.remove('drawer-open');};panel.querySelector('.panel-head').appendChild(close);}
  document.body.classList.add('drawer-open');return;
 }
 $('#settings').classList.add('hidden');document.body.classList.remove('drawer-open');await oldView(name);
 if(name==='mission'){$('#pageTitle').textContent='Merhaba Berke.';$('#pageSubtitle').textContent='Bir sohbet. Bütün ekip.';}
};
const preferences=document.createElement('section');preferences.className='personal-preferences';preferences.innerHTML='<h3>Dil & ses</h3><div class="preference-grid"><label>Language / Dil<select id="languageChoice"><option value="tr">Türkçe</option><option value="en">English</option></select></label><label>Sesli giriş dili<select id="speechLanguageChoice"><option value="auto">Otomatik · Türkçe + English</option><option value="tr-TR">Türkçe</option><option value="en-GB">English (UK)</option></select></label><label>Asistan sesi<select id="voiceChoice"><option value="">Otomatik · sakin</option></select></label><button id="voicePreview" class="button">Sesi dene</button></div><p class="muted">Türkçe Yelda, English Samantha. Yalnızca kadın asistan sesleri. Kalite, Mac’te yüklü ses paketlerine bağlıdır.</p><h3>Yerel model</h3><p id="localModelState" class="muted"></p><p class="muted">Qwen3 1.7B · 2048 bağlam · düşünme kapalı · kısa, akışlı yanıt. Basit yönlendirme, hesap ve görev durumu model kullanmaz. Yerel başarısız olursa buluta sessiz geçiş yapılmaz.</p>';
$('#settings .connection-panel').after(preferences);
$('#languageChoice').onchange=()=>safe(async()=>{await api('connection-settings',{language:$('#languageChoice').value});setUILanguage(state.language);nativeSend('preferences',{language:state.language,speechLanguage:state.speech_language});});
$('#speechLanguageChoice').onchange=()=>safe(async()=>{await api('connection-settings',{speech_language:$('#speechLanguageChoice').value});nativeSend('preferences',{language:state.language,speechLanguage:state.speech_language});});
$('#voiceChoice').onchange=()=>nativeSend('preferences',{voice:$('#voiceChoice').value});
$('#voicePreview').onclick=()=>nativeSend('speak',{text:state.language==='en'?'Good morning, Berke. I am here. What shall we work on today?':'Merhaba Berke. Buradayım. Bugün ne üzerinde çalışalım?'});
const previousRender=renderWorkspace;
renderWorkspace=function(){
 previousRender();renderInlineApprovals();
 engine.value=state.chat_mode||'auto';$('#shareContextToggle').checked=state.share_context!==false;
 $('#languageChoice').value=state.language||'tr';$('#speechLanguageChoice').value=state.speech_language||'auto';
 $('#composerCostLabel').textContent=state.chat_mode==='codex'?'CODEX ABONELİK KOTASI':state.chat_mode==='local'?'YEREL · BULUT KOTASI YOK':'OTOMATİK · GEMINI / CODEX';
 $('#buildBadge').textContent='v'+(state.version||'0.3.0');
 $('#localModelState').textContent=state.local_status&&state.local_status.installed?'Yerel model kurulu. İlk yükleme sonrası yanıtlar bu Mac’te çalışır.':'Yerel model henüz hazır değil.';
 const label=state.chat_mode==='codex'?'Codex bağlantısı · abonelik kotası':state.chat_mode==='local'?'Yerel model · API $0':'JARVIS · otomatik ve ekonomik';$('#modelConnection').textContent=state.model_job?'Yanıt hazırlanıyor…':label;
 $('#endScreenFromChat').classList.toggle('hidden',!liveScreenSharing);
 if(typeof setUILanguage==='function')setUILanguage(state.language||'tr');
};
window.addEventListener('jarvis-native',e=>{
 const {type,data}=e.detail;
 if(type==='host-frame'){$('#hostMirror').classList.remove('hidden');$('#hostFrame').src=data.image;$('#hostStatus').textContent=data.title+' · '+data.time;$('#stopHost').classList.remove('hidden');}
 if(type==='host-stopped'){$('#hostMirror').classList.add('hidden');$('#hostFrame').removeAttribute('src');$('#stopHost').classList.add('hidden');}
 if(type==='host-error')toast(data.message);
 if(type==='voices'){$('#voiceChoice').innerHTML='<option value="">Otomatik · sakin</option>'+data.voices.map(v=>`<option value="${esc(v.id)}">${esc(v.name)} · ${esc(v.language)}</option>`).join('');$('#voiceChoice').value=data.selected||'';}
 if(type==='handoff-ready'){toast('Görev paketi kopyalandı. ChatGPT’de yeni sohbete yapıştırıp gönder. Sonra buradan pencereyi izle.');}
});
window.addEventListener('jarvis-ready',()=>nativeSend('preferences',{language:state.language||'tr',speechLanguage:state.speech_language||'auto'}));

const unpreparedVoiceStart=startVoiceRoom;
startVoiceRoom=function(){if((state.chat_mode==='local'||(state.chat_mode==='auto'&&!state.google_status?.verified))&&!liveScreenSharing)safe(()=>api('warm-local'));unpreparedVoiceStart();};
$('#micButton').onclick=startVoiceRoom;$('#liveVoice').onclick=startVoiceRoom;
const projectContextSettings=document.createElement('details');projectContextSettings.className='context-settings';projectContextSettings.innerHTML='<summary>Proje bağlamı · isteğe bağlı</summary>';
projectContextSettings.appendChild($('#briefForm'));$('#settings .personal-preferences').after(projectContextSettings);
