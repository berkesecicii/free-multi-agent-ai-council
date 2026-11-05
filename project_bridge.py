"""Bounded project tools. Reads stay in the chosen root; every edit/test waits for approval."""
import difflib,hashlib,json,os,re,time,uuid
from pathlib import Path

SKIP={'.git','.env','.ssh','.aws','.venv','venv','node_modules','__pycache__','.DS_Store'}
def spec(name,description,properties,required):return dict(type='function',name=name,description=description,inputSchema=dict(type='object',properties=properties,required=required,additionalProperties=False))
TOOLS=[spec('project_list','List text file paths in the user-selected project.',{},[]),spec('project_read','Read one UTF-8 file from the selected project.',{'path':{'type':'string'}},['path']),spec('project_edit','Propose complete new text for one file. Waits for Berke approval; returns whether it was actually saved. Never claim saved before success.',{'path':{'type':'string'},'content':{'type':'string'},'reason':{'type':'string'}},['path','content','reason']),spec('project_test','Request approval to run project tests. Only python unittest/pytest, node --test, npm test or swift test are supported. Network is disabled.',{'argv':{'type':'array','items':{'type':'string'}},'reason':{'type':'string'}},['argv','reason'])]


TOOLS.append(spec('project_command','Run one command in the selected project and get its output back, like a terminal. Give an exact argv; for pipes, redirects or loops use ["sh","-c","..."]. Programs: python3, node, npm, npx, swift, xcodebuild, git, make, curl, pip, pip3, sh, bash, zsh and common tools (ls, cat, grep, find, sed, awk, mkdir, cp, mv, rm, tar, unzip, diff, chmod, head, tail, wc, sort). Runs in a sandbox: writes only inside the project, no network by default. Set network=true ONLY for installs and downloads (npm install, pip install, curl): Berke always approves those himself, even in turbo mode. git push, pull, fetch, clone and ls-remote open the network by themselves (run git directly, not inside sh -c, so his saved GitHub sign-in works) and always ask him too. Risky commands (rm, sudo, git push, git reset --hard, chmod -R, piping into a shell) also always ask him. Open apps with project_open_editor or the desktop tools, never from here.',{'argv':{'type':'array','items':{'type':'string'}},'reason':{'type':'string'},'timeout_seconds':{'type':'integer','description':'5-120, default 30'},'network':{'type':'boolean','description':'true only for installs and downloads; always needs Berke’s approval'}},['argv','reason']))
TOOLS.append(spec('project_patch','Replace one exact snippet in an existing project file, like a precise edit. `old` must match exactly once unless replace_all is true. Prefer this over project_edit for changes to existing files; it needs far less text. Waits for Berke approval like project_edit.',{'path':{'type':'string'},'old':{'type':'string'},'new':{'type':'string'},'replace_all':{'type':'boolean'},'reason':{'type':'string'}},['path','old','new']))
TOOLS.append(spec('project_search','Search the selected project for a literal text (case-insensitive). Returns file, line number and the line, at most 80 hits. Read-only; use it instead of reading every file.',{'query':{'type':'string'},'path':{'type':'string','description':'optional folder inside the project'}},['query']))
TOOLS.append(spec('project_note','Add ONE short line (max 300 characters) to a shared notebook that the team reads. scope=project (default): a decision, the current state or what is left on THIS project. scope=team: a lasting fact for all projects, such as Berke’s preference, a command or approach that worked, or a lesson learned. It is not a file of the project and needs no approval.',{'line':{'type':'string'},'scope':{'type':'string','enum':['project','team']}},['line']))
TOOLS.append(spec('project_skill','List the reusable how-to guides (skills) saved for the team, or read one by name. Read-only. Call it without a name before a familiar kind of job (browser game, new project, debugging, git, verifying work), then follow the guide you pick.',{'name':{'type':'string'}},[]))
TOOLS.append(spec('project_browser','Open a web page in a real headless browser (Chromium) and run a short scripted session. Two modes. (1) A project file: give `file` (default index.html); only the project’s own files load, the internet is blocked. Use it to really try what you built. (2) The internet: give `url` (http or https). Berke approves every internet session himself, even in turbo mode. The browser is fresh and signed in nowhere, only reads (no POST/PUT/DELETE), cannot reach localhost or the home network, cannot download files and never types into password or card fields; do not try to log in. Give `steps`, each ONE action: {"press":"ArrowRight"}, {"click":"#restart"}, {"type":"#name","text":"abc"}, {"wait":500} (ms, max 5000), {"text":"#score"} (visible text; use "body" to read a whole page), {"count":".card"} (matching elements), {"eval":"snake.length"} (a JavaScript expression in the page; project files only), {"goto":"https://..."} (another page; internet mode only). Returns every step’s result plus page errors. Max 40 steps. If it answers that the browser tool is not installed, say so; do not claim you tested.',{'file':{'type':'string','description':'HTML file inside the project, default index.html'},'url':{'type':'string','description':'http or https address for internet mode instead of file'},'steps':{'type':'array','items':{'type':'object'}},'reason':{'type':'string'}},['steps']))
TOOLS.append(spec('project_open_editor','Open something of the selected project on Berke’s Mac. app=vscode (default) opens the project folder in Visual Studio Code; app=browser opens one HTML file of the project (path, default index.html) in the default browser so he can play or see the result. It only opens; it types and clicks nothing. Waits for approval unless his permission mode allows commands.',{'app':{'type':'string','enum':['vscode','browser']},'path':{'type':'string','description':'HTML file inside the project, only for app=browser'},'reason':{'type':'string'}},[]))
TOOLS.append(spec('project_progress','One short status line (max 200 characters, Berke’s language) in the chat while you keep working: what just finished, what is next. Only after a real milestone of a long job, at most 6 per job, never the final answer. No approval.',{'line':{'type':'string'}},['line']))
NEW_TOOL_NAMES=('project_patch','project_search','project_note','project_command','project_open_editor','project_skill','project_browser','project_progress')

