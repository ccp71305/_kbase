"""The new build's documents vs QA's own indexing of the same real events (2026-11-19), marks mapped back."""
import json

ids = json.load(open('ids-v2.json'))                      # original -> marked
back = sorted(((m, o) for o, m in ids.items() if m != o), key=lambda mo: -len(mo[0]))


def original(obj):
    text = json.dumps(obj, sort_keys=True)
    for mark, orig in back:
        text = text.replace(mark, orig)
    return json.loads(text)


def hits(name):
    return json.load(open('out/%s.json' % name))['hits']['hits']


mine = {h['_source']['eventId']: original(h['_source']) for h in hits('events-v2')
        if not h['_source']['eventId'].startswith('wi01124532')}
qa = {}
for h in hits('events-qa'):
    if not h['_source'].get('workflowId', '').startswith('wi01124532'):
        qa.setdefault(h['_source']['eventId'], []).append((h['_index'], json.loads(json.dumps(h['_source'], sort_keys=True))))

lines = []
same = [k for k in mine if k in qa and len(qa[k]) == 1 and qa[k][0][1] == mine[k]]
differ = [k for k in mine if k not in same]
lines.append('events: %d real events in the new build; QA indexed %d of them (%s); identical: %d; differ: %d'
             % (len(mine), len([k for k in mine if k in qa]), sorted({i for v in qa.values() for i, _ in v}), len(same), len(differ)))
for k in differ[:5]:
    x = qa.get(k, [(None, {})])[0][1]
    y = mine[k]
    lines.append('  %s: %s' % (k, {f: (str(x.get(f))[:90], str(y.get(f))[:90]) for f in set(x) | set(y) if x.get(f) != y.get(f)}))

aggs = {original(h['_id']): original(h['_source']) for h in hits('aggs-v2')}
for h in sorted(hits('aggs-qa'), key=lambda h: h['_id']):
    src = json.loads(json.dumps(h['_source'], sort_keys=True))
    m = aggs.get(h['_id'], {})
    d = {f: (src.get(f), m.get(f)) for f in set(src) | set(m) if src.get(f) != m.get(f)}
    lines.append('aggregate %s (QA %s): %s' % (h['_id'][:8], h['_index'], 'identical' if not d else d))
print('\n'.join(lines))
