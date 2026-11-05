'use strict';
// Jump rail on the left edge of the chat: one tick per turn (your message plus the replies that follow it).
// Hover or focus a tick for a small card with your prompt and the start of the reply; click to jump there.
(()=>{
const pane=document.querySelector('.conversation'),list=document.getElementById('messages');
if(!pane||!list)return;
const rail=document.createElement('nav');rail.id='msgRail';rail.className='msg-rail hidden';rail.setAttribute('aria-label',tr('Mesajlara atla','Jump to message'));
const track=document.createElement('div');track.className='rail-track';
const tip=document.createElement('div');tip.className='rail-tip';tip.setAttribute('role','tooltip');tip.hidden=true;
const tipHead=document.createElement('div');tipHead.className='rail-tip-head';
const tipTitle=document.createElement('b');tipTitle.className='rail-tip-title';
const tipMark=document.createElement('span');tipMark.className='rail-tip-mark';tipMark.setAttribute('aria-hidden','true');
tipMark.innerHTML='<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 4h11a1 1 0 0 1 1 1v15l-6.5-4-6.5 4V5a1 1 0 0 1 1-1z"/></svg>';
tipHead.append(tipTitle,tipMark);
const tipBody=document.createElement('span');tipBody.className='rail-tip-body';
tip.append(tipHead,tipBody);
rail.append(track,tip);pane.append(rail);
let signature='',turns=[],ticks=[];
const rows=()=>[...list.querySelectorAll('.message')];
const clean=row=>(row?.querySelector('.message-text')?.textContent||'').trim().replace(/\s+/g,' ');
const clip=(text,n)=>text.length>n?text.slice(0,n-1)+'…':text;
const whoOf=row=>(row?.querySelector('.message-meta')?.firstChild?.textContent||'').trim();
function mark(){
  if(!ticks.length)return;
  const all=rows(),top=list.scrollTop+48;let current=0;
  all.forEach((row,i)=>{if(row.offsetTop<=top)current=i;});
  if(list.scrollHeight-list.scrollTop-list.clientHeight<4)current=all.length-1;
  let best=0;turns.forEach((turn,k)=>{if(turn.index<=current)best=k;});
  ticks.forEach((tick,k)=>tick.classList.toggle('active',k===best));
}
function spacing(count){
  const room=Math.max(160,pane.clientHeight*0.8);
  const gap=count>1?(room-count*2)/(count-1):0;
  track.style.setProperty('--tick-gap',Math.max(4,Math.min(14,gap))+'px');
}
function build(){
  const all=rows();
  const key=all.length+'|'+(all[all.length-1]?.textContent.length||0)+'|'+(document.documentElement.lang||'')+'|'+pane.clientHeight;
  if(key===signature){mark();return;}
  signature=key;
  turns=[];
  all.forEach((row,i)=>{
    if(row.classList.contains('you'))turns.push({index:i,row,reply:null});
    else if(turns.length&&!turns[turns.length-1].reply)turns[turns.length-1].reply=row;
  });
  if(turns.length<2){rail.classList.add('hidden');track.replaceChildren();ticks=[];turns=[];return;}
  const limit=Math.max(8,Math.floor(Math.max(160,pane.clientHeight*0.8)/7));
  if(turns.length>limit){
    const step=turns.length/limit;
    turns=Array.from({length:limit},(_,n)=>turns[Math.min(turns.length-1,Math.floor(n*step))]).concat(turns[turns.length-1]).filter((t,n,a)=>a.indexOf(t)===n);
  }
  ticks=turns.map((turn,k)=>{
    const tick=document.createElement('button');tick.type='button';tick.className='rail-tick';tick.dataset.k=k;
    tick.setAttribute('aria-label',clip(clean(turn.row),90));
    const who=turn.reply?whoOf(turn.reply):'';if(who&&typeof agentColor==='function')tick.style.setProperty('--agent',agentColor(who));
    return tick;
  });
  track.replaceChildren(...ticks);spacing(ticks.length);rail.classList.remove('hidden');mark();
}
function showTip(tick){
  const turn=turns[Number(tick.dataset.k)];if(!turn)return;
  tipTitle.textContent=clip(clean(turn.row),90)||tr('Mesaj','Message');
  const reply=turn.reply?clip(clean(turn.reply),420):'';
  const who=turn.reply?whoOf(turn.reply):'';
  tipBody.textContent=reply?(who?who+' · ':'')+reply:tr('Yanıt bekleniyor…','Waiting for a reply…');
  tip.hidden=false;
  const box=rail.getBoundingClientRect(),t=tick.getBoundingClientRect(),paneBox=pane.getBoundingClientRect();
  const h=tip.offsetHeight;
  let y=t.top+t.height/2-box.top-h/2;
  const minY=paneBox.top+8-box.top,maxY=paneBox.bottom-8-box.top-h;
  y=Math.max(minY,Math.min(maxY,y));
  tip.style.top=y+'px';
}
function hideTip(){tip.hidden=true;ticks.forEach(tick=>tick.classList.remove('hovered','near','nearby'));}
function magnify(tick){
 const selected=Number(tick.dataset.k);
 ticks.forEach((item,index)=>{const distance=Math.abs(index-selected);item.classList.toggle('hovered',distance===0);item.classList.toggle('near',distance===1);item.classList.toggle('nearby',distance===2);});
 showTip(tick);
}
track.addEventListener('mouseover',e=>{const tick=e.target.closest('.rail-tick');if(tick)magnify(tick);});
track.addEventListener('focusin',e=>{const tick=e.target.closest('.rail-tick');if(tick)magnify(tick);});
rail.addEventListener('mouseleave',hideTip);
track.addEventListener('focusout',hideTip);
rail.addEventListener('click',e=>{
  const tick=e.target.closest('.rail-tick');if(!tick)return;
  const turn=turns[Number(tick.dataset.k)];if(!turn)return;
  list.scrollTo({top:Math.max(0,turn.row.offsetTop-12),behavior:'smooth'});
});
let waiting=false;list.addEventListener('scroll',()=>{if(waiting)return;waiting=true;requestAnimationFrame(()=>{waiting=false;mark();});},{passive:true});
window.addEventListener('resize',()=>{signature='';build();});
const previous=renderWorkspace;renderWorkspace=function(){previous();build();};
build();
})();
