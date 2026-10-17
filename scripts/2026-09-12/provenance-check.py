# provenance-check.py — the check that decides whether any statistic from this corpus
# is usable: read one workflow at three points in the repo's history and compare the
# per-node error-handling properties. Run 2026-09-12; all five counts identical across
# c4885eee (pre type-rewrite), 3c0a92c4 (the rewrite) and HEAD, while @n8n/ types went
# 11 -> 0 and connections went from fully resolving to zero.
#
#   gh auth login && python provenance-check.py
import json, subprocess, urllib.request, collections
PATH_='workflows/Wait/1955_Wait_Splitout_Automation_Scheduled.json'
TOKEN=subprocess.run(['gh','auth','token'],capture_output=True,text=True).stdout.strip()
for sha in ('c4885eee','3c0a92c4','5ffee225','HEAD'):
    url=f'https://raw.githubusercontent.com/Zie619/n8n-workflows/{sha}/{PATH_}'
    req=urllib.request.Request(url, headers={'Authorization':f'token {TOKEN}'})
    d=json.load(urllib.request.urlopen(req))
    ns=[n for n in (d.get('nodes') or []) if isinstance(n,dict)]
    fl=collections.Counter()
    for n in ns:
        for k in ('retryOnFail','continueOnFail','alwaysOutputData'):
            if n.get(k) is True: fl[k]+=1
        if n.get('onError'): fl['onError:'+str(n['onError'])]+=1
        for k in ('maxTries','waitBetweenTries'):
            if n.get(k): fl[k]+=1
    ids={n.get('id') for n in ns}; names={n.get('name') for n in ns}
    tgt=real=0
    for k,v in (d.get('connections') or {}).items():
        for br in (v or {}).get('main') or []:
            for e in br or []:
                tgt+=1
                if e.get('node') in ids or e.get('node') in names: real+=1
    scoped=sum(1 for n in ns if (n.get('type') or '').startswith('@n8n/'))
    print(f'{sha:10} nodes={len(ns):4} scoped={scoped:3} targets={tgt:4} resolve={real:4}  {dict(fl)}')