COMMAND_PROGRAMS=frozenset(('python3','python','node','npm','npx','swift','xcodebuild','git','rg','ls','cat','pwd','mkdir','cp','mv','touch','grep','head','tail','wc','sort','make','sh','bash','zsh','curl','pip','pip3','rm','find','sed','awk','tar','unzip','diff','echo','chmod'))
# Commands that must never run without Berke's own click, even in turbo mode.
RISKY=re.compile(r'(?:^|[\s;&|(`])(?:sudo|su|dd|mkfs\w*|shutdown|reboot|chown|diskutil|rm)(?=$|[\s;&|)`])|\bgit\s+(?:push|reset\s+--hard|clean|checkout\s+--|restore|branch\s+-D)\b|\bchmod\s+-R\b|\|\s*(?:sh|bash|zsh)\b|>>?\s*(?:/(?!dev/null)|~)',re.I)
# Commands that could drive other apps or the system from inside the sandbox; the desktop tools are the only way to do that.
FORBIDDEN=re.compile(r'(?:^|[\s;&|(`/])(?:osascript|launchctl|open|security|defaults|networksetup|systemsetup|pmset|csrutil|spctl|tccutil)(?=$|[\s;&|)`])',re.I)
GIT_NETWORK=frozenset(('push','pull','fetch','clone','ls-remote'))
GIT_OPTIONS_WITH_VALUE=frozenset(('-C','-c','--git-dir','--work-tree','--namespace','--exec-path'))
def git_subcommand(tokens):
    # First real git subcommand of one git invocation, skipping global options such as -C <dir> or -c k=v.
    i=1
    while i<len(tokens):
        t=tokens[i]
        if t in GIT_OPTIONS_WITH_VALUE:i+=2;continue
        if t.startswith('-'):i+=1;continue
        return t
    return None
