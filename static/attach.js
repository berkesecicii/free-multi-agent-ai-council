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
    show(sheet.image,tr('Bu videoya bak, kısaca ne olduğunu söyle.','Look at this video and tell me briefly what it is.'),tr(`Video (${sheet.frames} kare özeti${sheet.duration?' · '+clock(sheet.duration):''}) FRIDAY’e (ChatGPT) gönderilecek`,`Video (${sheet.frames}-frame summary${sheet.duration?' · '+clock(sheet.duration):''}) will be sent to FRIDAY (ChatGPT)`));
    return;
  }
  if(file.type.startsWith('image/')||/\.(jpe?g|png|gif|webp|heic|heif)$/i.test(file.name)){
    const image=await photoToJpeg(file);
    show(image,tr('Bu fotoğrafa bak, kısaca ne olduğunu söyle.','Look at this photo and tell me briefly what it is.'),tr('Bu fotoğraf FRIDAY’e (ChatGPT) gönderilecek','This photo will be sent to FRIDAY (ChatGPT)'));
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
