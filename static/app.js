'use strict';
const $ = s => document.querySelector(s);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let displayedChat=null,refreshSequence=0,pollTimer;
const renderMetrics={count:0,lastMs:0,maxMs:0,reusedRows:0};
let state, currentView = 'mission', currentFile = 'research.md', timer, lastMessages = '', busy = false;
const statusNames = {review:'İnceleme bekliyor',queued:'Sırada',working:'Çalışılıyor',done:'Tamamlandı',cancelled:'İptal',pending:'Onay bekliyor',rejected:'Reddedildi',expired:'Süresi doldu',failed:'Başarısız',interrupted:'Kesildi',running:'Çalışıyor'};
function toast(text) { $('#toast').textContent=text; $('#toast').classList.add('show'); clearTimeout(timer);timer=setTimeout(()=>$('#toast').classList.remove('show'),4200); }
async function api(action, data={}) {
  const response=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':state.csrf},body:JSON.stringify({chat_id:state.active_chat,...data})});
  const result=await response.json(); if(!response.ok){if(String(result.error||'').includes('macOS Ekran Kaydı'))await refresh();throw new Error(result.error || 'İşlem başarısız.');}
  await refresh();schedulePoll();return result;
}
async function safe(work) {try {await work();} catch(error){toast(error.message);}}
function modal(title, body) {$('#dialogTitle').textContent=title;$('#dialogBody').innerHTML=body;if(!$('#dialog').open)$('#dialog').showModal();}
function closeModal(){$('#dialog').close();}
async function refresh(){
 const sequence=++refreshSequence;const response=await fetch('/api/state');if(!response.ok)throw new Error('Yerel sunucuya bağlanılamadı.');const received=await response.json();if(sequence!==refreshSequence)return;state=received;
 if(displayedChat!==state.active_chat){if(typeof liveConversation!=='undefined'&&liveConversation)stopVoiceRoom();displayedChat=state.active_chat;$('#channel').value=state.chats.find(c=>c.id===state.active_chat)?.agent||'common';lastMessages='';}
 $('#connection').textContent='SİSTEM ÇEVRİMİÇİ';render();
}
function render(){
 const renderStarted=performance.now();
 if(typeof syncAgents==='function')syncAgents();
 for(const name of ['FRIDAY','EDITH','VISION'])$('#count-'+name).textContent=state.tasks.filter(t=>t.owner===name&&['queued','working','review'].includes(t.status)).length+' aktif görev';
 $('#cacheMetric').textContent=state.cache_hits;
 const channel=$('#channel').value;const visibleMessages=state.messages.filter(m=>(m.channel||'common')===channel);const signature=channel+JSON.stringify(visibleMessages);
 if(signature!==lastMessages){
  const nearBottom=$('#messages').scrollHeight-$('#messages').scrollTop-$('#messages').clientHeight<70;
  lastMessages=signature;
  const host=$('#messages'), retained=new Map(Array.from(host.querySelectorAll(':scope > .message[data-message-id]'),el=>[el.dataset.messageId,el]));
  const nextHTML='<div class="welcome">'+(state.integrations_enabled&&state.live_chat?(state.chat_mode==='codex'?'CODEX / CHATGPT ABONELİĞİ · GERÇEK SOHBET':state.chat_mode==='local'?'YEREL QWEN · BULUT KOTASI YOK':'JARVIS · EKONOMİK YÖNLENDİRME'):'YEREL NOT MODU · MODEL KAPALI')+'</div>'+visibleMessages.map(m=>`<article class="message ${m.author==='YOU'?'you':''}"><div class="message-avatar">${esc(m.author[0])}</div><div class="message-content"><div class="message-meta">${esc(m.author)}${m.model?'<span class="model-label">'+({local:'LOCAL',codex:'CODEX',gemini:'GEMINI',claude_google:'CLAUDE'}[m.provider]||'MODEL')+'</span>':''}${m.status==='streaming'?'<span class="stream-label">YANITLIYOR…</span>':''}<time>${esc(m.time)}</time></div><div class="message-text">${esc(m.text)}</div></div></article>`).join('')+(state.tasks.length===0&&channel==='common'?'<div class="suggestions"><button data-example="Mac için not uygulaması geliştir">⌘ Bir uygulama geliştir</button><button data-example="Yerel veri saklama seçeneklerini araştır">✧ Araştırma başlat</button><button data-example="MVP güvenliğini incele">◈ İkinci görüş al</button></div>':'');
  const fragment=document.createElement('template');fragment.innerHTML=nextHTML;
  Array.from(fragment.content.querySelectorAll('.message')).forEach((row,i)=>{
   const m=visibleMessages[i],key=String(m.id),sig=JSON.stringify(m),prior=retained.get(key);
   if(prior&&prior.dataset.recordSignature===sig){row.replaceWith(prior);renderMetrics.reusedRows++;}
   else{row.dataset.messageId=key;row.dataset.recordSignature=sig;}
  });
  host.replaceChildren(fragment.content);
  if(nearBottom)$('#messages').scrollTop=$('#messages').scrollHeight;
 }
 renderTasks();renderCommands();
 if(typeof renderWorkspace==='function')renderWorkspace();
 $('#handoffUsage').textContent=`BUGÜN: ${state.usage.handoffs} / ${state.settings.daily_handoffs} MANUEL PAKET · GERÇEK SAĞLAYICI KOTASI ÖLÇÜLMEZ`;
 renderMetrics.count++;renderMetrics.lastMs=performance.now()-renderStarted;renderMetrics.maxMs=Math.max(renderMetrics.maxMs,renderMetrics.lastMs);
 $('#messages').dataset.renderMs=renderMetrics.lastMs.toFixed(2);$('#messages').dataset.reusedRows=String(renderMetrics.reusedRows);
}
function renderTasks(){
 const filter=$('#taskFilter').value;const tasks=state.tasks.filter(t=>!t.archived&&(filter==='all'||(filter==='active'?['queued','working','review'].includes(t.status):t.status===filter)));
 $('#taskCount').textContent=state.tasks.filter(t=>!t.archived).length+' GÖREV';
 $('#tasks').innerHTML=tasks.length?tasks.slice().reverse().map((t,i)=>`<article class="task-row"><span class="task-num">${String(tasks.length-i).padStart(2,'0')}</span><div class="task-title">${esc(t.title)}<small>${esc(t.id)} ${t.cache_hit?' / ÖNBELLEKTEN':''}</small></div><span class="owner-badge">${esc(t.owner)}</span><span class="status ${esc(t.status)}">${statusNames[t.status]}</span><div class="task-actions">${['queued','working','review'].includes(t.status)?`<button class="button small" data-task="${t.id}" data-action="handoff">Paketi al ↗</button><button class="button small primary" data-task="${t.id}" data-action="result">Yanıt aktar</button><button class="button small" data-task="${t.id}" data-action="transfer">Devret ⇄</button><button class="button small" data-task="${t.id}" data-action="cancel" aria-label="Görevi iptal et">×</button>`:`<button class="button small" data-task="${t.id}" data-action="detail">Sonucu aç ↗</button>`}</div></article>`).join(''):'<div class="empty">Henüz görev yok. Oluşturduğunda burada görünecek.</div>';
}
function renderCommands(){
 $('#commands').innerHTML=state.commands.length?state.commands.slice().reverse().map(c=>`<article class="command-row"><code>${esc(c.argv.join(' '))}</code><p>${esc(c.id)} · ${esc(c.created_at)} · ${statusNames[c.status]} · Onay 10 dakika geçerli</p>${c.status==='pending'?`<div class="dialog-actions"><button class="button danger" data-command="${c.id}" data-action="reject">Reddet</button><button class="button primary" data-command="${c.id}" data-action="review-command">İncele ve onayla</button></div>`:''}${c.output?`<pre>${esc(c.output)}</pre>`:''}</article>`).join(''):'<p class="empty">Bekleyen komut yok. Önerilen komutlar burada tek tek onaylanır.</p>';
}
async function showFile(file){
 const response=await fetch('/api/files');if(!response.ok)throw new Error('Dosyalar okunamadı.');const files=await response.json();
 currentFile=file;$('#fileContent').textContent=files[file];document.querySelectorAll('.file-tabs button').forEach(b=>b.classList.toggle('active',b.dataset.file===file));
}
async function view(name){
 if(currentView==='screen'&&name!=='screen'&&typeof nativeSend==='function'&&!(typeof liveScreenSharing!=='undefined'&&liveScreenSharing))nativeSend('stop-screen');
 currentView=name;document.body.dataset.view=name;document.querySelectorAll('.view').forEach(el=>el.classList.toggle('hidden',el.id!==name));
 document.querySelectorAll('.rail-btn').forEach(el=>el.classList.toggle('active',el.dataset.view===name));
 const titles={project:['Project workspace.','Dosyalar, kod ve FRIDAY ile aynı çalışma alanında.'],screen:['Visual cortex.','Ekranını yalnızca sen istediğinde gözlemle.'],mission:['Mission control.','Merhaba Berke. Sistem hazır, seni dinliyorum.'],memory:['Shared context.','Sen bir kez anlat. Ekip aynı konuşmadan devam etsin.'],approvals:['Command authority.','Çalıştırılacak her komut, önce senin onayından geçer.'],settings:['System protocol.','Bütçe, sınırlar ve gelecekteki bağlantılar.']};
 $('#pageTitle').textContent=titles[name][0];$('#pageSubtitle').textContent=titles[name][1];
 if(name==='memory'){if(typeof renderSharedMemory==='function')renderSharedMemory();await showFile(currentFile);}
 if(name==='settings')Object.entries(state.settings).forEach(([key,value])=>$('#'+key).value=value);
}
async function taskAction(id,action){
 const task=state.tasks.find(t=>t.id===id);
 if(action==='handoff'){
  const result=await api('handoff',{id});
  modal(task.owner+' · Görev paketi',`<p class="dialog-text">Paket hazırlandı; hiçbir sağlayıcıya gönderilmedi. Kopyala, ${esc(task.owner)} için kullandığın resmi araca yapıştır, sonra yanıtı aktar. İçerik yerel proje hafızası içerir.</p><textarea id="packet" class="packet" readonly aria-label="Görev paketi">${esc(result.packet)}</textarea><div class="dialog-actions"><button id="copyPacket" class="button primary">Paketi kopyala</button></div>`);
  $('#copyPacket').onclick=()=>safe(async()=>{try{await navigator.clipboard.writeText(result.packet);toast('Paket kopyalandı.');}catch{$('#packet').select();toast('Paket seçildi. ⌘C ile kopyala.');}});
 }else if(action==='result'){
  modal(task.owner+' · Yanıtı aktar',`<form id="resultForm"><p class="dialog-text">${esc(task.title)}<br>Yanıt kullanıcı tarafından aktarılmış olarak işaretlenir.${task.owner==='EDITH'?' Araştırma, süreli önbelleğe de kaydedilir.':''}</p><textarea id="resultText" class="result-input" required maxlength="50000" placeholder="Aldığın yanıtı ve varsa kaynak bağlantılarını yapıştır…" aria-label="Sağlayıcı yanıtı"></textarea><div class="dialog-actions"><button class="button primary">Kaydet & tamamla</button></div></form>`);
  $('#resultForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('result',{id,text:$('#resultText').value});closeModal();toast('Yanıt ortak konuşmaya kaydedildi.');});};
 }else if(action==='transfer'){
  openTransferModal(task);
 }else if(action==='cancel'){
  modal('Görevi iptal et',`<p class="dialog-text">${esc(task.title)}</p><div class="dialog-actions"><button class="button danger" id="confirmCancel">İptali kaydet</button></div>`);
  $('#confirmCancel').onclick=()=>safe(async()=>{await api('cancel',{id});closeModal();});
 }else{
  modal('Görev sonucu',`<p class="dialog-text">${esc(task.owner)} / ${esc(task.id)} / ${statusNames[task.status]}</p><pre>${esc(task.result||'Bu görevde sonuç yok.')}</pre>`);
 }
}
document.addEventListener('click',e=>{
 const target=e.target.closest('button');if(!target)return;
 if(target.dataset.view)safe(()=>view(target.dataset.view));
 if(target.dataset.file)safe(async()=>{await view('memory');$('#technicalMemory').classList.remove('hidden');await showFile(target.dataset.file);});
 if(target.dataset.example){$('#prompt').value=target.dataset.example;$('#prompt').focus();}
 if(target.dataset.task)safe(()=>taskAction(target.dataset.task,target.dataset.action));
 if(target.dataset.command)safe(async()=>{
  const id=target.dataset.command;
  if(target.dataset.action==='reject'){await api('reject',{id});toast('Komut reddedildi.');return;}
  const command=state.commands.find(c=>c.id===id);
  modal('Komutu çalıştırmayı onayla',`<p class="dialog-text">Bu işlem yalnızca Python sürümünü okur. Dosya değiştirmez ve internete erişmez. Onay tek kullanımlıktır.</p><pre>${esc(command.argv.join(' '))}</pre><div class="dialog-actions"><button id="approveExact" class="button primary">Bu komutu çalıştır</button></div>`);
  $('#approveExact').onclick=()=>safe(async()=>{$('#approveExact').disabled=true;await api('approve',{id});closeModal();toast('Komut işlendi. Sonuç onay merkezinde.');});
 });
});
$('#composer').onsubmit=e=>{e.preventDefault();if(busy)return;if(state.model_job){toast('Yanıt hazırlanıyor. Durdur düğmesiyle kesebilirsin.');return;}busy=true;const send=$('.send');send.disabled=true;safe(async()=>{try{const text=$('#prompt').value;const result=await api($('#messageMode').value,{text,owner:$('#owner').value,channel:$('#channel').value,project_work:Boolean(state.chats.find(c=>c.id===state.active_chat)?.project_work),image:typeof pendingScreenImage!=='undefined'?(pendingScreenImage||(liveScreenSharing?lastScreenImage:null)):null});$('#prompt').value='';$('#prompt').style.height='42px';if(result.task_id){$('#messageMode').value='converse';$('#messageMode').dispatchEvent(new Event('change'));}if(typeof clearScreenAttachment==='function')clearScreenAttachment();if(!result.model_started&&state.messages[state.messages.length-1]?.provider!=='rules')window.dispatchEvent(new CustomEvent('jarvis-reply',{detail:{channel:$('#channel').value,message:state.messages[state.messages.length-1]}}));}catch(error){window.dispatchEvent(new Event('jarvis-send-error'));throw error;}finally{busy=false;send.disabled=false;}});};
$('#prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#composer').requestSubmit();}});
$('#messageMode').onchange=()=>{$('#owner').disabled=$('#messageMode').value!=='task';};
$('#taskFilter').onchange=renderTasks;
$('#closeDialog').onclick=closeModal;
$('#help').onclick=()=>modal('JARVIS · v0.4.0',`<div class="dialog-text"><p>Günlük sohbet Gemini Flash, kod işleri Codex ile çalışır. İstersen tamamen yerel motoru seçebilirsin.</p><p>Proje bağlamı isteğe bağlıdır. Onay isteyen komutlar sohbet içinde kart olarak görünür.</p><p>Bilgisayar veya site üzerinde aktif çalışma için Araçlar → ChatGPT’ye devret. Hazırlanan görevi ChatGPT’de gönder; istersen seçtiğin pencereyi burada canlı izle.</p><p>Dil ve ses seçenekleri Ayarlar’dadır. Sesli konuşma Enter gerektirmez; konuşurken en güncel ekranı paylaşmak da isteğe bağlıdır.</p></div>`);
$('#settingsForm').onsubmit=e=>{e.preventDefault();safe(async()=>{const settings={};['daily_usd','task_usd','daily_handoffs','cache_hours'].forEach(k=>settings[k]=Number($('#'+k).value));await api('settings',settings);toast('Bütçe ayarları kaydedildi. API anahtarıyla ücretli bağlantı açılmaz.');});};
$('#proposeCommand').onclick=()=>safe(async()=>{await api('propose',{command:'python-version'});toast('Komut önerildi; henüz çalıştırılmadı.');});
$('#decisionForm').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('decision',{text:$('#decisionText').value});$('#decisionText').value='';await showFile('decisions.md');toast('Karar kaydedildi.');});};
$('#clearCache').onclick=()=>{modal('Araştırma önbelleğini temizle',`<p class="dialog-text">Kaydedilmiş araştırmalar yeni görevlerde yeniden kullanılmayacak. Eski yanıtlar görev geçmişinde kalacak.</p><div class="dialog-actions"><button class="button danger" id="confirmClear">Önbelleği temizle</button></div>`);$('#confirmClear').onclick=()=>safe(async()=>{await api('clear-cache');await showFile(currentFile);closeModal();toast('Önbellek temizlendi.');});};
function clock(){$('#clock').textContent=new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});}clock();setInterval(clock,1000);
$('#owner').disabled=true;
function schedulePoll(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{if(!busy)try{await refresh();}catch{$('#connection').textContent='BAĞLANTI KESİLDİ';}schedulePoll();},state&&Object.keys(state.model_jobs||{}).length?700:4000);}
safe(async()=>{await refresh();window.dispatchEvent(new Event('jarvis-ready'));schedulePoll();});