def git_commands(argv):
    # Every git invocation inside the argv (direct, or inside sh -c "..."): list of (subcommand, tokens).
    import shlex
    found=[]
    def scan(tokens):
        if tokens and tokens[0]=='git':
            sub=git_subcommand(tokens)
            if sub:found.append((sub,tokens))
    if argv and argv[0]=='git':scan(list(argv))
    elif argv and argv[0] in ('sh','bash','zsh') and '-c' in argv[1:] and argv.index('-c')+1<len(argv):
        for part in re.split(r'[;&|\n]+|\(|\)|`|\$\(',argv[argv.index('-c')+1]):
            try:tokens=shlex.split(part)
            except ValueError:tokens=part.split()
            scan(tokens)
    return found
def git_network_info(argv):
    # (opens the network, is a push, direct git so the saved sign-in may be used)
    commands=git_commands(argv)
    net=any(sub in GIT_NETWORK for sub,_ in commands);push=any(sub=='push' for sub,_ in commands)
    direct=bool(argv) and argv[0]=='git' and len(commands)==1 and net and not any(t in ('-c','--exec-path') or t.startswith(('--exec-path=','--upload-pack','--receive-pack','--config','--exec')) for t in argv[1:])
    return net,push,direct
def digest(data):return hashlib.sha256(data).hexdigest()

