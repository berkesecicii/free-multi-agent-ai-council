"""Opt-in OpenRouter FREE router. No paid model or fallback accepted."""
import json
import subprocess
import threading
import urllib.request
import urllib.error

def key():
    p=subprocess.run(['/usr/bin/security','find-generic-password','-s','BerkeJARVIS.OpenRouter','-a','api-key','-w'],capture_output=True,text=True,timeout=8)
    return p.stdout.strip() if p.returncode==0 else ''

def has_key():return bool(key())

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class FreeConversation:
    def __init__(self,delta,cancelled,model='openrouter/free'):
        if model!='openrouter/free' and not (isinstance(model,str) and model.endswith(':free')):raise ValueError('Ücretli OpenRouter modeli reddedildi.')
        self.delta=delta;self.cancelled=cancelled;self.model=model
    def run(self,prompt):
        credential=key()
        if not credential:raise ValueError('OpenRouter anahtarı eklenmemiş.')
        payload={'model':self.model,'messages':[{'role':'user','content':prompt[-20000:]}],'max_tokens':700,'stream':True,'provider':{'max_price':{'prompt':0,'completion':0}}}
        request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+credential,'Content-Type':'application/json'})
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=30) as response:
                watchdog=threading.Thread(target=self._close_on_cancel,args=(response,),daemon=True);watchdog.start()
                parts=[]
                for line in response:
                    if self.cancelled.is_set():raise ValueError('Yanıt durduruldu.')
                    if not line.startswith(b'data: '):continue
                    value=line[6:].strip()
                    if value==b'[DONE]':break
                    item=json.loads(value)
                    if item.get('error'):raise ValueError('Ücretsiz sağlayıcı yanıtı tamamlayamadı; ücretli modele geçilmedi.')
                    piece=((item.get('choices') or [{}])[0].get('delta') or {}).get('content') or ''
                    if piece:parts.append(piece);self.delta(piece)
                return ''.join(parts)
        except urllib.error.HTTPError as error:
            raise ValueError('OpenRouter bağlantısı başarısız ('+str(error.code)+'). Ücretsiz kota veya anahtarı kontrol et. Ücretli modele geçilmedi.') from None
        finally:self.finished=True
    def _close_on_cancel(self,response):
        while not getattr(self,'finished',False):
            if self.cancelled.wait(.25):response.close();return
