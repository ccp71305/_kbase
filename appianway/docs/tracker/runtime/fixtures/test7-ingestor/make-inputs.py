"""Runtime test 7 inputs: real QA lineage events with every workflow id replaced by a marked one.

Usage: python -I make-inputs.py <repo> <outdir>
Writes, per build (v1, v2): messages-<b>.jsonl (one SNS envelope per line, in send order), ids-<b>.json (original
workflow id -> marked id), annotations key; and annotations.json (the failed run's annotations object).
"""
import copy, glob, json, os, sys

repo, out = sys.argv[1], sys.argv[2]
fx = os.path.join(repo, 'docs/tracker/runtime/fixtures')
TOPIC = 'arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event'


def events(trace):
    es = [json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(fx, trace, 'events', '*.json'))]
    return sorted(es, key=lambda e: (e['timestamp'], e['eventId']))


def compact(o):
    return json.dumps(o, separators=(',', ':'), ensure_ascii=False)


def envelope(n, evs):
    return compact({'Type': 'Notification', 'MessageId': 'wi01124532-rt-ing-%04d' % n, 'TopicArn': TOPIC,
                    'Message': compact(evs), 'Timestamp': '2026-11-20T19:00:00.000Z', 'SignatureVersion': '1'})


booking = events('qa-iftmbf-bk3-minmsc')
confirm = events('qa-iftmbc-2docs-sa-confirm-max')
workflows = []
for e in booking + confirm:
    for k in ('rootWorkflowId', 'parentWorkflowId', 'workflowId'):
        if e.get(k) and e[k] not in workflows:
            workflows.append(e[k])

for build in ('v1', 'v2'):
    ids = {w: 'wi01124532-rt-ing-%s-%02d' % (build, i + 1) for i, w in enumerate(workflows)}

    def marked(e):
        text = compact(e)
        for original, mark in ids.items():
            text = text.replace(original, mark)
        return json.loads(text)

    lines = [envelope(i + 1, [marked(e)]) for i, e in enumerate(booking)]
    lines.append(envelope(100, [marked(e) for e in confirm]))
    base = next(e for e in booking if e['component'] == 'dispatcher' and e['type'] == 'closeRun')
    fail = copy.deepcopy(marked(base))
    wf = 'wi01124532-rt-ing-%s-fail' % build
    fail['eventId'] = 'wi01124532-rt-ing-%s-fail-event' % build
    fail['status'] = 'failure'
    for k in ('workflowId', 'parentWorkflowId', 'rootWorkflowId'):
        fail[k] = wf
        fail['eventContent'][k] = wf
    fail['eventContent'].update({'exitStatus': 'failure', 'bucket': 'inttra2-qa-workspace',
                                 'fileName': wf + '/annotations'})
    fail.pop('annotations', None)
    lines.append(envelope(200, [fail]))
    ids[wf] = wf
    with open(os.path.join(out, 'messages-%s.jsonl' % build), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    json.dump(ids, open(os.path.join(out, 'ids-%s.json' % build), 'w', encoding='utf-8'), indent=1)

json.dump({'Annotations': [{'type': 'error', 'code': '/exception/dispatcher/business/messagePipeline/unableToResolveMftId',
                            'value': 'wi01124532 runtime test 7: annotations of a failed run'}]},
          open(os.path.join(out, 'annotations.json'), 'w', encoding='utf-8'))
print(len(booking), len(confirm), 'workflows', len(workflows), 'messages per build', len(lines))
