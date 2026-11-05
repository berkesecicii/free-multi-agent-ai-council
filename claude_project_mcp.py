"""Small stdio MCP server; bounded project actions stay in the JARVIS approval host."""
import json,os,sys,urllib.request,urllib.error
from project_bridge import TOOLS
ALLOWED={t['name']:t for t in TOOLS if t['name'] in ('project_list','project_read','project_edit','project_patch','project_search','project_note','project_skill','project_browser','project_progress','project_command','project_open_editor') and os.environ.get('JARVIS_PROJECT_TOOLS','1')=='1'}
if os.environ.get('JARVIS_DESKTOP_TOOLS')=='1':
    from desktop_bridge import TOOLS as DESKTOP_TOOLS
    ALLOWED.update({t['name']:t for t in DESKTOP_TOOLS})

def process(request):
    method=request.get('method');params=request.get('params') or {}
    if method=='initialize':return {'protocolVersion':params.get('protocolVersion','2024-11-05'),'capabilities':{'tools':{}},'serverInfo':{'name':'jarvis-project','version':'0.6.1'}}
    if method=='ping':return {}
    if method=='tools/list':return {'tools':[{'name':t['name'],'description':t['description'],'inputSchema':t['inputSchema']} for t in ALLOWED.values()]}
    if method=='tools/call':
        if params.get('name') not in ALLOWED:raise ValueError('Araç izinli değil.')
        endpoint=os.environ['JARVIS_CLAUDE_TOOL_ENDPOINT']
        if not endpoint.startswith('http://127.0.0.1:') or not endpoint.endswith('/claude-tool'):raise ValueError('Geçersiz yerel araç adresi.')
        data=json.dumps({'tool':params['name'],'arguments':params.get('arguments',{})}).encode()
        req=urllib.request.Request(endpoint,data=data,headers={'Content-Type':'application/json','X-Jarvis-Project-Token':os.environ['JARVIS_CLAUDE_TOOL_TOKEN']})
        try:
            with urllib.request.urlopen(req,timeout=620) as response:value=json.load(response)
        except urllib.error.HTTPError as error:
            # the host answers a refused or failed action with 400 and the reason in the body; the agent must read that reason, not just "400 Bad Request"
            try:body=json.loads(error.read() or b'{}')
            except ValueError:body={}
            value={'error':str((body.get('error') if isinstance(body,dict) else '') or error)[:500]}
        image=value.pop('image',None)
        content=[{'type':'text','text':json.dumps(value,ensure_ascii=False)}]
        if image:content.append({'type':'image','mimeType':'image/jpeg','data':image.split(',',1)[1]})
        return {'content':content,'isError':bool(value.get('error'))}
    raise ValueError('Desteklenmeyen MCP yöntemi.')

def main():
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if 'id' not in request:continue
            try:response={'jsonrpc':'2.0','id':request['id'],'result':process(request)}
            except Exception as e:response={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32603,'message':str(e)[:500]}}
            print(json.dumps(response),flush=True)
        except ValueError:continue
if __name__=='__main__':main()
