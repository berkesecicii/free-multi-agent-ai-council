'use strict';
let briefDirty=false,liveScreenSharing=false,pendingScreenVoice=false;
let pendingScreenImage=null,lastScreenImage=null,screenToAttach=null,knownModelMessages=null,sharedSignature='',voicePaused=false;
// Voice room text follows the language you speak (last detected), not the interface language.
let spokenLang='';try{spokenLang=localStorage.getItem('jarvis-speech-lang')||'';}catch(error){}
const voiceEnglish=()=>(spokenLang||(typeof state!=='undefined'&&state?.language)||'tr')==='en';
const vt=(trText,enText)=>voiceEnglish()?enText:trText;
let autoDetecting=false,quietRestarts=0;
function paintVoiceRoomLabels(){
 $('#voiceRoom').setAttribute('aria-label',vt('Canlı sesli konuşma','Live voice conversation'));
 $('#closeVoiceRoom').textContent=vt('Konuşmayı bitir ×','End conversation ×');
 $('#voiceInterrupt').textContent=vt('◉ Söz al / JARVIS’i sustur','◉ Interrupt / speak now');
 $('#voiceMute').textContent=voicePaused?vt('Mikrofonu aç','Resume microphone'):vt('Mikrofonu duraklat','Pause microphone');
 const micro=document.querySelector('#voiceRoom .micro');if(micro)micro.textContent=vt('SIRAYLA DİNLEME VE KONUŞMA · SES GERİ DÖNGÜSÜNE KARŞI YANIT SIRASINDA DİNLEME DURUR','TAKING TURNS · LISTENING PAUSES WHILE JARVIS SPEAKS TO AVOID AUDIO FEEDBACK');
}
// Collapsed agent cards: the 5-hour window comes first when the provider reports it; otherwise the window it does report is named.
function shortQuotaText(u,pool){
 const rows=[u?.primary,u?.secondary].filter(w=>w&&typeof w.used_percent==='number'&&w.used_percent>=0&&w.used_percent<=100);
 const five=rows.find(w=>w.minutes===300),w=five||rows[0];
 if(!w)return '';
 return Math.round(100-w.used_percent)+'% ('+(five?tr('5 sa','5h'):w.minutes===10080?tr('haftalık','weekly'):w.minutes===1440?tr('günlük','daily'):tr('kota','quota'))+') · '+pool;
}
const quotaLabel=mins=>mins===10080?'Haftalık':mins===1440?'Günlük':mins%60===0?(mins/60)+' saatlik':mins?mins+' dk':'Kota';
function usageMarkup(agent){
 const value=(state.provider_usage||{})[agent];
 if(['FRIDAY','EDITH','VISION','CLAUDE_PRO'].includes(agent)&&value&&value.status==='live'){
  const rows=[value.primary,value.secondary].filter(Boolean).map(w=>{
   const valid=typeof w.used_percent==='number'&&w.used_percent>=0&&w.used_percent<=100;
   const remaining=valid?Math.round(100-w.used_percent):null;
   const reset=w.resets_at?new Date(w.resets_at*1000).toLocaleString('tr-TR'):'';
   return `<div class="quota-row" data-quota-period="${w.minutes===10080?'week':'window'}" title="${esc(reset?'Yenilenme: '+reset:'Resmi kaynak yenileme saati döndürmedi')}"><span>${esc(quotaLabel(w.minutes))}</span><progress max="100" value="${remaining===null?0:remaining}" aria-label="${esc(quotaLabel(w.minutes))} kalan kota"></progress><b>${remaining===null?'?':remaining+'%'}</b></div>`;
  }).join('');
  const shortMissing=['EDITH','VISION'].includes(agent)&&![value.primary,value.secondary].some(w=>w?.minutes===300)?'<div class="quota-row quota-unavailable" title="'+esc(tr('Antigravity’nin resmi /usage çıktısı bu hesapta yalnızca haftalık sınır bildiriyor; 5 saatlik pencere verilmiyor.','Antigravity’s official /usage output reports only a weekly limit for this account; no 5-hour window is given.'))+'"><span>'+esc(tr('5 saatlik','5-hour'))+'</span><b>'+esc(tr('Bildirilmiyor','Not reported'))+'</b></div>':'';
  return shortMissing+rows+`<small class="quota-source">${agent==='FRIDAY'?'CODEX':agent==='CLAUDE_PRO'?'CLAUDE PRO · /usage':'GOOGLE · ANTIGRAVITY'} · ${esc(value.plan||'')} · ${esc(new Date(value.checked_at*1000).toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'}))}</small>`;
 }
 if(agent==='CLAUDE_PRO')return '<div class="quota-local">Claude Pro <b>'+tr('Bilinmiyor','Unknown')+'</b></div><small class="quota-source">/usage · '+tr('Saatlik sorgu · okunamadı','Hourly check · unavailable')+'</small>';
 if(agent==='JARVIS')return '<div class="quota-local">Koordinatör <b>JARVIS</b></div><small class="quota-source">SEÇİLİ SOHBET BAĞLANTISI</small>';
 if((agent==='EDITH'&&state.google_status?.verified)||(agent==='VISION'&&state.google_status?.claude_verified))return '<div class="quota-local">Antigravity <b>Bağlı</b></div><small class="quota-source">KALAN KOTA SAĞLANMIYOR</small>';
 if(agent==='EDITH')return '<div class="quota-local">Kalan kota <b>Bilinmiyor</b></div><small class="quota-source">ANTIGRAVITY · BAĞLANTI HENÜZ YOK</small>';
 return `<div class="quota-local">Kalan kota <b>Bilinmiyor</b></div><small class="quota-source">${value&&value.status==='error'?'SON SORGU BAŞARISIZ · YENİLE':'MANUEL BAĞLANTI'}</small>`;
}
let observedChat=null;
function renderWorkspace(){
 if(observedChat!==state.active_chat){observedChat=state.active_chat;knownModelMessages=new Set(state.messages.filter(m=>(m.model||m.provider==='rules')&&m.status!=='streaming').map(m=>m.id));}
 if(!knownModelMessages)knownModelMessages=new Set(state.messages.filter(m=>(m.model||m.provider==='rules')&&m.status!=='streaming').map(m=>m.id));
 for(const m of state.messages){
  if((m.model||m.provider==='rules')&&m.status!=='streaming'&&!knownModelMessages.has(m.id)){
   knownModelMessages.add(m.id);
   if((m.channel||'common')===$('#channel').value){
    if((m.status==='done'||m.provider==='rules')&&!m.joined&&!m.finished&&!m.voice_hold)window.dispatchEvent(new CustomEvent('jarvis-reply',{detail:{channel:m.channel||'common',message:m}}));
    else window.dispatchEvent(new Event('jarvis-send-error'));
   }
  }
 }
 document.querySelectorAll('.agent').forEach(card=>{
  const name=card.querySelector('h2').textContent;
  let area=card.querySelector('.agent-quota');if(!area){area=document.createElement('div');area.className='agent-quota';card.appendChild(area);}
  area.innerHTML=usageMarkup(name);
  if(name==='FRIDAY')card.querySelector('.pill').textContent=state.integrations_enabled&&state.live_chat?'GERÇEK SOHBET':'SOHBET KAPALI';
  if(name==='EDITH')card.querySelector('footer>span').textContent='Gemini / Antigravity';
 });
 $('#liveModelToggle').checked=state.live_chat;$('#liveModelToggle').disabled=!state.integrations_enabled;
 if(document.activeElement!==$('#quotaMonitorToggle'))$('#quotaMonitorToggle').checked=state.quota_monitor;
 $('#composerCostLabel').textContent=state.integrations_enabled&&state.live_chat?'CODEX ABONELİK KOTASI':'MODEL KAPALI';
 $('#modelConnection').textContent=state.model_job?'Codex yanıtlıyor · Abonelik kotası kullanılıyor':state.integrations_enabled&&state.live_chat?'CODEX BAĞLANTISI · API ANAHTARI YOK':'YEREL NOT MODU';
 $('#stopModel').classList.toggle('hidden',!state.model_job);
 const selected=$('#channel').value;
 if(['common','FRIDAY','EDITH','VISION'].includes(selected))$('#directTools').classList.add('hidden');
 if(state.model_job&&liveConversation){voiceWaiting=true;$('#voiceRoomPhase').textContent=vt('DÜŞÜNÜYOR','THINKING');$('#voiceRoomTitle').textContent=vt('Bir saniye, Berke…','One moment, Berke…');}
 renderSharedMemory();updateReactor();renderProjectAssistant();
}
function renderSharedMemory(){
 const shared=state.messages.filter(m=>(m.channel||'common')==='common'&&(m.author==='YOU'||m.model));
 const user=shared.filter(m=>m.author==='YOU');
 $('#sharedCount').textContent=user.length+' ortak ileti · '+state.tasks.length+' görev';
 $('#sharedMini').innerHTML=user.slice(-2).map(m=>`<div class="shared-mini-item"><span>BERKE</span><p>${esc(m.text.slice(0,110))}${m.text.length>110?'…':''}</p></div>`).join('')||'<p class="muted">Ortak sohbette anlattıkların burada görünür.</p>';
 const signature=JSON.stringify(shared);
 if(signature!==sharedSignature){sharedSignature=signature;$('#sharedTimeline').innerHTML=shared.slice(-50).map(m=>`<article class="shared-entry"><div><b>${esc(m.author==='YOU'?'Berke':m.author)}</b><time>${esc(m.time)}</time></div><p>${esc(m.text)}</p></article>`).join('')||'<p class="muted">Henüz ortak konuşma yok. Ana sohbette anlatmaya başlayabilirsin.</p>';}
 if(!briefDirty&&document.activeElement!==$('#projectBrief'))$('#projectBrief').value=state.project_brief||'';
 $('#memoryScope').textContent=(state.active_project?'Proje: '+state.active_project+' · ':'')+'Son 50 ortak ileti ve görev özeti otomatik aktarılır. Ayrı ajan kanalının geçmişi yalnızca kendi paketine eklenir.';
}
function updateReactor(){
 const channel=$('#channel').value;
 const themes={common:{letter:'J',role:'COORDINATOR',name:'JARVIS',caption:'ORTAK KANAL / BAĞLAMI YÖNETİR'},FRIDAY:{letter:'F',role:'DEVELOPER',name:'FRIDAY',caption:'CODEX / GELİŞTİRİCİ'},EDITH:{letter:'E',role:'RESEARCH',name:'EDITH',caption:'ANTIGRAVITY / ARAŞTIRMA'},VISION:{letter:'V',role:'REVIEWER',name:'VISION',caption:'CLAUDE / İNCELEME'}};
 const theme=themes[channel]||{letter:channel[0],role:'CUSTOM AGENT',name:channel,caption:'ÖZEL AJAN / MANUEL'};
 $('.reactor').dataset.agent=channel;$('#reactorLetter').textContent=theme.letter;$('#reactorRole').textContent=theme.role;$('#reactorTitle').textContent=theme.name+' ÇEKİRDEĞİ';$('#reactorCaption').textContent=theme.caption;
 document.querySelectorAll('.agent').forEach(card=>card.classList.toggle('selected',card.querySelector('h2').textContent===(channel==='common'?'JARVIS':channel)));
}
$('#channel').addEventListener('change',updateReactor);
$('#liveModelToggle').onchange=()=>safe(async()=>{await api('connection-settings',{live_chat:$('#liveModelToggle').checked});toast(state.live_chat?'Ajan yanıtları açık. Seçtiğin yanıt motoru kullanılır.':'AI yanıtları kapalı. Yerel notlar ve görevler açık.');});
$('#quotaMonitorToggle').onchange=()=>safe(()=>api('connection-settings',{quota_monitor:$('#quotaMonitorToggle').checked}));
$('#refreshQuota').onclick=()=>safe(async()=>{await api('quota-refresh');toast('Resmi kota bilgisi yenileniyor. Model çalıştırılmaz.');});
$('#stopModel').onclick=()=>safe(()=>api('stop-model'));
$('#organizeTeam').onclick=()=>safe(async()=>{await api('organize');toast('Görev düzeni ortak konuşmaya eklendi.');});
$('#showTechnicalMemory').onclick=()=>{$('#technicalMemory').classList.toggle('hidden');};
$('#briefForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('brief',{text:$('#projectBrief').value});briefDirty=false;toast('Özet kaydedildi. Görev ve ajan paketlerine otomatik eklenir.');});};
// Editor: a local text surface with synchronized syntax layer, line gutter and cursor status.
function highlightCode(text){
 const pattern=/(#[^\n]*|\/\/[^\n]*|\/\*[\s\S]*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\b(?:import|from|class|def|return|if|else|elif|for|while|try|except|with|as|in|not|and|or|True|False|None|const|let|var|function|async|await|new|throw|catch|switch|case|break|public|private|func|guard|self|struct|enum|protocol|final|void|int|String|extends|export|default)\b|\b\d+(?:\.\d+)?\b)/g;
 let out='',position=0,match;
 while((match=pattern.exec(text))!==null){out+=esc(text.slice(position,match.index));const value=match[0];const type=/^(#|\/\/|\/\*)/.test(value)?'comment':/^["'`]/.test(value)?'string':/^\d/.test(value)?'number':'keyword';out+=`<span class="syntax-${type}">${esc(value)}</span>`;position=pattern.lastIndex;}
 return out+esc(text.slice(position))+'\n';
}
function refreshEditor(){
 const editor=$('#codeEditor'),lines=editor.value.split('\n').length;
 $('#lineNumbers').textContent=Array.from({length:lines},(_,i)=>i+1).join('\n')+'\n';
 $('#highlightText').innerHTML=highlightCode(editor.value);
 const ext=openFile?openFile.path.split('.').pop().toLowerCase():'';
 $('#editorLanguage').textContent=({py:'Python',js:'JavaScript',ts:'TypeScript',swift:'Swift',html:'HTML',css:'CSS',json:'JSON',md:'Markdown',sh:'Shell'})[ext]||'Plain Text';
 syncEditorScroll();updateCursor();
}
function syncEditorScroll(){const editor=$('#codeEditor');$('#codeHighlight').scrollTop=editor.scrollTop;$('#codeHighlight').scrollLeft=editor.scrollLeft;$('#lineNumbers').scrollTop=editor.scrollTop;}
function updateCursor(){const editor=$('#codeEditor'),before=editor.value.slice(0,editor.selectionStart),parts=before.split('\n');$('#cursorPosition').textContent='Ln '+parts.length+', Col '+(parts[parts.length-1].length+1);}
$('#codeEditor').addEventListener('input',refreshEditor);$('#codeEditor').addEventListener('scroll',syncEditorScroll);['click','keyup','select'].forEach(event=>$('#codeEditor').addEventListener(event,updateCursor));
window.addEventListener('jarvis-native',e=>{
 const {type,data}=e.detail;
 if(type==='file'||type==='project')refreshEditor();
 if(type==='project')safe(()=>api('project-context',{name:data.name,path:data.path}));
 if(type==='screen')lastScreenImage=data.image;
 if(type==='screen-stopped'||type==='screen-error')lastScreenImage=null;
 if(type==='screen-attachment-approved'&&screenToAttach){pendingScreenImage=screenToAttach;screenToAttach=null;$('#attachedScreenThumb').src=pendingScreenImage;$('#attachedScreen').classList.remove('hidden');$('#channel').value='common';$('#channel').dispatchEvent(new Event('change'));$('#prompt').value=$('#screenQuestion').value.trim()||'Bu ekran karesini incele ve ne gördüğünü açıkla.';safe(()=>view('mission'));$('#prompt').focus();}
 if(type==='transcript'&&liveConversation){quietRestarts=0;$('#voiceRoomTranscript').textContent=data.text;$('#voiceRoomTranscript').classList.toggle('provisional',autoDetecting&&!data.final);if(autoDetecting&&!data.final)$('#voiceRoomPhase').textContent=vt('DİL ALGILANIYOR','DETECTING LANGUAGE');}
 if(type==='speech-detected'){spokenLang=String(data.locale||'').startsWith('tr')?'tr':'en';try{localStorage.setItem('jarvis-speech-lang',spokenLang);}catch(error){}autoDetecting=false;$('#voiceRoomTranscript').classList.remove('provisional');paintVoiceRoomLabels();if(liveConversation)voiceRoomState(nativeListening?'listening':'ready');}
 if(type==='speaking'){voiceRoomState(data.active?'speaking':nativeListening?'listening':'ready');}
 if(type==='listening'){autoDetecting=Boolean(data.active&&data.auto);voiceRoomState(data.active?'listening':voiceWaiting?'thinking':'ready');}
 if(type==='voice-error'){
  // "No speech detected" is not a failure while the room is open: keep listening for your voice, no button press needed.
  if(liveConversation&&!voicePaused&&noSpeechError(data.message)&&quietRestarts<40){quietRestarts++;voiceRoomState('listening');setTimeout(()=>{if(liveConversation&&!voicePaused)resumeListening();},450);return;}
  $('#voiceRoomTitle').textContent=vt('Ses bağlantısı durdu.','Voice connection stopped.');$('#voiceRoomTranscript').textContent=data.message;
 }
});
$('#screenToChat').onclick=()=>{if(!lastScreenImage){toast('Önce ekran önizlemesini aç.');return;}if(!state.live_chat||!state.integrations_enabled){toast('Görseli yorumlamak için gerçek Codex sohbetini aç.');return;}screenToAttach=lastScreenImage;nativeSend('approve-screen-attachment');};
function clearScreenAttachment(){pendingScreenImage=null;$('#attachedScreenThumb').removeAttribute('src');$('#attachedScreen').classList.add('hidden');}
$('#removeScreen').onclick=clearScreenAttachment;
// Voice room: automatic turn submission; dictation remains a separate secondary action.
function voiceRoomState(phase){
 $('#voiceRoom').dataset.phase=phase;
 const states={listening:[vt('DİNLİYORUM','LISTENING'),vt('Seni dinliyorum, Berke.','I am listening, Berke.')],speaking:[vt('JARVIS KONUŞUYOR','JARVIS IS SPEAKING'),vt('Birlikte düşünelim.','Let’s think together.')],thinking:[vt('DÜŞÜNÜYOR','THINKING'),vt('Bir saniye, Berke…','One moment, Berke…')],ready:[vt('HAZIR','READY'),vt('Buradayım, Berke.','I am here, Berke.')]};
 paintVoiceRoomLabels();
 $('#voiceRoomPhase').textContent=states[phase][0];$('#voiceRoomTitle').textContent=states[phase][1];
}
let voiceBeforeRoom=false;
function startVoiceRoom(){
 voiceBeforeRoom=voiceEnabled;
 if(!nativeHost){nativeSend('listen');return;}
 liveConversation=true;voicePaused=false;voiceEnabled=true;voiceWaiting=false;$('#messageMode').value='converse';$('#owner').disabled=true;
 $('#voiceRoom').classList.remove('hidden');quietRestarts=0;$('#voiceRoomTranscript').textContent=vt('Cümleni bitirdiğinde otomatik gönderilir. Enter’a gerek yok.','It is sent automatically when you finish your sentence. No Enter needed.');voiceRoomState('listening');sound();
 nativeSend('stop-speech');nativeSpeaking=false;nativeSend('listen');setVoiceState('CANLI SESLİ KONUŞMA');
}
function stopVoiceRoom(){voiceEnabled=voiceBeforeRoom;if(liveScreenSharing)stopLiveScreenSharing();liveConversation=false;voiceWaiting=false;voicePaused=false;nativeSend('stop-listening');nativeSend('stop-speech');$('#voiceRoom').classList.add('hidden');setVoiceState('KONUŞMA BİTTİ');}
$('#micButton').onclick=startVoiceRoom;$('#liveVoice').onclick=startVoiceRoom;$('#closeVoiceRoom').onclick=stopVoiceRoom;
$('#dictationButton').onclick=()=>{liveConversation=false;nativeSend('stop-speech');nativeSend('listen');setVoiceState('DİKTE · YALNIZCA YAZIYA ÇEVİRME');};
$('#voiceInterrupt').onclick=()=>{if(state.model_job)safe(()=>api('stop-model'));voiceWaiting=false;nativeSend('stop-speech');nativeSpeaking=false;if(nativeListening)nativeSend('stop-listening');liveConversation=true;nativeSend('listen');voiceRoomState('listening');};
$('#voiceMute').onclick=()=>{voicePaused=!voicePaused;if(voicePaused){liveConversation=false;nativeSend('stop-listening');paintVoiceRoomLabels();$('#voiceRoomPhase').textContent=vt('DURAKLATILDI','PAUSED');}else{liveConversation=true;paintVoiceRoomLabels();resumeListening();}};
window.addEventListener('jarvis-send-error',()=>{voiceWaiting=false;if(liveConversation)resumeListening();});
window.addEventListener('jarvis-reply',e=>{if(liveConversation)$('#voiceRoomTranscript').textContent=e.detail.message.text;});
// An in-project assistant uses the same FRIDAY channel and shared context.
const projectAssistant=document.createElement('section');projectAssistant.className='project-assistant';projectAssistant.innerHTML='<div class="small-heading">FRIDAY / PROJE SOHBETİ<span>CODEX</span></div><div id="projectReplies"></div><form id="projectAskForm"><textarea id="projectQuestion" rows="3" required maxlength="1600" placeholder="Bu kodu açıkla, hatayı bul veya değişiklik öner…" aria-label="Projeyle ilgili soru"></textarea><label class="switch-label"><input type="checkbox" id="includeCode" checked> Açık dosyayı / seçtiğim kodu ekle</label><button class="button primary">FRIDAY’a sor ↗</button></form><p class="micro">KOD ÖNERİSİ VE İNCELEME · OTOMATİK TERMİNAL / DOSYA DEĞİŞTİRME KAPALI</p>';
$('.code-layout').appendChild(projectAssistant);
function renderProjectAssistant(){if(!$('#projectReplies'))return;const messages=state.messages.filter(m=>m.channel==='FRIDAY').slice(-5);$('#projectReplies').innerHTML=messages.map(m=>`<article><b>${esc(m.author==='YOU'?'Berke':m.author)}</b><p>${esc(m.text.slice(-5000))}</p></article>`).join('')||'<p class="muted">Ortak sohbeti zaten biliyorum. Açık dosya hakkında buradan sorabilirsin.</p>';}
$('#projectAskForm').onsubmit=e=>{e.preventDefault();safe(async()=>{let text=$('#projectQuestion').value;if($('#includeCode').checked&&openFile){const editor=$('#codeEditor');const selection=editor.value.slice(editor.selectionStart,editor.selectionEnd);const code=selection||editor.value;if(code.length>8000){toast('Kod büyük. 8000 karaktere kadar bir bölüm seç veya dosya ekini kapat.');return;}text+='\n\nDosya: '+openFile.path+'\n<code_reference>\n'+code+'\n</code_reference>';}
 await api('converse',{text,channel:'FRIDAY'});$('#projectQuestion').value='';toast('Soru FRIDAY’a gönderildi. Yanıt burada ve FRIDAY kanalında görünecek.');});};
refreshEditor();

$('#projectBrief').addEventListener('input',()=>{briefDirty=true;});
function handleVoiceTranscript(data){
 if(!data.final||!liveConversation)return false;
 const command=data.text.toLocaleLowerCase('tr-TR').replace(/[.,!?]/g,'').replace(/^jarvis\s+/, '').trim();
 if(['dur','konuşmayı bitir','konuşmayı kapat','dinlemeyi durdur','sesi kapat'].includes(command)){stopVoiceRoom();return true;}
 return false;
}
const openAntigravity=document.createElement('button');openAntigravity.className='button';openAntigravity.textContent='Antigravity’de aç ↗';openAntigravity.onclick=()=>nativeSend('open-antigravity');$('.project-panel>.panel-head').appendChild(openAntigravity);

const shareIndicator=document.createElement('button');shareIndicator.className='button small danger hidden';shareIndicator.id='screenSharingIndicator';shareIndicator.textContent='◉ EKRAN PAYLAŞIMI AÇIK · DURDUR';shareIndicator.onclick=stopLiveScreenSharing;$('.top-status').prepend(shareIndicator);
function stopLiveScreenSharing(){liveScreenSharing=false;pendingScreenVoice=false;shareIndicator.classList.add('hidden');nativeSend('stop-screen');}
$('#screenVoice').onclick=()=>{if(!state.live_chat||!state.integrations_enabled){toast('Ekranla konuşmak için gerçek Codex sohbetini aç.');return;}nativeSend('approve-live-screen');};
window.addEventListener('jarvis-native',e=>{
 const {type,data}=e.detail;
 if(type==='live-screen-approved'){liveScreenSharing=true;pendingScreenVoice=true;shareIndicator.classList.remove('hidden');$('#channel').value='common';$('#channel').dispatchEvent(new Event('change'));}
 if(type==='screen'&&pendingScreenVoice){pendingScreenVoice=false;startVoiceRoom();$('#voiceRoomTranscript').textContent='Her yeni sorunda en güncel ekran karesi Codex’e eklenecek. Konuşmayı bitirince ekran paylaşımı da durur.';}
 if(type==='screen-stopped'||type==='screen-error'){liveScreenSharing=false;pendingScreenVoice=false;shareIndicator.classList.add('hidden');}
});
