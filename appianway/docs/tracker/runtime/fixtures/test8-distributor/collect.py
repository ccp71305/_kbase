"""Runtime test 8: collect what each build delivered (read only) and compare v1, the new build and QA's own run.

Usage (credentials exported): python -I collect.py <run folder> <repo>
Reads the "has been copied to" lines of run-<build>.log, gets each delivered object's headers and content, the
lineage events under each marked root, and QA's own deliveries of the same documents on 2026-11-19 (keys from QA's
events). Writes out/ and prints the comparison.
"""
import glob, json, os, re, subprocess, sys

run, repo = sys.argv[1], sys.argv[2]
P = '642960533737_INTTRA2-QATeam'
OUT_B = 'inttra2-qa-outbound-delivery'
WS = 'inttra2-qa-workspace'
os.makedirs(os.path.join(run, 'out'), exist_ok=True)


def aws(*args):
    return subprocess.run(['aws', '--profile', P, *args], capture_output=True, text=True, check=True).stdout


def obj(bucket, key, name):
    head = json.loads(aws('s3api', 'head-object', '--bucket', bucket, '--key', key, '--query',
                          '{ContentType:ContentType,ContentLength:ContentLength,Metadata:Metadata}', '--output', 'json'))
    path = os.path.join(run, 'out', name)
    aws('s3', 'cp', 's3://%s/%s' % (bucket, key), path, '--only-show-errors')
    return head, open(path, 'rb').read()


copied = re.compile(r'File (\S+?)/(\S+) has been copied to (\S+?)/(\S+)$')
result = {}
for build in ('v1', 'v2'):
    rows = []
    for line in open(os.path.join(run, 'run-%s.log' % build), encoding='utf-8', errors='replace'):
        m = copied.search(line.strip())
        if m:
            src, dst = m.group(2), m.group(4)
            case = src.split('/')[0].split('-')[-1]
            kind = 'archive' if '/outbound_archive/' in dst else 'delivery'
            head, body = obj(m.group(3), dst, '%s-%s-%s' % (build, case, kind))
            rows.append({'case': case, 'kind': kind, 'key': dst, 'head': head, 'body': body})
    events = {}
    roots = {}
    for line in open(os.path.join(run, 'messages-%s.jsonl' % build), encoding='utf-8'):
        m = json.loads(line)
        roots[m['fileName'].split('/')[0].split('-')[-1]] = m['rootWorkflowId']
    for case in ('fa', '301', 'opt'):
        root = roots[case]   # in the 301 trace the root is also the parent: marked "-parent"
        keys = aws('s3', 'ls', 's3://%s/eventstore/2026-11-20/%s/' % (WS, root)).split()
        events[case] = [k for k in keys if k.endswith('.json') or len(k) > 30]
    result[build] = {'rows': rows, 'events': events}

norm = lambda s, b: re.sub(r'wi01124532-rt-dist-%s-' % b, 'wi01124532-rt-dist-X-', s)
key_shape = lambda k: re.sub(r'\d{17}_\d{10}', '<time>_<random>', re.sub(r'/\d{8}/', '/<date>/', k))
lines = []
for r1, r2 in zip(sorted(result['v1']['rows'], key=lambda r: (r['case'], r['kind'])),
                  sorted(result['v2']['rows'], key=lambda r: (r['case'], r['kind']))):
    same_body = r1['body'] == r2['body']
    m1 = json.loads(norm(json.dumps(r1['head']['Metadata'], sort_keys=True), 'v1'))
    m2 = json.loads(norm(json.dumps(r2['head']['Metadata'], sort_keys=True), 'v2'))
    lines.append('%-4s %-8s key %s | body %s (%d B) | content type %s / %s | metadata %s' % (
        r1['case'], r1['kind'], 'same shape' if key_shape(r1['key']) == key_shape(r2['key']) else 'DIFFER %s %s' % (r1['key'], r2['key']),
        'identical' if same_body else 'DIFFER', len(r1['body']), r1['head']['ContentType'], r2['head']['ContentType'],
        'identical' if m1 == m2 else 'DIFFER v1=%s v2=%s' % (m1, m2)))
    if r1['case'] == 'opt':
        lines.append('     opt metadata (new build): %s' % r2['head']['Metadata'])
for case in ('fa', '301', 'opt'):
    lines.append('events %-4s v1 %d, new %d' % (case, len(result['v1']['events'][case]), len(result['v2']['events'][case])))

# QA's own deliveries of the same documents (2026-11-19), keys from QA's events
for trace, case in (('qa-iftmbf-bk3-minmsc', 'fa'), ('qa-iftmbc-2docs-sa-confirm-max', '301')):
    source = json.load(open(os.path.join(repo, 'docs/tracker/runtime/fixtures', trace, 'input-distributor.json'),
                            encoding='utf-8'))
    qa_key = None
    for f in glob.glob(os.path.join(repo, 'docs/tracker/runtime/fixtures', trace, 'events', 'distributor-*.json')):
        e = json.load(open(f, encoding='utf-8'))
        if (e.get('eventContent') or {}).get('fileName') == source['fileName'] or \
                e.get('workflowId') == source['workflowId']:
            qa_key = (e.get('tokens') or {}).get('s3DeliveryFileName')
    mine = next(r for r in result['v2']['rows'] if r['case'] == case and r['kind'] == 'delivery')
    head, body = obj(OUT_B, qa_key, 'qa-%s-delivery' % case)
    ids = {source['rootWorkflowId']: 'R', source['parentWorkflowId']: 'P', source['workflowId']: 'W'}
    marks = {'wi01124532-rt-dist-v2-%s' % case: 'R', 'wi01124532-rt-dist-v2-%s-parent' % case: 'P',
             'wi01124532-rt-dist-v2-%s-wf' % case: 'W'}
    if source['rootWorkflowId'] == source['parentWorkflowId']:
        ids[source['rootWorkflowId']] = 'P'
    qm = {k: ids.get(v, v) for k, v in head['Metadata'].items()}
    mm = {k: marks.get(v, v) for k, v in mine['head']['Metadata'].items()}
    lines.append('QA %-3s %s | body %s | content type %s / %s | metadata %s' % (
        case, 'same key shape' if key_shape(qa_key) == key_shape(mine['key']) else 'key DIFFER %s' % qa_key,
        'identical' if body == mine['body'] else 'DIFFER', head['ContentType'], mine['head']['ContentType'],
        'identical' if qm == mm else 'DIFFER qa=%s new=%s' % (qm, mm)))
open(os.path.join(run, 'compare.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
