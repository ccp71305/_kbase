"""Golden inputs for ingestor from the two QA traces. Usage: python -I make-golden.py <repo>"""
import json, glob, os, sys, copy
repo = sys.argv[1]
fx = os.path.join(repo, 'docs/tracker/runtime/fixtures')
out = os.path.join(repo, 'ingestor/src/test/resources-functional/golden')
os.makedirs(out, exist_ok=True)
TOPIC = 'arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event'
def events(trace):
    es = [json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(fx, trace, 'events', '*.json'))]
    return sorted(es, key=lambda e: (e['timestamp'], e['eventId']))
def compact(o): return json.dumps(o, separators=(',', ':'), ensure_ascii=False)
def envelope(n, evs):
    return compact({'Type': 'Notification', 'MessageId': '00000000-0000-0000-0000-%012d' % n, 'TopicArn': TOPIC,
                    'Message': compact(evs), 'Timestamp': '2026-11-19T17:55:40.000Z', 'SignatureVersion': '1'})
booking = events('qa-iftmbf-bk3-minmsc')
confirm = events('qa-iftmbc-2docs-sa-confirm-max')
with open(os.path.join(out, 'booking-trace.sns.txt'), 'w', encoding='utf-8', newline='\n') as f:
    for i, e in enumerate(booking, 1): f.write(envelope(i, [e]) + '\n')
with open(os.path.join(out, 'confirm-trace.sns.json'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(envelope(100, confirm) + '\n')
base = next(e for e in booking if e['component'] == 'dispatcher' and e['type'] == 'closeRun')
def failure(n, wf, key):
    e = copy.deepcopy(base)
    e['eventId'] = 'golden-event-%d' % n
    e['status'] = 'failure'
    for k in ('workflowId', 'parentWorkflowId', 'rootWorkflowId'): e[k] = wf; e['eventContent'][k] = wf
    e['eventContent'].update({'exitStatus': 'failure', 'bucket': 'workspace', 'fileName': key})
    e.pop('annotations', None)
    return envelope(200 + n, [e])
open(os.path.join(out, 'failure-annotations.sns.json'), 'w', encoding='utf-8', newline='\n').write(failure(1, 'golden-failed-wf', 'golden-failed-wf/annotations') + '\n')
open(os.path.join(out, 'failure-annotations-missing.sns.json'), 'w', encoding='utf-8', newline='\n').write(failure(2, 'golden-failed-wf-2', 'golden-failed-wf-2/missing') + '\n')
open(os.path.join(out, 'annotations.json'), 'w', encoding='utf-8', newline='\n').write(compact({'Annotations': [
    {'type': 'error', 'code': 'E-STRUCT-01', 'value': 'Segment UNH missing'},
    {'type': 'warning', 'code': 'W-01', 'value': 'Unknown qualifier'}]}) + '\n')
print(len(booking), len(confirm), sorted({(e['component']) for e in booking + confirm}))
