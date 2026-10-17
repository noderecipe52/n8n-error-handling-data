import json, glob, collections, re
files=sorted(glob.glob('corpus/workflows/**/*.json', recursive=True))
scoped=0; ai_named=0; ai_noop=0; files_with_ai=set()
pat=re.compile(r'(agent|openai|chat model|embedding|vector|langchain|llm|memory|anthropic|gemini|ollama)',re.I)
noop_types=collections.Counter()
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    for n in d.get('nodes') or []:
        if not isinstance(n,dict): continue
        t=n.get('type') or ''
        if t.startswith('@n8n/'): scoped+=1
        nm=n.get('name') or ''
        if pat.search(nm):
            ai_named+=1; files_with_ai.add(f)
            if t=='n8n-nodes-base.noOp': ai_noop+=1
            noop_types[t]+=1
print('nodes with a scoped @n8n/ type :',scoped)
print('nodes with an AI-ish NAME      :',ai_named,'across',len(files_with_ai),'files')
print('  ...typed n8n-nodes-base.noOp :',ai_noop)
print('\ntypes carried by AI-named nodes:')
for t,c in noop_types.most_common(8): print(f'   {t:46}{c}')
