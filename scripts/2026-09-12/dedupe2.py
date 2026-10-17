import json, glob, hashlib, collections, os
VOLATILE={'id','versionId','webhookId','position','createdAt','updatedAt','meta','tags','pinData','active','instanceId'}
def norm(o):
    if isinstance(o,dict):
        return {k:norm(v) for k,v in sorted(o.items()) if k not in VOLATILE}
    if isinstance(o,list):
        return [norm(x) for x in o]
    return o
rows=[]
for f in sorted(glob.glob('corpus/workflows/**/*.json', recursive=True)):
    d=json.load(open(f,encoding='utf-8'))
    nodes=[n for n in (d.get('nodes') or []) if isinstance(n,dict)]
    core={'nodes':sorted([json.dumps(norm(n),sort_keys=True) for n in nodes]),
          'connections':json.dumps(norm(d.get('connections') or {}),sort_keys=True)}
    h=hashlib.sha1(json.dumps(core,sort_keys=True).encode()).hexdigest()
    rows.append({'file':f,'fp':h,'n':len(nodes)})
by=collections.defaultdict(list)
for r in rows: by[r['fp']].append(r)
dups={k:v for k,v in by.items() if len(v)>1}
print('files              :',len(rows))
print('unique workflows   :',len(by))
print('duplicate groups   :',len(dups))
print('redundant copies   :',sum(len(v)-1 for v in dups.values()))
empty=sum(1 for r in rows if r['n']==0)
print('zero-node files    :',empty)
for g in sorted(dups.values(),key=len,reverse=True)[:3]:
    print(f'  x{len(g)} n={g[0]["n"]}:', ', '.join(os.path.basename(x["file"])[:34] for x in g[:3]))
json.dump({k:[x['file'] for x in v] for k,v in by.items()}, open('groups.json','w'))
