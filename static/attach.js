'use strict';
// Photo and video attachments for the chat (0.7.4).
// Photos are shrunk to a JPEG; a video becomes one time-stamped contact-sheet JPEG (up to 6 frames).
// The server sends the picture to the only agent that can read images today (Codex / FRIDAY).
(()=>{
const MAX_CHARS=2300000,MAX_SIDE=1600,MAX_FRAMES=6;
const row=document.querySelector('.compact-actions'),chip=document.getElementById('attachedScreen');
if(!row||!chip)return;
const label=chip.querySelector('span'),original=label?label.textContent:'';
const input=document.createElement('input');input.type='file';input.accept='image/*,video/*';input.hidden=true;input.id='attachInput';
const button=document.createElement('button');button.type='button';button.id='attachButton';button.className='compact-action';
button.innerHTML=glyph('<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>');
const setTitle=()=>{button.title=tr('Fotoğraf veya video ekle','Attach a photo or video');button.setAttribute('aria-label',button.title);};setTitle();
$('#toolsButton').after(button);row.append(input);
button.onclick=()=>{input.value='';input.click();};
input.onchange=()=>{const file=input.files&&input.files[0];if(file)safe(()=>attachFile(file));};

const wait=(target,event,ms=9000)=>new Promise((ok,bad)=>{const timer=setTimeout(()=>{target.removeEventListener(event,done);bad(new Error('timeout'));},ms);const done=()=>{clearTimeout(timer);ok();};target.addEventListener(event,done,{once:true});});
function encode(canvas){
  let quality=.86,out=canvas.toDataURL('image/jpeg',quality);
  while(out.length>MAX_CHARS&&quality>.42){quality-=.12;out=canvas.toDataURL('image/jpeg',quality);}
  let source=canvas;
  for(let i=0;out.length>MAX_CHARS&&i<6;i++){const smaller=document.createElement('canvas');smaller.width=Math.max(64,Math.round(source.width*.8));smaller.height=Math.max(64,Math.round(source.height*.8));const g=smaller.getContext('2d');g.fillStyle='#fff';g.fillRect(0,0,smaller.width,smaller.height);g.drawImage(source,0,0,smaller.width,smaller.height);source=smaller;out=smaller.toDataURL('image/jpeg',.7);}
  if(out.length>MAX_CHARS)throw new Error(tr('Görsel çok büyük; daha küçük bir dosya seç.','The image is too large; pick a smaller file.'));
  return out;
}
function drawFitted(source,width,height){
  const scale=Math.min(1,MAX_SIDE/Math.max(width,height)),canvas=document.createElement('canvas');
  canvas.width=Math.max(1,Math.round(width*scale));canvas.height=Math.max(1,Math.round(height*scale));
  const g=canvas.getContext('2d');g.fillStyle='#fff';g.fillRect(0,0,canvas.width,canvas.height);g.drawImage(source,0,0,canvas.width,canvas.height);return canvas;
}
async function photoToJpeg(file){
  if(window.createImageBitmap){try{const bitmap=await createImageBitmap(file,{imageOrientation:'from-image'});const canvas=drawFitted(bitmap,bitmap.width,bitmap.height);bitmap.close&&bitmap.close();return encode(canvas);}catch(error){}}
  const url=URL.createObjectURL(file);
  try{const img=new Image();img.src=url;await img.decode();return encode(drawFitted(img,img.naturalWidth,img.naturalHeight));}
  catch(error){throw new Error(tr('Bu fotoğraf biçimi okunamadı.','This photo format could not be read.'));}
  finally{URL.revokeObjectURL(url);}
}
const clock=s=>Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
async function videoToSheet(file){
  const url=URL.createObjectURL(file),video=document.createElement('video');
  video.muted=true;video.preload='auto';video.playsInline=true;video.src=url;
  try{
    try{await wait(video,'loadeddata',12000);}catch(error){throw new Error(tr('Bu video biçimi okunamadı (MP4/MOV dene).','This video format could not be read (try MP4/MOV).'));}
    const duration=isFinite(video.duration)&&video.duration>0?video.duration:0,count=duration<2?1:Math.min(MAX_FRAMES,Math.max(3,Math.round(duration/4))),cols=count<=3?count:3,rows=Math.ceil(count/cols);
    const vw=video.videoWidth||640,vh=video.videoHeight||360,tileW=Math.floor(MAX_SIDE/cols),tileH=Math.round(tileW*vh/vw);
    const sheet=document.createElement('canvas');sheet.width=tileW*cols;sheet.height=tileH*rows;
    const g=sheet.getContext('2d');g.fillStyle='#000';g.fillRect(0,0,sheet.width,sheet.height);g.font=Math.max(14,Math.round(tileW/22))+'px -apple-system, sans-serif';g.textBaseline='bottom';
    for(let i=0;i<count;i++){
      const at=duration?Math.min(duration-.05,(i+.5)/count*duration):0;
      if(count>1||duration){video.currentTime=Math.max(0,at);try{await wait(video,'seeked',9000);}catch(error){}}
      const x=(i%cols)*tileW,y=Math.floor(i/cols)*tileH;g.drawImage(video,x,y,tileW,tileH);
      const tag=(i+1)+' · '+clock(video.currentTime||at);g.fillStyle='rgba(0,0,0,.62)';g.fillRect(x,y+tileH-Math.round(tileW/16),Math.round(tileW/5),Math.round(tileW/16));g.fillStyle='#fff';g.fillText(tag,x+6,y+tileH-4);
    }
    return {image:encode(sheet),frames:count,duration};
  }finally{URL.revokeObjectURL(url);}
}
function show(image,text,note){
  pendingScreenImage=image;$('#attachedScreenThumb').src=image;chip.classList.remove('hidden');
  if(label)label.textContent=note;
  const channel=$('#channel'),agent=(state.agents||[]).find(a=>a.name===channel.value);
  if(channel.value!=='common'&&agent?.connector!=='codex'){channel.value='common';channel.dispatchEvent(new Event('change'));}
  const prompt=$('#prompt');if(!prompt.value.trim()){prompt.value=text;prompt.dispatchEvent(new Event('input'));}
  prompt.focus();
  if(!state.live_chat||!state.integrations_enabled)toast(tr('Görseli yorumlamak için gerçek Codex sohbetini aç.','Turn on the live Codex chat so the image can be read.'));
}
async function attachFile(file){
  if(file.type.startsWith('video/')||/\.(mp4|mov|m4v|webm)$/i.test(file.name)){
    toast(tr('Video kareleri hazırlanıyor…','Preparing video frames…'));
    const sheet=await videoToSheet(file);
    show(sheet.image,tr('Bu videoya bak, kısaca ne olduğunu söyle.','Look at this video and tell me briefly what it is.'),tr(`Video (${sheet.frames} kare özeti${sheet.duration?' · '+clock(sheet.duration):''}) görsel okuyabilen ajana gönderilecek`,`Video (${sheet.frames}-frame summary${sheet.duration?' · '+clock(sheet.duration):''}) will be sent to an image-capable agent`));
    return;
  }
  if(file.type.startsWith('image/')||/\.(jpe?g|png|gif|webp|heic|heif)$/i.test(file.name)){
    const image=await photoToJpeg(file);
    show(image,tr('Bu fotoğrafa bak, kısaca ne olduğunu söyle.','Look at this photo and tell me briefly what it is.'),tr('Fotoğraf görsel okuyabilen seçili ajana gönderilecek','The photo will go to the selected image-capable agent'));
    return;
  }
  throw new Error(tr('Yalnızca fotoğraf ve video eklenebilir.','Only photos and videos can be attached.'));
}
// Drag a file onto the composer, or paste an image into the prompt.
const composer=document.getElementById('composer');
['dragenter','dragover'].forEach(name=>composer.addEventListener(name,e=>{if([...(e.dataTransfer?.types||[])].includes('Files')){e.preventDefault();composer.classList.add('drop-ready');}}));
['dragleave','drop'].forEach(name=>composer.addEventListener(name,()=>composer.classList.remove('drop-ready')));
composer.addEventListener('drop',e=>{const file=e.dataTransfer?.files?.[0];if(!file)return;e.preventDefault();safe(()=>attachFile(file));});
$('#prompt').addEventListener('paste',e=>{const file=[...(e.clipboardData?.files||[])].find(f=>f.type.startsWith('image/')||f.type.startsWith('video/'));if(!file)return;e.preventDefault();safe(()=>attachFile(file));});
// Restore the original chip text once the attachment is cleared (screen shares reuse the same chip).
new MutationObserver(()=>{if(chip.classList.contains('hidden')&&label&&label.textContent!==original)label.textContent=original;}).observe(chip,{attributes:true,attributeFilter:['class']});
window.addEventListener('jarvis-language',setTitle);
})();

