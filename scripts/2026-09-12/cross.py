import json, collections
groups=json.load(open('groups.json')); files=[v[0] for v in groups.values()]
rows=[]
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    nodes=[n for n in (d.get('nodes') or []) if isinstance(n,dict)]
    ups=[n for n in nodes if (n.get('type') or '')=='n8n-nodes-base.googleSheets'
         and (n.get('parameters') or {}).get('operation') in ('appendOrUpdate','upsert')]
    if not ups: continue
    retry=any(n.get('retryOnFail') is True for n in nodes)
    eb=any(n.get('onError')=='continueErrorOutput' for n in nodes)
    et=any((n.get('type') or '').endswith('errorTrigger') for n in nodes)
    sup=any(n.get('onError')=='continueRegularOutput' or n.get('continueOnFail') is True for n in nodes)
    trig=[n.get('type') for n in nodes if 'rigger' in (n.get('type') or '') or (n.get('type') or '').endswith('.webhook')]
    # retry on the upsert node itself
    self_retry=any(n.get('retryOnFail') is True for n in ups)
    rows.append({'f':f,'retry':retry,'self_retry':self_retry,'eb':eb,'et':et,'sup':sup,'trig':trig})
N=len(rows)
print('workflows with a Sheets appendOrUpdate/upsert:',N)
def pct(k): 
    v=sum(1 for r in rows if r[k]); return f'{v:4}  {100*v/N:5.1f}%'
print(' any retryOnFail anywhere        :',pct('retry'))
print(' retryOnFail ON THE UPSERT NODE  :',pct('self_retry'))
print(' any continueErrorOutput         :',pct('eb'))
print(' any errorTrigger                :',pct('et'))
print(' error suppression present       :',pct('sup'))
none=[r for r in rows if not (r['retry'] or r['eb'] or r['et'])]
print(f'\n NO retry / error branch / errorTrigger at all: {len(none)}  ({100*len(none)/N:.1f}%)')
tc=collections.Counter()
for r in rows:
    for t in r['trig']: tc[t]+=1
print('\ntriggers in these workflows:'); [print(f'   {a:44}{b}') for a,b in tc.most_common(7)]
auto=[r for r in rows if any(t for t in r['trig'] if 'manualTrigger' not in t)]
print(f'\nof the {N}, workflows with a non-manual (automatic) trigger: {len(auto)}')
autonone=[r for r in auto if not (r['retry'] or r['eb'] or r['et'])]
print(f'   ...and no retry/error-branch/errorTrigger: {len(autonone)}')
