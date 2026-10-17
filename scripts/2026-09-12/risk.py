import json, glob, collections, re
files=sorted(glob.glob('corpus/workflows/**/*.json', recursive=True))
et_name=collections.Counter(); gs_name=collections.Counter()
etpat=re.compile(r'error\s*trigger',re.I)
gspat=re.compile(r'google\s*sheet',re.I)
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    for n in d.get('nodes') or []:
        if not isinstance(n,dict): continue
        nm=n.get('name') or ''; t=n.get('type') or ''
        if etpat.search(nm): et_name[t]+=1
        if gspat.search(nm): gs_name[t]+=1
print('nodes NAMED like an Error Trigger, by type:')
for t,c in et_name.most_common(6): print(f'   {t:44}{c}')
print('\nnodes NAMED like Google Sheets, by type:')
for t,c in gs_name.most_common(6): print(f'   {t:44}{c}')
