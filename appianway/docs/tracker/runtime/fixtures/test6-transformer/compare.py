"""Compares test 6's outputs of v1 and the new build (v2), case by case.

Pairs each v1 message with its v2 twin by (queue, case, contextCode, targetId, formatCode), where case is the marked
root without the build (bf, bc, ob-fa, ob-bc). Then compares, after normalizing:
  - the routed MetaData: ids (messageId, workflowId, random object names), the build in the root, wall-clock times
  - the document it names: bytes; for differing outbound documents, a diff after masking digits runs (control numbers,
    dates and times differ by design: each build drew its own block of the QA sequence)
  - its headers (content type, length, user metadata)
  - the lineage events under the case's root (sorted, normalized the same way, incl. the timeTakenFor... tokens)
Usage: python -I compare.py   (in rt6/, after collect.sh)
"""
import difflib, glob, json, os, re

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")


def norm_text(s):
    s = re.sub(r"wi01124532-rt-tf-v[12]-", "wi01124532-rt-tf-vX-", s)
    s = UUID.sub("<uuid>", s)
    s = TIME.sub("<time>", s)
    s = re.sub(r'("timeTakenFor\w*"\s*:\s*")\d+"', r'\1<ms>"', s)
    s = re.sub(r"(timeTakenFor\w*\\?\"\s*:\s*\\?\")\d+", r"\1<ms>", s)
    return s


def norm_json(obj):
    return json.loads(norm_text(json.dumps(obj, sort_keys=True)))


def case_of(root):
    return re.sub(r"^wi01124532-rt-tf-(v[12])-", "", root), re.search(r"-(v[12])-", root).group(1)


msgs = {}
for f in sorted(glob.glob("out/msg/*.json")):
    q = os.path.basename(f).split("-")[0]
    m = json.load(open(f, encoding="utf-8"))
    case, build = case_of(m["rootWorkflowId"])
    p = m.get("projections", {})
    key = (q, case, p.get("contextCode"), p.get("targetId"), p.get("formatCode"), p.get("integrationProfileFormatId"))
    msgs.setdefault(key, {}).setdefault(build, []).append(m)

ok = True
for key in sorted(msgs, key=str):
    pair = msgs[key]
    v1s, v2s = pair.get("v1", []), pair.get("v2", [])
    label = f"{key[0]:<18} {key[1]:<6} {key[2] or '-':<15} target={key[3] or '-'}"
    if len(v1s) != len(v2s):
        print(f"DIFF  {label}: {len(v1s)} v1 vs {len(v2s)} v2 messages"); ok = False; continue
    # several identical twins (the two confirmations): pair them by the document's content
    def body(m):
        return open("out/obj/" + m["fileName"].replace("/", "__"), "rb").read()
    v1s.sort(key=body); v2s.sort(key=body)
    for a, b in zip(v1s, v2s):
        res = []
        res.append("MetaData " + ("same" if norm_json(a) == norm_json(b) else "DIFF"))
        da, db = body(a), body(b)
        if da == db:
            res.append(f"document same ({len(da)} B)")
        else:
            ma = re.sub(rb"\d+", b"#", da); mb = re.sub(rb"\d+", b"#", db)
            res.append(f"document {'same except digits' if ma == mb else 'DIFF'} ({len(da)} vs {len(db)} B)")
            if ma == mb:
                ta, tb = da.decode("latin-1"), db.decode("latin-1")
                sa = set(re.findall(r"\d+", ta)) ^ set(re.findall(r"\d+", tb))
                res.append(f"differing numbers: {sorted(sa)[:12]}")
        ha = json.load(open("out/obj/" + a["fileName"].replace("/", "__") + ".head.json"))
        hb = json.load(open("out/obj/" + b["fileName"].replace("/", "__") + ".head.json"))
        res.append("headers " + ("same" if norm_json(ha) == norm_json(hb) else f"DIFF {ha} vs {hb}"))
        if any("DIFF" in r for r in res):
            ok = False
            if "MetaData DIFF" in res:
                ja, jb = (json.dumps(norm_json(x), indent=1, sort_keys=True).splitlines() for x in (a, b))
                res.append("\n      " + "\n      ".join(difflib.unified_diff(ja, jb, "v1", "v2", n=0, lineterm="")))
        print(f"{'OK  ' if not any('DIFF' in r for r in res) else 'DIFF'}  {label}: " + "; ".join(res))

# events per case
print()
for case in ("bf", "bc", "ob-fa", "ob-bc"):
    ev = {}
    for build in ("v1", "v2"):
        ev[build] = sorted(json.dumps(norm_json(json.load(open(f, encoding="utf-8"))), sort_keys=True)
                           for f in glob.glob(f"out/events/wi01124532-rt-tf-{build}-{case}/*.json"))
    same = ev["v1"] == ev["v2"]
    ok &= same
    print(f"{'OK  ' if same else 'DIFF'}  events {case:<6}: {len(ev['v1'])} v1, {len(ev['v2'])} v2, {'identical' if same else 'differ'}")
    if not same:
        for x, y in zip(ev["v1"], ev["v2"]):
            if x != y:
                for l in difflib.unified_diff(json.dumps(json.loads(x), indent=1).splitlines(),
                                              json.dumps(json.loads(y), indent=1).splitlines(), "v1", "v2", n=0, lineterm=""):
                    print("      " + l)
print("\nRESULT:", "all identical (after normalization)" if ok else "differences above")
