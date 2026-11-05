'use strict';
const nativeHost=!!(window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.native);
const noSpeechError=message=>/no speech detected|ses algılanmadı/i.test(String(message||''));
const nativeSend=(action,data={})=>{if(nativeHost)window.webkit.messageHandlers.native.postMessage({action,...data});else toast('Bu özellik JARVIS.app içinde çalışır. Mac uygulamasını aç, Berke.');};
let voiceEnabled=false,liveConversation=false,nativeListening=false,nativeSpeaking=false,voiceWaiting=false;
let projectFiles=[],openFile=null,dirty=false,soundEnabled=localStorage.getItem('jarvis-sound')!=='off',audioContext;
// Local weighted greetings; no model call and no chat-history entry.
const AGENT_GREETINGS=[
 [5,'Tekrar merhaba, Berke. Buradayım.','Hello again, Berke. I am here.'],
 [5,'Seni dinliyorum, Berke.','I am listening, Berke.'],
 [4,'Hoş geldin, Berke. Nereden devam edelim?','Welcome back, Berke. Where shall we continue?'],
 [4,'Buradayım. Devam edebiliriz.','I am here. We can continue.'],
 [4,'Tekrar hoş geldin. Seni dinliyorum.','Welcome back. I am listening.'],
 [3,'Hazırım, Berke.','Ready, Berke.'],
 [3,'Merhaba Berke. Ne düşünüyorsun?','Hello Berke. What is on your mind?'],
 [3,'Yeniden buradayız. Nasıl ilerleyelim?','Here we are again. How shall we proceed?'],
 [2,'Buyur Berke, seni dinliyorum.','Go ahead, Berke. I am listening.'],
 [2,'Hoş geldin. Bugün neye odaklanalım?','Welcome back. What shall we focus on today?'],
 [2,'Buradayım, Berke. Söyle bakalım.','I am here, Berke. Tell me.'],
 [2,'Tekrar merhaba. Kaldığımız yerden devam edelim mi?','Hello again. Shall we pick up where we left off?'],
 [1,'Seni yeniden duymak güzel, Berke.','Good to hear from you again, Berke.'],
 [1,'Berke, buradayım. Aklındaki konuyu dinliyorum.','Berke, I am here. What do you have in mind?'],
 [1,'Yeniden hoş geldin, Berke. Söz sende.','Welcome back, Berke. Over to you.']
];
function pickAgentGreeting(name,english=false,random=Math.random){
 let saved={};try{const parsed=JSON.parse(localStorage.getItem('jarvis-agent-greetings')||'{}');if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed))saved=parsed;}catch{}
 if(typeof state!=='undefined'&&state?.agent_greetings)saved={...saved,...state.agent_greetings};
 const previous=saved[name];let index=-1,text;
 if(!previous)text=english?'Hello Berke. I am '+name+'. I am listening.':'Merhaba Berke. Ben '+name+'. Seni dinliyorum.';
 else{
  const options=AGENT_GREETINGS.map((row,index)=>({row,index})).filter(item=>item.index!==previous.last);
  let weight=random()*options.reduce((sum,item)=>sum+item.row[0],0);
  const chosen=options.find(item=>(weight-=item.row[0])<0)||options[options.length-1];
  index=chosen.index;text=chosen.row[english?2:1];
 }
 saved[name]={last:index,visits:(Number(previous?.visits)||0)+1,at:Date.now()};
 if(typeof state!=='undefined'&&state)state.agent_greetings=saved;
 try{localStorage.setItem('jarvis-agent-greetings',JSON.stringify(saved));}catch{}
 return text;
}
function greetSelectedAgent(name,text){
 toast(name+' · '+text);
 if(nativeHost)nativeSend('speak',{agent:name,text});
}
// Return greetings are triggered by sending after a real idle gap, not by every keystroke.
$('#composer').addEventListener('submit',()=>{
 if(busy||state?.model_job||!$('#prompt').value.trim())return;
 const channel=$('#channel').value,name=channel==='common'?'JARVIS':channel;
 const rows=(state.messages||[]).filter(m=>m.author==='YOU'&&(m.channel||'common')===channel);
 const previous=rows[rows.length-1],at=previous&&new Date(String(previous.time).replace(' ','T')).getTime();
 const recent=state.agent_greetings?.[name]?.at||0;
 if(Number.isFinite(at)&&Date.now()-at>=30*60*1000&&Date.now()-recent>=30*60*1000){
  const text=pickAgentGreeting(name,state.language==='en');greetSelectedAgent(name,text);
 }
},true);
// END_AGENT_GREETINGS
// LAUNCH_GREETINGS
// What JARVIS says when the app opens: many lines, a few for the time of day, never the same line twice in a row. Local, no model call, no chat entry.
// Row: [weight, when ('any' or morning/day/evening/night), Turkish, English].
const LAUNCH_GREETINGS=[
 [2,'any','Merhaba Berke. Buradayım, nereden başlıyoruz?','Hello Berke. I am here. Where do we start?'],
 [2,'any','Hazırım Berke. Söyle, ne yapıyoruz?','Ready, Berke. Tell me, what are we doing?'],
 [2,'any','Sistemler açık. Seni dinliyorum, Berke.','Systems are up. I am listening, Berke.'],
 [2,'any','Hoş geldin Berke. Bugün neyi çözüyoruz?','Welcome, Berke. What are we solving today?'],
 [2,'any','Tekrar buradayız. Ne yapalım?','Back at it. What shall we do?'],
 [2,'any','Merhaba. Ekip hazır, sıra sende.','Hello. The team is ready, over to you.'],
 [2,'any','Buyur Berke, bugün ne var ne yok?','Go ahead, Berke. What is on the list today?'],
 [2,'any','Her şey yerinde. Ne üzerinde çalışalım?','Everything is in place. What shall we work on?'],
 [2,'any','Seni görmek güzel Berke. Bir iş mi var?','Good to see you, Berke. Got something for us?'],
 [2,'any','Ben hazırım, sen hazır olunca başlayalım.','I am ready. Let us start whenever you are.'],
 [2,'any','Berke, buradayım. Aklında ne var?','Berke, I am here. What is on your mind?'],
 [2,'any','Merhaba Berke. Bugün ne üzerinde çalışalım?','Hello Berke. What shall we work on today?'],
 [2,'any','Açıldık. Komut sende, Berke.','We are up. The floor is yours, Berke.'],
 [2,'any','Tamam, buradayım. Söz sende.','Alright, I am here. Over to you.'],
 [2,'any','Hoş geldin Berke. Önce ne yapalım?','Welcome, Berke. What first?'],
 [2,'any','Ekip nöbette. Ne lazım?','The team is on duty. What do you need?'],
 [2,'any','Berke, JARVIS burada. Ne yapalım?','Berke, JARVIS here. What shall we do?'],
 [2,'any','Yeni oturum, yeni iş. Nereden başlayalım?','New session, new work. Where shall we begin?'],
 [4,'morning','Günaydın Berke. Bugün neyle başlıyoruz?','Good morning, Berke. What are we starting with today?'],
 [4,'morning','Günaydın. Kahveni al, ben hazırım.','Good morning. Grab your coffee, I am ready.'],
 [4,'morning','Günaydın Berke. Güne bir görevle başlayalım mı?','Good morning, Berke. Shall we start the day with a task?'],
 [4,'day','İyi günler Berke. Ne yapıyoruz?','Good afternoon, Berke. What are we doing?'],
 [4,'day','Öğleden sonra, tam çalışma saati. Söyle Berke.','Afternoon, the right time to work. Tell me, Berke.'],
 [4,'evening','İyi akşamlar Berke. Bu akşam ne yapıyoruz?','Good evening, Berke. What are we doing tonight?'],
 [4,'evening','Akşam oldu ama ben hazırım. Ne lazım?','It is evening, but I am ready. What do you need?'],
 [4,'evening','İyi akşamlar. Günün son işi ne olsun?','Good evening. What shall be the last job of the day?'],
 [4,'night','Gece geç oldu Berke ama buradayım. Ne yapıyoruz?','It is late, Berke, but I am here. What are we doing?'],
 [4,'night','Hâlâ ayaktayız demek. Söyle Berke.','Still up, then. Tell me, Berke.'],
 [4,'night','Gece vardiyası. Hazırım Berke.','Night shift. Ready, Berke.']
];
function launchPeriod(hour){return hour>=5&&hour<12?'morning':hour>=12&&hour<18?'day':hour>=18&&hour<23?'evening':'night';}
function pickLaunchGreeting(english=false,random=Math.random,hour=new Date().getHours()){
 let last=-1;try{last=Number(JSON.parse(localStorage.getItem('jarvis-launch-greeting')||'{}').last);}catch{}
 const period=launchPeriod(hour);
 const options=LAUNCH_GREETINGS.map((row,index)=>({row,index})).filter(item=>item.index!==last&&(item.row[1]==='any'||item.row[1]===period));
 let weight=random()*options.reduce((sum,item)=>sum+item.row[0],0);
 const chosen=options.find(item=>(weight-=item.row[0])<0)||options[options.length-1];
 try{localStorage.setItem('jarvis-launch-greeting',JSON.stringify({last:chosen.index,at:Date.now()}));}catch{}
 return chosen.row[english?3:2];
}
// END_LAUNCH_GREETINGS
function sound(kind='send'){
 if(!soundEnabled)return;
 try{const C=window.AudioContext||window.webkitAudioContext;audioContext=audioContext||new C();audioContext.resume();const now=audioContext.currentTime;
 const notes=kind==='approve'?[420,630,840]:kind==='error'?[220,180]:[520,780];
 notes.forEach((hz,i)=>{const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.type='sine';oscillator.frequency.setValueAtTime(hz,now+i*.055);gain.gain.setValueAtTime(.0001,now+i*.055);gain.gain.exponentialRampToValueAtTime(.025,now+i*.055+.008);gain.gain.exponentialRampToValueAtTime(.0001,now+i*.055+.1);oscillator.connect(gain);gain.connect(audioContext.destination);oscillator.start(now+i*.055);oscillator.stop(now+i*.055+.12);});
 }catch{}
}
function setVoiceState(text){$('#voiceStatus').textContent=text;$('#micButton').classList.toggle('on',liveConversation||nativeListening);$('#liveVoice').classList.toggle('on',liveConversation);$('#liveVoice').textContent=liveConversation?'■ Konuşmayı bitir':'◌ Konuşmayı başlat';$('#speakerButton').classList.toggle('on',voiceEnabled);$('#speakerButton').textContent='♫ Bu sohbette sesli yanıt: '+(voiceEnabled?'açık':'kapalı');$('#speakerButton').setAttribute('aria-pressed',String(voiceEnabled));document.querySelectorAll('.reactor').forEach(r=>{r.classList.toggle('listening',nativeListening);r.classList.toggle('speaking',nativeSpeaking);});}
function resumeListening(){if(liveConversation&&!nativeSpeaking&&!nativeListening&&!voiceWaiting)nativeSend('listen');}
$('#micButton').onclick=()=>{sound();if(nativeListening){nativeSend('stop-listening');setVoiceState('DİNLEME DURDURULDU');}else{nativeSend('listen');setVoiceState('MİKROFON HAZIRLANIYOR');}};
$('#liveVoice').onclick=()=>{if(!nativeHost){nativeSend('listen');return;}sound();liveConversation=!liveConversation;if(liveConversation){voiceEnabled=true;$('#messageMode').value='converse';$('#owner').disabled=true;voiceWaiting=false;resumeListening();}else{nativeSend('stop-listening');nativeSend('stop-speech');}setVoiceState(liveConversation?'KONUŞMA MODU':'KONUŞMA DURDURULDU');};
$('#speakerButton').onclick=()=>{sound();voiceEnabled=!voiceEnabled;if(!voiceEnabled){nativeSend('stop-speech');}else if(nativeHost){nativeSend('speak',{text:'Merhaba Berke. Seni dinliyorum.'});}setVoiceState('YAZILI SOHBET HAZIR');};
window.addEventListener('jarvis-ready',()=>{if(nativeHost){
 nativeSend('ready');
 // On its first "ready" the Mac app speaks one fixed line. A second speak replaces it at once (speak stops the running voice), so every launch greets differently. Only the first page load of an app run.
 let first=true;try{first=sessionStorage.getItem('jarvis-launch-greeted')!=='1';sessionStorage.setItem('jarvis-launch-greeted','1');}catch{}
 if(first)nativeSend('speak',{text:pickLaunchGreeting(typeof state!=='undefined'&&state?.language==='en')});
 setVoiceState('MAC SES MOTORU HAZIR');
}else setVoiceState('SES İÇİN JARVIS.APP’İ AÇ');});
window.addEventListener('jarvis-reply',e=>{sound();const m=e.detail.message;voiceWaiting=false;if(m.voice_on||m.voice_off){voiceEnabled=Boolean(m.voice_on);if(!voiceEnabled)nativeSend('stop-speech');else if(!nativeHost)toast(tr('Sesli yanıt için JARVIS.app’i aç.','Open JARVIS.app for spoken replies.'));setVoiceState(voiceEnabled?'MAC SES MOTORU HAZIR':'YAZILI SOHBET HAZIR');}if(voiceEnabled&&nativeHost&&!['YOU','SYSTEM'].includes(m.author)&&Boolean(m.text)){nativeSend('speak',{text:spokenReply(m.text),agent:m.author});}else resumeListening();});
window.addEventListener('jarvis-native',e=>{
 const {type,data}=e.detail;
 if(type==='listening'){nativeListening=data.active;setVoiceState(data.active?(data.local?'DİNLİYORUM · CİHAZ İÇİNDE':'DİNLİYORUM · APPLE SES HİZMETİ'):'SES ALINDI');}
 if(type==='transcript'){if(typeof handleVoiceTranscript==='function'&&handleVoiceTranscript(data))return;$('#prompt').value=data.text;if(data.final){sound();if(liveConversation){voiceWaiting=true;$('#composer').requestSubmit();}else setVoiceState('SES YAZIYA DÖNÜŞTÜ · GÖNDERMEYE HAZIR');}}
 if(type==='speech-detected'){toast((String(data.locale).startsWith('tr')?'Dil: Türkçe':'Language: English')+' · '+data.scores);}
 if(type==='speaking'){nativeSpeaking=data.active;setVoiceState(data.active?'JARVIS KONUŞUYOR':'HAZIR, BERKE');if(!data.active)setTimeout(resumeListening,250);}
 if(type==='voice-error'&&!(liveConversation&&noSpeechError(data.message))){liveConversation=false;nativeListening=false;voiceWaiting=false;setVoiceState('SES DURDURULDU');sound('error');toast(data.message);}
 if(type==='project'){projectFiles=data.files;$('#projectName').textContent=data.name;$('#projectPath').textContent=data.path;openFile=null;dirty=false;$('#codeEditor').value='';$('#editorPath').textContent='Bir dosya seç';renderFileTree();sound();}
 if(type==='file'){openFile=data;dirty=false;$('#codeEditor').value=data.text;$('#editorPath').textContent=data.path;$('#editorStatus').textContent='UTF-8 · Kaydedilmiş sürüm · Onaylı kayıt + yedek';renderFileTree();}
 if(type==='file-error'){sound('error');toast(data.message);}
 if(type==='file-saved'){sound('approve');toast(data.message);}
 if(type==='screen'){$('#screenImage').src=data.image;$('#screenImage').classList.remove('hidden');$('#screenPlaceholder').classList.add('hidden');$('#screenState').textContent='CANLI · YEREL';$('#screenStatus').textContent='Son kare: '+data.time+' · Görüntüler ajana gönderilmiyor.';}
 if(type==='screen-stopped'||type==='screen-error'){$('#screenImage').removeAttribute('src');$('#screenImage').classList.add('hidden');$('#screenPlaceholder').classList.remove('hidden');$('#screenState').textContent='KAPALI';$('#screenStatus').textContent=data.message||'Ekran önizlemesi durduruldu; son görüntü temizlendi.';if(type==='screen-error'){sound('error');toast(data.message);}}
});
function renderFileTree(){const query=$('#fileSearch').value.toLowerCase();$('#projectFiles').innerHTML=projectFiles.filter(f=>f.toLowerCase().includes(query)).map(f=>`<button class="tree-file ${openFile&&openFile.path===f?'selected':''}" data-project-file="${esc(f)}">${esc(f)}</button>`).join('')||'<p class="muted">Dosya bulunamadı.</p>';}
function discardReview(then){if(!dirty){then();return;}modal('Kaydedilmemiş düzenleme var',`<p class="dialog-text">${esc(openFile.path)} dosyasındaki kaydedilmemiş düzenleme bırakılacak.</p><div class="dialog-actions"><button class="button danger" id="discardEdit">Düzenlemeyi bırak</button></div>`);$('#discardEdit').onclick=()=>{dirty=false;closeModal();then();};}
$('#chooseProject').onclick=()=>discardReview(()=>nativeSend('choose-project'));
$('#fileSearch').oninput=renderFileTree;
$('#codeEditor').oninput=()=>{if(openFile){dirty=true;$('#editorStatus').textContent='DÜZENLENDİ · Henüz diske yazılmadı';}};
$('#codeEditor').addEventListener('keydown',e=>{if(e.key==='Tab'){e.preventDefault();const el=e.target;el.setRangeText('    ',el.selectionStart,el.selectionEnd,'end');el.dispatchEvent(new Event('input'));}});
$('#saveFile').onclick=()=>{if(!openFile){toast('Önce bir dosya aç, Berke.');return;}if(!dirty){toast('Yeni değişiklik yok.');return;}sound();nativeSend('save-file',{path:openFile.path,text:$('#codeEditor').value,hash:openFile.hash});};
$('#fileToChat').onclick=()=>safe(async()=>{if(!openFile){toast('Önce bir dosya aç.');return;}const text=$('#codeEditor').value;if(text.length>1400){toast('Dosya büyük. Sohbete eklemek için 1400 karaktere kadar bir bölümü seç.');const el=$('#codeEditor');const selection=el.value.slice(el.selectionStart,el.selectionEnd);if(!selection||selection.length>1400)return;$('#prompt').value=`Dosya: ${openFile.path}\n\n${selection}`;}else $('#prompt').value=`Dosya: ${openFile.path}\n\n${text}`;await view('mission');$('#prompt').focus();toast('Kod seçili ajanın taslağına eklendi; henüz gönderilmedi.');});
$('#startScreen').onclick=()=>{sound();nativeSend('start-screen');};$('#stopScreen').onclick=()=>{sound();nativeSend('stop-screen');};
$('#channel').onchange=()=>{lastMessages='';$('#directTools').classList.toggle('hidden',$('#channel').value==='common');$('#messageMode').value='converse';$('#owner').disabled=true;render();sound();};
$('#chatPacket').onclick=()=>safe(async()=>{const result=await api('chat-packet',{channel:$('#channel').value});modal('Sohbet paketi',`<p class="dialog-text">Bu kanalı kullandığın resmi araca taşı. Otomatik gönderim yapılmaz.</p><textarea id="chatPacketText" class="packet" readonly>${esc(result.packet)}</textarea><div class="dialog-actions"><button class="button primary" id="copyChat">Kopyala</button></div>`);$('#copyChat').onclick=()=>safe(async()=>{try{await navigator.clipboard.writeText(result.packet);toast('Sohbet paketi kopyalandı.');}catch{$('#chatPacketText').select();toast('⌘C ile kopyala.');}});});
$('#chatImport').onclick=()=>{modal('Sohbet yanıtını aktar',`<form id="importChatForm"><textarea id="importChatText" class="result-input" required maxlength="50000" aria-label="Sohbet yanıtı" placeholder="Sağlayıcının yanıtını yapıştır…"></textarea><div class="dialog-actions"><button class="button primary">Bu kanala kaydet</button></div></form>`);$('#importChatForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('chat-result',{channel:$('#channel').value,text:$('#importChatText').value});closeModal();sound();});};};
document.addEventListener('click',e=>{const file=e.target.closest('[data-project-file]');if(file)discardReview(()=>nativeSend('read-file',{path:file.dataset.projectFile}));const card=e.target.closest('.agent');if(card){const name=card.querySelector('h2').textContent,agent=name==='JARVIS'?'common':name;safe(async()=>{chatDrafts[state.active_chat]=$('#prompt').value;const greeting=pickAgentGreeting(name,state.language==='en');await api('agent-chat',{agent,greeting_index:state.agent_greetings[name].last});$('#prompt').value=chatDrafts[state.active_chat]||'';$('#channel').value=agent;$('#channel').dispatchEvent(new Event('change'));view('mission');greetSelectedAgent(name,greeting);});}const button=e.target.closest('button');if(button&&button.id!=='micButton'){if(button.id==='approveExact')sound('approve');else if(button.dataset.view||button.classList.contains('send'))sound();}});
const sfx=document.createElement('button');sfx.className='icon-btn';sfx.id='soundToggle';sfx.title='Küçük arayüz seslerini aç/kapat';sfx.setAttribute('aria-label','Arayüz seslerini aç veya kapat');sfx.textContent=soundEnabled?'♪':'♩';$('.top-status').appendChild(sfx);sfx.onclick=()=>{soundEnabled=!soundEnabled;localStorage.setItem('jarvis-sound',soundEnabled?'on':'off');sfx.textContent=soundEnabled?'♪':'♩';if(soundEnabled)sound('approve');toast('Arayüz sesleri '+(soundEnabled?'açık':'kapalı'));};
setVoiceState(nativeHost?'MAC SES MOTORU':'SES İÇİN JARVIS.APP’İ AÇ');
let agentSignature='';
function syncAgents(){
 const signature=JSON.stringify(state.agents);if(signature===agentSignature)return;agentSignature=signature;
 const selected=$('#channel').value||state.chats.find(c=>c.id===state.active_chat)?.agent||'common',owner=$('#owner').value;
 $('#channel').innerHTML='<option value="common">Ortak · JARVIS</option>'+state.agents.map(a=>`<option value="${esc(a.name)}">${esc(a.name)} · ${esc(a.provider)}</option>`).join('');$('#channel').value=selected;
 $('#owner').innerHTML='<option value="AUTO">JARVIS yönlendirsin</option>'+state.agents.map(a=>`<option>${esc(a.name)}</option>`).join('');$('#owner').value=owner;
 document.querySelectorAll('.agent.custom').forEach(a=>a.remove());
 state.agents.filter(a=>!['FRIDAY','EDITH','VISION'].includes(a.name)).forEach(a=>{
  const card=document.createElement('article');card.className='agent custom';card.innerHTML=`<div class="agent-top"><span class="agent-symbol">⬡</span><span class="pill">MANUEL AKTARIM</span></div><h2>${esc(a.name)}</h2><p>${esc(a.role)}</p><footer><span>${esc(a.provider)}</span><b>Hazır</b></footer>`;$('.agent-grid').appendChild(card);
 });
 $('#agentRegistry').innerHTML=state.agents.map(a=>`<div class="registry-row"><b>${esc(a.name)}</b><span>${esc(a.provider)}</span><small>MANUEL / BAĞLI DEĞİL</small></div>`).join('');
}
$('#addAgent').onclick=()=>{
 sound();modal('Ekibe yeni ajan ekle',`<form id="addAgentForm"><p class="dialog-text">İstediğin AI aracını manuel rolle ekle. Ortak hafızayı görev paketiyle taşıyabilir, devam eden görevi bu ajana devredebilirsin. “Ücretsiz” veya “tokensiz” olduğu varsayılmaz; servis erişimi ayrıca doğrulanır. Bu form bağlantı açmaz, API anahtarı istemez.</p><label>Ajan adı<input id="newAgentName" placeholder="Örn. NOVA" pattern="[A-Za-z][A-Za-z0-9_-]{1,19}" maxlength="20" required></label><label>Sağlayıcı / kullandığın araç<input id="newAgentProvider" placeholder="Örn. yerel model veya resmi web aracı" maxlength="80" required></label><label>Rol<input id="newAgentRole" placeholder="Örn. Alternatif geliştirici" maxlength="100" required></label><div class="dialog-actions"><button class="button primary">Ajanı ekle</button></div></form>`);
 $('#addAgentForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('add-agent',{name:$('#newAgentName').value,provider:$('#newAgentProvider').value,role:$('#newAgentRole').value});closeModal();sound('approve');toast('Ajan eklendi. Sohbet ve görev devir menüsünde hazır.');});};
};
function openTransferModal(task){
 sound();modal('Kaldığın yerden başka ajanla devam et',`<form id="transferForm"><p class="dialog-text">${esc(task.title)}<br>Mevcut sorumlu: ${esc(task.owner)}. Yeni sorumlu tek sahip olur. Eski çalışma kaybolmaz; kontrol noktası ve ortak hafıza yeni görev paketine eklenir.</p><label>Yeni sorumlu<select id="nextOwner">${state.agents.filter(a=>a.name!==task.owner).map(a=>`<option>${esc(a.name)}</option>`).join('')}</select></label><label>Kontrol noktası / nerede kaldık?<textarea id="checkpoint" class="result-input" maxlength="12000" required placeholder="Tamamlanan işler, kalan adımlar, dosyalar, hata çıktısı ve kota dolduysa son durum…">${esc(task.checkpoint||'')}</textarea></label><div class="dialog-actions"><button class="button primary">Bağlamı koru & devret</button></div></form>`);
 $('#transferForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('transfer',{id:task.id,owner:$('#nextOwner').value,checkpoint:$('#checkpoint').value});closeModal();sound('approve');toast('Görev devredildi. Yeni sorumlu için “Paketi al” ile devam et.');});};
}

let spokenTurn=0;
function spokenReply(text){
 // Spoken replies are short and human: the first sentences (up to ~200 characters) plus a natural hand-off line such as
 // "sonuçları sohbete gönderiyorum", never the whole text and never a stock "details are in the chat".
 const english=(text.match(/\b(the|and|you|with|this|that|is|are|can|will)\b/gi)||[]).length>(text.match(/[çğıöşüÇĞİÖŞÜ]|\b(bir|ve|için|ile|bu|değil|ama)\b/gi)||[]).length;
 const hadCode=/```/.test(text);
 const cleaned=text.replace(/```[\s\S]*?```/g,' ').replace(/\|[^\n]*\|/g,' ').replace(/https?:\/\/\S+/g,' ').replace(/^\s*(?:[-*•]|\d+[.)])\s+/gm,'').replace(/[#*_`>~]/g,'').replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu,'').replace(/→/g,' ').replace(/\s+/g,' ').trim();
 const sentences=cleaned.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g)||[];
 let spoken='';
 for(const s of sentences){if(spoken&&(spoken+s).length>200)break;spoken+=s;if(spoken.length>=100)break;}
 spoken=spoken.trim();
 const pick=list=>list[spokenTurn++%list.length];
 const tail=hadCode
  ?(english?pick([' Sending the code to the chat.',' I passed the code on to the chat, you can check it there.']):pick([' Kodu sohbete gönderiyorum.',' Kod parçasını sohbete aktardım, oradan bakabilirsin.']))
  :'';
 return (spoken||(english?'Done.':'Hazır.')).slice(0,300)+tail;
}
