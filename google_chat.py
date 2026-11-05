"""Official Antigravity CLI adapter using the user's vendor-managed sign-in.
No keys, no credential reads, no automatic billing, no model tool permissions.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import selectors
import shutil
import subprocess
import time

DEFAULT_MODEL='gemini-3.8-flash-low'
DENIED=['read_file(*)','write_file(*)','command(*)','mcp(*)','read_url(*)','execute_url(*)']

def binary():
    choices=[shutil.which('agy'),Path.home()/'Library/Application Support/BerkeJARVIS/integrations/bin/agy',Path.home()/'.local/bin/agy']
    return next((str(p) for p in choices if p and Path(p).is_file() and os.access(p,os.X_OK)),None)

def available():return bool(binary())

def summarize(event):
    # One short line per CLI event (names only, no user text) so a failed picture test can be diagnosed.
    step=event.get('step_update') or {}
    bits=[str(event.get('event'))]+[str(step[k]) for k in ('step_type','state','tool_name') if step.get(k)]
    for source in (step,event.get('result') or {},event):
        for key in ('error','status'):
            if isinstance(source.get(key),(str,int)) and source.get(key):bits.append(key+'='+str(source[key])[:60]);break
    return '/'.join(bits)

class GoogleConversation:
    def __init__(self,directory,on_delta,cancelled,model=DEFAULT_MODEL):
        self.directory=Path(directory)/'google-chat-workspace'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.on_delta=on_delta;self.cancelled=cancelled;self.model=model;self.process=None
    def save_attachment(self,image):
        # The CLI has no image flag in print mode; it looks at a picture through its file tool. The picture is written to this
        # private workspace (nothing else lives here), read-allowed for that one file, and deleted when the turn ends.
        if not isinstance(image,str) or not image.startswith('data:image/jpeg;base64,'):raise ValueError('Geçerli bir JPEG görsel gerekli.')
        raw=base64.b64decode(image.split(',',1)[1],validate=True)
        if not raw.startswith(b'\xff\xd8'):raise ValueError('Görsel verisi geçersiz.')
        for old in self.directory.glob('attachment-*.jpg'):
            try:
                if time.time()-old.stat().st_mtime>600:old.unlink()
            except OSError:pass
        path=self.directory/('attachment-'+secrets.token_hex(4)+'.jpg')
        path.write_bytes(raw);os.chmod(path,0o600)
        return path
    def run(self,prompt,image=None):
        attachment=None
        try:
            if image:attachment=self.save_attachment(image)
            return self._run(prompt,attachment)
        finally:
            if attachment:
                try:attachment.unlink()
                except OSError:pass
    def _run(self,prompt,attachment=None):
        executable=binary()
        if not executable:raise ValueError('Resmi Antigravity CLI kurulu değil. API anahtarına geçilmedi.')
        if attachment:prompt='The user attached a picture, saved as ./'+attachment.name+' in the current workspace. Open that one file with your file-reading tool and actually look at the picture before you answer. Never open any other file. If you cannot see the picture, say so plainly instead of guessing.\n\n'+prompt
        env={k:v for k,v in os.environ.items() if 'API_KEY' not in k and not k.startswith(('ANTHROPIC_','GOOGLE_CLOUD_PROJECT','GOOGLE_APPLICATION_CREDENTIALS','VERTEX_'))}
        research=bool(getattr(self,'web_research',False))
        stream=research or bool(attachment)
        mode=getattr(self,'picture_mode','review')  # how the CLI is allowed to open the picture: review | strict | open
        allow=(['read_url(*)'] if research else [])+(['read_file('+str(attachment)+')'] if attachment and mode!='open' else [])
        settings={'useG1Credits':False,'toolPermission':'request-review' if research or (attachment and mode=='review') else 'strict','permissions':{'deny':[d for d in DENIED if (not research or d!='read_url(*)') and (not attachment or d!='read_file(*)')],'allow':allow,'ask':[]}}
        args=[executable,'--model',self.model,'--sandbox','--settings',json.dumps(settings),'--disable-slash-commands','--print-timeout','90s','--output-format','stream-json' if stream else 'json','-p',prompt]
        if getattr(self,'effort',None):args[1:1]=['--effort',self.effort]
        self.process=subprocess.Popen(args,cwd=self.directory,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        selector=selectors.DefaultSelector();selector.register(self.process.stdout,selectors.EVENT_READ)
        output=bytearray();event_buffer=bytearray();seen_tools=set();deadline=time.monotonic()+100
        try:
            while True:
                if self.cancelled.is_set():raise ValueError('Antigravity yanıtı durduruldu.')
                if time.monotonic()>deadline:raise ValueError('Antigravity yanıt süresi doldu. Otomatik tekrar yapılmadı.')
                if selector.select(.2):
                    chunk=os.read(self.process.stdout.fileno(),65536)
                    if not chunk:break
                    output.extend(chunk)
                    if stream:
                        event_buffer.extend(chunk)
                        while b'\n' in event_buffer:
                            line,_,rest=event_buffer.partition(b'\n');event_buffer=bytearray(rest)
                            try:event=json.loads(line)
                            except ValueError:continue
                            step=event.get('step_update') or {}
                            signature=(step.get('step_index'),step.get('state'),step.get('tool_name'))
                            if step.get('step_type')=='tool' and step.get('state') in ('ACTIVE','RUNNING','DONE') and signature not in seen_tools:
                                seen_tools.add(signature)
                                if getattr(self,'activity',None):self.activity(step.get('tool_name','web'),json.dumps(dict(state=step.get('state'),parameters=(step.get('tool_info') or {}).get('parameters',{})),ensure_ascii=False)[:1000])
                    if len(output)>2000000:raise ValueError('Antigravity yanıt boyutu sınırı aşıldı.')
                elif self.process.poll() is not None:break
            try:
                self.tools_used=[];self.debug=''
                if stream:
                    events=[json.loads(line) for line in output.splitlines() if line.strip().startswith(b'{')]
                    self.debug=' | '.join(summarize(e) for e in events[:16])[:700]
                    value=next((e['result'] for e in reversed(events) if e.get('event')=='result'),{})
                    for event in events:
                        step=event.get('step_update') or {}
                        if step.get('step_type')=='tool' and step.get('state')=='DONE':
                            self.tools_used.append(step.get('tool_name','tool'))

                else:value=json.loads(output)
            except ValueError:raise ValueError('Antigravity yanıtı alınamadı. Resmi uygulamadaki oturumunu kontrol et; API anahtarına geçilmedi.')
            if value.get('status')!='SUCCESS':raise ValueError('Antigravity görevi tamamlanamadı. Resmi oturum/kota durumunu kontrol et; başka modele geçilmedi.')
            usage=value.get('usage') or value.get('usageMetadata') or {}
            if isinstance(usage,dict):
                incoming=usage.get('input_tokens',usage.get('promptTokenCount'));outgoing=usage.get('output_tokens',usage.get('candidatesTokenCount'))
                if isinstance(incoming,int) and isinstance(outgoing,int):self.token_usage={'input':incoming,'output':outgoing,'cached_input':usage.get('cachedContentTokenCount',0)}
            answer=value.get('response','').strip()
            if not answer:raise ValueError('Antigravity boş yanıt döndürdü.')
            self.on_delta(answer)
            return answer
        finally:selector.close();self.close()
    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
            if self.process.stdout:self.process.stdout.close()