// Persistent attachments, document previews and a quiet three-action tools menu.
(()=>{
let pendingDocs=[];const input=$('#attachInput'),attach=$('#attachButton');
input.accept='image/*,video/*,.pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.json,.html,.htm,.rtf,.odt,.ods,.odp,.log,.xml,.yaml,.yml';
attach.title=tr('Fotoğraf veya belge ekle','Attach photo or document');attach.setAttribute('aria-label',attach.title);
const pending=document.createElement('div');pending.className='pending-documents';$('#composer').prepend(pending);
function drawPending(){pending.replaceChildren();for(const d of pendingDocs){const b=document.createElement('button');b.type='button';b.className='attachment-chip';b.textContent='📄 '+d.name+' ×';b.title=tr('Göndermeden kaldır','Remove before sending');b.onclick=()=>{pendingDocs=pendingDocs.filter(x=>x.id!==d.id);drawPending();};pending.append(b);}}
const oldChange=input.onchange;
async function upload(file){
 if(file.size>25*1024*1024)throw new Error(tr('Dosya 25 MB sınırını aşıyor.','The file exceeds 25 MB.'));
 if(pendingDocs.length>=4)throw new Error(tr('En fazla dört belge ekle.','Attach up to four documents.'));
 const chatId=state.active_chat;toast(tr('Belge okunuyor…','Reading document…'));
 const response=await fetch('/upload',{method:'POST',headers:{'X-Jarvis-Token':state.csrf,'X-File-Name':encodeURIComponent(file.name),'X-Chat-Id':chatId},body:file});
 const value=await response.json();if(!response.ok)throw new Error(value.error);
 if(chatId!==state.active_chat)throw new Error(tr('Sohbet değişti; belge gönderilmedi.','The chat changed; the document was not sent.'));
 pendingDocs.push(value.attachment);drawPending();if(!$('#prompt').value.trim())$('#prompt').value=tr('Bu belgeyi kısaca özetle.','Briefly summarize this document.');$('#prompt').focus();
}
function isMedia(f){return /^(image|video)\//.test(f.type)||/\.(jpg|jpeg|png|gif|webp|heic|heif|mp4|mov|m4v|webm)$/i.test(f.name);}
input.onchange=e=>{const file=input.files?.[0];if(!file)return;if(isMedia(file))oldChange(e);else safe(()=>upload(file));};
// Capture document drops before the older media-only drop handler.
$('#composer').addEventListener('drop',e=>{const f=e.dataTransfer?.files?.[0];if(f&&!isMedia(f)){e.preventDefault();e.stopImmediatePropagation();safe(()=>upload(f));}},true);
const oldApi=api;api=async function(action,data={}){if(action==='converse'&&pendingDocs.length)data={...data,docs:pendingDocs.map(d=>d.id)};const value=await oldApi(action,data);if(action==='converse'||action==='new-chat'||action==='select-chat'){pendingDocs=[];drawPending();}return value;};
let pendingChat=null;
async function preview(a){
 const url=a.src||'/attachment/'+encodeURIComponent(a.id);modal(a.name,`<div class="attachment-preview"></div>`);$('#dialog').classList.add('attachment-viewer');const box=$('#dialogBody .attachment-preview');
 if(a.kind==='image'){const image=document.createElement('img');image.src=url;image.alt=a.name;box.append(image);return;}
 const textButton=document.createElement('button');textButton.className='button';textButton.textContent=tr('Metni göster','Show text');box.append(textButton);
 let frame;if(a.mime==='application/pdf'){frame=document.createElement('iframe');frame.src=url;frame.title=a.name;box.append(frame);}
 const pre=document.createElement('pre');pre.className='document-text';box.append(pre);if(frame)pre.hidden=true;
 async function loadText(){const r=await fetch(url+'?text=1');pre.textContent=r.ok?await r.text():tr('Metin alınamadı.','Text unavailable.');}
 textButton.onclick=()=>{if(frame){pre.hidden=!pre.hidden;frame.hidden=!pre.hidden;}else pre.hidden=false;};await loadText();
}
const thumb=$('#attachedScreenThumb');thumb.tabIndex=0;thumb.setAttribute('role','button');thumb.setAttribute('aria-label',tr('Görseli büyüt','Expand image'));thumb.onclick=()=>{const src=pendingScreenImage||thumb.getAttribute('src');if(src)safe(()=>preview({name:tr('Gönderilecek görsel','Image to send'),kind:'image',src}));};thumb.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();thumb.click();}};
const render=renderWorkspace;renderWorkspace=function(){render();if(pendingChat!==state.active_chat){pendingChat=state.active_chat;pendingDocs=[];drawPending();}
 const messages=state.messages.filter(m=>(m.channel||'common')===$('#channel').value);document.querySelectorAll('#messages .message').forEach((row,i)=>{const m=messages[i];if(!m?.attachments?.length||row.querySelector('.message-attachments'))return;const area=document.createElement('div');area.className='message-attachments';for(const a of m.attachments){const b=document.createElement('button');b.type='button';b.className=a.kind==='image'?'attachment-thumbnail':'attachment-chip';b.setAttribute('aria-label',tr('Eki aç: ','Open attachment: ')+a.name);if(a.kind==='image'){const image=document.createElement('img');image.src='/attachment/'+a.id;image.alt=a.name;image.loading='lazy';b.append(image);}else b.textContent='📄 '+a.name+' · '+Math.ceil(a.size/1024)+' KB';b.onclick=()=>safe(()=>preview(a));area.append(b);}row.querySelector('.message-content')?.prepend(area);});
 // JARVIS and EDITH share the Google pool; own Claude Pro is distinct from Antigravity 3p.
 const jarvis=document.querySelector('.agent.jarvis .agent-quota');if(jarvis&&state.jarvis_connector==='gemini'){jarvis.innerHTML=usageMarkup('EDITH');const u=state.provider_usage?.EDITH;if(u?.status==='live')jarvis.closest('.agent').querySelector('.agent-summary').textContent=shortQuotaText(u,'Google');}
 const vision=document.querySelector('.agent[data-agent="VISION"]');document.querySelectorAll('.agent').forEach(card=>{const a=state.agents.find(a=>a.name===card.querySelector('h2')?.textContent);if(a?.connector==='claude_code'){const el=card.querySelector('.agent-quota');if(el){el.innerHTML=usageMarkup('CLAUDE_PRO');const cu=state.provider_usage?.CLAUDE_PRO;if(cu?.status==='live')el.title=(cu.scope||'Claude Pro')+' · '+(cu.checked_at?new Date(cu.checked_at*1000).toLocaleString():'');else el.title=cu?.message||tr('Saatte bir /usage denenir.','Checks /usage hourly.');}const summary=card.querySelector('.agent-summary'),u=state.provider_usage?.CLAUDE_PRO;if(summary&&u?.status==='live')summary.textContent=shortQuotaText(u,'Claude Pro');}});
};
const main=document.createElement('div');main.className='tools-main';const advanced=document.createElement('details');advanced.className='tools-advanced';const summary=document.createElement('summary');summary.textContent=tr('Gelişmiş araçlar','Advanced tools');advanced.append(summary);const auto=document.createElement('p');auto.className='tools-auto';auto.textContent=tr('JARVIS isteğine göre araştırır, planlar ve gerekli ajanı çağırır. Bilgisayar kontrolü için ayrıca onay ister.','JARVIS researches, plans and calls the relevant agent for your request. Computer control needs separate approval.');
const photo=document.createElement('button');photo.className='button';photo.textContent=tr('Fotoğraf / belge ekle','Attach photo / document');photo.onclick=()=>attach.click();main.append(photo,chooseFromChat,$('#shareScreenFromChat'));
const body=tools.querySelector('.tool-actions');if(body){for(const child of [...body.children])advanced.append(child);body.replaceChildren(main,auto,advanced);}
// Move explanatory screen and handoff blocks beneath the advanced disclosure too.
for(const node of [...tools.children])if(!node.classList.contains('panel-head')&&!node.classList.contains('tools-heading')&&node!==body&&!node.contains(body))advanced.append(node);
})();
