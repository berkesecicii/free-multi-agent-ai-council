"""Bounded project tools. Reads stay in the chosen root; every edit/test waits for approval."""
import difflib,hashlib,json,os,time,uuid
from pathlib import Path

SKIP={'.git','.env','.ssh','.aws','.venv','venv','node_modules','__pycache__','.DS_Store'}
def spec(name,description,properties,required):return dict(type='function',name=name,description=description,inputSchema=dict(type='object',properties=properties,required=required,additionalProperties=False))
TOOLS=[spec('project_list','List text file paths in the user-selected project.',{},[]),spec('project_read','Read one UTF-8 file from the selected project.',{'path':{'type':'string'}},['path']),spec('project_edit','Propose complete new text for one file. Waits for Berke approval; returns whether it was actually saved. Never claim saved before success.',{'path':{'type':'string'},'content':{'type':'string'},'reason':{'type':'string'}},['path','content','reason']),spec('project_test','Request approval to run project tests. Only python unittest/pytest, node --test, npm test or swift test are supported. Network is disabled.',{'argv':{'type':'array','items':{'type':'string'}},'reason':{'type':'string'}},['argv','reason'])]

TOOLS.append(spec('project_command','Propose an exact command argv to run in the selected project. Every command waits for explicit Berke approval. No shell interpolation. Network is disabled; writes restricted to project.',{'argv':{'type':'array','items':{'type':'string'}},'reason':{'type':'string'}},['argv','reason']))

def digest(data):return hashlib.sha256(data).hexdigest()

class ProjectBridge:
    def __init__(self,root,backup,approve,activity,cancelled):
        self.root=Path(root).resolve(strict=True);self.backup=Path(backup);self.approve=approve;self.activity=activity;self.cancelled=cancelled;self.client=None
        if not self.root.is_dir() or self.root==Path('/') or self.root==Path.home():raise ValueError('Belirli bir proje klasörü seç.')
    def path(self,relative):
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts or any(part in SKIP or part.startswith('.env') for part in p.parts):raise ValueError('Proje yolu izinli değil.')
        target=(self.root/p).resolve()
        if target==self.root or self.root not in target.parents:raise ValueError('Dosya seçili projenin dışında.')
        return target
    def invoke(self,params):
        name=params['tool'];args=params.get('arguments',{})
        if isinstance(args,str):args=json.loads(args)
        if self.cancelled.is_set():raise ValueError('İş durduruldu.')
        self.activity(name, str(args.get('path') or args.get('reason') or ''))
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
        if name in ('project_read','project_edit'):
            target=self.path(args.get('path',''));old=target.read_bytes() if target.exists() else b''
            if len(old)>300000:raise ValueError('Dosya 300 KB sınırını aşıyor.')
            before=old.decode('utf-8')
            if name=='project_read':return {'path':args['path'],'text':before}
            content=args.get('content')
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
            return {'saved':True,'path':args['path'],'sha256':digest(content.encode())}
        if name in ('project_test','project_command'):
            argv=args.get('argv');prefixes=[['python3','-m','unittest'],['python3','-m','pytest'],['node','--test'],['npm','test'],['swift','test']]
            if not isinstance(argv,list) or not argv or len(argv)>60 or not all(isinstance(a,str) and len(a)<16000 for a in argv):raise ValueError('Geçersiz komut.')
            if name=='project_test' and not any(argv[:len(p)]==p for p in prefixes):raise ValueError('Desteklenmeyen test komutu.')
            if name=='project_command' and argv[0] not in {'python3','python','node','npm','npx','swift','xcodebuild','git','rg','ls','cat','pwd'}:raise ValueError('Bu çalıştırılabilir program desteklenmiyor.')
            if not self.approve('test',{'argv':argv,'reason':str(args.get('reason',''))[:400],'root':str(self.root)}):return {'ran':False,'message':'Test çalıştırma reddedildi.'}
            if self.cancelled.is_set():raise ValueError('İş durduruldu.')
            result=self.client.rpc('command/exec',{'command':argv,'cwd':str(self.root),'timeoutMs':30000,'outputBytesCap':18000,'sandboxPolicy':{'type':'workspaceWrite','writableRoots':[str(self.root)],'networkAccess':False}},timeout=40)
            self.activity('command_result',str(result)[:1200])
            return {'ran':True,'result':result}
        raise ValueError('Desteklenmeyen proje aracı.')
