import json, collections, re
groups=json.load(open('groups.json')); files=[v[0] for v in groups.values()]
tot_keys=0; key_match_name=0; key_match_id=0; key_orphan=0
tgt=0; tgt_match=0; tgt_phantom=0
wf_any_conn=0; wf_all_orphan=0; wf_phantom=0
for f in files:
    d=json.load(open(f,encoding='utf-8'))
    nodes=[n for n in (d.get('nodes') or []) if isinstance(n,dict)]
    names={n.get('name') for n in nodes}; ids={n.get('id') for n in nodes}
    c=d.get('connections') or {}
    if not isinstance(c,dict) or not c: continue
    wf_any_conn+=1
    orphan_here=0; ph=False
    for k,v in c.items():
        tot_keys+=1
        if k in names: key_match_name+=1
        elif k in ids: key_match_id+=1
        else: key_orphan+=1; orphan_here+=1
        if not isinstance(v,dict): continue
        for kind,branches in v.items():
            for br in (branches or []):
                for e in (br or []):
                    if not isinstance(e,dict): continue
                    tgt+=1
                    t=e.get('node')
                    if t in names or t in ids: tgt_match+=1
                    else:
                        tgt_phantom+=1
                        if isinstance(t,str) and t.startswith('error-handler-'): ph=True
    if orphan_here==len(c): wf_all_orphan+=1
    if ph: wf_phantom+=1
print('workflows with a non-empty connections object:',wf_any_conn,'of',len(files))
print()
print('connection SOURCE keys       :',tot_keys)
print('   match a node name         :',key_match_name)
print('   match a node id           :',key_match_id)
print('   match NOTHING (orphan)    :',key_orphan, f'({100*key_orphan/tot_keys:.1f}%)')
print()
print('connection TARGETS           :',tgt)
print('   match a real node         :',tgt_match)
print('   phantom                   :',tgt_phantom, f'({100*tgt_phantom/tgt:.1f}%)')
print()
print('workflows where EVERY connection key is an orphan :',wf_all_orphan)
print('workflows containing "error-handler-*" phantoms   :',wf_phantom)
