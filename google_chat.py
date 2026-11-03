"""Official Antigravity CLI adapter using the user's vendor-managed sign-in.
No keys, no credential reads, no automatic billing, no model tool permissions.
"""
import json
import os
from pathlib import Path
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

class GoogleConversation:
    def __init__(self,directory,on_delta,cancelled,model=DEFAULT_MODEL):
        self.directory=Path(directory)/'google-chat-workspace'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.on_delta=on_delta;self.cancelled=cancelled;self.model=model;self.process=None
    def run(self,prompt,image=None):
        if image:raise ValueError('Antigravity metin bağlantısına bu sürümde ekran gönderilmez. Codex seçebilirsin.')
        executable=binary()
        if not executable:raise ValueError('Resmi Antigravity CLI kurulu değil. API anahtarına geçilmedi.')
        env={k:v for k,v in os.environ.items() if 'API_KEY' not in k and not k.startswith(('ANTHROPIC_','GOOGLE_CLOUD_PROJECT','GOOGLE_APPLICATION_CREDENTIALS','VERTEX_'))}
        research=bool(getattr(self,'web_research',False))
        settings={'useG1Credits':False,'toolPermission':'request-review' if research else 'strict','permissions':{'deny':[d for d in DENIED if not research or d!='read_url(*)'],'allow':['read_url(*)'] if research else [],'ask':[]}}
        args=[executable,'--model',self.model,'--sandbox','--settings',json.dumps(settings),'--disable-slash-commands','--print-timeout','90s','--output-format','stream-json' if research else 'json','-p',prompt]
        if getattr(self,'effort',None):args[1:1]=['--effort',self.effort]
        self.process=subprocess.Popen(args,cwd=self.directory,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        selector=selectors.DefaultSelector();selector.register(self.process.stdout,selectors.EVENT_READ)
        output=bytearray();deadline=time.monotonic()+100
        try:
            while True:
                if self.cancelled.is_set():raise ValueError('Antigravity yanıtı durduruldu.')
                if time.monotonic()>deadline:raise ValueError('Antigravity yanıt süresi doldu. Otomatik tekrar yapılmadı.')
                if selector.select(.2):
                    chunk=os.read(self.process.stdout.fileno(),65536)
                    if not chunk:break
                    output.extend(chunk)
                    if len(output)>2000000:raise ValueError('Antigravity yanıt boyutu sınırı aşıldı.')
                elif self.process.poll() is not None:break
            try:
                if research:
                    events=[json.loads(line) for line in output.splitlines() if line.strip().startswith(b'{')]
                    value=next((e['result'] for e in reversed(events) if e.get('event')=='result'),{})
                    for event in events:
                        step=event.get('step_update') or {}
                        if step.get('step_type')=='tool' and step.get('state')=='DONE' and getattr(self,'activity',None):self.activity(step.get('tool_name','web'),str((step.get('tool_info') or {}).get('parameters',{}))[:400])
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
