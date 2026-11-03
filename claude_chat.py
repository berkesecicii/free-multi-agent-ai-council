"""Official Claude Code CLI; subscription sign-in only, no API-key fallback."""
import json,os,selectors,shutil,subprocess,sys,time
from pathlib import Path

def binary():
    choices=[Path.home()/'Library/Application Support/BerkeJARVIS/cli/claude',Path.home()/'.local/bin/claude',Path('/opt/homebrew/bin/claude'),Path('/usr/local/bin/claude')]
    return next((str(p) for p in choices if p.is_file() and os.access(p,os.X_OK)),shutil.which('claude'))

def environment():
    return {k:v for k,v in os.environ.items() if not k.startswith(('ANTHROPIC_','CLAUDE_CODE_OAUTH_TOKEN','CLAUDE_CODE_USE_','CLAUDE_CODE_API_KEY_HELPER')) and 'API_KEY' not in k}

def status():
    exe=binary()
    if not exe:return {'installed':False,'signed_in':False}
    try:
        p=subprocess.run([exe,'auth','status'],capture_output=True,text=True,env=environment(),timeout=12)
        value=json.loads(p.stdout)
        return {'installed':True,'signed_in':bool(value.get('loggedIn')) and value.get('authMethod')=='claude.ai','auth_method':value.get('authMethod','none'),'plan':value.get('subscriptionType') or 'unknown'}
    except Exception:return {'installed':True,'signed_in':False,'error':'Claude oturumu okunamadı.'}

class ClaudeConversation:
    def __init__(self,directory,delta,cancelled,model='sonnet'):
        self.directory=directory;self.delta=delta;self.cancelled=cancelled;self.model=model;self.process=None
        self.effort='low';self.tool_endpoint=None;self.tool_token=None
    def run(self,prompt,image=None):
        if image:raise ValueError('Bu Claude Code bağlantısında görsel aktarımı henüz yok.')
        account=status()
        if not account.get('signed_in'):raise ValueError('Claude Code abonelik girişi gerekli. Ayarlar → Claude hesabı → Giriş yap. API anahtarına geçilmedi.')
        env=environment();env['CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC']='1'
        args=[binary(),'--restricted','--setting-sources','','--settings',json.dumps({'disableAllHooks':True,'autoMemoryEnabled':False}),'--disable-slash-commands','--no-chrome','--no-session-persistence','--tools','','--permission-prompts','none','--model',self.model,'--effort',self.effort or 'low','--output-format','json','--max-turns','8' if self.tool_endpoint else '1']
        if self.tool_endpoint:
            env.update(JARVIS_CLAUDE_TOOL_ENDPOINT=self.tool_endpoint,JARVIS_CLAUDE_TOOL_TOKEN=self.tool_token)
            config={'mcpServers':{'jarvis_project':{'command':sys.executable,'args':['-B',str(Path(__file__).with_name('claude_project_mcp.py'))],'env':{'JARVIS_CLAUDE_TOOL_ENDPOINT':self.tool_endpoint,'JARVIS_CLAUDE_TOOL_TOKEN':self.tool_token,'JARVIS_DESKTOP_TOOLS':'1' if getattr(self,'desktop_tools',False) else '0','JARVIS_PROJECT_TOOLS':'1' if getattr(self,'project_tools',True) else '0'}}}}
            args+=['--strict-mcp-config','--mcp-config',json.dumps(config),'--allowedTools',','.join('mcp__jarvis_project__'+name for name in ((['project_list','project_read','project_edit'] if getattr(self,'project_tools',True) else [])+(['desktop_observe','desktop_click','desktop_type','desktop_key','desktop_scroll','desktop_open_url'] if getattr(self,'desktop_tools',False) else [])))]
        else:args+=['--safe-mode','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--disallowedTools','*']
        args+=['-p',prompt]
        self.process=subprocess.Popen(args,cwd=self.directory,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        selector=selectors.DefaultSelector();selector.register(self.process.stdout,selectors.EVENT_READ);data=bytearray();deadline=time.monotonic()+(650 if self.tool_endpoint else 100)
        try:
            while True:
                if self.cancelled.is_set():raise ValueError('Claude işi durduruldu.')
                if time.monotonic()>deadline:raise ValueError('Claude süresi doldu; otomatik tekrar yapılmadı.')
                if selector.select(.2):
                    chunk=os.read(self.process.stdout.fileno(),65536)
                    if not chunk:break
                    data.extend(chunk)
                    if len(data)>2000000:raise ValueError('Claude çıktı sınırı aşıldı.')
                elif self.process.poll() is not None:break
            try:value=json.loads(data)
            except ValueError:raise ValueError('Claude yanıtı alınamadı. Resmî oturumu kontrol et; API anahtarına geçilmedi.')
            if value.get('is_error') or value.get('subtype') not in ('success',None):raise ValueError(str(value.get('result') or value.get('errors') or 'Claude işi tamamlanmadı.')[:700])
            usage=value.get('usage') or {}
            if isinstance(usage.get('input_tokens'),int) and isinstance(usage.get('output_tokens'),int):
                self.token_usage={'input':usage['input_tokens']+usage.get('cache_read_input_tokens',0)+usage.get('cache_creation_input_tokens',0),'output':usage['output_tokens'],'cached_input':usage.get('cache_read_input_tokens',0)}
            answer=value.get('result','')
            if not answer:raise ValueError('Claude boş yanıt verdi.')
            self.delta(answer);return answer
        finally:selector.close();self.close()
    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
