import json, collections
groups=json.load(open('groups.json')); files=[v[0] for v in groups.values()]
N=len(files); S=collections.Counter()
second_branch_nodes=0; errflag_with_2nd=0
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    nodes=[n for n in (d.get('nodes') or []) if isinstance(n,dict)]
    conns=d.get('connections') or {}
    retry=errout=suppress=legacy=False
    for n in nodes:
        oe=n.get('onError')
        if n.get('retryOnFail') is True: retry=True
        if oe=='continueErrorOutput':
            errout=True
            c=conns.get(n.get('id')) or {}
            m=c.get('main') or []
            if len(m)>1 and any(br for br in m[1:]): errflag_with_2nd+=1
        if oe=='continueRegularOutput': suppress=True
        if n.get('continueOnFail') is True: legacy=True
        c=conns.get(n.get('id')) or {}
        m=c.get('main') or []
        if len(m)>1 and any(br for br in m[1:]): second_branch_nodes+=1
    et=any((n.get('type') or '').endswith('errorTrigger') for n in nodes)
    if retry: S['retryOnFail on >=1 node']+=1
    if errout: S['onError=continueErrorOutput']+=1
    if suppress: S['onError=continueRegularOutput']+=1
    if legacy: S['continueOnFail=true (legacy)']+=1
    if et: S['contains an errorTrigger']+=1
    any_signal = retry or errout or suppress or legacy or et
    real = retry or errout or et
    if not any_signal: S['** NO error-handling field of any kind **']+=1
    if not real: S['** no retry / error-branch / errorTrigger **']+=1
    if (suppress or legacy) and not real: S['suppression only (errors silently swallowed)']+=1
print('UNIQUE WORKFLOWS:',N,'\n')
for k,v in S.most_common(): print(f'{v:6}  {100*v/N:5.1f}%  {k}')
print(f'\nnodes with a 2nd+ main branch (id-keyed): {second_branch_nodes}')
print(f'  of which the node sets continueErrorOutput: {errflag_with_2nd}')