class ProjectBridge:
    def __init__(self,root,backup,approve,activity,cancelled):
        self.root=Path(root).resolve(strict=True);self.backup=Path(backup);self.approve=approve;self.activity=activity;self.cancelled=cancelled;self.client=None;self.note=None;self.progress=None;self.progress_lines=[];self.saved=[];self.runs=[]
        # Where the installed tool venv may live: next to the app's state folder, or the app's fixed data folder (a test run keeps its state elsewhere).
        self.tools_dirs=[Path(backup).parent/'tools',Path.home()/'Library'/'Application Support'/'BerkeJARVIS'/'tools']
        if not self.root.is_dir() or self.root==Path('/') or self.root==Path.home():raise ValueError('Belirli bir proje klasörü seç.')
    def path(self,relative):
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts or any(part in SKIP or part.startswith('.env') for part in p.parts):raise ValueError('Proje yolu izinli değil.')
        target=(self.root/p).resolve()
        if target==self.root or self.root not in target.parents:raise ValueError('Dosya seçili projenin dışında.')
        return target
    def sandbox_profile(self,network=False,git=False):
        # macOS sandbox-exec profile: no network, writes only inside the project and temp folders, no reading of key and app-data folders.
        root=str(self.root);home=str(Path.home())
        if any(ch in root+home for ch in '"\\'):raise ValueError('Proje yolu komut ortamı için uygun değil.')
        # Always unreadable: key folders, the agents' own sign-in folders, browser/message data and shell history. Without git: also the Keychain and token files (git needs them for its saved sign-in).
        always=('.ssh','.aws','.gnupg','.codex','.claude','.gemini','.antigravity','Library/Application Support/BerkeJARVIS','Library/Application Support/Claude','Library/Application Support/Google/Chrome','Library/Safari','Library/Cookies','Library/Messages','Library/Mail')
        blocked=' '.join('(subpath "%s/%s")'%(home,part) for part in always+(() if git else ('Library/Keychains','.config/gh','.config/gcloud')))
        blocked+=' '+' '.join('(literal "%s/%s")'%(home,name) for name in ('.zsh_history','.bash_history')+(() if git else ('.netrc','.git-credentials')))
        return ('(version 1)(allow default)'+('' if network else '(deny network*)')+'(deny mach-lookup (global-name "com.apple.coreservices.appleevents"))(deny file-read* '+blocked+')'
            '(deny file-write* (require-not (require-any (subpath "'+root+'") (subpath "/private/tmp") (subpath "/private/var/folders") (regex #"^/dev/(null|tty|zero|dtracehelper)$"))))')
    def local_exec(self,argv,timeout=30,network=False,git=False):
        # Used when no Codex client runs the command (Claude Code sessions). Never runs without the sandbox.
        import subprocess
        sandbox=Path('/usr/bin/sandbox-exec')
        if not sandbox.exists():raise ValueError('Güvenli komut ortamı (sandbox) bu sistemde yok; komut çalıştırılmadı.')
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin','HOME':str(Path.home()),'LANG':'en_US.UTF-8','TMPDIR':'/private/tmp','PYTHONDONTWRITEBYTECODE':'1','NO_COLOR':'1','CI':'1','GIT_TERMINAL_PROMPT':'0'}
        try:
            done=subprocess.run([str(sandbox),'-p',self.sandbox_profile(network,git)]+list(argv),cwd=str(self.root),env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
            text=done.stdout.decode('utf-8','replace');code=done.returncode
        except subprocess.TimeoutExpired as error:
            text=(error.stdout or b'').decode('utf-8','replace')+'\n[süre doldu: %d sn; komut durduruldu]'%timeout;code=None
        except OSError as error:raise ValueError('Komut başlatılamadı: '+str(error)[:200])
        if len(text)>18000:text=text[:9000]+'\n...[ortası kısaltıldı]...\n'+text[-9000:]
        return {'exitCode':code,'output':text}
    def browser_exec(self,url,steps,internet=False):
        # Headless Chromium through Playwright in the JARVIS tools venv (installed once by Tarayici-kur.command). File mode never touches the internet; internet mode is read-only and public hosts only (browser_runner enforces both).
        import subprocess,sys
        python=next((d/'venv'/'bin'/'python' for d in self.tools_dirs if (d/'venv'/'bin'/'python').exists()),None)
        if python is None:return {'ran':False,'installed':False,'message':'Tarayıcı aracı kurulu değil. Berke’nin Tarayici-kur.command dosyasını bir kez çalıştırması gerekiyor; denendi diye yazma.'}
        runner=Path(__file__).with_name('browser_runner.py')
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(Path.home()),'LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
        if os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):env['PLAYWRIGHT_BROWSERS_PATH']=os.environ['PLAYWRIGHT_BROWSERS_PATH']
        try:done=subprocess.run([str(python),'-B',str(runner)],input=json.dumps({'url':url,'root':str(self.root),'steps':steps,'internet':internet}),capture_output=True,text=True,timeout=120 if internet else 60,env=env,cwd=str(python.parent.parent.parent))
        except subprocess.TimeoutExpired:return {'ran':True,'ok':False,'error':'Tarayıcı denemesi süresinde bitmedi.'}
        except OSError as error:return {'ran':False,'message':'Tarayıcı başlatılamadı: '+str(error)[:200]}
        lines=[l for l in done.stdout.strip().splitlines() if l.startswith('{')]
        if not lines:return {'ran':True,'ok':False,'error':(done.stderr or 'Çıktı yok')[-400:]}
        try:value=json.loads(lines[-1])
        except ValueError:return {'ran':True,'ok':False,'error':'Tarayıcı çıktısı okunamadı.'}
        value['ran']=True;return value
    def invoke(self,params):
        name=params['tool'];args=params.get('arguments',{})
        if isinstance(args,str):args=json.loads(args)
        if self.cancelled.is_set():raise ValueError('İş durduruldu.')
        self.activity(name, str(args.get('path') or args.get('reason') or args.get('line') or ''))
        if name=='project_list':
            files=[]
            for directory,dirs,names in os.walk(self.root,followlinks=False):
                dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith('.') and not (Path(directory)/d).is_symlink()]
                for f in names:
                    if f.startswith('.') or f in SKIP:continue
                    try:p=self.path(str((Path(directory)/f).relative_to(self.root)))
                    except ValueError:continue
                    if p.is_file() and p.stat().st_size<=300000:files.append(str(p.relative_to(self.root)))
                    if len(files)>=600:return {'files':files,'limited':True}
            return {'files':files}
        if name=='project_note':
            line=re.sub(r'\s+',' ',str(args.get('line',''))).strip()
            if not 3<=len(line)<=300:raise ValueError('Not 3-300 karakter olmalı.')
            if not self.note:raise ValueError('Proje defteri bu oturumda kapalı.')
            scope='team' if args.get('scope')=='team' else 'project'
            self.note(line,scope);return {'saved':True,'scope':scope}
        if name=='project_browser':
            import browser_runner
            from urllib.parse import urlsplit
            address=args.get('url');internet=address is not None
            if internet and args.get('file'):raise ValueError('Ya file ya url ver, ikisini birden değil.')
            def check_address(value):
                if not isinstance(value,str) or not 8<=len(value)<=500:raise ValueError('Adres geçersiz.')
                try:parts=urlsplit(value);host=parts.hostname;parts.port
                except ValueError:raise ValueError('Adres geçersiz.')
                if parts.scheme not in ('http','https') or not host or parts.username or parts.password:raise ValueError('Yalnızca kullanıcı bilgisi içermeyen http veya https adresi açılır.')
                if not browser_runner.host_ok(host,resolve=False):raise ValueError('Yerel ağ ve bu bilgisayar adresleri açılmaz; yalnızca herkese açık siteler.')
                return value
            if internet:check_address(address);target=None
            else:
                target=self.path(args.get('file') or 'index.html')
                if target.suffix.lower() not in ('.html','.htm') or target.is_symlink() or not target.is_file():raise ValueError('Yalnızca projedeki bir .html dosyası açılır.')
            steps=args.get('steps')
            if not isinstance(steps,list) or not 1<=len(steps)<=40:raise ValueError('1 ile 40 arası adım ver.')
            kinds=('press','click','type','wait','text','count')+(('goto',) if internet else ('eval',))
            clean=[];shown=[]
            for step in steps:
                if not isinstance(step,dict) or not step:raise ValueError('Her adım tek bir eylem olmalı.')
                kind=next(iter(step));value=step[kind]
                if kind not in kinds or (len(step)!=1 if kind!='type' else bool(set(step)-{'type','text'})):raise ValueError('Bilinmeyen tarayıcı adımı: '+str(kind)[:30])
                if kind=='wait':
                    if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=5000:raise ValueError('wait 0-5000 ms olmalı.')
                elif kind=='goto':check_address(value)
                elif not isinstance(value,str) or not 1<=len(value)<=(600 if kind=='eval' else 200):raise ValueError('Adım değeri geçersiz: '+kind)
                if kind=='type' and not isinstance(step.get('text',''),str):raise ValueError('type için text metin olmalı.')
                clean.append(dict(step))
                shown.append(kind+' '+(str(value)+(' = '+step.get('text','')[:60] if kind=='type' else '')))
            if internet:
                payload={'argv':['browser',address]+shown[:12],'reason':str(args.get('reason') or 'İnternette sayfaya bak')[:400],'root':str(self.root),'network':True,'force':True,'browser':True}
            else:
                payload={'argv':['browser',str(target.relative_to(self.root))],'reason':str(args.get('reason') or 'Tarayıcıda dene')[:400],'root':str(self.root)}
            if not self.approve('test',payload):return {'ran':False,'message':'Tarayıcı denemesi reddedildi.'}
            if self.cancelled.is_set():raise ValueError('İş durduruldu.')
            result=self.browser_exec(address if internet else target.as_uri(),clean,internet)
            if result.get('ran'):self.runs.append(0 if result.get('ok') else 1)
            self.activity('command_result',str(result)[:1200])
            return result
        if name=='project_progress':
            line=' '.join(str(args.get('line','')).split())
            if not 5<=len(line)<=200:raise ValueError('Ara mesaj 5-200 karakter olmalı.')
            if not self.progress:raise ValueError('Ara mesaj bu oturumda kapalı.')
            if len(self.progress_lines)>=6:return {'posted':False,'message':'Ara mesaj sınırı (6) doldu; kapanış cevabında özetle.'}
            if line in self.progress_lines:return {'posted':False,'message':'Aynı ara mesaj zaten gönderildi.'}
            self.progress(line);self.progress_lines.append(line);return {'posted':True}
        if name=='project_skill':
            import skills
            if not args.get('name'):return {'skills':skills.listing(self.backup.parent)}
            return {'name':str(args['name']).strip().lower(),'guide':skills.read(args['name'],self.backup.parent)}
        if name=='project_search':
            query=str(args.get('query',''))
            if not 2<=len(query)<=200:raise ValueError('Arama metni 2-200 karakter olmalı.')
            needle=query.casefold();scope=self.path(args['path']) if args.get('path') else self.root
            if not scope.is_dir():raise ValueError('Arama klasörü bulunamadı.')
            hits=[]
            for directory,dirs,names in os.walk(scope,followlinks=False):
                dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith('.') and not (Path(directory)/d).is_symlink()]
                for f in names:
                    if f.startswith('.') or f in SKIP:continue
                    file=Path(directory)/f
                    try:
                        if file.is_symlink() or file.stat().st_size>300000:continue
                        lines=file.read_text(encoding='utf-8').splitlines()
                    except (OSError,UnicodeDecodeError):continue
                    for number,text in enumerate(lines,1):
                        if needle in text.casefold():
                            hits.append({'path':str(file.relative_to(self.root)),'line':number,'text':text.strip()[:200]})
                            if len(hits)>=80:return {'hits':hits,'limited':True}
            return {'hits':hits}
        if name in ('project_read','project_edit','project_patch'):
            target=self.path(args.get('path',''));old=target.read_bytes() if target.exists() else b''
            if len(old)>300000:raise ValueError('Dosya 300 KB sınırını aşıyor.')
            before=old.decode('utf-8')
            if name=='project_read':return {'path':args['path'],'text':before}
            if name=='project_patch':
                old_text=args.get('old');new_text=args.get('new')
                if not target.exists():raise ValueError('Dosya yok; yeni dosya için project_edit kullan.')
                if not isinstance(old_text,str) or not old_text or not isinstance(new_text,str):raise ValueError('old ve new metin olmalı.')
                count=before.count(old_text)
                if count==0:return {'saved':False,'error':'old metni dosyada bulunamadı; project_read ile güncel metni kontrol et.'}
                if count>1 and not args.get('replace_all'):return {'saved':False,'error':'old metni '+str(count)+' yerde geçiyor; daha fazla çevre metin ekle ya da replace_all kullan.'}
                content=before.replace(old_text,new_text) if args.get('replace_all') else before.replace(old_text,new_text,1)
            else:content=args.get('content')
            if not isinstance(content,str) or len(content.encode())>300000:raise ValueError('Yeni içerik sınırı aşıyor.')
            diff=''.join(difflib.unified_diff(before.splitlines(True),content.splitlines(True),fromfile=args['path'],tofile=args['path']))
            if not diff:return {'saved':False,'message':'Değişiklik yok.'}
            if not self.approve('file',{'path':args['path'],'reason':str(args.get('reason',''))[:400],'diff':diff,'root':str(self.root)}):return {'saved':False,'message':'Berke değişikliği reddetti veya onay süresi doldu.'}
            # Re-check after approval, and reject changed or redirected targets.
            if self.path(args['path'])!=target or target.is_symlink() or (target.read_bytes() if target.exists() else b'')!=old:raise ValueError('Dosya onay beklerken değişti; yeniden inceleme gerekli.')
            if self.cancelled.is_set():raise ValueError('İş durduruldu.')
            target.parent.mkdir(parents=True,exist_ok=True)
            self.backup.mkdir(parents=True,exist_ok=True)
            record={'path':str(target),'before':before,'existed':target.exists(),'saved_at':time.time()}
            (self.backup/('agent-edit-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
            temp=target.with_name('.jarvis-'+uuid.uuid4().hex+'.tmp');temp.write_text(content,encoding='utf-8');os.replace(temp,target)
            if args['path'] not in self.saved:self.saved.append(args['path'])
            return {'saved':True,'path':args['path'],'sha256':digest(content.encode())}
        if name in ('project_test','project_command'):
            argv=args.get('argv');prefixes=[['python3','-m','unittest'],['python3','-m','pytest'],['node','--test'],['npm','test'],['swift','test']]
            if not isinstance(argv,list) or not argv or len(argv)>60 or not all(isinstance(a,str) and len(a)<16000 for a in argv):raise ValueError('Geçersiz komut.')
            if name=='project_test' and not any(argv[:len(p)]==p for p in prefixes):raise ValueError('Desteklenmeyen test komutu.')
            line=' '.join(argv)
            if name=='project_command' and argv[0] not in COMMAND_PROGRAMS:raise ValueError('Bu çalıştırılabilir program desteklenmiyor.')
            if name=='project_command' and FORBIDDEN.search(line):raise ValueError('Başka uygulamayı ya da sistemi yöneten komutlar buradan çalışmaz; masaüstü araçlarını kullan.')
            git_net,git_push,git_direct=git_network_info(argv) if name=='project_command' else (False,False,False)
            network=name=='project_command' and (args.get('network') is True or git_net)
            risky=name=='project_command' and (bool(RISKY.search(line)) or git_push)
            payload={'argv':argv,'reason':str(args.get('reason',''))[:400],'root':str(self.root)}
            if network:payload['network']=True
            if risky:payload['risky']=True
            if network or risky:payload['force']=True
            if not self.approve('test',payload):return {'ran':False,'message':'Test çalıştırma reddedildi.'}
            if self.cancelled.is_set():raise ValueError('İş durduruldu.')
            seconds=args.get('timeout_seconds') if isinstance(args.get('timeout_seconds'),int) and not isinstance(args.get('timeout_seconds'),bool) else 30
            seconds=max(5,min(120,seconds))
            if self.client is None:result=self.local_exec(argv,seconds,network,git_direct)
            else:result=self.client.rpc('command/exec',{'command':argv,'cwd':str(self.root),'timeoutMs':seconds*1000,'outputBytesCap':18000,'sandboxPolicy':{'type':'workspaceWrite','writableRoots':[str(self.root)],'networkAccess':network}},timeout=seconds+10)
            self.runs.append(result.get('exitCode') if isinstance(result,dict) else None)
            self.activity('command_result',str(result)[:1200])
            return {'ran':True,'result':result}
        if name=='project_open_editor':
            app=args.get('app') or 'vscode'
            if app not in ('vscode','browser'):raise ValueError('app vscode veya browser olmalı.')
            if app=='browser':
                target=self.path(args.get('path') or 'index.html')
                if not target.is_file() or target.is_symlink() or target.suffix.lower() not in ('.html','.htm'):raise ValueError('Tarayıcıda yalnız projedeki bir .html dosyası açılır.')
                argv=['/usr/bin/open',str(target)];label='Projeyi tarayıcıda aç: '+str(target.relative_to(self.root))
            else:
                argv=['/usr/bin/open','-a','Visual Studio Code',str(self.root)];label='Projeyi Visual Studio Code ile aç'
            if not self.approve('test',{'argv':['open']+argv[1:],'reason':str(args.get('reason') or label)[:400],'root':str(self.root)}):return {'opened':False,'message':'Berke reddetti veya onay süresi doldu.'}
            if self.cancelled.is_set():raise ValueError('İş durduruldu.')
            import subprocess
            try:done=subprocess.run(argv,capture_output=True,timeout=20)
            except (OSError,subprocess.TimeoutExpired) as error:return {'opened':False,'error':str(error)[:200]}
            if done.returncode:return {'opened':False,'error':(done.stderr.decode('utf-8','replace').strip() or 'Açılamadı; uygulama kurulu olmayabilir.')[:300]}
            return {'opened':True,'app':app,'path':str(argv[-1])}
        raise ValueError('Desteklenmeyen proje aracı.')
