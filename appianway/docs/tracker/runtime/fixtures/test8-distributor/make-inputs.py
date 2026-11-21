"""Runtime test 8 inputs: the two real QA distributor inputs, workflow ids marked, each on its own marked copy.

Usage: python -I make-inputs.py <repo> <outdir>
Writes messages-<build>.jsonl (one MetaData per line) and copies-<build>.tsv (source key, marked key) per build.
"""
import copy, json, os, sys, uuid

repo, out = sys.argv[1], sys.argv[2]
fx = os.path.join(repo, 'docs/tracker/runtime/fixtures')


def load(trace):
    return json.load(open(os.path.join(fx, trace, 'input-distributor.json'), encoding='utf-8'))


cases = {'fa': load('qa-iftmbf-bk3-minmsc'), '301': load('qa-iftmbc-2docs-sa-confirm-max')}
cases['opt'] = copy.deepcopy(cases['fa'])
for k in ('contextCode', 'outboundEdiId'):
    cases['opt']['projections'].pop(k)

for build in ('v1', 'v2'):
    lines, copies = [], []
    for name, original in cases.items():
        m = copy.deepcopy(original)
        root = 'wi01124532-rt-dist-%s-%s' % (build, name)
        ids = {original['rootWorkflowId']: root, original['parentWorkflowId']: root + '-parent',
               original['workflowId']: root + '-wf'}
        text = json.dumps(m)
        for o, n in ids.items():
            text = text.replace(o, n)
        m = json.loads(text)
        m['messageId'] = str(uuid.uuid5(uuid.NAMESPACE_URL, root))
        source = original['fileName']
        m['fileName'] = root + '/' + source.split('/')[-1]
        copies.append((source, m['fileName']))
        lines.append(json.dumps(m, separators=(',', ':')))
    open(os.path.join(out, 'messages-%s.jsonl' % build), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    open(os.path.join(out, 'copies-%s.tsv' % build), 'w', encoding='utf-8', newline='\n').write(
        ''.join('%s\t%s\n' % c for c in copies))
print('cases', list(cases))
