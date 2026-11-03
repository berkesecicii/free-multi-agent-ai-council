'use strict';
const nativeHost=!!(window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.native);
const nativeSend=(action,data={})=>{if(nativeHost)window.webkit.messageHandlers.native.postMessage({action,...data});else toast('Bu özellik JARVIS.app içinde çalışır. Mac uygulamasını aç, Berke.');};
let voiceEnabled=false,liveConversation=false,nativeListening=false,nativeSpeaking=false,voiceWaiting=false;
let projectFiles=[],openFile=null,dirty=false,soundEnabled=localStorage.getItem('jarvis-sound')!=='off',audioContext;
function sound(kind='send'){
 if(!soundEnabled)return;
 try{const C=window.AudioContext||window.webkitAudioContext;audioContext=audioContext||new C();audioContext.resume();const now=audioContext.currentTime;
 const notes=kind==='approve'?[420,630,840]:kind==='error'?[220,180]:[520,780];
 notes.forEach((hz,i)=>{const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();oscillator.type='sine';oscillator.frequency.setValueAtTime(hz,now+i*.055);gain.gain.setValueAtTime(.0001,now+i*.055);gain.gain.exponentialRampToValueAtTime(.025,now+i*.055+.008);gain.gain.exponentialRampToValueAtTime(.0001,now+i*.055+.1);oscillator.connect(gain);gain.connect(audioContext.destination);oscillator.start(now+i*.055);oscillator.stop(now+i*.055+.12);});
 }catch{}
}
function setVoiceState(text){$('#voiceStatus').textContent=text;$('#micButton').classList.toggle('on',liveConversation||nativeListening);$('#liveVoice').classList.toggle('on',liveConversation);$('#liveVoice').textContent=liveConversation?'■ Konuşmayı bitir':'◌ Konuşmayı başlat';$('#speakerButton').classList.toggle('on',voiceEnabled);$('#speakerButton').textContent='♫ Sesli yanıt: '+(voiceEnabled?'açık':'kapalı');$('#speakerButton').setAttribute('aria-pressed',String(voiceEnabled));document.querySelectorAll('.reactor').forEach(r=>{r.classList.toggle('listening',nativeListening);r.classList.toggle('speaking',nativeSpeaking);});}
function resumeListening(){if(liveConversation&&!nativeSpeaking&&!nativeListening&&!voiceWaiting)nativeSend('listen');}
$('#micButton').onclick=()=>{sound();if(nativeListening){nativeSend('stop-listening');setVoiceState('DİNLEME DURDURULDU');}else{nativeSend('listen');setVoiceState('MİKROFON HAZIRLANIYOR');}};
$('#liveVoice').onclick=()=>{if(!nativeHost){nativeSend('listen');return;}sound();liveConversation=!liveConversation;if(liveConversation){voiceEnabled=true;$('#messageMode').value='converse';$('#owner').disabled=true;voiceWaiting=false;resumeListening();}else{nativeSend('stop-listening');nativeSend('stop-speech');}setVoiceState(liveConversation?'KONUŞMA MODU':'KONUŞMA DURDURULDU');};
$('#speakerButton').onclick=()=>{sound();voiceEnabled=!voiceEnabled;if(!voiceEnabled){nativeSend('stop-speech');}else if(nativeHost){nativeSend('speak',{text:'Merhaba Berke. Seni dinliyorum.'});}setVoiceState('YAZILI SOHBET HAZIR');};
window.addEventListener('jarvis-ready',()=>{if(nativeHost){nativeSend('ready');setVoiceState('MAC SES MOTORU HAZIR');}else setVoiceState('SES İÇİN JARVIS.APP’İ AÇ');});
window.addEventListener('jarvis-reply',e=>{sound();const m=e.detail.message;voiceWaiting=false;if(voiceEnabled&&nativeHost&&m.author!=='YOU'&&Boolean(m.text)){nativeSend('speak',{text:spokenReply(m.text)});}else resumeListening();});
window.addEventListener('jarvis-native',e=>{
 const {type,data}=e.detail;
 if(type==='listening'){nativeListening=data.active;setVoiceState(data.active?(data.local?'DİNLİYORUM · CİHAZ İÇİNDE':'DİNLİYORUM · APPLE SES HİZMETİ'):'SES ALINDI');}
 if(type==='transcript'){if(typeof handleVoiceTranscript==='function'&&handleVoiceTranscript(data))return;$('#prompt').value=data.text;if(data.final){sound();if(liveConversation){voiceWaiting=true;$('#composer').requestSubmit();}else setVoiceState('SES YAZIYA DÖNÜŞTÜ · GÖNDERMEYE HAZIR');}}
 if(type==='speaking'){nativeSpeaking=data.active;setVoiceState(data.active?'JARVIS KONUŞUYOR':'HAZIR, BERKE');if(!data.active)setTimeout(resumeListening,250);}
 if(type==='voice-error'){liveConversation=false;nativeListening=false;voiceWaiting=false;setVoiceState('SES DURDURULDU');sound('error');toast(data.message);}
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
document.addEventListener('click',e=>{const file=e.target.closest('[data-project-file]');if(file)discardReview(()=>nativeSend('read-file',{path:file.dataset.projectFile}));const card=e.target.closest('.agent');if(card){const name=card.querySelector('h2').textContent;$('#channel').value=name==='JARVIS'?'common':name;$('#channel').dispatchEvent(new Event('change'));safe(()=>view('mission'));}const button=e.target.closest('button');if(button&&button.id!=='micButton'){if(button.id==='approveExact')sound('approve');else if(button.dataset.view||button.classList.contains('send'))sound();}});
const sfx=document.createElement('button');sfx.className='icon-btn';sfx.id='soundToggle';sfx.title='Küçük arayüz seslerini aç/kapat';sfx.setAttribute('aria-label','Arayüz seslerini aç veya kapat');sfx.textContent=soundEnabled?'♪':'♩';$('.top-status').appendChild(sfx);sfx.onclick=()=>{soundEnabled=!soundEnabled;localStorage.setItem('jarvis-sound',soundEnabled?'on':'off');sfx.textContent=soundEnabled?'♪':'♩';if(soundEnabled)sound('approve');toast('Arayüz sesleri '+(soundEnabled?'açık':'kapalı'));};
setVoiceState(nativeHost?'MAC SES MOTORU':'SES İÇİN JARVIS.APP’İ AÇ');
let agentSignature='';
function syncAgents(){
 const signature=JSON.stringify(state.agents);if(signature===agentSignature)return;agentSignature=signature;
 const selected=$('#channel').value,owner=$('#owner').value;
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

function spokenReply(text){
 const cleaned=text.replace(/```[\s\S]*?```/g,' Kod örneğini sohbete ekledim. ').replace(/https?:\/\/\S+/g,' bağlantı ').replace(/[#*_`]/g,'').trim();
 return cleaned.length>1100?cleaned.slice(0,1100)+' Devamı sohbette.':cleaned;
}
