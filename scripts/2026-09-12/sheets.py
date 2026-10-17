import json, collections
groups=json.load(open('groups.json')); files=[v[0] for v in groups.values()]
ops=collections.Counter(); match=collections.Counter(); mcols=collections.Counter()
upsert_nodes=0; upsert_wf=set(); with_match=0; tv=collections.Counter()
noop_null=0
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    for n in d.get('nodes') or []:
        if not isinstance(n,dict) or (n.get('type') or '')!='n8n-nodes-base.googleSheets': continue
        p=n.get('parameters') or {}
        op=p.get('operation')
        ops[str(op)]+=1
        if op is None: noop_null+=1
        if op in ('appendOrUpdate','upsert'):
            upsert_nodes+=1; upsert_wf.add(f); tv[str(n.get('typeVersion'))]+=1
            cols=p.get('columns')
            mc=None
            if isinstance(cols,dict): mc=cols.get('matchingColumns')
            if mc is None: mc=p.get('columnToMatchOn') or p.get('key')
            if mc: 
                with_match+=1
                mcols[json.dumps(mc)[:40]]+=1
            else:
                match['NO matching column specified']+=1
print('googleSheets nodes total:',sum(ops.values()))
print('operations:'); [print(f'   {a:20}{b}') for a,b in ops.most_common(10)]
print(f'\nappendOrUpdate/upsert nodes: {upsert_nodes} across {len(upsert_wf)} workflows')
print('  typeVersions:',dict(tv))
print('  with a matching column   :',with_match)
print('  without                  :',match["NO matching column specified"])
print('  top matching columns:'); [print(f'     {a:42}{b}') for a,b in mcols.most_common(8)]
