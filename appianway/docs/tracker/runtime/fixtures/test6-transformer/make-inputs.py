"""Makes transformer's six test-6 inputs from splitter's three test-5 routed messages (new build).

For each build (v1, v2) and each routed message: the same MetaData with
  rootWorkflowId = parentWorkflowId = wi01124532-rt-tf-<build>-<case>   (case = bf | bc)
  fileName       = <that root>/<the object's name>                     (the marked copy, made by copy-object)
  messageId, workflowId = new random UUIDs
Everything else (projections: IPF, context, format, partner) is unchanged.
Writes input-<build>-<case>-<name>.json and copies.tsv (source key <TAB> target key) for the copy-object loop.
Usage: python -I make-inputs.py <routed dir> <out dir>
"""
import json, os, sys, uuid

routed_dir, out_dir = sys.argv[1], sys.argv[2]
copies = []
for build in ("v1", "v2"):
    for f in sorted(os.listdir(routed_dir)):
        if not f.startswith("v2-"):          # splitter's new-build messages only (identical to v1's anyway)
            continue
        md = json.load(open(os.path.join(routed_dir, f), encoding="utf-8"))
        case = f.split("-")[1]                # bf | bc
        name = md["fileName"].split("/", 1)[1]
        root = f"wi01124532-rt-tf-{build}-{case}"
        copies.append((md["fileName"], f"{root}/{name}"))
        md.update(messageId=str(uuid.uuid4()), workflowId=str(uuid.uuid4()),
                  rootWorkflowId=root, parentWorkflowId=root, fileName=f"{root}/{name}")
        out = os.path.join(out_dir, f"input-{build}-{case}-{name[:8]}.json")
        json.dump(md, open(out, "w", encoding="utf-8"), indent=2)
        print(out, md["fileName"])
with open(os.path.join(out_dir, "copies.tsv"), "w", encoding="utf-8", newline="\n") as t:
    for s, d in sorted(set(copies)):
        t.write(f"{s}\t{d}\n")
