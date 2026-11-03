"""Read-only official CLI account telemetry. Never starts a model turn or consumes credits."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

CODEX_APP = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'

def codex_binary():
    found = shutil.which('codex')
    for path in (found, CODEX_APP, '/opt/homebrew/bin/codex', '/usr/local/bin/codex'):
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return path
    return None

def inventory():
    return {'antigravity_app': Path('/Applications/Antigravity.app').exists(), 'antigravity_cli': bool(shutil.which('agy')), 'codex_installed': bool(codex_binary()), 'gemini_installed': bool(shutil.which('gemini') or Path('/opt/homebrew/bin/gemini').exists() or Path('/usr/local/bin/gemini').exists())}

def window(value):
    if not isinstance(value, dict):
        return None
    percent = value.get('usedPercent')
    duration = value.get('windowDurationMins')
    reset = value.get('resetsAt')
    return dict(used_percent=percent if isinstance(percent,(int,float)) else None, minutes=duration if isinstance(duration,(int,float)) else None, resets_at=reset if isinstance(reset,(int,float)) else None)

def read_codex_limits(timeout=18, cancelled=None):
    binary = codex_binary()
    if not binary:
        raise ValueError('Codex CLI kurulu değil.')
    env = os.environ.copy()
    # Never fall through to a paid API key inherited from the launching shell.
    for key in list(env):
        if 'API_KEY' in key or key.startswith('ANTHROPIC_'):
            env.pop(key,None)
    process = subprocess.Popen([binary,'app-server','--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=False, env=env)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout,selectors.EVENT_READ)
    buffer = b''
    deadline = time.monotonic()+timeout
    def send(data):
        process.stdin.write(json.dumps(data).encode()+b'\n');process.stdin.flush()
    def rpc(i,method,params=None):
        nonlocal buffer
        send({'id':i,'method':method,'params':params or {}})
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled.is_set():raise ValueError('Kota izleme durduruldu.')
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                try: message=json.loads(line)
                except (ValueError,UnicodeDecodeError): continue
                if message.get('id') == i and 'method' not in message:
                    if 'error' in message:
                        raise ValueError('Codex resmi durum sorgusu başarısız: '+str(message['error'].get('message','Bilinmeyen hata'))[:300])
                    return message.get('result',{})
                # Refuse all unexpected server requests. This client has no execution tools.
                if 'id' in message and 'method' in message:
                    send({'id':message['id'],'error':{'code':-32601,'message':'Telemetry-only client; no tool or auth-token access'}})
            if process.poll() is not None:
                raise ValueError('Codex durum servisi kapandı. Resmi CLI oturumunu kontrol et.')
            ready=selector.select(timeout=min(0.5,max(0,deadline-time.monotonic())))
            if ready:
                chunk=os.read(process.stdout.fileno(),65536)
                if not chunk: raise ValueError('Codex durum bağlantısı kesildi.')
                buffer+=chunk
        raise ValueError('Codex durum sorgusu zaman aşımına uğradı; son değer güncel sayılmaz.')
    try:
        rpc(1,'initialize',{'clientInfo':{'name':'berke_jarvis','title':'Berke JARVIS','version':'0.2.0'}})
        send({'method':'initialized','params':{}})
        account=rpc(2,'account/read',{'refreshToken':False}).get('account')
        if not account or account.get('type') not in ('chatgpt','chatgptAuthTokens'):
            raise ValueError('ChatGPT abonelik oturumu doğrulanamadı. API anahtarına geçiş yapılmadı.')
        limits=rpc(3,'account/rateLimits/read')
        value=(limits.get('rateLimitsByLimitId') or {}).get('codex') or limits.get('rateLimits')
        if not isinstance(value,dict):
            value=(limits.get('rateLimitsByLimitId') or {}).get('codex',{})
        return dict(status='live',source='Resmi Codex app-server · account/rateLimits/read',scope='Codex abonelik kotası; genel ChatGPT sohbet kotası değildir.',plan=account.get('planType','unknown'),checked_at=time.time(),primary=window(value.get('primary')),secondary=window(value.get('secondary')))
    finally:
        selector.close()
        if process.stdin: process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=3)
        if process.stdout: process.stdout.close()

def read_google_limits(timeout=18,cancelled=None):
    """Static official /usage command. Reject any response that ran a model turn."""
    from datetime import datetime
    from google_chat import binary,DENIED
    executable=binary()
    if not executable:raise ValueError('Antigravity CLI kurulu değil.')
    settings={'useG1Credits':False,'toolPermission':'strict','permissions':{'deny':DENIED,'allow':[],'ask':[]}}
    env={k:v for k,v in os.environ.items() if 'API_KEY' not in k and not k.startswith(('ANTHROPIC_','GOOGLE_CLOUD_PROJECT','GOOGLE_APPLICATION_CREDENTIALS','VERTEX_'))}
    process=subprocess.Popen([executable,'--settings',json.dumps(settings),'--print-timeout','15s','--output-format','json','-p','/usage'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,text=True)
    deadline=time.monotonic()+timeout
    try:
        while True:
            if cancelled is not None and cancelled.is_set():raise ValueError('Antigravity kota kontrolü durduruldu.')
            if time.monotonic()>deadline:raise ValueError('Antigravity kota kontrolü zaman aşımına uğradı.')
            try:output,_=process.communicate(timeout=min(.3,max(.01,deadline-time.monotonic())));break
            except subprocess.TimeoutExpired:continue
        if process.returncode!=0 or len(output)>2000000:raise ValueError('Antigravity resmi kota komutu başarısız.')
        value=json.loads(output)
        command=value.get('command',{})
        if command.get('name')!='usage' or value.get('num_turns')!=0:raise ValueError('Antigravity kota komutu salt durum yanıtı olarak doğrulanamadı.')
        groups=command.get('data',{}).get('groups',[]);result={}
        for agent,group_id in (('EDITH','gemini-weekly'),('VISION','3p-weekly')):
            bucket=next((b for group in groups for b in group.get('buckets',[]) if b.get('id')==group_id),None)
            if not bucket:continue
            fraction=bucket.get('remaining_fraction')
            if not isinstance(fraction,(int,float)) or not 0<=fraction<=1:raise ValueError('Geçersiz Antigravity kota değeri.')
            reset=bucket.get('reset_time');reset_at=None
            try:reset_at=datetime.fromisoformat(reset.replace('Z','+00:00')).timestamp() if reset else None
            except ValueError:pass
            result[agent]=dict(status='live',source='Resmi Antigravity CLI · /usage',scope='Antigravity Gemini ortak haftalık grubu' if agent=='EDITH' else 'Antigravity Claude ve GPT ortak haftalık grubu; ayrı Claude hesabı değil.',plan='Google',checked_at=time.time(),primary=dict(used_percent=100*(1-fraction),minutes=10080,resets_at=reset_at),secondary=None)
        if len(result)!=2:raise ValueError('Antigravity kota grupları eksik.')
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
        if process.stdout:process.stdout.close()
