"""Local-only Ollama adapter. No API keys, cloud models or silent remote fallback."""
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from memory_guard import model_memory_lock

MODEL='gemma3:4b'
ALLOWED_MODELS={'gemma3:4b','qwen3.5:4b-q4_K_M'}
PORT=11435
ROOT=Path(__file__).resolve().parent

class LocalEngine:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.model=MODEL
        self.process=None
        self.lock=threading.Lock()
    def configure(self,model):
        if model not in ALLOWED_MODELS:raise ValueError('Desteklenmeyen yerel model.')
        self.model=model
    def binary(self):
        for item in (ROOT.parent/'ollama/ollama',ROOT/'runtime/ollama'):
            if item.is_file():return item
        return None
    def installed(self):
        return (self.directory/'local-models/manifests/registry.ollama.ai/library'/self.model.replace(':','/')).is_file()
    def status(self):
        value={'installed':self.installed(),'runtime':bool(self.binary()),'model':self.model,'cost':'local','context':2048,'loaded':False,'memory_bytes':0}
        connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=.2)
        try:
            connection.request('GET','/api/ps');response=connection.getresponse()
            if response.status==200:
                model=next((m for m in json.loads(response.read()).get('models',[]) if m.get('name')==self.model),None)
                if model:value.update(loaded=True,memory_bytes=model.get('size_vram',model.get('size',0)))
        except (OSError,ValueError):pass
        finally:connection.close()
        return value
    def probe(self):
        connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=.5)
        try:
            connection.request('GET','/api/tags');response=connection.getresponse()
            if response.status!=200:return False
            return any(x.get('name')==self.model for x in json.loads(response.read()).get('models',[]))
        except (OSError,ValueError):return False
        finally:connection.close()
    def start(self):
        with self.lock:
            if self.probe():return
            binary=self.binary()
            if not binary or not self.installed():raise ValueError('Yerel model henüz kurulu değil. Otomatik bulut geçişi yapılmadı; Ayarlar’dan model durumunu kontrol et.')
            env=os.environ.copy()
            for key in list(env):
                if 'API_KEY' in key:env.pop(key,None)
            env.update(OLLAMA_HOST=f'127.0.0.1:{PORT}',OLLAMA_MODELS=str(self.directory/'local-models'),OLLAMA_NO_CLOUD='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_CONTEXT_LENGTH='2048',OLLAMA_KEEP_ALIVE='30s')
            self.process=subprocess.Popen([str(binary),'serve'],env=env,cwd=self.directory,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            until=time.monotonic()+15
            while time.monotonic()<until:
                if self.probe():return
                if self.process.poll() is not None and not self.probe():raise ValueError('Yerel model servisi başlatılamadı. Buluta geçilmedi.')
                time.sleep(.15)
            raise ValueError('Yerel model başlatma süresi doldu. Buluta geçilmedi.')
    def warm(self):
        with model_memory_lock(self.directory,timeout=20):return self._warm()
    def _warm(self):
        self.start()
        connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=20)
        try:
            connection.request('POST','/api/generate',json.dumps({'model':self.model,'prompt':'','stream':False,'keep_alive':'30s','options':{'num_ctx':2048}}),{'Content-Type':'application/json'})
            response=connection.getresponse();response.read()
        finally:connection.close()
    def run(self,messages,on_delta,cancelled):
        with model_memory_lock(self.directory,cancelled):return self._run(messages,on_delta,cancelled)
    def _run(self,messages,on_delta,cancelled):
        self.start()
        connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=60)
        finished=threading.Event()
        def watch():
            while not finished.wait(.2):
                if cancelled.is_set():
                    try:
                        if connection.sock:connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                    return
        try:
            payload={'model':self.model,'messages':messages,'think':False,'stream':True,'keep_alive':'30s','options':{'num_ctx':2048,'num_predict':200,'temperature':.7,'top_p':.8,'top_k':20,'repeat_penalty':1.0}}
            if not self.model.startswith('qwen'):payload.pop('think',None)
            connection.request('POST','/api/chat',json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
            threading.Thread(target=watch,daemon=True).start()
            response=connection.getresponse()
            if response.status!=200:raise ValueError('Yerel model yanıtı alınamadı. Bulut modeli çağrılmadı.')
            text=''
            while not cancelled.is_set():
                line=response.readline()
                if not line:break
                value=json.loads(line)
                if value.get('error'):raise ValueError(str(value['error'])[:300])
                fragment=value.get('message',{}).get('content','')
                if fragment:text+=fragment;on_delta(fragment)
                if value.get('done'):return text
            raise ValueError('Yerel yanıt durduruldu.')
        finally:finished.set();connection.close()
    def unload(self):
        if not self.probe():return
        connection=http.client.HTTPConnection('127.0.0.1',PORT,timeout=10)
        try:
            connection.request('POST','/api/generate',json.dumps({'model':self.model,'keep_alive':0}),{'Content-Type':'application/json'})
            response=connection.getresponse();response.read()
        finally:connection.close()
    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
