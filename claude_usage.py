"""Read subscription limits through the official CLI's zero-turn JSON /usage command."""
import json,os,re,subprocess,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from claude_chat import binary,environment,status

def reset_timestamp(text,now=None):
    match=re.search(r'resets\s+(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+at\s+)?(\d{1,2})(?::(\d{2}))?(am|pm)\s*\(([^)]+)\)',text,re.I)
    if not match:return None
    try:
        month,day,hour,minute,ampm,zone=match.groups();tz=ZoneInfo(zone);current=datetime.fromtimestamp(now or time.time(),tz)
        hour=int(hour)%12+(12 if ampm.lower()=='pm' else 0)
        value=current.replace(hour=hour,minute=int(minute or 0),second=0,microsecond=0)
        if month:
            months=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
            value=value.replace(month=months.index(month.lower())+1,day=int(day))
            if value<current-timedelta(days=30):value=value.replace(year=current.year+1)
        elif value<current:value+=timedelta(days=1)
        return value.timestamp()
    except (ValueError,KeyError):return None

def parse_usage(text,now=None):
    result={}
    for heading,key,minutes in [('Current session','primary',300),('Current week (all models)','secondary',10080)]:
        at=text.lower().rfind(heading.lower())
        if at<0:continue
        block=re.split(r'\n\s*Current (?:session|week)',text[at:at+1000],maxsplit=1,flags=re.I)[0]
        match=re.search(r'(\d{1,3}(?:\.\d+)?)\s*%\s*used',block,re.I)
        if match and 0<=float(match.group(1))<=100:
            reset=re.search(r'resets\s+[^\n]+',block,re.I)
            result[key]=dict(used_percent=float(match.group(1)),minutes=minutes,resets_at=reset_timestamp(block,now),reset_text=reset.group() if reset else '')
    if 'primary' not in result or 'secondary' not in result:raise ValueError('Claude 5 saatlik/haftalık limitleri eksik; tahmin edilmedi.')
    cached=bool(re.search(r'last.known|cached|showing last',text,re.I))
    return dict(status='live',source='Resmi Claude Code · JSON /usage',scope='Claude Pro: Claude sohbeti ve Claude Code ortak abonelik havuzu.',plan='Claude Pro',checked_at=time.time(),cached=cached,**result)

def parse_response(value):
    if not isinstance(value,dict) or value.get('local_command')!='usage' or value.get('type')!='result' or value.get('is_error') or value.get('num_turns')!=0 or value.get('duration_api_ms')!=0 or value.get('total_cost_usd')!=0:
        raise ValueError('Claude /usage salt durum komutu olarak doğrulanamadı.')
    usage=value.get('usage') or {}
    if any(usage.get(k,0)!=0 for k in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')) or value.get('modelUsage'):
        raise ValueError('Kota okumasında beklenmeyen model kullanımı bildirildi.')
    if not isinstance(value.get('result'),str):raise ValueError('Claude kullanım yanıtı geçersiz.')
    result=parse_usage(value['result']);result['zero_model_turns']=True
    return result

def read_limits(cancelled=None,timeout=18):
    process=None
    try:
        exe=binary()
        if not exe:raise ValueError('Claude CLI kurulu değil.')
        if cancelled and cancelled.is_set():raise ValueError('Kota okuması durduruldu.')
        account=status()
        if not account.get('signed_in'):raise ValueError('Resmi Claude abonelik girişi gerekli; API anahtarına geçilmedi.')
        args=[exe,'--restricted','--safe-mode','--tools','','--permission-prompts','none','--setting-sources','','--settings','{"disableAllHooks":true,"autoMemoryEnabled":false}','--no-chrome','--no-session-persistence','--output-format','json','--max-turns','1','-p','/usage']
        process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=environment(),text=True)
        end=time.monotonic()+timeout
        while True:
            if cancelled and cancelled.is_set():raise ValueError('Kota okuması durduruldu.')
            if time.monotonic()>end:raise ValueError('Claude kota komutu zaman aşımına uğradı.')
            try:output,_=process.communicate(timeout=min(.3,max(.01,end-time.monotonic())));break
            except subprocess.TimeoutExpired:continue
        if process.returncode or len(output)>1000000:raise ValueError('Resmi Claude kota komutu başarısız.')
        result=parse_response(json.loads(output));result['plan']='Claude '+str(account.get('plan','Pro'))
        return result
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        return dict(status='error',message=str(error)[:250],attempted_at=time.time())
    finally:
        if process:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            if process.stdout:process.stdout.close()
