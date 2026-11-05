'use strict';
// "Who is working right now" bubble above the composer (0.7.4).
// Shows every agent that is running, in this chat and in other chats/projects, with a one-line summary.
(()=>{
const composer=document.getElementById('composer');
if(!composer)return;
const box=document.createElement('div');box.id='agentPulse';box.className='agent-pulse hidden';box.setAttribute('role','status');box.setAttribute('aria-live','polite');
const anchor=document.getElementById('inlineApprovals');
(anchor?anchor:composer).insertAdjacentElement(anchor?'afterend':'beforebegin',box);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clip=(s,n)=>{s=String(s||'').trim();return s.length>n?s.slice(0,n-1)+'…':s;};
const kindVerb=kind=>{
  if(/read_url|browse|fetch/i.test(kind))return tr('kaynak okuyor','is reading a source');
  if(/search|web/i.test(kind))return tr("web'de arama yapıyor",'is searching the web');
  if(/project_command|project_test|command_result/i.test(kind))return tr('komut çalıştırıyor','is running a command');
  if(/project_edit/i.test(kind))return tr('dosya düzenliyor','is editing a file');
  if(/project_list/i.test(kind))return tr('projeyi inceliyor','is browsing the project');
  if(/project_read/i.test(kind))return tr('dosya okuyor','is reading a file');
  return '';
};
const clock=sec=>{const m=Math.floor(sec/60),s=sec%60;return m?m+tr(' dk ',' min ')+s+tr(' sn',' s'):s+tr(' sn',' s');};
const verb=row=>{
  if(row.mode==='computer')return tr('bilgisayarı kullanıyor','is using your Mac');
  const fromActivity=row.activity?kindVerb(String(row.activity).split(' ')[0]):'';if(fromActivity)return fromActivity;
  if(row.mode==='project')return tr('projede çalışıyor','is working in the project');
  if(row.mode==='planning')return tr('planlıyor','is planning');
  if(row.mode==='research')return tr('internette araştırıyor','is researching the web');
  if(row.mode==='team')return tr('ekibi yürütüyor','is running the team');
  return row.writing?tr('yazıyor','is writing'):tr('düşünüyor','is thinking');
};
const seconds=row=>row.started_at?Math.max(0,Math.round(Date.now()/1000-row.started_at)):null;
let lastKey='';
function paint(){
  const rows=(typeof state!=='undefined'&&state&&state.active_work)||[];
  document.body.classList.toggle('has-pulse',rows.length>0);
  if(!rows.length){box.classList.add('hidden');lastKey='';return;}
  const ordered=[...rows].sort((a,b)=>Number(b.current)-Number(a.current));
  const shown=ordered.slice(0,4),extra=ordered.length-shown.length;
  const html=shown.map(row=>{
    const secs=seconds(row),where=row.current?'':`<span class="pulse-where">${esc(clip(row.chat,28))}${row.project?' · '+esc(clip(row.project,22)):''}</span>`;
    const detail=row.activity||row.summary?`<span class="pulse-detail">${esc(clip(row.activity||('“'+row.summary+'”'),64))}</span>`:'';
    return `<button type="button" class="pulse-row${row.current?' current':''}" data-pulse-chat="${esc(row.chat_id)}" data-agent="${esc(row.agent)}" title="${esc(row.summary)}"><i class="pulse-dot"></i><b>${esc(row.agent)}</b><span class="pulse-verb">${esc(verb(row))}<em class="pulse-dots"><u></u><u></u><u></u></em></span>${detail}${where}${secs!==null?`<small>${clock(secs)}</small>`:''}</button>`;
  }).join('')+(extra>0?`<span class="pulse-more">+${extra} ${tr('daha','more')}</span>`:'');
  const key=html.replace(/<small>[^<]*<\/small>/g,'');
  box.classList.remove('hidden');
  if(key===lastKey){ // only the seconds changed
    box.querySelectorAll('.pulse-row small').forEach((el,i)=>{const s=seconds(shown[i]);if(s!==null)el.textContent=clock(s);});return;
  }
  lastKey=key;box.innerHTML=html;
}
box.addEventListener('click',e=>{const row=e.target.closest('[data-pulse-chat]');if(!row||row.classList.contains('current'))return;safe(async()=>{await api('select-chat',{id:row.dataset.pulseChat});});});
const previous=renderWorkspace;
renderWorkspace=function(){previous();paint();};
setInterval(()=>{if(!box.classList.contains('hidden'))paint();},1000);
paint();
})();
