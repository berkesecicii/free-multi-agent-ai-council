"""Official model discovery. No inference, credentials or paid API calls."""
import json,os,re,subprocess,threading,time,urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import re as _re
_FLASH=_re.compile(r'^(gemini-3\.8-flash)-(low|medium|high)$')

def escalate_model(model,available,planning=False,web_research=False):
    """Cheapest thinking tier by default; one step up (medium) only for planning or live research
    and only if the catalog offers it. Never goes to high automatically and never downgrades a user choice."""
    m=_FLASH.match(model or '')
    if m and m.group(2)=='low' and (planning or web_research):
        candidate=m.group(1)+'-medium'
        if candidate in available:return candidate
    return model

_THINK=('neden','nasıl','nasil','analiz','karşılaştır','karsilastir','planla','strateji','tasarla','mimari','değerlendir','degerlendir','öner','oner','why','explain','compare','analy','plan ','design','architect','review','debug','hata','optimi','karar')
def coordinator_tier(text,planning=False,delegation=False):
    """JARVIS thinking depth per message: high for planning, delegation or long briefs,
    low for short small talk, medium for everything in between."""
    t=(text or '').strip()
    if planning or delegation or len(t)>280:return 'high'
    if len(t)<=80 and '\n' not in t and not any(w in t.casefold() for w in _THINK):return 'low'
    return 'medium'

def with_tier(model,tier,available):
    """Switch a gemini-3.8-flash-* model id to the wanted tier if the catalog offers it; otherwise the nearest lower one."""
    m=_FLASH.match(model or '')
    if not m:return model
    order=['low','medium','high']
    for t in order[:order.index(tier)+1][::-1]:
        candidate=m.group(1)+'-'+t
        if candidate in available:return candidate
    return model

def cheapest_flash(model):
    """One-time cost migration helper: Flash medium/high saved settings fall back to low."""
    m=_FLASH.match(model or '')
    return m.group(1)+'-low' if m and m.group(2)!='low' else model

DEFAULTS={'claude_code':'sonnet','codex':'','gemini':'gemini-3.8-flash-low','claude_google':'claude-sonnet-4-6','local':'gemma3:4b','openrouter':'openrouter/free','manual':''}

def bundled_catalog():
    try:return json.loads(Path(__file__).with_name('model-catalog.json').read_text())
    except (OSError,ValueError):return {k:[{'id':v,'name':v or 'Provider default'}] for k,v in DEFAULTS.items()}

def discover():
    from google_chat import binary
    from codex_chat import CodexConversation
    result={};errors={}
    def codex():
        c=CodexConversation(str(Path.home()/'Library/Application Support/BerkeJARVIS'),lambda _:None,threading.Event())
        try:
            c.rpc('initialize',{'clientInfo':{'name':'jarvis_model_catalog','version':'0.6'}});c.send({'method':'initialized','params':{}})
            models=[];cursor=None
            for _ in range(5):
                page=c.rpc('model/list',{'limit':100,**({'cursor':cursor} if cursor else {})})
                models.extend({'id':m['id'],'name':m.get('displayName',m['id']),'default':bool(m.get('isDefault')),'efforts':[r['reasoningEffort'] for r in m.get('supportedReasoningEfforts',[]) if r['reasoningEffort']!='ultra']} for m in page.get('data',[]));cursor=page.get('nextCursor')
                if not cursor:break
            if not models:raise ValueError('Codex model listesi boş.')
            return models
        finally:c.close()
    def google():
        executable=binary()
        if not executable:raise ValueError('Antigravity CLI bulunamadı.')
        env={k:v for k,v in os.environ.items() if 'API_KEY' not in k and not k.startswith(('ANTHROPIC_','VERTEX_','GOOGLE_APPLICATION_CREDENTIALS'))}
        p=subprocess.run([executable,'models'],capture_output=True,text=True,timeout=20,env=env)
        models=[]
        if p.returncode:raise ValueError('Antigravity model listesi alınamadı.')
        for line in p.stdout.splitlines():
            parts=line.split('\t',1)
            if re.fullmatch(r'[a-z][a-z0-9._-]+',parts[0]):models.append({'id':parts[0],'name':parts[-1]})
        if not models:raise ValueError('Antigravity model listesi boş.')
        return models
    def free():
        with urllib.request.urlopen('https://openrouter.ai/api/v1/models',timeout=15) as r:models=json.load(r).get('data',[])
        return [{'id':'openrouter/free','name':'Free router · ücretsiz modeller'}]+[{'id':m['id'],'name':m.get('name',m['id'])} for m in models if m.get('id','').endswith(':free') and all(str(m.get('pricing',{}).get(k,'1')) in ('0','0.0') for k in ('prompt','completion'))][:50]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={key:pool.submit(fn) for key,fn in [('codex',codex),('google',google),('openrouter',free)]}
        for key,f in futures.items():
            try:result[key]=f.result()
            except Exception as error:errors[key]=str(error)[:180]
    if 'google' in result:
        result['gemini']=[m for m in result['google'] if not m['id'].startswith('claude')]
        result['claude_google']=[m for m in result.pop('google') if m['id'].startswith('claude')]
    result['local']=[{'id':'gemma3:4b','name':'Gemma 3 · bu Mac'},{'id':'qwen3.5:4b-q4_K_M','name':'Qwen 3.5 · bu Mac'}]
    result['manual']=[{'id':'','name':'Manuel aktarım'}]
    return result,errors
