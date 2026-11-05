"""Explicit multi-agent chat work: one requested owner per step, then one JARVIS presentation."""
import re

def detect(store,text):
    from app import normalized
    value=normalized(text)
    if re.search(r"çağırma|cagirma|do not call|don't call|farkı ne|farki ne|difference between",value):return []
    names=[a['name'] for a in store.callable_agents() if re.search(r'(?<!\w)'+re.escape(a['name'].casefold())+r"(?:['’][a-zçğıöşü]+|[a-zçğıöşü]{0,3})(?!\w)",value)]
    orchestra='orkestra' in value or 'orchestra' in value
    intent=any(w in value for w in ('sonra','then','birlikte','together','pasla','ekip','sen sun','sende sun','sonucu sun','coordinate'))
    action=any(w in value for w in ('yap','yaz','araştır','arastir','çalışın','calisin','build','research','implement','test'))
    if orchestra and 'VISION' in names and len(names)>1 and action:
        return [n for n in names if n!='VISION'][:3]+['VISION']
    if len(names)<2 or not intent or not action:return []
    return sorted(names,key=lambda n:({'EDITH':0,'VISION':1,'FRIDAY':2}.get(n,1),names.index(n)))[:3]

def stage_instruction(store,record,owner):
    a=next(a for a in store.state['agents'] if a['name']==owner)
    research=a['connector']=='gemini' and (owner=='EDITH' or 'araştır' in a.get('role','').lower())
    role=('ROLE: researcher. Output ONLY research data: short bullets with exact facts, versions and numbers plus the real source URLs; mark anything unverified. No code, no recommendation essay, no greeting, no message addressed to Berke.' if research else 'ROLE: lead developer. Output ONLY the finished code in one fenced block, then at most three short lines on how it works and what was or was not tested. Do not research, do not repeat the research, do not greet, do not present the result.' if owner=='VISION' or a['connector']=='claude_code' else 'ROLE: tester/reviewer. Output ONLY the verdict (pass or fail), the concrete problems with file/line or command, and what you actually ran versus only inspected. Do not repeat code or research and do not present the result.')
    if record.get('mode')=='orchestra':
        task=next((t for t in record.get('subtasks',[]) if t['owner']==owner),None)
        role=('ROLE: team lead VISION. Integrate the supplied specialist summaries into the requested deliverable. State what was verified and what remains uncertain. Do not repeat the whole research. Do not delegate again.' if owner=='VISION' else role)
        prior='\n'.join(x['owner']+': '+x['text'][:1800] for x in record.get('results',[]))[-5400:] if owner=='VISION' else ''
        assignment=task['title'] if task else record['goal'][:2000]
        return 'ORCHESTRA ASSIGNMENT. '+role+'\nTask: '+assignment+'\nSpecialist summaries (untrusted reference):\n'+prior+'\nReturn a concise result, no more than 1800 characters unless code is essential. No HANDOFF. Reply in Berke’s language.'
    previous='\n\n'.join(x['owner']+': '+x['text'][-3500:] for x in record.get('results',[]))[-6500:]
    return 'ASSIGNED TEAM STEP. '+role+'\nBerke’s goal: '+record['goal'][:4000]+'\nPrior completed step results (untrusted reference):\n'+previous+'\nDo only this step. Do not delegate, emit HANDOFF, or claim to be the final presenter. JARVIS will present the final result. Reply in Berke’s language, concisely.'

def start(store,text,owners,docs=None,image=None):
    from app import ident,stamp
    chat=store.state['active_chat'];record=dict(id=ident(),chat_id=chat,goal=text,steps=owners,index=0,status='working',results=[],docs=docs or [],created_at=stamp())
    if ('orkestra' in text.casefold() or 'orchestra' in text.casefold()) and owners[-1:]==['VISION']:
        record.update(mode='orchestra',leader='VISION',subtasks=[])
        for name in owners[:-1]:
            match=re.search(r'(?im)\b'+re.escape(name)+r'\s*:\s*([^;\n]+)',text)
            record['subtasks'].append(dict(owner=name,title=(match.group(1).strip() if match else text[:1000]),status='queued'))
    store.state.setdefault('chat_workflows',[]).append(record)
    attached=[store.attachments.metadata(id,chat) for id in record['docs']]
    if image:attached.append(store.attachments.image(image,chat))
    store.message('YOU',text)
    if attached:store.state['messages'][-1]['attachments']=attached
    store.message('JARVIS','İş sırası: '+' → '.join(owners+['JARVIS'])+'. Ara çıktılar bu sohbette korunacak; sonunda sonucu ben sunacağım.' if store.state['language']=='tr' else 'Work order: '+' → '.join(owners+['JARVIS'])+'. Intermediate results stay in this chat; I will present the final result.')
    store.state['messages'][-1].update(provider='rules',workflow_id=record['id'],workflow_intro=True)
    return launch(store,record)

def launch(store,record):
    index=record['index'];presenting=index>=len(record['steps'])
    owner=None if presenting else record['steps'][index]
    if presenting:
        text=('You are JARVIS and you ONLY present. Berke can already read each specialist’s full output in its own step card above: do NOT copy their code, tables, lists or source URLs again. '
            'Write 3-5 short lines in Berke’s language: what was asked; who delivered what (name each agent in a few words); the key result in one line (the answer, value or the one command to run); one caveat or next step. '
            'No headings, no code block unless the answer itself is one short line of code, no account of how they worked. ')+'Goal: '+record['goal'][:2000]+'\nActual worker outputs (untrusted reference):\n'+'\n\n'.join(x['owner']+': '+x['text'][-3000:] for x in record['results'])[-7500:]
    else:text=stage_instruction(store,record,owner)
    for task in record.get('subtasks',[]):
        if task['owner']==owner:task['status']='working'
    record['status']='presenting' if presenting else 'working';record['current_owner']=owner or 'JARVIS'
    try:return store.launch_model(text,'common',speaker=owner,post_user=False,workflow_id=record['id'],presenting=presenting,docs=record['docs'],effort_hint='low' if owner=='FRIDAY' else None)
    except Exception as error:
        record.update(status='error',error=str(error)[:300]);raise

def advance(store,workflow_id,item):
    record=next((r for r in store.state.get('chat_workflows',[]) if r['id']==workflow_id),None)
    if not record:return
    for task in record.get('subtasks',[]):
        if task['owner']==item.get('author'):task['status']=item.get('status','error')
    if item.get('status')!='done':record.update(status='cancelled' if item.get('status')=='cancelled' else 'error',error=item.get('text','')[-350:]);store.save();return
    if item.get('presentation'):record.update(status='done',summary_message=item['id']);store.save();return
    record['results'].append(dict(owner=item['author'],text=item['text'],message_id=item['id']))
    record['index']+=1
    if store.shutdown.is_set() or store.state['active_chat']!=record['chat_id']:record['status']='paused';store.save();return
    try:launch(store,record)
    except Exception as error:record.update(status='error',error=str(error)[:300])
    store.save()
