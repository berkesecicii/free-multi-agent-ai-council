"""Runs a short scripted session of one web page in headless Chromium (Playwright) and prints the result as JSON.
Started by project_browser with the tools venv python; reads {"url","root","steps","internet"} on stdin.
File mode (internet=false): only file:// pages inside the project load; every other request is blocked.
Internet mode (internet=true): a fresh browser without any saved sign-in; only public http(s) hosts, read-only requests (GET/HEAD/OPTIONS), no local network, no downloads, no passwords typed."""
import ipaddress,json,re,socket,sys
from pathlib import Path
from urllib.parse import urlsplit

SENSITIVE_FIELD=re.compile(r'pass(?:word|wd)?|pwd|cvc|cvv|card.?n(?:um|o)|iban|one-time-code|cc-',re.I)
LOCAL_SUFFIXES=('.localhost','.local','.internal','.lan','.home','.localdomain','.corp','.intranet','.home.arpa')
_resolved={}

def clip(value,limit=1500):
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,default=str)
    return text if len(text)<=limit else text[:limit]+'…'

def public_address(text):
    ip=ipaddress.ip_address(text)
    if ip.version==6 and ip.ipv4_mapped:ip=ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast

def host_ok(host,resolve=True):
    # True only for a public internet host. Names that point at this Mac or the home network are refused.
    name=(host or '').lower().strip('[]').rstrip('.')
    if not name or name=='localhost' or name.endswith(LOCAL_SUFFIXES):return False
    try:return public_address(name)
    except ValueError:pass
    if '.' not in name:return False
    if not resolve:return True
    if name not in _resolved:
        try:_resolved[name]=all(public_address(item[4][0].split('%')[0]) for item in socket.getaddrinfo(name,None))
        except (OSError,ValueError):_resolved[name]=False
    return _resolved[name]

def blocked_request(method,url):
    # Internet mode: should this request be refused?
    parts=urlsplit(url);scheme=parts.scheme.lower()
    if scheme in ('data','about','blob'):return False
    if scheme not in ('http','https') or (method or 'GET').upper() not in ('GET','HEAD','OPTIONS'):return True
    if parts.username or parts.password:return True
    try:host=parts.hostname
    except ValueError:return True
    return not host_ok(host)

def sensitive_target(page,selector=None):
    # Is the field (or the focused field when selector is None) a password or payment field?
    script='e=>{if(!e)return"";return [e.type,e.autocomplete,e.name,e.id].join(" ")}'
    try:info=page.eval_on_selector(selector,script) if selector else page.evaluate('()=>{const e=document.activeElement;return e?[e.type,e.autocomplete,e.name,e.id].join(" "):""}')
    except Exception:return False
    return bool(SENSITIVE_FIELD.search(info or ''))

def main():
    job=json.loads(sys.stdin.read());root=str(Path(job['root']).resolve());steps=job['steps'];internet=job.get('internet') is True
    from playwright.sync_api import sync_playwright
    results=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--disable-extensions','--no-first-run'])
        try:
            context=browser.new_context(viewport={'width':900,'height':700},service_workers='block',accept_downloads=False)
            def gate(route):
                url=route.request.url
                if internet:
                    if blocked_request(route.request.method,url):route.abort()
                    else:route.continue_()
                elif url.startswith('file://') and str(Path(url[7:].split('?')[0].split('#')[0]).resolve()).startswith(root):route.continue_()
                elif url.startswith(('data:','about:','blob:')):route.continue_()
                else:route.abort()
            context.route('**/*',gate)
            if internet and hasattr(context,'route_web_socket'):
                context.route_web_socket('**/*',lambda ws:ws.close())  # a web page must not open sockets to this Mac
            page=context.new_page();page.set_default_timeout(8000 if internet else 4000)
            page.on('pageerror',lambda e:errors.append(clip(str(e),300)))
            page.on('console',lambda m:errors.append('console: '+clip(m.text,300)) if m.type=='error' else None)
            if internet:page.goto(job['url'],timeout=20000,wait_until='domcontentloaded')
            else:page.goto(job['url'])
            results.append({'step':'open','title':page.title(),**({'url':page.url} if internet else {})})
            for index,step in enumerate(steps,1):
                kind=next(iter(step));value=step[kind]
                try:
                    if kind=='press':
                        if internet and sensitive_target(page):out='REDDEDİLDİ: parola veya ödeme alanına yazılmaz.'
                        else:page.keyboard.press(str(value));out='ok'
                    elif kind=='click':page.click(str(value));out='ok'
                    elif kind=='type':
                        if internet and sensitive_target(page,str(value)):out='REDDEDİLDİ: parola veya ödeme alanına yazılmaz.'
                        else:page.fill(str(value),str(step.get('text','')));out='ok'
                    elif kind=='wait':page.wait_for_timeout(max(0,min(5000,int(value))));out='ok'
                    elif kind=='text':out=clip(page.inner_text(str(value)),4000 if internet else 1500)
                    elif kind=='count':out=page.locator(str(value)).count()
                    elif kind=='goto' and internet:
                        if blocked_request('GET',str(value)):out='REDDEDİLDİ: bu adrese gidilmez.'
                        else:page.goto(str(value),timeout=20000,wait_until='domcontentloaded');out='ok: '+clip(page.url,200)
                    elif kind=='eval' and not internet:out=clip(page.evaluate(str(value)))
                    else:out='bilinmeyen adım'
                except Exception as error:out='HATA: '+clip(str(error).splitlines()[0],300)
                results.append({'step':index,kind:value if kind!='type' else value,'sonuç':out})
            if internet:results.append({'step':'son','url':page.url})
        finally:browser.close()
    print(json.dumps({'ok':True,'results':results,'page_errors':errors[:10]},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'ok':False,'error':clip(str(error),600)},ensure_ascii=False))
