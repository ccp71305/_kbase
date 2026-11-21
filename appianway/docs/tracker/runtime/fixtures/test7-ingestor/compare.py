import json, sys
def hits(f): return json.load(open('out/%s.json' % f))['hits']['hits']
def norm(text, b): return text.replace('wi01124532-rt-ing-%s' % b, 'wi01124532-rt-ing-X')
def key_events(hs, b):
    out = {}
    for h in hs:
        s = json.loads(norm(json.dumps(h['_source'], sort_keys=True), b))
        out.setdefault(s['eventId'], []).append(s)
    return out
lines = []
e1, e2 = key_events(hits('events-v1'), 'v1'), key_events(hits('events-v2'), 'v2')
lines.append('events: v1 %d docs / %d eventIds, v2 %d docs / %d eventIds' % (sum(map(len, e1.values())), len(e1), sum(map(len, e2.values())), len(e2)))
diff = [k for k in set(e1) | set(e2) if e1.get(k) != e2.get(k)]
lines.append('events v1 vs v2: %s' % ('identical' if not diff else 'DIFFER: %s' % diff[:5]))
a1 = {norm(h['_id'], 'v1'): json.loads(norm(json.dumps(h['_source'], sort_keys=True), 'v1')) for h in hits('aggs-v1')}
a2 = {norm(h['_id'], 'v2'): json.loads(norm(json.dumps(h['_source'], sort_keys=True), 'v2')) for h in hits('aggs-v2')}
adiff = [k for k in set(a1) | set(a2) if a1.get(k) != a2.get(k)]
lines.append('aggregates: v1 %d, v2 %d; v1 vs v2: %s' % (len(a1), len(a2), 'identical' if not adiff else 'DIFFER: %s' % adiff))
for k in adiff:
    x, y = a1.get(k, {}), a2.get(k, {})
    lines.append('  %s: %s' % (k, {f: (x.get(f), y.get(f)) for f in set(x) | set(y) if x.get(f) != y.get(f)}))
# new build vs QA's own indexing of the same real events (workflow marks mapped back)
back = {v: k for k, v in json.load(open('ids-v2.json')).items()}
def unmark(text):
    for m, o in sorted(back.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(m, o)
    return text
qa = {}
for h in hits('events-qa'):
    if h['_source'].get('workflowId', '').startswith('wi01124532'):
        continue
    qa.setdefault(h['_source']['eventId'], []).append(json.loads(json.dumps(h['_source'], sort_keys=True)))
mine = {k: [json.loads(unmark(json.dumps(s, sort_keys=True)).replace('wi01124532-rt-ing-X', 'wi01124532-rt-ing-v2')) for s in v] for k, v in e2.items() if not k.startswith('wi01124532')}
qdiff = [k for k in mine if qa.get(k) != mine[k]]
lines.append('events new vs QA run: QA has %d of the %d real events (%d docs); %s' % (len([k for k in mine if k in qa]), len(mine), sum(map(len, qa.values())), 'identical' if not qdiff else '%d differ: %s' % (len(qdiff), qdiff[:6])))
for k in qdiff[:3]:
    x, y = (qa.get(k) or [{}])[0], mine[k][0]
    lines.append('  %s: %s' % (k, {f: (str(x.get(f))[:80], str(y.get(f))[:80]) for f in set(x) | set(y) if x.get(f) != y.get(f)}))
qa_aggs = {h['_id']: (h['_index'], h['_source']) for h in hits('aggs-qa')}
lines.append('QA aggregates found: %s' % sorted((k[:8], i) for k, (i, _) in qa_aggs.items()))
for k, (i, src) in sorted(qa_aggs.items()):
    m = json.loads(unmark(json.dumps(a2.get(back_k, {}), sort_keys=True))) if (back_k := next((mk for mk, o in back.items() if o == k), None)) else {}
    m = json.loads(unmark(json.dumps(a2.get(back_k.replace('-v2', '-X') if back_k else '', {}), sort_keys=True)))
    d = {f: (str(src.get(f))[:60], str(m.get(f))[:60]) for f in set(src) | set(m) if src.get(f) != m.get(f)}
    lines.append('  agg %s (%s): %s' % (k[:8], i, 'identical' if not d else d))
print('\n'.join(lines))
