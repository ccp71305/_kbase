"""Runtime test 8: the lineage events of v1 and the new build, normalized (marks, times, ids, random file names)."""
import glob, json, re


def load(b):
    out = {}
    for f in glob.glob('out/events/%s-*/*' % b):
        t = json.dumps(json.load(open(f, encoding='utf-8')), sort_keys=True)
        t = t.replace('wi01124532-rt-dist-%s-' % b, 'wi01124532-rt-dist-X-')
        t = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+', '<time>', t)
        t = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', t)
        t = re.sub(r'\d{17}_\d{10}', '<time>_<random>', t)
        t = re.sub(r'/2026112\d/', '/<date>/', t)
        d = json.loads(t)
        out.setdefault((d.get('component'), d.get('type'), d.get('subType'), d.get('workflowId')), []).append(d)
    return out


a, b = load('v1'), load('v2')
print('events: v1 %d, new %d, groups %d / %d: %s' % (sum(map(len, a.values())), sum(map(len, b.values())), len(a), len(b),
                                                     'identical' if a == b else 'DIFFER'))
for k in sorted(set(a) | set(b), key=str):
    if a.get(k) != b.get(k):
        x, y = (a.get(k) or [{}])[0], (b.get(k) or [{}])[0]
        print(' ', k, {f: (str(x.get(f))[:100], str(y.get(f))[:100]) for f in set(x) | set(y) if x.get(f) != y.get(f)})
print(sorted({k[:3] for k in a}, key=str))
