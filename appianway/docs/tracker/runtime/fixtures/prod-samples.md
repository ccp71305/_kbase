# Production booking files: what splitter really receives (read 2026-11-20)

← [Runtime index](../README.md) · [Tracker home](../../README.md)

Read-only queries of production's inbound bucket `inttra2-pr-inbound-pickup` (in the QA account `642960533737`, QATeam role), asked for by Arijit on 2026-11-20. Keys and sizes come from `list-objects-v2`; the document counts come from streaming each sampled file through a counter (`aws s3 cp s3://… - | classify`). **No production content was saved, copied or sent anywhere**; only the counts and the envelope structure below. Production content is not used as test input: tests use QA's own files ([qa-iftmbf-bk3-minmsc](qa-iftmbf-bk3-minmsc/README.md), [qa-iftmbc-2docs-sa-confirm-max](qa-iftmbc-2docs-sa-confirm-max/README.md)), or files built from them.

## Summary

| | IFTMBF (booking requests, `300_IFTMBF/`) | IFTMBC (booking confirmations, `301_IFTMBC/`) |
|---|---|---|
| Files on 2026-11-19 | 15,521 | 211,768 |
| Zips | none | none |
| Formats in the sample | EDIFACT 109, XML 29, ANSI 12 (150 files, 41 senders, up to 4 per sender) | EDIFACT (`IFTMBC:D:99B:UN:2.0`, some `IFTMBC:D:99B:UN`), a few XML |
| Documents per file | **always 1** (also the 25 largest, up to 55 KB: single XML or EDIFACT bookings) | **1 for most carriers; batches for some** (below) |
| Envelope | one `UNB`, no `UNG` | one `UNB`; `UNG` groups only in MSC's large batches |

"IFTMBC2" is not a separate folder: the `UNH` version (`IFTMBC:D:99B:UN:2.0`) is in the same `301_IFTMBC/` files.

## IFTMBC batches (carriers that send several confirmations per file)

| Carrier folder | Example size | Confirmations (`UNH`) | `UNG` groups | Files ≥ 5 KB that day |
|---|---|---|---|---|
| `mram5166` (MSC, `MSCU_IFTMBC_…EDI`) | 11.4 MB, 11.4 MB, 11.0 MB | **3,479, 3,460, 3,284** | **26, 11, 22** | 242 |
| `mram5166` | 103 KB | 51 | 0 | |
| `a1917831` | 6 KB, 53 KB, 81 KB, 192 KB | 4, 37, 55, 135 | 0 | 16 |
| `hbef5169` | 45 KB, 89 KB, 172 KB | 8, 13, 27 | 0 | 1,196 |
| `cnaj5171`, `mram5167`, `z3328020`, `CA2000`, most others | 0.3–50 KB | 1 | 0 | `cnaj5171` 6,801 (single, large) |

Busiest IFTMBC folders that day: `cnaj5171` 125,680 files, `mram5167` 60,886, `z3328020` 11,845, `o0448461` 6,988, `c1518246` 1,391, `hbef5169` 1,209.

## What it means for splitter and its tests

- **Splitting is a production path, for confirmations.** Multi-document IFTMBC files are routine (thousands of confirmations a day in batches), so the splitting path matters as much as the single-document one.
- **MSC's 11 MB batches with 11–26 `UNG` groups** are exactly where [KD-8](../../known-defects.md#kd-8) applies (groups routed in parallel share the parent's control number), and where [KD-9](../../known-defects.md#kd-9) writes 11 MB per file to the log. Both stay unfixed ([D43](../../decisions.md#d43)); the facts are here for when someone asks.
- **Memory:** splitter reads the whole file into memory (ISO-8859-1 string) and parses it; an 11 MB, 3,479-document file is the realistic upper bound to keep in mind for the local runs.
- **No zips**, so dispatcher's zip path is not exercised by these two formats.
- **For the runtime tests:** single document → QA's IFTMBF trace; splitting → QA's two-confirmation IFTMBC trace. A multi-group test file, if wanted, can be built from QA's own IFTMBC messages (several `UNG` groups in one `UNB`), never from production content.

## Commands (all read only)

```bash
P=642960533737_INTTRA2-QATeam
aws s3api list-objects-v2 --profile $P --bucket inttra2-pr-inbound-pickup --prefix 301_IFTMBC/20261119/ \
    --query 'Contents[].[Key,Size,LastModified]' --output text > iftmbc.tsv            # keys and sizes only
aws s3 cp --profile $P --quiet "s3://inttra2-pr-inbound-pickup/<key>" - | python -I classify2.py   # counts, nothing saved
```

`classify2.py` prints the format and the `UNB` / `UNG` / `UNH` (or `ISA` / `GS` / `ST`) counts and the `UNH` message versions; it prints no content. The top-level folder listing (`--delimiter /`) scans the whole bucket and was stopped; the folder names were taken from QA's dispatcher mapping instead.
