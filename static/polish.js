'use strict';
// One quota pool per connector. Reusing a role never creates a second allowance.
function quotaKeyFor(name){
 const a=state.agents.find(a=>a.name===name),connector=name==='JARVIS'?state.jarvis_connector:a?.connector,model=name==='JARVIS'?state.jarvis_model:a?.model;
 return connector==='codex'?'FRIDAY':connector==='claude_code'?'CLAUDE_PRO':connector==='claude_google'?'VISION':connector==='gemini'?(model?.startsWith('gemini')?'EDITH':'VISION'):null;
}
function readableModel(model){
 if(!model||model==='Codex varsayılanı')return tr('Otomatik model','Automatic model');
 const m=model.match(/^gemini-([\d.]+)-(flash-lite|flash|pro)(?:-(low|medium|high))?$/);if(m)return 'Gemini '+m[1]+' '+({'flash-lite':'Flash-Lite',flash:'Flash',pro:'Pro'})[m[2]]+(m[3]?' · '+({low:tr('Hızlı','Fast'),medium:tr('Dengeli','Balanced'),high:tr('Derin','Deep')})[m[3]]:'');
 return ({sonnet:'Claude Sonnet',opus:'Claude Opus',haiku:'Claude Haiku','openrouter/free':tr('Ücretsiz model seçimi','Free model selection')})[model]||model;
}
function projectScopeSummary(){const chat=state.chats.find(c=>c.id===state.active_chat);return !state.active_project_path?tr('Proje klasörü bağlı değil. Dosyalarla çalışmak için + menüsünden bir klasör bağla.','No project folder is attached. Attach one from + to work with files.'):chat?.project_work?tr('Proje çalışması açık. Yalnızca görevlendirilen Codex/Claude Code ajanı seçili klasöre erişir; diğerleri otomatik çalışmaz.','Project work is on. Only the assigned Codex/Claude Code agent gets the selected folder; other agents are not started.'):tr('Klasör bağlı; proje çalışması kapalı. Sohbetteki proje çipinden Projede çalış seçeneğini aç. İzin düzeyi tek başına dosya aracı başlatmaz.','A folder is attached; project work is off. Enable Work on project in the chat project chip. The permission level alone does not start tools.');}
function agentPermissionSummary(a){
 if(['codex','claude_code'].includes(a.connector)){
  const chat=state.chats.find(c=>c.id===state.active_chat),active=state.active_project_path&&chat?.project_work;
  return (active?tr('Proje araçları açık','Project tools enabled'):tr('Proje araçları destekleniyor · bu sohbette kapalı','Project tools supported · off in this chat'))+' · '+(a.connector==='codex'?tr('Dosyalar ve testler','Files and tests'):tr('Dosya okuma ve düzenleme','Read and edit files'));
 }
 if(a.connector==='gemini')return tr('Sohbet, görsel ve web araştırması · proje dosyası düzenlemez','Chat, images and web research · no project file editing');
 return a.connector==='manual'?tr('Elle görev aktarımı','Manual task transfer'):tr('Sohbet ve verilen belgeyi inceleme · proje araçları yok','Chat and attached documents · no project file tools');
}
// Reset large previews when opening an ordinary settings dialog.
const plainModal=modal;modal=function(title,body){$('#dialog').classList.remove('attachment-viewer');delete $('#dialog').dataset.quotaAgent;delete $('#dialog').dataset.quotaStamp;plainModal(title,body);};
function showAgentDetails(name){
 const a=state.agents.find(a=>a.name===name),key=quotaKeyFor(name),usage=key?state.provider_usage?.[key]:null;
 const provider=name==='JARVIS'?state.jarvis_connector:a?.connector,model=name==='JARVIS'?state.jarvis_model:a?.model;
 const rows=[[tr('Görev','Role'),name==='JARVIS'?tr('Seninle konuşur, işleri planlar ve dağıtır','Talks with you, plans and assigns work'):a?.role||tr('Asistan','Assistant')],[tr('Bağlantı','Connection'),connectionNames[provider]||provider||'—'],[tr('Model seçimi','Model selection'),readableModel(model)],[tr('Efor','Effort'),a?.effort||tr('İsteğe göre otomatik','Automatic for the request')],[tr('Proje erişimi','Project access'),name==='JARVIS'?projectScopeSummary():agentPermissionSummary(a)]];
 const windows=usage&&['live','stale'].includes(usage.status)?[usage.primary,usage.secondary].filter(Boolean):[];
 modal(name+' · '+tr('Ayrıntılar','Details'),`<div class="agent-detail-tabs" role="tablist"><button class="button active" role="tab" aria-selected="true" data-agent-tab="general">${tr('Genel','General')}</button><button class="button" role="tab" aria-selected="false" data-agent-tab="quota">${tr('Kota','Usage limits')}</button></div><section data-agent-panel="general"><dl class="agent-detail-grid">${rows.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl><p class="muted">${tr('Her yanıttaki model etiketi o istekte gönderilen seçimdir. Otomatik modda basit soru hızlı, görsel veya araştırma daha yüksek efor kullanabilir. Ajanın kendi söylediği model adı kaynak alınmaz.','Each reply label shows the model selection sent for that request. Automatic mode may use a faster tier for simple questions and more effort for images or research. The model’s self-description is not the source.')}</p></section><section data-agent-panel="quota" hidden>${['EDITH','VISION'].includes(key)&&!windows.some(w=>w.minutes===300)?'<div class="detail-quota quota-unavailable"><b>'+esc(tr('5 saatlik','5-hour'))+'</b><strong>'+esc(tr('Okunamıyor','Unavailable'))+'</strong></div>':''}${windows.length?windows.map(w=>`<div class="detail-quota"><b>${esc(quotaLabel(w.minutes))}</b><progress max="100" value="${100-w.used_percent}"></progress><strong>${Math.round(100-w.used_percent)}% ${tr('kaldı','left')}</strong><small>${esc(w.resets_at?new Date(w.resets_at*1000).toLocaleString():w.reset_text||tr('Yenilenme saati sağlanmadı','Reset time unavailable'))}</small></div>`).join(''):`<p>${esc(provider==='local'?tr('Yerel modelde abonelik kotası yok; bu Mac’in kaynaklarını kullanır.','Local models use this Mac’s resources and have no subscription quota.'):provider==='openrouter'&&!state.free_key_available?tr('OpenRouter anahtarı eklenmedi; hesap kotası okunamaz.','No OpenRouter key is configured; account limits are unavailable.'):usage?.message||tr('Sağlayıcı doğrulanmış kota bilgisi vermedi.','The provider has not supplied verified limits.'))}</p>`}<p class="muted">${esc(usage?.scope||'')}</p>${provider==='gemini'?'<p class="muted">'+esc(tr('Gemini modeldir; bağlantı Antigravity’dir. JARVIS, EDITH ve NOVA aynı Gemini kota grubunu paylaşır. NOVA bağımsız sohbet rolüdür; ayrı Gemini uygulaması bağlantısı değildir. 5 saatlik yüzde bu resmî kaynakta yoksa okunamıyor gösterilir.','Gemini is the model; Antigravity is the connection. JARVIS, EDITH and NOVA share its Gemini quota group. NOVA is an independent chat role, not a separate Gemini app connection. If the official source does not report the five-hour percentage, it is shown as unavailable.'))+'</p>':''}<p class="muted">${esc(usage?.source||'')}${usage?.checked_at?' · '+new Date(usage.checked_at*1000).toLocaleString():''}</p><button class="button" id="detailQuotaRefresh">${tr('Kotaları yenile','Refresh limits')}</button></section>`);
 $('#dialog').dataset.quotaAgent=name;$('#dialog').dataset.quotaStamp=JSON.stringify(usage||null);
 $('#dialogBody').querySelectorAll('[data-agent-tab]').forEach(button=>button.onclick=()=>{$('#dialogBody').querySelectorAll('[data-agent-panel]').forEach(p=>p.hidden=p.dataset.agentPanel!==button.dataset.agentTab);$('#dialogBody').querySelectorAll('[data-agent-tab]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-selected',String(b===button));});});
 $('#detailQuotaRefresh').onclick=()=>safe(async()=>{await api('quota-refresh');toast(tr('Resmî kotalar yenileniyor; model çağrılmaz.','Refreshing official limits; no model call.'));});
}
const polishedRender=renderWorkspace;renderWorkspace=function(){polishedRender();
 const selected=$('#channel').value==='common'?'JARVIS':$('#channel').value,active=state.agents.find(a=>a.name===selected),accent=active?.color||'#70d5e8';
 agentHeading.style.setProperty('--agent-accent',accent);agentHeading.dataset.symbol=selected[0];agentHeading.dataset.mode=state.model_job?tr('Çalışıyor','Working'):tr('Sohbet','Chat');agentHeading.classList.toggle('agent-busy',Boolean(state.model_job));
 document.querySelectorAll('.agent').forEach(card=>{
  const name=card.querySelector('h2').textContent,a=state.agents.find(a=>a.name===name),key=quotaKeyFor(name),u=key?state.provider_usage?.[key]:null;
  if(key){card.querySelector('.agent-quota').innerHTML=usageMarkup(key);if(u?.status==='live'){const pool=key==='FRIDAY'?'ChatGPT':key==='CLAUDE_PRO'?'Claude Pro':key==='EDITH'?'Antigravity':'Antigravity';card.querySelector('.agent-summary').textContent=shortQuotaText(u,pool);}}
  const model=card.querySelector('.agent-model-name');if(model){model.textContent=readableModel(a?.model);model.title=a?.model||tr('Modeli resmî sağlayıcı seçer.','The official provider selects the model.');}
  const role=card.querySelector('p');if(role){const short={JARVIS:tr('Koordinatör','Coordinator'),FRIDAY:tr('Yardımcı geliştirici','Supporting developer'),EDITH:tr('Araştırma ve tasarım','Research and design'),VISION:tr('Ana geliştirici','Lead developer')};role.textContent=short[name]||a?.role||tr('Asistan','Assistant');role.title=a?.role||role.textContent;}
  const footer=card.querySelector('footer>span');if(footer){footer.textContent=({codex:'ChatGPT',claude_code:'Claude Pro',gemini:'Gemini · Antigravity',claude_google:'Antigravity',openrouter:'OpenRouter',local:tr('Bu Mac','This Mac')})[name==='JARVIS'?state.jarvis_connector:a?.connector]||tr('Elle aktarım','Manual');}
  const count=card.querySelector('footer>b');if(count){if(name==='JARVIS')count.textContent=tr('Koordinatör','Coordinator');else{const n=Number.parseInt(count.textContent,10);if(Number.isFinite(n))count.textContent=n+' '+tr('görev','tasks');}}
  let details=card.querySelector('.agent-details-button');if(!details){details=document.createElement('button');details.type='button';details.className='agent-details-button';details.textContent=tr('Ayrıntılar','Details');details.setAttribute('aria-label',name+' · '+details.textContent);details.onclick=e=>{e.stopPropagation();showAgentDetails(name);};card.append(details);}
 });
 const messages=state.messages.filter(m=>(m.channel||'common')===$('#channel').value);document.querySelectorAll('#messages .message').forEach((row,i)=>{const m=messages[i],label=row.querySelector('.model-label');if(label&&m?.model){label.textContent=readableModel(m.model.split(' · ')[0]);label.title=tr('Bu yanıta gönderilen model: ','Model sent for this reply: ')+m.model;}});
};
// Honest live activity: only actual CLI tool events and URLs, never simulated browsing.
const stageOpen=new Map();
function activityText(activity){let data={};try{data=JSON.parse(activity.detail);}catch{}const p=data.parameters||{};if(/search|web/i.test(activity.kind))return {label:tr('Web araştırması','Web research'),detail:p.query||p.search_query||p.url||activity.detail,live:data.state&&data.state!=='DONE'};if(/read_url|browse|fetch/i.test(activity.kind))return {label:tr('Kaynak inceleniyor','Reading source'),detail:p.url||activity.detail,live:data.state&&data.state!=='DONE'};return {label:({project_read:tr('Dosya okunuyor','Reading file'),project_edit:tr('Dosya düzenleniyor','Editing file'),project_command:tr('Test çalıştırılıyor','Running test'),project_list:tr('Proje inceleniyor','Inspecting project')})[activity.kind]||tr('İşlem','Activity'),detail:activity.detail,live:false};}
const stagesRender=renderWorkspace;renderWorkspace=function(){stagesRender();const messages=state.messages.filter(m=>(m.channel||'common')===$('#channel').value);
 document.querySelectorAll('#messages .message').forEach((row,i)=>{const m=messages[i];if(!m)return;
  if(m.workflow_id&&!m.workflow_intro&&!m.presentation&&!row.querySelector('.agent-stage')){const body=row.querySelector('.message-text'),details=document.createElement('details');details.className='agent-stage';const sum=document.createElement('summary');const job={EDITH:tr('araştırma çıktısı','research output'),VISION:tr('kod çıktısı','code output'),FRIDAY:tr('test/inceleme çıktısı','review output')}[m.author];sum.textContent=m.author+(job?' · '+job:'')+' · '+(m.status==='streaming'?tr('Çalışıyor','Working'):m.status==='done'?tr('Görev tamamlandı','Task completed'):tr('İşlem durdu','Work stopped'));details.open=stageOpen.has(m.id)?stageOpen.get(m.id):true;details.ontoggle=()=>stageOpen.set(m.id,details.open);body.before(details);details.append(sum,body);row.querySelector('.execution-log')&&details.append(row.querySelector('.execution-log'));}
  if(m.presentation)row.classList.add('jarvis-presentation');
  if(!m.activities?.length)return;let box=row.querySelector('.live-research');if(!box){box=document.createElement('div');box.className='live-research';row.querySelector('.message-meta').after(box);}
  const signature=JSON.stringify([m.status,m.activities]);if(box.dataset.signature===signature)return;box.dataset.signature=signature;const latest=m.activities[m.activities.length-1],label=activityText(latest),urls=[];
  for(const event of m.activities){for(const match of String(event.detail).matchAll(/https?:\/\/[^\s"'<>}\\]+/g)){try{const u=new URL(match[0]);if(!urls.some(x=>x.hostname===u.hostname))urls.push(u);}catch{}}}
  box.innerHTML=`<div class="research-status ${m.status==='streaming'?'working':'complete'}"><i></i><strong>${esc(m.author)}</strong><span>${esc(m.status==='streaming'?label.label:m.status==='done'?tr('Görev tamamlandı','Task completed'):tr('Durduruldu','Stopped'))}</span></div><p>${esc(String(label.detail||'').slice(0,160))}</p><div class="research-sources">${urls.slice(0,6).map(u=>`<button data-source-url="${esc(u.href)}"><span class="site-orbit">${esc(u.hostname.replace(/^www\./,'')[0].toUpperCase())}</span>${esc(u.hostname.replace(/^www\./,''))}</button>`).join('')}</div>`;
  box.querySelectorAll('[data-source-url]').forEach(b=>b.onclick=()=>nativeSend('open-task-site',{url:b.dataset.sourceUrl}));
 });
 let progress=$('#chatWorkflowProgress');if(!progress){progress=document.createElement('div');progress.id='chatWorkflowProgress';$('#messages').after(progress);}
 const shownChannel=$('#channel').value;const run=(state.chat_workflows||[]).filter(r=>r.chat_id===state.active_chat&&state.messages.some(m=>m.workflow_id===r.id&&(m.channel||'common')===shownChannel)).slice(-1)[0];progress.classList.toggle('hidden',!run);if(!run)progress.dataset.signature='';if(run){const sig=JSON.stringify([run.id,run.status,run.index]);if(progress.dataset.signature!==sig){progress.dataset.signature=sig;progress.innerHTML='<div class="workflow-track">'+[...run.steps,'JARVIS'].map((name,i)=>`<span class="${i<run.index||run.status==='done'?'done':i===run.index&&['working','presenting'].includes(run.status)?'active':''}"><i></i>${esc(name)}</span>`).join('<b>›</b>')+'</div><small>'+esc(run.status==='done'?tr('Ekip işi tamamlandı · JARVIS sonucu sundu','Team work complete · JARVIS presented the result'):run.status==='paused'?tr('Duraklatıldı · ara sonuçlar saklandı','Paused · intermediate results preserved'):run.status==='error'?tr('Bir adım tamamlanamadı · otomatik tekrar yapılmadı','A step failed · no automatic retry'):run.current_owner+' · '+tr('çalışıyor','working'))+'</small>'+(run.status==='paused'?'<button class="button small" id="resumeChatWorkflow">'+tr('Devam et','Resume')+'</button>':'');if($('#resumeChatWorkflow'))$('#resumeChatWorkflow').onclick=()=>safe(()=>api('workflow-resume',{id:run.id}));}}
};

// Explicit orchestra: one lead and only the specialists named for this task.
(()=>{
const prior=renderWorkspace;renderWorkspace=function(){prior();
 if(!state)return;
 const run=(state.chat_workflows||[]).filter(r=>r.chat_id===state.active_chat&&r.mode==='orchestra').slice(-1)[0];
 let panel=document.getElementById('orchestraPlan');
 if(!run||$('#channel').value!=='common'){if(panel)panel.remove();return;}
 if(!panel){panel=document.createElement('section');panel.id='orchestraPlan';panel.className='orchestra-plan';$('#messages').before(panel);}
 const sig=JSON.stringify([run.id,run.status,run.subtasks]);if(panel.dataset.signature===sig)return;panel.dataset.signature=sig;
 panel.innerHTML='<details><summary>'+esc(tr('VISION liderliğinde ekip','Team led by VISION'))+' · '+esc(run.status==='done'?tr('Tamamlandı','Completed'):tr('Görev planı','Task plan'))+'</summary><ul>'+run.subtasks.map(t=>'<li><b>'+esc(t.owner)+'</b><span>'+esc(t.title)+'</span><small>'+esc(({queued:tr('Sırada','Queued'),working:tr('Çalışıyor','Working'),done:tr('Tamamlandı','Completed'),error:tr('Hata','Error'),cancelled:tr('Durduruldu','Stopped')})[t.status]||t.status)+'</small></li>').join('')+'</ul></details>';
 };
})();

// Keep the open quota view in sync when the official background reader finishes.
(()=>{
 const prior=renderWorkspace;renderWorkspace=function(){prior();
  const dialog=$('#dialog'),name=dialog.dataset.quotaAgent;if(!dialog.open||!name)return;
  const key=quotaKeyFor(name),usage=key?state.provider_usage?.[key]:null;
  if(dialog.dataset.quotaStamp===JSON.stringify(usage||null))return;
  const tab=dialog.querySelector('[data-agent-tab].active')?.dataset.agentTab||'general';
  showAgentDetails(name);dialog.querySelector('[data-agent-tab="'+tab+'"]').click();
 };
})();
