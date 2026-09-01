# Visibility Prod Fix — Post-Rollout Verification / Checkout (2026-08-24)

> Extracted from `2026-08-21-vis-prod-issue.md` §16. Cross-references to other sections (e.g. §11.5,
> §12.1/§12.2, §15) refer back to that source document. This file is the standalone post-production-fix
> rollout checkout record for ION-16663.

---

## 0. Executive summary (TL;DR)

- **Fix A (restore the query time-window bound) is deployed and working** (commit `8bd89dffbd`, prod
  `VisibilityOutbound-prod` redeployed 2026-08-24 17:33 EDT). Confirmed by the new `DynamoDB query for IPF …
  returned N records` log line (§16).
- **The orphan handling is unresolved — and "skip the orphan" (the earlier "Fix B") is NOT acceptable.**
  The outbound transaction is built *from the inbound event's data* (`gisTransaction.build(outbound, inbound)`),
  so skipping a record whose inbound is TTL-purged means the **customer gets no / invalid outbound**. The
  current code instead throws and poison-loops the batch — also wrong. The correct, record-preserving fix is
  **outbound-side** (keep outbound current so the inbound still exists; snapshot inbound data into the outbound
  row; recover the already-orphaned backlog from the S3 archive) — see **§22**. Neither throw-and-poison nor
  silent-skip is acceptable.
- **Mixed reality (§16.7):** Fix A advances the majority of profiles (e.g. IPF 4450 progressed), but a subset
  whose window contains a TTL-purged inbound event stay **frozen** (e.g. 5811/5857, cursor stuck at 2023-08-25,
  verified unchanged across 37 attempts). A planned **MySQL cursor-bump appears not to have been committed**,
  consistent with those profiles still reading their old cursor.
- **Processor is deliberately scaled to 0** right now; backlog is large: IPF queue **83,672**, IPF **DLQ
  264,749**, transaction queue **554,403**.
- **Throughput/throttling (§19):** the outbound query is `consistentRead` **≈243 RCU** per 1000-item page,
  run by **120 workers**; both tables autoscale to only **2000 RCU**. Throttling already occurred during the
  post-deploy burst (287× `ProvisionedThroughputExceededException`); the SDK retried **8×** then threw. The
  **inbound `container_events` table is already at ~1863/2000 RCU** and is the tighter constraint.
- **Recommended capacity for the drain (§19.7):** put **both** tables on **on-demand** for the drain (or
  raise limits far above 2000 + pre-warm), and/or **cap concurrency to ~3 tasks + eventually-consistent
  reads**. WCU unchanged.
- **Failure-path assessment (§20):** DLQ is **app-managed on the first failure** (not `maxReceiveCount`).
  **Outbound-table throttle is benign** (silent skip, clean delete, retried) but makes no progress;
  **inbound-table throttle and orphaned inbounds are DANGEROUS** — they propagate and send the IPF to the DLQ
  immediately and freeze the cursor. A drain that overloads the near-capacity inbound table will therefore
  **grow the 264 K DLQ fast**. No data loss in any path; the failure modes are "poison→DLQ+frozen" and "silent
  no-progress".

---

## 16. Production verification (2026-08-24) — what is actually deployed, and what still needs to be done

This section records a **read-only** production check performed with the QA/read-only SSO profile
`642960533737_INTTRA2-QATeam` (`describe-services`, `describe-task-definition`, CloudWatch Logs
`filter-log-events`). No AWS resources or configuration were modified. It exists because the earlier
sections (§11.5, §12.2) recorded a fix ("Fix B") that turned out **not to be in the shipped code**.

### 16.1 In plain terms

Today's prod release (commit `8bd89dffbd`, ION-16663) :

- **Fix A — "read the right records."** Before, the outbound poller had lost its time-window filter and was
  re-reading the *oldest* 1000 records of each profile from the start of the partition. Fix A restores the
  "only records at or after the cursor" bound. **This fix is deployed and working.**

- **Fix B — "don't let one bad record kill the whole batch." - NOT in commit and not pushed** 
- When one outbound record points at an inbound event that has already been deleted (by the 400-day TTL), 
  the code throws and **the entire batch for that
  profile fails**, so the profile's cursor never moves and the same 1000 records are re-read forever (a
  "poison message" loop). Fix B was supposed to make that single bad record be *skipped and logged* instead
  of aborting the batch. 

**Net result (refined by the 18:20 EDT re-check in §16.7):** this is a **mixed** picture, not a blanket
freeze. Fix A lets the **majority** of profiles progress — their cursor advances normally. A **subset** of
heavily-backlogged profiles whose current 1000-record window still contains a TTL-orphaned inbound (e.g.
5811, 5857) stay **frozen**, because every batch still hits that orphan and aborts. 

#### 16.1.1 "If Fix A restores the query bound, why fetch very old records at all? Why is Fix B still needed?"

This is the most natural objection, so it is answered directly. **Fix A bounds the query to `>= cursor`; it
does not, and cannot, move the cursor.** The two fixes solve different halves of the problem.

- The query window is `[cursor, now − delay]`, where `cursor = lastTransactionCreationDatetime` (the
  profile's stored progress marker). Fix A restored the lower bound so we read **from the cursor** instead of
  from the start of the partition. It has **no influence over the *value* of the cursor**.
- The cursor advances **only when a batch is processed successfully** and the profile's threshold is updated.
- For the backlogged profiles the cursor is frozen **~3 years in the past** (observed live: IPF 5811 cursor
  `1692942388874`, IPF 5857 cursor `1692997897992` — both **2023-08-25**). So a *correct* `>= cursor` query
  legitimately means "records from Aug 2023 onward", and the oldest 1000 of those **are** 2023-era rows.
  Fix A is behaving exactly as designed — the window starts in 2023 because that is where the bookmark sits.
- Those 2023 outbound rows reference inbound events already purged by the 400-day inbound TTL (§11.6:
  outbound retention 1095 d ≫ inbound 400 d), so the lookup throws → the whole batch aborts → the cursor
  stays frozen → the same oldest-1000 rows are re-read forever. **Fix A can never break this loop, because it
  never advances the cursor** — it only reads correctly from wherever the frozen cursor points.
- **Fix B is what breaks the loop:** by skipping the single orphaned row instead of aborting, the batch
  completes, the threshold advances, and the cursor climbs forward through the backlog until it re-enters the
  healthy `< 400-day` window where no orphans exist. From then on orphans essentially stop and Fix B rarely
  fires.

**Analogy:** Fix A fixed *"start reading at the bookmark, not page 1."* But if the bookmark is stuck on a
torn page three years back, you hit that torn page every cycle and give up. Fix B lets you skip the torn
page and move the bookmark forward.

**So the premise "we should not be fetching very old records" is the desired *end state*, not something Fix A
delivers on its own.** Old records stop being fetched only once the cursor has moved out of the old region —
which requires either Fix B (self-healing, gradual) or the one-time cursor bump in §16.6 step 3 (immediate).
And because the TTL mismatch guarantees orphans for *any* profile that ever falls >400 days behind (from the
original bug, downtime, a slow consumer, or reprocessing), **Fix B is a permanent resilience requirement, not
a one-off cleanup** — Fix A keeps healthy profiles correct; Fix B rescues and protects the ones that fall
behind.

### 16.2 Deployment — CONFIRMED

| What | Evidence |
|---|---|
| Service | `VisibilityOutbound-prod` on cluster `ANEPRVIS-001` (task def `VisibilityOutbound-latest-prod-Task:1`) |
| New rollout | PRIMARY deployment **created 2026-08-24 17:33:01 EDT**, reached **8/8 running tasks at 17:35:56 EDT** |
| New build is live | The fix-only INFO line `ContainerEventOutboundDao: DynamoDB query for IPF … returned N records` appears **1,990×** in the 5 min after full rollout (17:37–17:42 EDT) |
| Log location | `inttra2-ecs-logs`, log-stream prefix `VisibilityOutbound-latest-prod` (note: **not** `inttra2-pr-lg-visibility`) |

### 16.3 Behaviour after rollout — Fix A works, Fix B is absent

Measured in the same fully-post-rollout window (17:37–17:42 EDT, all 8 tasks on the new build):

| Signal | Count (≈5 min) | Meaning |
|---|---|---|
| `DynamoDB query for IPF … returned N records` (Fix A fingerprint) | **1,990** | New bounded query is live and executing (e.g. IPF 5904 → 1000 records in 143 ms) |
| `Failed to process SQS message` (fatal, whole-batch abort) | **1,259** | Poison-batch loop is **still happening** — Fix B is not in the build |

The fatal errors carry the **identical** stack trace to the original incident, proving Fix B was never applied:

```
java.lang.IllegalArgumentException: Could not find inbound transaction with ID ce:...
  at OutboundGenerator.getInboundContainerEvent(OutboundGenerator.java:199)
  at OutboundGenerator.lambda$createAndSendBatchTransactions$0(OutboundGenerator.java:102)   // inside .map(...)
  at OutboundGenerator.createAndSendBatchTransactions(OutboundGenerator.java:104)            // .toList()
  at OutboundMultiTransactionProcessor.process(OutboundMultiTransactionProcessor.java:97)
```

Concrete stuck profiles observed (cursor frozen ~3 years in the past, so every read is below the 400-day
inbound horizon and every batch aborts):

- **IPF 5811** — `lastTransactionCreationDatetime = 1692942388874` (**2023-08-25**)
- **IPF 5857** — `lastTransactionCreationDatetime = 1692997897992` (**2023-08-25**, `locked = 1`)

### 16.4 Source-tree confirmation (why Fix B is missing)

- `OutboundGenerator.java:102` still builds each element with
  `...inboundEvent(getInboundContainerEvent(item.getInboundContainerEventId()))...` **inside** the
  `stream().map(...).toList()`.
- `OutboundGenerator.getInboundContainerEvent` (lines 193–202) still **throws**
  `IllegalArgumentException` when the inbound is not found (line 199). That throw is *outside* the per-record
  `catch` in `generateOutboundMessage` (line ~186), so it escapes to
  `OutboundMultiTransactionProcessor.process` and fails the whole SQS message.
- A repo-wide search finds **no** `toOutboundMetaDataOrSkip` method and **no**
  `skipsOrphanedInboundWithoutFailingBatch` test — i.e. the artefacts §11.5/§12.2 claim exist, do not.

### 16.5 QA note

The fix is effectively being validated in **prod, not QA**. In QA, `inttra2-qa-lambda-visibility-outbound-poller`
only *enqueues* IPF IDs onto `inttra2_qa_sqs_ce_outbound_ipf`; the actual processor `VisibilityOutbound-qa`
(cluster `ANEQAVIS-001`) showed **no** `DynamoDB query for IPF` fingerprint activity in the last 5 days, so
the outbound query path is not currently being exercised in QA.

### 16.6 What needs to be done

1. **⚠️ SUPERSEDED by §22 — do NOT implement "skip".** (The text below proposed skipping the orphaned record;
   that is not acceptable because the outbound is built from the inbound's data, so skipping drops the
   customer's outbound. See §22 for the correct outbound-side fix.) ~~Implement Fix B for real (primary,
   unblocks the stuck profiles). Make a single missing inbound event skip that one record instead of aborting
   the batch.~~ In
   `OutboundGenerator.createAndSendBatchTransactions` change the mapping at line 102 so that a lookup which
   cannot resolve the inbound event is filtered out rather than thrown:

   ```java
   List<ContainerEventOutboundMetaData> qualifiedEvents = containerEventOutboundList.stream()
           .map(this::toOutboundMetaDataOrSkip)          // returns null (logged) when inbound is missing
           .filter(Objects::nonNull)
           .filter(item -> !excludeTransaction(item.getOutboundEvent(), item.getInboundEvent()))
           .toList();

   private ContainerEventOutboundMetaData toOutboundMetaDataOrSkip(ContainerEventOutbound outbound) {
       List<ContainerEvent> inbound = containerEventDao.findById(outbound.getInboundContainerEventId());
       if (inbound == null || inbound.isEmpty()) {
           log.error("Skipping outbound row with orphaned inbound id {} (IPF {}, sortKey {}) - "
                   + "inbound TTL-expired; row will not block the batch",
                   outbound.getInboundContainerEventId(),
                   outbound.getIntegrationProfileFormatId(), outbound.getSortKey());
           return null;   // skip this one record; batch and cursor proceed
       }
       return ContainerEventOutboundMetaData.builder()
               .outboundEvent(outbound).inboundEvent(inbound.get(0)).build();
   }
   ```
   Keep the null/empty **input** guard already added (invalid id → still an error). Retire the throwing
   `getInboundContainerEvent`, or keep it only where a hard failure is genuinely wanted.

2. **Add the regression test that was claimed but is missing:**
   `OutboundGeneratorTest.skipsOrphanedInboundWithoutFailingBatch` — a 3-row batch with one orphaned inbound
   must send the 2 valid transactions and must **not** throw.

3. **Rescue the already-stuck profiles.** Even after (1), backlogged profiles (e.g. 5811, 5857) will churn
   through many thousands of orphaned rows before their cursor climbs back inside the 400-day window. Decide
   and document a remediation for the existing backlog — e.g. a controlled one-time cursor
   (`lastTransactionCreationDatetime`) advance to just inside the inbound-retention horizon for the affected
   IPFs — so they drain promptly instead of skip-logging ~millions of dead rows.

4. **Re-verify in prod after the next deploy** using the exact signals in §16.3: `DynamoDB query for IPF`
   should stay high (processing continues) while `Failed to process SQS message` drops to ≈0, and the
   previously-stuck IPFs (5811, 5857) should show their cursor advancing on subsequent poller cycles.

5. **Address the retention mismatch (§11.6) as a follow-up decision** — outbound TTL (1095 d) outliving
   inbound TTL (400 d) is what continuously manufactures these orphans; with Fix B in place it is no longer
   correctness-critical, but aligning the two (or guaranteeing outbound rows are processed within 400 d) is
   the durable way to stop generating orphans at the source.

6. **Correct the record.** §11.5 and §12.2 have been annotated as superseded by this section; keep future
   "fixed" claims tied to a commit + a prod-log signal so a documented fix cannot drift from the shipped code
   again.

### 16.7 Live re-check (2026-08-24 ~18:20 EDT) — mixed reality, service scaled to 0, and the DB-cursor hypothesis

A follow-up observation from a colleague ("the cursor *was* advancing for IPF 4450, so maybe the process is
working; maybe the DB cursor changes were not committed") prompted a second read-only pass. It refines §16.1
and §16.3 in three important ways.

**(a) The processor is currently scaled to zero — the recent "quiet" is not recovery.**
`describe-services` on `VisibilityOutbound-prod` (ANEPRVIS-001) returns `runningCount = 0, desiredCount = 0`,
with ECS events *"has stopped 8 running tasks … has reached a steady state."* So after the ~16-minute
post-deploy burst (17:33–17:49 EDT), the service was **scaled down to 0 tasks**. This was a **deliberate stop
by the team** (confirmed), done to halt the poison-loop / DLQ growth while the data-side remediation is sorted
out — so the last CloudWatch window shows **0** `DynamoDB query for IPF` and **0** `Failed to process SQS
message` simply because **nothing is processing**, not because the backlog cleared.

**(b) It is a *mixed* reality — some IPFs advance, a subset are frozen. Both halves are now proven:**

| IPF | Fatal errors in burst | Cursor (`lastTransactionCreationDatetime`) behaviour | Verdict |
|---|---|---|---|
| **4450** | **0** (`"Outbound IPF: 4450"` search returned empty) | Advanced `1693243473398 → 1693483075949` (colleague's DB read); `transactionCount` ~157→163 | **Working** — Fix A alone is enough because it has no orphan in-window |
| **5811** | **37**, all identical | `1692942388874` (2023-08-25) **unchanged across all 37 attempts**; `transactionCount` grew 7377→7563 | **Frozen** — poison-loop; cursor never moves |
| **5857** | present in burst | `1692997897992` (2023-08-25), `locked=1`; `transactionCount` 757→773 | **Frozen** |

So the colleague is **right about 4450** (and about the general point that processing works for un-poisoned
profiles), but it does **not** generalise: 5811's cursor is provably frozen (same value 37×). The correct
statement is *"Fix A advances the majority; the orphan-containing subset stays frozen until Fix B or a cursor
bump."*

**(c) Queue/DLQ depths confirm a large stuck backlog:**

| Queue | Approx. messages |
|---|---|
| `inttra2_pr_sqs_ce_outbound_ipf` (IPF work) | 83,672 |
| `inttra2_pr_sqs_ce_outbound_ipf_dlq` | **264,749** |
| `inttra2_pr_sqs_ce_outbound` (transactions) | 554,403 |
| `inttra2_pr_sqs_ce_outbound_dlq` | 4,638 |

The 264,749-message IPF DLQ is where poison IPF messages land after exhausting `maxReceiveCount` — the sink
for the still-frozen profiles.

**(d) On "the DB cursor changes may not have been committed" (leading explanation).** This is **strongly
consistent with the evidence**. The remediation for the stuck profiles was a MySQL `UPDATE` advancing
`lastTransactionCreationDatetime` (the cursor) past the 400-day orphan horizon — and the current working
theory is that a **bulk `UPDATE` run in a MySQL query editor was never committed** (autocommit off / an
explicit `COMMIT` was missed), so it did **not** persist for the application. The AWS-side evidence matches
this exactly: throughout the post-deploy burst the app read the **pre-bump** cursor for every sampled stuck
profile — IPF 5811 = `1692942388874` (2023-08-25) on all 37 attempts, unchanged; 5857 = `1692997897992`,
`locked=1`. If the bump had committed, the app (on its own connection) would have read the new, recent value
and those profiles would have skipped straight past the orphan zone. Because it did not, **no** profile got
the bump: orphan-free profiles (4450) creep forward under Fix A, orphan-containing ones (5811/5857) stay
poisoned.

> **Extra risk from an uncommitted editor transaction:** besides not persisting, an open (uncommitted)
> `UPDATE` **holds row locks** on those threshold rows and keeps a transaction open. That can block the
> application's own writes to the same rows (cursor advance / `locked` flag), and the whole change **silently
> rolls back** if the editor session disconnects or times out. So an uncommitted bulk update can both fail to
> help *and* actively interfere.

**(e) How to confirm and correctly apply the cursor bump (MySQL — needs DB access this AWS profile does not
have).**

1. **Confirm it did not persist:** from a *fresh* connection (not the editor session that ran the `UPDATE`),
   `SELECT integrationProfileFormatId, lastTransactionCreationDatetime FROM <threshold_table>
    WHERE integrationProfileFormatId IN (5811, 5857, 4450);` — if 5811/5857 still show the 2023-08 values,
   the bump is not committed.
2. **Check for a lingering open transaction / locks:**
   `SELECT * FROM information_schema.innodb_trx;` and
   `SELECT * FROM performance_schema.data_locks;` — a long-running `trx` on the threshold table indicates the
   editor's transaction is still open (or was rolled back on disconnect).
3. **Re-apply correctly:** re-run the `UPDATE` and **explicitly `COMMIT;`** (or set `autocommit=1` for the
   session). Bump `lastTransactionCreationDatetime` to a value safely inside the inbound-retention window
   (e.g. `now() − ~390 days` in epoch-ms) for the affected IPFs, then verify with the step-1 `SELECT` from a
   new connection.
4. **Only then scale the processor back up.** Order matters: apply the committed bump (and/or ship Fix B)
   *before* restoring `desiredCount`, otherwise the still-frozen profiles will immediately re-feed the
   264 K IPF DLQ.

**Note on scope of this analysis:** the RDS/MySQL threshold table was **not** queried here — the
`642960533737_INTTRA2-QATeam` profile is read-only against DynamoDB/CloudWatch/ECS/SQS only. Steps (e) must be
run by someone with MySQL access; the AWS-side cursor readings above are the indirect corroboration.

**Net:** deployment of Fix A is confirmed and genuinely working for the bulk of traffic; the still-stuck,
DLQ-feeding subset needs Fix B and/or the cursor bump; and the processor is currently scaled to 0, so no
progress is being made until it is scaled back up (ideally only after Fix B and/or the cursor remediation is
in place, to avoid re-growing the 264 K DLQ).

---

## 17. Post-fix processed-record checkout (2026-08-24, read-only — NO table scans)

**Method (scan-free).** Successful/failed IPF sets are derived entirely from CloudWatch logs of the fixed
build (log group `inttra2-ecs-logs`, stream prefix `VisibilityOutbound-latest-prod`) over the only window
the fixed build ran before the service was deliberately scaled to 0: the burst **17:33-17:49 EDT
(21:33-21:49 UTC) on 2026-08-24**. An IPF *progressed/succeeded* if it has a `DynamoDB query for IPF <id>
returned <n> records` line **and no** `Failed to process SQS message` for that IPF; it *failed/poisoned* if
it produced the fatal line. Record-level detail (§17.2) came from a **single targeted DynamoDB `Query`**
(partition key + sort-key `BETWEEN`) - **no `Scan`**.

### 17.1 Summary

| Metric | Value |
|---|---|
| IPFs queried by the fixed build | **485** |
| Progressed / ran successfully (no fatal) | **311** |
| - of which actually sent records (returned > 0) | 219 |
| - of which already caught-up (returned 0, nothing to send) | 92 |
| Poisoned / failed (fatal batch abort) | **174** |

### 17.2 IPF 4450 - record-level detail (the window you gave: `1693243473398 -> 1693483075949`)

- **1000 records** processed as one full batch; cursor advanced `1693243473398 -> 1693483075949`; **zero** fatal errors -> all 1000 succeeded.
- Targeted Query: partition integrationProfileFormatId = '4450', sequenceNumber BETWEEN '1693243473398' AND '1693483075949_g'. Single page, no LastEvaluatedKey (exactly 1000 in-window records).
- First: `1693243473398_ce:9a7d45ef-45fe-4256-9f3e-a91faa339c9a`
- Last:  `1693483075949_ce:c20ef24f-ec07-4b57-a73b-24c3af760aa8`
- Full list of the 1000 processed `sequenceNumber` values in **Appendix A**.

### 17.3 All progressed IPFs (id : max records returned in the burst)

> `0` = bounded query found no records at/after the cursor (profile already caught up; nothing to send) - a trivially-successful cycle. `> 0` = records read and sent without a batch failure.

```
4450:1000     4454:1000     4456:1000     4462:1000     4468:1000     4471:1000
4475:1000     4476:0        4485:1000     4486:1000     4489:1000     4491:1000
4519:0        4531:1000     4543:0        4550:567      4571:17       4574:1000
4578:1000     4586:0        4597:0        4600:1000     4601:1000     4609:1000
4610:0        4617:1000     4618:0        4619:1000     4620:1000     4626:48
4627:1000     4637:0        4665:0        4670:1000     4672:0        4675:31
4680:0        4684:1000     4693:1000     4694:0        4698:1000     4701:0
4704:0        4705:1000     4707:1000     4718:0        4720:1000     4728:1000
4733:0        4736:1000     4739:0        4743:1000     4752:1000     4757:471
4775:1000     4781:1000     4804:1000     4807:1000     4811:1000     4819:0
4823:1000     4828:1000     4831:1000     4835:0        4840:1000     4842:1000
4846:1000     4847:1000     4851:1000     4852:0        4853:322      4880:1000
4891:0        4899:1000     4920:2        4929:0        4941:1000     4942:0
4943:0        4944:0        4949:0        4972:1000     4984:1000     4991:1000
4992:1000     4993:0        5000:681      5002:0        5019:1000     5020:1000
5023:0        5037:1000     5043:0        5046:1000     5061:1000     5063:1000
5067:1000     5069:0        5070:1000     5071:1000     5080:0        5084:1000
5086:1000     5087:1000     5094:0        5096:1000     5097:1000     5099:1000
5100:0        5105:1000     5111:1000     5113:1000     5114:8        5117:0
5123:1000     5126:1000     5132:1000     5143:1000     5144:0        5146:1000
5158:0        5161:1000     5163:1000     5166:1000     5182:5        5205:1000
5209:1000     5223:1000     5224:1000     5226:73       5230:562      5231:1000
5235:0        5237:0        5239:0        5249:10       5255:1000     5258:1000
5266:0        5276:1000     5281:0        5286:0        5289:0        5291:1000
5299:0        5310:1000     5311:1000     5314:0        5315:1000     5320:0
5323:1000     5327:1000     5335:1000     5338:0        5344:0        5358:1000
5360:1000     5361:1000     5365:0        5368:1000     5371:1000     5381:1000
5382:0        5387:0        5394:0        5395:0        5398:0        5404:0
5419:1000     5429:0        5433:1000     5450:888      5453:1000     5469:1000
5470:1000     5474:1000     5477:1000     5482:1000     5494:1000     5513:1000
5515:0        5533:1000     5535:1000     5536:32       5542:0        5546:1000
5555:1000     5560:0        5566:1000     5567:1000     5571:38       5572:1000
5588:0        5592:1000     5601:1000     5614:1000     5626:1000     5643:0
5644:0        5649:1000     5652:1000     5653:932      5660:1000     5661:1000
5677:1000     5678:1000     5680:1000     5695:1000     5700:1000     5718:1000
5720:1000     5721:1000     5727:1000     5731:1000     5737:1000     5743:812
5747:0        5757:1000     5759:0        5762:0        5765:1000     5789:1000
5799:1000     5810:44       5820:135      5837:1000     5845:1000     5859:1000
5867:0        5873:354      5891:1000     5893:0        5903:1000     5906:0
5917:1000     5918:0        5922:1000     5924:1000     5925:1000     5927:0
5928:1000     5930:0        5931:1000     5932:1000     5939:1000     5940:1000
5941:1000     5942:1000     5947:1000     5950:1000     5958:0        5960:0
5962:1000     5966:1000     5972:1000     5978:1000     5979:19       5980:0
5984:1000     5986:1        5993:1000     5996:1000     6004:1000     6007:0
6010:1000     6012:1000     6019:0        6020:1000     6021:0        6023:0
6024:0        6029:1000     6042:1        6119:0        6140:1000     6156:1000
6176:1000     6328:1000     6331:0        6395:1000     6415:1000     6456:628
6474:13       6477:0        6507:0        6515:1000     6520:7        6523:0
6574:0        6595:1        6598:6        6611:0        6612:16       6624:1
6638:0        6641:0        6645:2        6654:1        6687:3        6717:0
6718:4        6731:17       6734:0        6753:4        6830:1000     6850:1000
6891:20       6942:1000     6968:518      6971:1000     6983:0
```

### 17.4 Poisoned IPFs that did NOT progress (still frozen - need Fix B / committed cursor bump)

```
4451    4452    4457    4469    4472    4483    4492    4496    4511    4540
4551    4557    4585    4632    4681    4683    4687    4761    4802    4808
4817    4834    4838    4843    4849    4859    4863    4879    4882    4887
4911    4912    4951    4982    4989    5014    5028    5054    5057    5064
5068    5075    5095    5109    5115    5128    5129    5151    5160    5168
5174    5175    5176    5177    5184    5189    5190    5203    5204    5213
5220    5227    5228    5247    5254    5270    5284    5295    5303    5305
5308    5325    5336    5346    5366    5379    5437    5438    5440    5441
5449    5459    5476    5488    5492    5496    5508    5514    5544    5554
5568    5599    5605    5607    5613    5618    5624    5627    5634    5636
5647    5662    5679    5683    5684    5694    5697    5707    5713    5722
5728    5729    5730    5735    5736    5738    5744    5750    5752    5754
5756    5758    5761    5766    5785    5787    5788    5792    5793    5795
5798    5801    5804    5811    5814    5816    5824    5832    5836    5842
5843    5852    5857    5887    5892    5895    5901    5904    5916    5920
5934    5944    5968    5969    5970    5977    5981    5989    5995    6005
6018    6032    6040    6125    6296    6297    6318    6341    6399    6424
6492    6496    6969    6970
```

---

## 18. Sort-key boundary handling and the `_g` sentinel suffix

### 18.1 What "sentinel suffix" means

A **sentinel** is a synthetic marker value that never occurs in real data and is used purely as a *boundary*
in a comparison. **Suffix** = it is appended to the end of the key string.

The cursor is stored as a bare millisecond timestamp, e.g. `1693483075949`. But the DynamoDB **sort key** of a
real row for that millisecond is `1693483075949_ce:<uuid>` (format `<timestamp>_<inboundContainerEventId>`,
and every id is `ce:<uuid>`). To turn the numeric cursor into a *string* boundary for a sort-key range query,
the DAO appends `_g`:

```java
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";   // "1693483075949_g"
String sortKeyUpperLimit = Instant.now().minusMillis(TIME_DELAY_IN_MILLISECONDS).toEpochMilli() + "_g";
```

Why `_g` specifically:
- `_` matches the real delimiter between the timestamp and the id.
- `g` is chosen because it sorts **after** the `c` that begins every real id (`ce:…`). Lexicographically
  `1693483075949_g` **>** `1693483075949_ce:<anything>`.

So `1693483075949_g` is a value that (a) **never equals any real row**, and (b) sits at a **precise, known
position** — immediately *after* the last possible real row of millisecond `1693483075949`. That lets one
string comparison (`>=`) express *"start strictly after everything in this millisecond"* without the code
having to know any of the ids. That synthetic boundary marker is the "sentinel."

> **Fragility note:** the trick relies on every real id's first character being `< 'g'`. All ids are
> `ce:<uuid>` (start `'c'`), so it is safe today; an id ever starting `'g'..'z'` would misplace the boundary.

### 18.2 Does the boundary row get re-fetched as the first row of the next batch? (No)

A natural concern: batch N ends on `1693483075949_ce:c20ef24f…`, the cursor becomes `1693483075949`, so won't
the next query return that same row again (duplicate outbound)?

**No — because the lower bound is `<cursor>_g`, not `<cursor>`.** The lexicographic compare that decides
re-fetch:

```
1693483075949_ce:c20ef24f...   (last processed row)
1693483075949_g                (next-query lower bound)
              ^  'c' (0x63) < 'g' (0x67)
```

So `1693483075949_ce:c20e…` **<** `1693483075949_g`, and `>= 1693483075949_g` **excludes** it → the boundary
row is **not** re-fetched. (The client-side `removeIf(seq < lowerLimit)` re-check at line ~93 enforces the
same thing defensively.)

- **If the bound were the plain timestamp (`>= "1693483075949"`)**, the observation would be correct — a
  prefix sorts before the longer string, so `1693483075949_ce:…` *would* be re-included and duplicated. The
  `_g` sentinel is exactly what makes the lower bound "strictly after the whole `1693483075949` millisecond."
  **A manual SQL/console repro using the bare timestamp will double-count the boundary millisecond; the
  application path does not.**
- **`_g` skips the entire `1693483075949` millisecond, not just the last row.** The opposite risk (dropping
  other unprocessed rows sharing that millisecond when the 1000-row limit cuts mid-millisecond) is handled by
  the trim block at line ~106: on hitting `RESULT_SIZE_LIMIT` it removes the last row **and all trailing rows
  with the same timestamp**, so the cursor only advances to a millisecond whose rows were *fully* processed.

**Net at the boundary: no duplicate and no skip.** Last-of-batch-N is not first-of-batch-N+1.

### 18.3 How to confirm the sentinel is not a record, and that it is not a 2.x feature

**It is not a stored record — it is only a query bound value.** Verified read-only against
`inttra2_prod_container_events_outbound` (IPF 4450):

| Check | Query | Result |
|---|---|---|
| Does a row `…_g` exist? | `integrationProfileFormatId = "4450" AND sequenceNumber = "1693483075949_g"` | **0 items** |
| What is really at that ms? | `… AND begins_with(sequenceNumber, "1693483075949_")` | 1 row: `1693483075949_ce:c20ef24f-ec07-4b57-a73b-24c3af760aa8` |

In code the `_g` string is only ever used as a **read** bound (`sortKeyValue`); the **write** path
(`createContainerEventOutbound`) always builds `now + "_" + inboundContainerEventId` = `<ts>_ce:<uuid>`, so a
`_g` row is never persisted. (To reproduce: run the two queries above with any `integrationProfileFormatId`.)

**It is not an AWS SDK 2.x feature — it predates the upgrade.** The pre-upgrade AWS SDK **v1** DAO
(`git 9a04010f1d^`, using `com.amazonaws.services.dynamodbv2.*`) already contains the identical construction
and documents it in the Javadoc:

```java
// pre-upgrade v1 (git 9a04010f1d^)
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";
// Javadoc: "sort_key is a composite of 'unix timestamp'_'inbound container event hash key'.
//           To ignore _'inbound container event hash key' from the query, append '_g' to the
//           creationTimestamp. This will functionally ignore the trailing hash key."
```

So `_g` is the team's own composite-key query convention, independent of SDK version — present verbatim in v1
and carried through the 2.x migration unchanged. What *did* change across the upgrade/fix: `RESULT_SIZE_LIMIT`
went 5000 → 1000, and the v1 `queryExpression`/`BETWEEN` was replaced by the structured
`sortKeyCondition(">=")` (§12.1) — but the `_g` sentinel itself was untouched.

### 18.4 Where the sentinel is introduced and how it reaches DynamoDB (code trace)

All in `visibility/visibility-commons/.../persistence/ContainerEventOutboundDao.java`,
`getUnprocessedTransactions(...)`:

**1. Constructed (~line 66-67)** — plain Java string concat, no SDK involvement:
```java
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";   // e.g. "1693483075949_g"
String sortKeyUpperLimit = Instant.now().minusMillis(TIME_DELAY_IN_MILLISECONDS).toEpochMilli() + "_g";
```

**2. Bound into the query spec as the range-key value (~lines 72-83):**
```java
DefaultQuerySpec querySpec = DefaultQuerySpec.builder()
        .partitionKeyName("integrationProfileFormatId").partitionKeyValue(CloudAttributeValue.ofString(ipfId))
        .sortKeyName("sequenceNumber")
        .sortKeyCondition(">=")
        .sortKeyValue(CloudAttributeValue.ofString(sortKeyLowerLimit))   // <-- sentinel goes in here
        .consistentRead(true).limit(RESULT_SIZE_LIMIT).maxResultSize(RESULT_SIZE_LIMIT)
        .build();
results = new ArrayList<>(repository.query(querySpec));
```

**3. Reaches DynamoDB.** `repository` is the enhanced repository from `commons` (`cloud-sdk-aws`); its
`query()` maps `sortKeyCondition(">=") + sortKeyValue` to `QueryConditional.sortGreaterThanOrEqualTo(...)`, so
the wire request is:
```
KeyConditionExpression: integrationProfileFormatId = :pk AND sequenceNumber >= :sk
  :pk = {S: "4450"}
  :sk = {S: "1693483075949_g"}     <- the sentinel, sent as the range-key lower bound value
```
So the sentinel is a **value bound to `:sk`** in the `>=` key condition — never a stored item.

**4. Reused client-side (~lines 93-97)** — the same sentinel strings enforce both bounds defensively
(and the upper bound, which cannot be a second server-side sort-key condition):
```java
results.removeIf(r -> {
    String seq = r.getSequenceNumber();
    return seq.compareTo(sortKeyLowerLimit) < 0 || seq.compareTo(sortKeyUpperLimit) > 0;
});
```

**Pre-upgrade (v1) plumbing, same sentinel:** the `_g` strings fed a `queryExpression`
(`"... sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper"`) passed to `queryWithSizeLimit(...)`, which
became DynamoDB's `keyConditionExpression` directly (both bounds server-side). The regression was that the
enhanced client silently ignored `queryExpression` (§4-§5); Fix A switched to the structured
`sortKeyCondition(">=")` above. The `_g` construction never changed.

## 19. Throughput, throttling, retry/backoff, and other exceptions (backlog-drain risk)

Read-only checks against `inttra2_prod_container_events_outbound` and the burst logs (17:33-17:49 EDT).

### 19.1 Table capacity

- **Provisioned RCU = 25, WCU = 200** (reads under-provisioned vs writes). Autoscaling enabled:
  read **min 25 / max 2000**, write **min 200 / max 2000**.
- The outbound query is **`consistentRead(true)`** (2× RCU cost), up to **1000 items/call** (~1 MB ≈ **~245 RCU
  per query**), issued by **8 tasks × ~15 threads**.

### 19.2 Throttling actually occurred (not hypothetical)

287× during the burst, e.g.:

```
ContainerEventOutboundDao: Failed to retrieve ContainerEventOutbound rows for IPF 5986 cursor 1787518372353_g
software.amazon.awssdk.services.dynamodb.model.ProvisionedThroughputExceededException:
  The level of configured provisioned throughput for the table was exceeded ...
  (Service: DynamoDb, Status Code: 400, ... SDK Attempt Count: 9)
```

The 8-task **cold start at 21:33-21:34** spiked read demand faster than autoscaling could ramp (autoscaling
reacts on a 1-2 min lag), so it throttled at ~21:34.

> CloudWatch `ReadThrottleEvents` / `ConsumedReadCapacityUnits` returned empty via the metric API for the
> window (a metric-query/propagation quirk), but the **application logs are authoritative** — throttling
> definitively occurred. Verify in the DynamoDB console.

### 19.3 SDK retry / exponential backoff

- `SDK Attempt Count: 9` = the DynamoDB v2 client's default **8 retries (9 attempts)** (DynamoDB's default is
  higher than the generic 3).
- Backoff is **exponential with equal jitter**, doubling from a ~0.5 s throttling base
  (~0.5s→1s→2s→4s→8s→16s), each attempt **capped at ~20 s**; total budget ~1 min before it gives up.
- Retries keep hitting the **same** throttled table — they do **not** wait for autoscaling. On exhaustion the
  SDK **throws `ProvisionedThroughputExceededException`**, which the DAO `catch` swallows and returns an
  **empty list** → the IPF looks "caught up" → **cursor stalls silently, no fatal error** (405×
  `Failed to retrieve ContainerEventOutbound`).

### 19.4 What happens at the autoscaling max (2000)

Autoscaling raises RCU only up to **2000, then stops**. Short spikes may be absorbed by DynamoDB **burst
capacity** (~300 s of banked unused capacity), but **sustained** demand > 2000 RCU/s **cannot be scaled away**
→ persistent throttling → retries → throws → silent skip. At ~245 RCU/consistent-query, 2000 RCU/s is only
**~8 queries/second sustained** — likely insufficient at full 8-task × 15-thread parallelism (which is why it
threw at cold start).

### 19.5 Other exceptions in the burst (beyond the poison-batch `IllegalArgumentException`)

| Pattern | Count | Meaning |
|---|---|---|
| `Failed to retrieve ContainerEventOutbound` | 405 | DAO read failed → returns empty (silent skip) |
| `ProvisionedThroughputExceededException` | 287 | DynamoDB read throttle on the outbound table |
| `TimeoutException` | 411 | SDK per-attempt timeouts during the overload |
| `SdkClientException` | 287 | wraps the above |
| `SnsEventPublisher: SNS_Failed_AFTER_RETRY` | ~100+ | **separate subsystem** — telemetry/notification SNS publishing failing after retry (sampled events are workflow `closeRun` telemetry) |
| `OutboundGenerator: Failed to generate outbound message` | 24 | per-record non-fatal orphan catch |
| `OutOfMemory`, `Unable to execute HTTP request` | 0 | none |

### 19.6 Recommendations before the backlog drain

1. **Raise the autoscaling max well above 2000, or switch the table to on-demand (`PAY_PER_REQUEST`) for the
   drain** — no ceiling, no cold-start ramp lag.
2. **Reconsider `consistentRead(true)` → eventually-consistent** (halves RCU; the existing 100 ms
   `TIME_DELAY_IN_MILLISECONDS` guard suggests it may be tolerable — a correctness call).
3. **Add backpressure to the drain** — fewer tasks/threads or smaller page size, and/or enable SDK **adaptive**
   retry mode (client-side rate limiter) instead of hammering.
4. **Pre-warm** by raising the autoscaling **min** before scaling the processor up, so RCU is already high at
   cold start.
5. **Stop the DAO from masking throttling as "no work"** — distinguish throttle/timeout failures (so the IPF is
   retried rather than treated as caught-up) and alert on `Failed to retrieve ContainerEventOutbound`.
6. **Investigate `SNS_Failed_AFTER_RETRY`** telemetry-publishing failures separately.

### 19.7 Recommended provisioned capacity for the drain (sized from measured cost)

**Measured inputs:**

| Input | Value |
|---|---|
| Outbound query cost | **243 RCU** per consistent 1000-item page (measured via `ReturnConsumedCapacity`); ~122 eventual |
| Processor concurrency | **8 tasks × 15 threads = 120 workers** (thread pool `pool-11-thread-1..15` per task) |
| Inbound `getInboundContainerEvent` → `findById` | ~2 RCU each (inbound items avg ~5.8 KB) × up to **1000 per batch** ≈ **~2000 RCU/batch** |
| Inbound `inttra2_prod_container_events` now | RCU **1863 / max 2000** (already near ceiling from baseline), WCU 976 / max 4000 |
| Outbound `inttra2_prod_container_events_outbound` now | RCU 25 / max 2000, WCU 200 / max 2000 |

**Key point:** the **inbound** table is the tighter constraint — it is already ~1863/2000 from baseline
traffic, and the outbound drain adds ~1000 `findById` reads per batch on top.

**Primary recommendation — switch BOTH tables to on-demand (`PAY_PER_REQUEST`) for the drain window, then
revert.** Removes all sizing / autoscale-ramp-lag risk given the 120-way cold-start burst and finite backlog.

**If staying provisioned, size for the peak:**

| Table | Reads (RCU) | Writes (WCU) |
|---|---|---|
| `…_container_events_outbound` | max **30,000**, pre-warm min **8,000** (consistent) — or **15,000 / 5,000** if switched to eventually-consistent | unchanged (200 / 2000 — drain does not write here) |
| `…_container_events` (inbound) | max **~10,000**, pre-warm min **~4,000** (on top of its ~1863 baseline) | unchanged |

Peak math: outbound 120 × 243 ≈ **29k RCU**; inbound `findById` load is comparable per batch — both far exceed
the current 2000 ceilings.

**Smarter than raw capacity (recommended combination):**
1. **Cap drain concurrency to 2-3 tasks** (not 8). At 3 tasks / 45 workers: outbound peak ≈ 45 × 243 ≈
   **~11k RCU** (or ~5.5k eventual) — cheaper and gentler on the inbound table. Trades drain speed for stability.
2. **Switch the outbound query to eventually-consistent** (halves to ~122 RCU/query; the 100 ms `TIME_DELAY`
   guard suggests it may be tolerable — a correctness call).
3. **Reduce `findById` load (code change)** — `BatchGetItem` or a short-lived cache instead of 1000 single
   reads/batch; this is what actually relieves the inbound bottleneck.

**Bottom line:** as-is you would need ~30k RCU (outbound) / ~10k RCU (inbound) — impractical against the 2000
ceilings, so **use on-demand for the drain, or cap concurrency to ~3 tasks + eventually-consistent reads to
land in the ~5-11k range.** WCU unchanged on both tables.

---

---

## 20. Failure-path assessment (what happens when outbound processing fails / throttles)

Traced from `OutboundMultiTransactionProcessor.process`, `OutboundGenerator.createAndSendBatchTransactions`,
`ContainerEventOutboundDao.getUnprocessedTransactions`, and `SqsMessageHandler`.

### 20.1 SQS + threshold mechanics (the common machinery)

- **DLQ is app-managed and fires on the FIRST failure — not via `maxReceiveCount`.**
  `SqsMessageHandler.createTask` runs `process(msg)`; on exception `taskExceptionHandler` **copies the message
  to the DLQ**, and the `finally` (`taskFinallyHandler`) **deletes it from the source queue**. So:
  - **Success** → message deleted from source only.
  - **Any exception** → message copied to DLQ **and** deleted from source (one failure = one DLQ entry). There
    is **no SQS redelivery/backoff loop**.
- **Cursor only advances on real progress.** In `process()`'s `finally`, `unlockThreshold(...)` is called with
  `results.getLastTransactionCreateTimestamp()` **only when `results != null` and `processedCount > 0`**. If an
  exception was thrown (`results == null`) *or* 0 were processed, it unlocks with the **unchanged cursor** and
  `lastExecution = now`.
- The poller re-enqueues the IPF on its next cycle (based on the MySQL threshold), so a stuck IPF is re-sent
  every poller cycle.

### 20.2 The distinct failure paths

| Trigger | Where it fails | Exception escapes `process()`? | SQS outcome | Cursor | Net effect |
|---|---|---|---|---|---|
| **Orphaned inbound** (TTL-purged) | `getInboundContainerEvent` throws `IllegalArgumentException` inside the `stream().map(...).toList()` | **Yes** | **DLQ + delete** | frozen | Poison loop; one DLQ entry **per poller cycle** → DLQ grows without bound |
| **Inbound-table throttle** (`ProvisionedThroughputExceededException` from `findById`) | same `stream().map(...)` (the `findById` call) | **Yes** | **DLQ + delete** | frozen | **Same as poison** — a capacity throttle on the **inbound** table sends the IPF straight to the DLQ |
| **Outbound-table throttle** (`ProvisionedThroughputExceededException` in `getUnprocessedTransactions`) | caught by the **DAO's own `catch`** → returns `emptyList()` | **No** | **delete only (no DLQ)** | frozen (0 processed) | Silent skip; retried next poller cycle; under sustained throttle → **livelock** (spins, no progress, no DLQ growth) |
| **Lock contention** (another worker holds the threshold lock) | `lockThreshold(...)` returns false | No | delete (treated as success) | unchanged | Skipped this cycle; retried; `forcedUnlock` after `MAX_MINUTES_BETWEEN_EXECUTIONS` |

### 20.3 Why this matters for the capacity-maxed (drain) scenario

- **Outbound-table throttling is benign but useless:** the DAO swallows it, returns empty, the message is
  cleanly deleted, and the IPF is retried next cycle — but it makes **no progress** while throttled.
- **Inbound-table throttling is dangerous:** `getInboundContainerEvent` does **not** catch it, so it
  propagates exactly like the orphan poison → the IPF is **sent to the DLQ on the first throttle** and the
  cursor freezes. Because the inbound `container_events` table is already at **~1863/2000 RCU** (§19.7), a
  drain that pushes it over the ceiling will **rapidly grow the already-264 K IPF DLQ** rather than simply
  retrying. **This is the single strongest reason to raise inbound capacity (or go on-demand) *before* any
  scale-up.**
- **No `maxReceiveCount` cushion:** because the DLQ is app-managed on first failure, there is no built-in
  retry buffer — one bad lookup (orphan or throttle) = one DLQ message immediately.
- **No data loss in any path:** on failure nothing is sent (the `toList()` throws *before* the
  `createAndSendTransactions` loop, so batches are atomic — no partial or duplicate sends) and the cursor is
  not advanced (so no records are skipped). The failure **modes** are "poison → DLQ + frozen cursor" and
  "silent no-progress", not lost/duplicated data.
- **DLQ does not self-heal:** the 264 K IPF-DLQ messages must be explicitly **redriven** to the main queue
  after Fix B and adequate capacity are in place; otherwise those profiles never resume.

### 20.4 Recommended handling changes (so failures degrade gracefully)

1. **⚠️ SUPERSEDED by §22 — skip is NOT acceptable** (drops the customer's outbound). The correct fix is
   outbound-side: keep outbound current, snapshot inbound data into the outbound row, and recover the
   orphaned backlog — see §22. ~~Implement Fix B (skip orphan per record).~~
2. **Catch throttling in `getInboundContainerEvent`** (or wrap the per-record lookup) so an inbound-table
   `ProvisionedThroughputExceededException` **retries the IPF** (leave on queue / do-not-DLQ) instead of
   poisoning it to the DLQ — distinguish *transient* (throttle/timeout) from *permanent* (orphan) failures.
3. **Provision/So-size per §19.7** (on-demand or capped concurrency + eventual reads) so the drain does not
   generate throttle-induced DLQ entries in the first place.
4. **Alert on `Failed to retrieve ContainerEventOutbound`** — today it is silently swallowed and looks like
   "no work", masking both throttling and a stalled cursor.

---

---

## 21. Go / No-Go: is it safe to drain WITHOUT raising provisioning?

**Verdict: No — not safe at current caps, and it would not drain the stuck backlog anyway.**

1. **The shared inbound table has almost no headroom.** `inttra2_prod_container_events` is provisioned at
   **~1863 / max 2000 RCU right now while the outbound processor is scaled to 0** — i.e. that load is *other
   consumers* (inbound ingestion / matcher + the visibility API). The drain adds up to ~1000 `findById`
   reads/batch on top → it hits the 2000 ceiling and throttles. Because the table is **shared**, that throttle
   is a **collateral production impact on live inbound processing and the API** — the real safety risk.
2. **Inbound throttle = DLQ poison (§20).** `getInboundContainerEvent` does not catch
   `ProvisionedThroughputExceededException`, so an inbound throttle propagates like an orphan → the IPF is sent
   to the DLQ on the **first** failure and the cursor freezes → the 264 K IPF-DLQ grows fast.
3. **It already throttled at these caps.** The brief 8-task post-deploy burst produced **287
   `ProvisionedThroughputExceededException`** on the outbound table at the current 2000 ceiling — full
   concurrency is demonstrably over budget.
4. **It won't unstick the frozen profiles anyway.** Backlogged IPFs (5811/5857/…) have 2023 cursors below the
   400-day inbound TTL → they hit orphans → **without Fix B they poison to the DLQ regardless of capacity.** A
   capacity-blind drain just churns them into the DLQ faster.

> **Note — the DLQ is recoverable (not data loss).** IPF-DLQ messages can be redriven back to the main queue
> and reprocessed, so DLQ growth is not permanent loss. But that does **not** make a no-cap run safe:
> (a) redriving **before** Fix B + the committed cursor bump just re-runs the same orphan lookups → they fail
> again → straight back to the DLQ (a churn loop); (b) reprocessing 264 K messages **is itself the drain
> workload** (264 K × outbound query + up to ~1000 inbound `findById` each) — it hammers the same near-cap
> shared inbound table, so redrive is a **heavy, capacity-bound** operation, not a free recovery; and (c) the
> safety risk here is collateral **inbound-table throttling of live traffic**, which is independent of DLQ
> recoverability. Redrive the DLQ only **after** Fix B + cursor bump + capacity are in place, and throttle the
> redrive rate.

**Only arguable "no-cap" option:** a tiny throttled trickle (1 task, few threads, eventually-consistent reads)
*might* stay within the inbound table's thin headroom, but it still will **not** drain the stuck IPFs until
Fix B and/or the committed cursor bump are in place, and it requires close watch of inbound throttle metrics
to protect live traffic. Not recommended.

**Safe order of operations (prerequisites before any scale-up):**
1. Ship the **outbound-side orphan fix (§22)** — preserve every record and emit a valid outbound (snapshot
   inbound data / recover from S3 archive); **do not skip** and do not throw-and-poison.
2. **Commit the MySQL cursor bump** for the stuck IPFs (move them inside the 400-day window).
3. **Add capacity** — on-demand, or raise the **inbound** table max first (the binding constraint) + pre-warm;
   plus eventually-consistent reads and capped concurrency to reduce demand (§19.7).
4. **Redrive the DLQ** and scale up **gradually**, watching inbound `ConsumedReadCapacityUnits` / throttle
   metrics.

---

---

## 22. Correction — "skip the orphan" is NOT an acceptable fix; the issue is outbound-side

**Supersedes the "Fix B (skip orphan)" recommendation in §16.6(1), §20.4(1) and §21.**

**Why skipping is wrong (code-confirmed).** The outbound transaction is generated *from the inbound event's
data*, not from the outbound row alone. In `OutboundGenerator.generateTransaction`:

```java
ContainerEvent containerEvent = containerEventOutboundMetaData.getInboundEvent();
gisData = gisTransaction.build(containerEventOutbound, containerEvent);   // requires the inbound
transactionMetaData = createTransactionMetaData(containerEvent, ...);      // metadata from the inbound
```

(the transformer path likewise uses `data.getInboundEvent()`). So if we **skip** a record whose inbound is
TTL-purged, the **customer never receives that outbound transaction** — a missing / invalid outbound. Silent
skip is therefore **not acceptable**. (The current behaviour — throw → poison the whole batch → DLQ — is also
wrong, but in the other direction.)

**The issue is on the outbound side, and every record must be preserved.** An orphan only arises because the
outbound row is transformed *long after* its inbound was created (past the 400-day inbound TTL). Correct,
record-preserving fixes — all outbound-side:

1. **Keep outbound current (the real fix).** Restore/maintain outbound throughput — Fix A (deployed) + unstick
   the frozen cursors (committed MySQL bump) + adequate drain — so rows are transformed within days of
   creation, while the inbound still exists. Prevents *new* orphans.
2. **Make the outbound row self-sufficient (durable design fix).** Snapshot the inbound fields that
   `gisTransaction.build(...)` needs into `ContainerEventOutbound` at creation time (matcher /
   `createContainerEventOutbound`), so generation never depends on a live `findById` of a purgeable inbound.
   Then a missing inbound can never invalidate an outbound.
3. **Recover the already-orphaned backlog — do not drop it.** For rows whose inbound is already purged (the
   2023 stuck backlog), regenerate from a source of truth (e.g. the visibility inbound **S3 archive** — cf.
   the `…-visibility-s3-archive` lambdas). If a record is genuinely unrecoverable, that is an explicit, logged
   **business/reconciliation decision** — never a silent skip.

**Required code change:** the generator must **preserve the record and still emit a valid outbound** via (2)/(3);
until the data is available, the record is **retried/parked for recovery**, not thrown-and-poisoned and not
skipped.

> Scope note: the inbound-table capacity discussion (§19–§21) is an **operational drain concern only**. Per
> direction, the primary concern is **outbound correctness — no dropped or invalid outbound**.

---

### Appendix A - IPF 4450 processed sequenceNumber values (1000, ascending)

```
1693243473398_ce:9a7d45ef-45fe-4256-9f3e-a91faa339c9a
1693243474694_ce:253c91a6-5bdc-4653-831c-3a705a649069
1693243478070_ce:aacc8873-7206-4dc3-a9b1-fe8278d425f7
1693243478149_ce:b5931db8-c844-422f-8de5-1335b4a62975
1693243479982_ce:397ec9c5-ca25-4f92-b28d-7aff59c7daef
1693243483244_ce:1f574b31-1092-42d0-b5ee-73ad8e7c1d0c
1693243483658_ce:0c938202-042b-4d72-90d4-fbba44f49365
1693243485487_ce:23942b9a-74cd-43f5-9092-fb8578e5ec22
1693243487129_ce:2a0f1041-f11f-4065-a260-c99f7ae4db47
1693243487264_ce:753a328a-52c0-477b-8d91-e0781017b0f2
1693243487916_ce:036c2143-140c-4c76-9486-8c2e5078283c
1693244233022_ce:9d545aa9-353f-433d-8ff7-0a0a597233a0
1693244345414_ce:2fa3f99b-113c-4500-a8c1-0bbe038144b3
1693244492638_ce:9ea77cb8-bfb7-49c6-abcc-534cb3adaf72
1693245230067_ce:5b0c4380-702e-4d67-873d-204d7e248627
1693245230200_ce:0b4ba6a0-bb4c-417d-9480-1547b1eda66a
1693245231208_ce:222e2240-597d-4170-94dc-4d77d9a0169f
1693245231832_ce:b23a6d37-defd-45e0-847d-0522164d6228
1693245315872_ce:16a4d7c8-12b6-4abd-ad8d-e33069dfe012
1693245401639_ce:1786421d-b833-4d58-a349-94e497ceb6c7
1693245403623_ce:bbc08c7b-d295-4484-b0b9-e23d5cbe4c7a
1693245406284_ce:4034d35e-ed4c-47db-8366-b0e1bd44a52e
1693246300359_ce:97d0678e-bf75-47ad-989d-419872d32412
1693246304573_ce:52de02a2-72b2-47d4-aa55-5487ae6d306e
1693246328976_ce:166efd39-6744-4646-9c04-1d51886ddadf
1693246872320_ce:7dca6762-0031-4769-8280-88dd69946b89
1693247259320_ce:e50145f0-c273-41f5-8714-a7a0dd811b23
1693247476683_ce:a6d25214-3687-421b-927f-e37859f5dc06
1693247521943_ce:adc4722f-25cf-4466-a647-000548e02b1c
1693248930139_ce:2f4cba04-75b9-415b-be0f-369e6b7b67b5
1693249071686_ce:89a6748d-8144-4a0a-b5ae-3411160b42d3
1693250310981_ce:47fc3d11-e9c9-4396-8745-28db61d1a6fa
1693250887345_ce:5505b682-d679-4b03-9bd7-f06b74ccb77e
1693250887345_ce:d1ba8fba-3598-43eb-ae64-fd7d17422160
1693250888765_ce:b84b3201-c394-4c73-b91b-cce8093fe5e2
1693250890996_ce:921b7e09-332e-43ed-b9e2-09595cdc4881
1693251365761_ce:c0236686-2354-4e87-9911-7dd95fa119f4
1693251666756_ce:27e825cc-bfb8-4ca6-8d69-1f691c3eadc9
1693252004495_ce:b32a1569-ac2a-4c4e-9457-2173d1907e62
1693252031087_ce:63b160e6-6852-46c3-80ac-bad0b08d0bb7
1693252031858_ce:36df5097-79b3-4344-827f-40bf09e4fe62
1693252981637_ce:a53152f5-9e3e-4814-af02-40ca7cec28f3
1693252982295_ce:7589044e-8fbe-4f28-8c8e-d7331d863d99
1693252982762_ce:5a3ca3ec-6395-4bdc-b6d4-337ee9632578
1693252982765_ce:26be114e-cb7c-48f6-8d67-36724a3823b2
1693252983457_ce:d40cf2ef-f7e8-469d-8185-cb50d783df2a
1693252987587_ce:78aa1d94-fa5d-4db8-93bf-bc99aa5d6021
1693252988306_ce:9c070c78-6bae-4db0-99a9-c7dbba368a4c
1693252988310_ce:26a9cb47-2af1-4750-adbb-4824e44af58a
1693252988468_ce:17db710a-deb9-47b0-b24d-9107f3b66037
1693252988922_ce:08eb892a-e2f3-42cf-846f-de16c6103462
1693253268859_ce:1ba1e31a-7f68-4835-bfe2-6fbdf746c735
1693253748474_ce:9a9f05e3-9985-4208-bbc0-f9321141bb87
1693253956495_ce:51b11e4d-9db5-4cfe-829e-4549bba9865d
1693254439677_ce:4d751b57-179b-436e-8bfa-06a66ed4759d
1693254659113_ce:4cb6bd4b-552c-42b5-901e-194c17067853
1693254787645_ce:0a00556f-f150-4d34-a958-d7655a1a574e
1693255579531_ce:444c7f63-efc5-4716-b5aa-376bb371bc21
1693256228765_ce:b556db36-239f-438f-af0b-c1b6286451d2
1693256237064_ce:0246a6c0-1a27-4242-a4a5-77ac98512a9d
1693256237182_ce:8dc6cbe8-db25-4369-a505-eabefd78e0ff
1693256238273_ce:fd07db05-401a-4482-a5c3-252301cf644d
1693256239099_ce:b06aac81-6bae-4ed0-b0a4-d161b28e3b94
1693256239344_ce:bbb0fde0-7f68-4be2-b227-477816ec3c7f
1693256483487_ce:25947192-68c9-405a-9ff1-90da3681af28
1693256857008_ce:38c14312-5c36-4d12-918a-3b9fdb5adfe1
1693257476440_ce:e6b79e68-d433-407f-aa27-49f815c06075
1693257691984_ce:d0041bef-eb5a-49e7-ac7a-c880db93ba0d
1693257692610_ce:0efbf505-c7e8-40bf-9d0e-3fedf1d84607
1693258109559_ce:478816d1-c806-489b-aae8-f67313cf5462
1693258259475_ce:ec294c93-f520-44b0-a0d8-a05e4b345d18
1693258260119_ce:ea681ff1-0aff-49ff-843f-5367972c4382
1693258260171_ce:2554e64f-33e0-490a-83cd-1cdce7bc2b18
1693259067658_ce:8b15a9fb-6426-4cd6-8f8b-1666e8b01304
1693259182791_ce:8a565c48-5425-455a-b89a-674ab8c53c1f
1693259572923_ce:b24873fc-7cb2-406b-9790-c296294f106d
1693259787139_ce:fdba3e0f-f985-4240-88b4-4ea408d6cf7a
1693259787697_ce:2ccafb03-a457-4b8d-a131-79dbda3121b5
1693259840377_ce:6efbca53-4b87-4d3e-95db-0e6024ba9312
1693259844516_ce:023e047e-f165-4e91-a149-bc3aa4890ab2
1693259849395_ce:076d7162-a698-4821-8225-8c7d66efdae0
1693259849621_ce:5c21ccdb-b468-4f52-bfb0-6232d98b7112
1693259849662_ce:f1b77f58-f142-4b66-94bf-477933e2b968
1693260552325_ce:0f240458-fe43-4f63-a872-e21a056486b1
1693262403730_ce:6551ad3b-4931-4d0d-842e-6d0dbfc21117
1693263371427_ce:57e7b7ca-3b6d-4aec-8015-872dc17d3c45
1693263392565_ce:0a3c385f-ee56-4375-8346-4d236d613238
1693263395134_ce:24be4c35-b85f-4c44-9eea-6ac4eb57b090
1693263432077_ce:7ec673df-26c2-4959-bc6e-f0f993ee514c
1693263715787_ce:4aa8d036-a7c0-4356-9bcc-388789e43e49
1693263716023_ce:9e981624-260f-4fc4-81fa-f8ed09f0f847
1693263716621_ce:a0a78b61-dabe-42e9-a8dd-9b70c5eccdc1
1693263736587_ce:7eb374bc-e3c8-495c-8c03-ec607e273977
1693265504934_ce:6393ad6e-c390-44d0-bebc-d479fab5d834
1693266999972_ce:bc06c206-4c36-49d5-abf5-3ab09ccb0404
1693267004693_ce:9c1e7956-53cb-4ece-a77d-b9760baffb6d
1693267101322_ce:a75586b7-a9cc-4543-be01-7197e25cb7ff
1693267109292_ce:ce91ab84-adfa-4c3c-8582-a0e69c1476bc
1693269698263_ce:2003036a-0785-44e4-83ed-729ae3ff78d2
1693270832256_ce:03e0d7e7-f715-43d4-b2e3-3bfefcc7a3af
1693273903311_ce:e3fa6959-775f-4132-aef6-3c84c8640944
1693274108508_ce:5a680896-408c-410a-b517-47b70c6f7222
1693275494628_ce:e389743b-2ebd-400c-bdb1-d2bf5706327c
1693275548407_ce:1e041ca7-202c-416c-bea1-908e79a7d1a0
1693275548521_ce:250fa08a-4245-4ed1-a4da-ea5224afb032
1693275548726_ce:9a98b18a-0a93-405c-84a3-6b69f3063d17
1693275548727_ce:b7c491d2-5570-4c19-93c5-8bfd5aad6b79
1693275573809_ce:c7511581-2644-43fb-8e5b-81e0b8ea33de
1693275573982_ce:fe0277b9-3f6d-4189-955b-f8fdbab9e8dc
1693275574167_ce:44c9c53a-0e15-4f1b-8d92-9b25a705fbed
1693275574172_ce:d90c6d53-ae89-4001-a775-29ac6cd7a8b9
1693275618790_ce:36b8c508-4037-4be4-859d-82bb07d4ffae
1693275618893_ce:93aa3357-5b3f-46b7-b81d-5d5fbfc1c26b
1693275619314_ce:4ede6fc8-8b49-4f60-811f-e35dc55d760a
1693275619318_ce:f0e73f7c-a228-46a6-b6cc-0231ced1e747
1693275620949_ce:9cf7d483-dc36-4854-9e89-f1d9bff3a42f
1693275621020_ce:7a525a4e-8b18-4d2a-95b3-e1c4fd24964e
1693275621031_ce:2cbd8213-f793-451e-91aa-f2f6ca37c04e
1693275621099_ce:7bb4cfec-d9e3-4c8c-8752-c48edb0f8fa4
1693275621168_ce:b8cc8dde-e805-4c1d-a7b6-99990d9e7fe8
1693275621376_ce:a7c5ec68-aeb0-4b4b-ba9b-6bc36e05eb76
1693275621377_ce:29769e3c-a461-4bcd-80df-003e8ac20ce4
1693275621384_ce:90c4fb2c-8367-4cae-bee2-2ce80a1bf050
1693275621412_ce:b0ba8fec-f18b-4a97-a6c2-b138fc85423a
1693275621412_ce:e9716c03-fd77-45c9-8da8-413f45c31da6
1693275621817_ce:1f7e7370-3652-45ca-979b-3ff80d8e16d0
1693275621888_ce:4ff45f73-65f1-4db5-9b63-4e5e09e4e3f4
1693276167547_ce:de3b4b00-ec72-4722-bef5-a3aefff263e3
1693276178961_ce:875c9bd8-9dcb-4021-9365-f08db220ce43
1693276178961_ce:e950d60c-5e7e-4b59-ba1a-b450e1847977
1693276178963_ce:fbc138c0-7402-4318-a66c-7b8f92e67b21
1693276182482_ce:e8819dd4-d89e-4ef9-8a40-16d7061a033e
1693276182514_ce:c1bc8fd1-e633-4e1d-ac95-cbab56e186c8
1693276182523_ce:cf4a8d5b-d221-43d4-9165-c3094ab47bb2
1693276190366_ce:1c99ad2b-80ae-43de-9956-9ccdf0159237
1693276258857_ce:38609580-0a41-4b12-98ad-8caf8c88189a
1693276493537_ce:7bab0312-8f2b-4da5-9dc8-0679b516d516
1693276493830_ce:a392b11d-cddf-4ea0-9d78-f2cdbd05a287
1693276545763_ce:7baff289-9218-43b6-a8a1-fdb986b9bf6a
1693276546123_ce:d647549b-7ba7-40d7-bfc0-08b4c1f6b9f4
1693276546324_ce:7c80ce2a-744d-47bb-b054-a4c41883a1f4
1693276546928_ce:16910942-ba56-4d4a-a3e4-075796295b18
1693276546955_ce:74672b5c-d785-45e6-8aa8-106bcdd50aa0
1693276695956_ce:55681d94-5a0d-4753-ae66-c8842d6a45b0
1693276696196_ce:d8d2c685-f575-43bf-a69d-d684421c5ddd
1693276698240_ce:76bd86b9-f59d-45ea-8a3b-861edc1c6ab7
1693276698270_ce:17e1bde0-5a65-4225-8abe-d7b641d5969a
1693276698271_ce:164289d8-2758-4f6a-9275-81cef1121b02
1693276698329_ce:7d8941e2-4fc8-42a6-b655-50cf5010f041
1693276698625_ce:2a8ce9d1-13ac-44cd-9480-a36bec6ded43
1693276698743_ce:97209ea5-7e0f-4585-975f-6dcb607647c0
1693276699096_ce:50f274a5-a175-45ba-8b29-f79de547143e
1693277000315_ce:87ccc156-7c7a-42b1-956e-ea2fda9e5480
1693277001810_ce:01c49c96-7b22-47ef-a884-f2b06933f8f7
1693277804854_ce:391d99c9-f782-49fe-9276-22dc93be70c6
1693277804854_ce:c6dd17f1-5174-4235-bac0-54b26c719831
1693277804884_ce:f39d65d6-c983-446d-91c6-5b9e8328112d
1693277804936_ce:5847abe4-57e4-4bdd-ab83-0da55c844fe2
1693277805293_ce:511d1b29-d5a1-45e4-a81b-b99be0e2d6c9
1693277805399_ce:3eac49ee-8987-4e6c-9089-efbe75ca8466
1693277805399_ce:eca4f8cf-dd3c-4ef5-b2b7-646b3a35a6e3
1693277805476_ce:f8499eb6-31d1-4d5a-bff5-275033101ecd
1693277805620_ce:574bf6cb-5d26-4e39-ac32-26b8d818b0a7
1693277805707_ce:65e8675d-90c3-4911-8069-72f26829d205
1693277805723_ce:694293a6-0391-4f44-b3b0-e4d48175d0ba
1693277805747_ce:b6660e61-91bb-4d59-bf4a-cd89708b479a
1693277846082_ce:6a8718c4-cb77-4f3f-bf7d-f9a41b1f69b1
1693278229497_ce:40192081-d403-44dd-82f2-9b6a78b013c9
1693279157957_ce:2d023a02-3579-4c0f-a0d9-7cd74d412773
1693280675392_ce:570648ee-fb97-4b37-9f1c-265bbce1b2a2
1693280675515_ce:602ed733-1f0b-464e-9a73-07e28dccff24
1693280675516_ce:f056800b-d809-40ca-94fd-092be99366da
1693280675590_ce:0cb9c064-3c5b-44bc-9e1c-d503eb45543e
1693280675618_ce:c22c1c42-77ea-46c9-859e-78f81281bc55
1693280675619_ce:00909f58-83cf-4765-b1c7-4c1d609303b2
1693281395689_ce:b90535c1-dc28-4bcb-a79c-5b3edb4c39da
1693281397028_ce:0e5332c3-9ccb-460e-894b-7a95f2441124
1693281399889_ce:de21edb5-fd02-471f-b01c-012623c8f918
1693281400975_ce:821e61c3-a385-4bae-9fa1-e58ae618d17b
1693281401260_ce:b96cf2ff-df06-4857-ba36-2bd7d1f84503
1693281401741_ce:04f5af13-ac3f-483b-afb8-d8c4ed73a3bf
1693281402131_ce:d0316535-8c74-44d1-ad64-771830f82298
1693282881837_ce:30b158ab-4c1b-4e15-84d6-5ecb88cb22e2
1693283470375_ce:9ba7c273-0dea-4c83-94bf-8e70a801ceb0
1693283471131_ce:ac70f3be-f55d-498e-8280-d98ce176106a
1693283471350_ce:1bf5dcfa-841a-4344-9c8f-8fede7df86e3
1693283471413_ce:b687d75b-4b8e-492e-ab2c-ae34ca6a9a92
1693283472196_ce:dcea8831-0966-4856-b5fb-6849a0487348
1693284077855_ce:a20fda41-1296-4509-a456-bfc755decb81
1693284080987_ce:aface7c4-87e8-48ad-ba65-fb9f63e52868
1693284674102_ce:ba2fade4-e777-4d20-ac41-0054b56539a9
1693285326491_ce:74c2735b-8d2d-42ab-8b30-c2c98c6a0052
1693285327235_ce:42065601-ebe0-4320-b77a-78fbe2288ac9
1693285329497_ce:b5086f4e-21d9-4bb9-bf67-84d7c2cde450
1693285331505_ce:41e738d6-5e55-439e-89aa-adbaa0b7be5c
1693285341132_ce:0a0a2f0d-b107-4f03-a425-4607ac07dc76
1693285376488_ce:57275040-cbf0-4a25-92dc-94603f523870
1693285377497_ce:c82dbb7e-baff-41ad-9bea-764c859a1e93
1693286485633_ce:2e1ee900-a3ea-445b-8733-c6a0b0c003f8
1693288580394_ce:3d119615-0cbd-4b06-9a26-afa62c4989d2
1693288580653_ce:69e653c5-9b57-4e72-8b24-d0598ec55e88
1693288581959_ce:100cd138-055b-4a73-b8ae-6c330b12427c
1693288582959_ce:056b3063-9cc9-4d12-877c-0eabf95b6f9b
1693288605674_ce:2d6d9803-56e5-4647-9427-3270c0f977fc
1693288606533_ce:90f0e0b1-5e66-4ff1-abe0-048b1cbb354b
1693288608810_ce:717d3491-80c5-4057-9e6a-d5322f0e9e99
1693288610749_ce:cdfaefd7-8f45-4851-9f7e-ba1946194bee
1693288616462_ce:38cf2e55-51bc-4dd4-90c8-3ea7832342a9
1693288619472_ce:568ae24a-609e-432b-80ec-eba9a75b49cb
1693288792450_ce:36fd33c2-35e5-4e48-ae69-361e7098bb60
1693288800494_ce:e4f5d115-a60e-4739-9dff-ec691571285a
1693288802207_ce:338accc4-fd45-4458-9ab8-650f44f60be8
1693288832825_ce:733b6ae5-28ad-4b43-8cf3-5c2175807fc1
1693288832939_ce:815cc905-c67b-4481-85f6-969668a2850b
1693288832977_ce:3dfd9139-f273-414d-b516-d6809af64599
1693288833381_ce:01cc8cc0-78ed-4936-b94e-d777cfe0e3b3
1693288839798_ce:ff4dcfd3-34eb-45a5-a4a4-52fec3a3bb13
1693288840059_ce:bd183cd0-f211-4157-a8be-75a9696d1f29
1693288840149_ce:1d4def73-33b1-48b8-acf1-9e7aa0a661a0
1693288840173_ce:e20a89e5-09dd-4f35-ae1d-61a6896d249e
1693289508194_ce:a2d40c23-f9f0-4930-956e-41366e896cdf
1693289699055_ce:e44db632-407b-48f6-a7f6-b90c563ed8ea
1693289699211_ce:fb5ae50d-83aa-4b92-97ea-41b00e9f0fd8
1693289699303_ce:3e712ab7-2aa3-49ac-8478-d67a030a28d4
1693289700731_ce:166697b0-8b4e-4bfc-9e00-882763ce571c
1693290084999_ce:b1369b3a-f13a-401c-af02-ea7dc1e61cdd
1693291016539_ce:e717bd9f-f32d-40a7-8183-efdbd54dc753
1693291922537_ce:b514b56e-9423-4c04-8368-112a716dc1ee
1693292257087_ce:d9b4de14-914d-498f-9142-5e4ee817a8df
1693292259139_ce:c7a80468-e4b8-44d9-a035-df8315c906e8
1693292259362_ce:65fa74b2-9f5b-4c16-b2d7-1960cbb5f1dd
1693292260856_ce:ae6c25fc-26af-46a6-8fc9-6b80f9aae7d8
1693292322243_ce:388b939c-120f-42fa-9d4e-5c64a18e517a
1693292322244_ce:a4401365-3eca-4a52-826f-a79b93278c7b
1693292322311_ce:ff057fa0-9188-4480-9099-55f60bbe2fbb
1693292322380_ce:e3fd2a52-123e-4a12-a74b-1416a60e5762
1693292322642_ce:922dc881-2608-4874-99b0-be67e9022f94
1693292322675_ce:083eaf1f-fd7f-4518-9e6b-6858aa8a5164
1693292322706_ce:96c80f8e-e3a7-4b54-8ef2-aaf9b2690ca6
1693292322709_ce:eeaafa15-76a2-440c-b0ce-68ec305f433d
1693292322815_ce:7542f20a-c936-4024-a175-8e54a609be75
1693292324257_ce:8e4a10ce-ae4f-4d3e-960f-7a4acb428eea
1693292330825_ce:68573aee-9857-4030-8ce6-39a7ca1ddd5f
1693292335206_ce:b95a0878-60ec-4454-8075-4920cbb6c269
1693292335273_ce:0e38826f-ad26-4fb7-92c7-6540bbc9fcde
1693292493987_ce:1d913b50-432b-462f-a6d5-200a4656376d
1693292808761_ce:16f6ae06-4c8e-4eb8-a41a-6c7fdf0885f0
1693292810706_ce:a0710696-6429-4115-b6c3-31724215bd41
1693293018278_ce:a8888335-69de-4b57-bff2-2323557c51e5
1693293213248_ce:c210e85a-d0d4-4881-9306-8f6acb09a3f5
1693293213347_ce:5614374f-4be7-46fd-96cb-fb754702ab10
1693293497234_ce:8026c6c5-d263-4cdd-b0be-7e2f9a2bd2fa
1693293497344_ce:0f1f0b8c-e9bc-4934-93ac-33ffe81b0978
1693293497448_ce:1fa7d151-6f8c-475c-b9dd-13d6ab766121
1693293505284_ce:cfeea2c0-d9f7-47c1-9a04-49ec7323b03b
1693293505508_ce:12b485bd-9661-47f3-a839-decb1ec90a50
1693293699268_ce:5dd11d85-4ca8-4295-af8a-3cd7eee18170
1693293754934_ce:b10c49ce-314f-4955-a70e-19526c23f53d
1693293755040_ce:23c37dec-da13-4066-af41-654842d8298e
1693293755231_ce:a1f883fb-14ce-44ba-86fc-5f76cc6f078f
1693293757859_ce:70d904e7-c7bd-445a-b982-6c1366af449b
1693295621783_ce:bc46c198-dbdb-43e6-bedb-579e91f9de88
1693295653086_ce:294e95e3-35dd-4ae0-b345-0f7634544809
1693295666021_ce:18e5e91b-9393-481d-bb49-669908fad593
1693296229226_ce:b9fc707d-3e43-46be-b353-ee1fbef89cf4
1693296229227_ce:58547360-660a-4724-b839-6dfcd80d623b
1693296229227_ce:f5fb9357-85f5-462c-a5e5-5d65deb3ef3c
1693296229338_ce:50ebba9d-a43d-4236-a9f0-1330e580fd25
1693296280451_ce:82886e60-3fae-408e-acb0-62e4a8d6bcc8
1693297340817_ce:e245b723-9fb6-4fa4-acee-e636c18cf109
1693297592626_ce:1995396b-dfa5-4375-ba62-77f73d63a543
1693297876106_ce:5c00f370-21d9-4a96-82b5-f30382cd632a
1693299050971_ce:b19b8993-965c-4864-9dbb-1093211eaeea
1693299051090_ce:341ee26e-e773-4371-9775-c786d76840cb
1693299051375_ce:69f8a0ff-bc8f-4f1f-9bf4-4746c31a0c82
1693299051442_ce:9d4084f2-f6db-4350-b8db-10d732cadff4
1693299051448_ce:74fb6cc0-d93a-494e-b7f0-f991b4f9c424
1693299051514_ce:c0643376-2da7-4074-89ee-c29033dbca49
1693299119030_ce:2d63ec66-2d9f-4a23-bb80-4e71a1f6aa10
1693299761033_ce:cad19871-ef28-42fd-b2c1-356aacc8b604
1693299761128_ce:da718919-83b5-4209-a1c8-526038aeace0
1693301094683_ce:6423c54b-7a2c-4686-95c5-b5dd92458234
1693301094811_ce:6c1145e0-4033-4185-872e-5075a9fcea07
1693301195354_ce:2513df5b-f804-485f-8e71-3b7e1de91a55
1693301249572_ce:e428b536-5082-4018-b5d4-3f2bd43234cb
1693301249941_ce:d86e8491-6c79-477f-9832-1c367f044fa6
1693303118105_ce:1e51c6b9-1f2f-43f1-80ad-e880f5472786
1693303118201_ce:6248666e-93d8-4fba-a1ec-97ea2bfee814
1693303119633_ce:02efd7c4-f60c-4654-bb72-783d88fd8af3
1693303121034_ce:4b39e0b1-d15b-43d0-9a79-4574f95a61cb
1693303442843_ce:5e2f6e7a-39ec-426d-a18a-c0f4142d1966
1693303501161_ce:cd9419c1-e178-4285-bbc8-818f0c1ef3a9
1693303501932_ce:44bc2a17-d7a6-4be9-80a5-43a1c3f423a8
1693303930142_ce:43b70247-de18-47fe-a645-5fc0b1c984af
1693304169600_ce:1bcdeee5-a0ea-4c42-84e4-fe15bc3ba0e0
1693304169758_ce:6d8d2878-d1e3-4f7f-94c3-0324539fac41
1693304244146_ce:67aa207d-1fc6-4bc1-90ea-5ba8f5b64ee8
1693304246575_ce:3f187f8c-f8ed-4257-9a6a-c9394237ace8
1693304827710_ce:2b301aa8-8242-4d9f-874f-309235a9e52d
1693305100568_ce:611440d9-a240-420f-b7bb-3dca4f8064fb
1693305787196_ce:89ff911b-0cde-49ea-a249-0f4d8d0bf764
1693306318861_ce:400ae595-f604-44f6-9a89-281b93bbbce9
1693306929756_ce:15b06067-7590-4462-bc0c-6dfde20916ef
1693307019718_ce:7386dae5-39a4-4cbe-b504-413691abae71
1693307020962_ce:de8545c4-ea1f-4434-b7da-f49faef876bb
1693307496791_ce:bed66e2d-fef8-4609-93f7-daeb28c340b7
1693307502821_ce:4d3fe604-08f2-4132-8f68-a599d2ba7e24
1693307859230_ce:fa37b113-47dd-4589-8280-d5f5868b4242
1693308395609_ce:e1b406d8-6ed2-4eeb-8342-73d7929450b1
1693308397211_ce:a944c971-612b-4807-833e-14913329746b
1693310000489_ce:cea485fb-0a73-462b-92e4-975457308851
1693310419821_ce:3f6e9a23-11bc-4aa1-8b94-23d89455db6e
1693310419861_ce:ef4c4e73-1649-4085-a344-5b47952e0db5
1693311120264_ce:c8374205-ce6f-45f1-8111-a78aeabad0cb
1693311452199_ce:800559db-f186-429b-9098-cf003d77efb8
1693311714398_ce:6dea7590-8f7a-48f7-94ea-456a0994a78e
1693312038554_ce:18b26e46-a570-4630-bf1d-7c3a74d20251
1693314201961_ce:18087e91-7a19-4bf9-8f0e-0456b717c6d4
1693314207846_ce:ed57ae2d-5d50-4342-acea-428283e9631b
1693314208116_ce:fd967df3-980b-4b30-87aa-98e7f32a2747
1693314252685_ce:ac3b7495-079c-48d5-a031-e866f2440c23
1693314406675_ce:942c36f3-3ddd-44fa-a28f-d52a51fba53c
1693314473315_ce:4962d8bb-35a3-47f8-b24f-d8804eba18e8
1693314494381_ce:c7406f70-3aad-475f-9e21-22a6ba931315
1693314494636_ce:2f191fc9-a24a-44c0-b365-38a641a17326
1693315914577_ce:b01f8096-6b8e-447e-afa7-4f26b74ab58e
1693315915485_ce:2f25ccb7-be87-4ef2-a158-5ecee6931b47
1693315986506_ce:d0dbd9da-da9f-4758-b594-322cc403f1cc
1693316885269_ce:bc3d6622-0fe7-42c7-9ed3-8345c451d393
1693316885269_ce:da97a02c-5d3b-4b62-9fe9-aa497f461ae9
1693316885367_ce:712fb137-08de-450a-8f5f-5dccdbb06d3b
1693316891685_ce:3c2871c8-a774-4ab4-bbf8-d327260602cc
1693317909986_ce:b2b1f6c5-ea91-4855-b8b7-ec48ce56b059
1693317910120_ce:8a2a3bc1-2925-44bd-af7d-95c974f03905
1693317910187_ce:827cdcb8-42c1-4ef8-9845-3a848f602db3
1693317910427_ce:f91527a7-943a-442c-af41-f49133fe4dbf
1693317912342_ce:9ca25a65-cb61-412a-ae8e-0b317c344aa3
1693317913035_ce:4d897021-801e-4efb-949f-99d258cafe1e
1693319197963_ce:4d0ea9cd-e088-4750-af36-77da8e34f525
1693319206614_ce:3036ddb9-b1f9-40eb-82c8-ec534f8271ce
1693319530655_ce:62969ccb-f804-4946-b41c-515cbbd20143
1693319530688_ce:8e37d27f-ced5-417a-bc9f-d5779d10dfc6
1693319530829_ce:2db7412d-7412-4744-9a69-0e09286df629
1693319530941_ce:c4684651-c7a1-4f77-b76a-106c3b9ea741
1693319940301_ce:bb233a4a-86c9-48ee-94ef-466bfebfef4b
1693320113797_ce:b4370306-8613-46e8-88c5-6f389daec593
1693320706890_ce:ad5ea9cb-f2f4-4011-9f34-b7911fc04564
1693321034594_ce:a67ad1c4-56dc-4371-8f04-9a1f1dc6abd3
1693322166166_ce:fe21dffd-d387-43af-9e52-fb0083516b59
1693322320120_ce:e1a68bef-253c-4597-96a4-acbf02eb9b59
1693322320124_ce:e7e51cf6-54df-40b4-935f-98aede2e3201
1693322320205_ce:f75cc989-81aa-4cff-b180-7c1d215d8961
1693322320543_ce:36957e25-4194-4698-a744-fb48ae73bc43
1693323734200_ce:9de9d20a-4fa4-4115-a041-462c1bc1b93a
1693324605577_ce:7f0ae1d8-f178-4b54-94f0-c73740651b3f
1693324691187_ce:a1fd1949-d3dc-4561-be2d-0d84f691abe0
1693324973329_ce:010acbf4-de77-4155-a5d3-96b5245a85e1
1693325177605_ce:b56d1b89-58e2-4839-a161-03ce4b066b52
1693326459861_ce:6ee51ff8-f6c3-4cad-9990-d3ec64a4c8b0
1693328335726_ce:b533645a-a229-4a91-bd32-845f275587c0
1693328348145_ce:f87b0d31-6457-4277-8f83-f0194f0e6441
1693328349340_ce:c945c1ea-be66-4bad-ae40-fc790ed8bc79
1693328350283_ce:82a790c0-3435-4f97-a0c8-b4bed24e7ffe
1693328353226_ce:4eb36eeb-0e95-49b7-bc03-5dc3d41b50df
1693328356537_ce:2abcd9f2-053a-457f-8ca2-bb1cfc4e734b
1693328357171_ce:9453f9bc-5f5a-4a9f-b027-a93d742fbeb0
1693328360165_ce:327e3788-c3dd-4ed6-bf7c-940f15d397ce
1693328374099_ce:b8419b8d-57e0-45a3-8140-bda5400f554b
1693328538129_ce:082dc924-2a0b-4414-bbcd-69f2ce107051
1693328543459_ce:99f13586-b387-41cf-ad9f-55f1a8aacbcf
1693328863733_ce:f06507aa-cfdf-4151-83f1-437732cec055
1693329694510_ce:9f8a8e7c-7c0c-4eff-985c-fb9a58247525
1693329995378_ce:41c1bb38-b2ad-4787-9006-184600822139
1693330616064_ce:29b7c18b-f0b4-4a5a-abbb-ee74543aaf0c
1693332171272_ce:fc498bb7-9665-468d-80d3-783e6beb1806
1693332175491_ce:88c17cf8-440c-4172-937f-8e75b97f792b
1693332175608_ce:601afc5b-864c-455a-8fbe-3ef29c99fe3c
1693332175608_ce:6f873c15-959a-4a86-9f06-b429b09884b3
1693332218139_ce:7a9c55f8-5854-44b0-bdf2-7adf6ee4cfc4
1693332374727_ce:257a5561-ccfa-43e9-9ae3-ea73f8f831bf
1693332374728_ce:fae01a3a-ce5a-4a2f-bcf3-b974e36ca276
1693332375307_ce:eb464f2e-886b-492d-9cf5-5e7d676244fe
1693332747902_ce:b63e62a0-7316-424f-b10f-507c08bb29b1
1693332993014_ce:d43084aa-27b7-4f78-8b01-355c47aa4f5d
1693333049178_ce:aefbdadc-a844-4ebe-9aad-39fd68242d5c
1693333050218_ce:da32cc28-d22f-46d0-a6a4-fa10dabd990f
1693333057719_ce:ae3d38ae-6daa-4a05-8a7a-01627a3ac4cc
1693333359525_ce:dd44009d-e09d-40c4-b147-c4c9e2328c2e
1693333361872_ce:d56fd19c-7479-4ae1-8693-ede8889665ba
1693333362118_ce:af7a63a4-27d0-4418-abc2-fcb430a3c597
1693333362166_ce:108a6648-8221-4a5b-9dd2-db211ac48821
1693333362178_ce:d922fea6-8f19-4cb2-b2c9-19b279639753
1693333362215_ce:33febcb4-2b83-4bba-a31f-98c29bfc6321
1693333362670_ce:5683de2d-9e05-4747-9dc7-6cce36fd784a
1693333364640_ce:9b9c2684-df69-4df2-bdd2-43d48a3de4c2
1693333366061_ce:94899853-75be-4b79-bda4-97ced357f233
1693333366162_ce:eb60a107-f721-41a6-a4eb-444a752eb7cd
1693333368517_ce:985f31e8-80e0-4fac-8e10-31966fa5e4bf
1693333370273_ce:3284d309-4cd3-453d-b3cc-2c538c29ecb7
1693333370592_ce:97055042-b7e9-49cc-95ce-232d35b7e53d
1693333370778_ce:14c689e3-9c22-470d-9af9-fc4d62554f61
1693333371031_ce:d43c0d6b-51d3-4e90-802c-907fb7caef11
1693333371262_ce:4fb0a8f6-cf7f-4bd8-901d-873167c4f520
1693333371827_ce:faf14619-c017-49da-ab65-3f3ed635468b
1693333371969_ce:14c892ba-4224-4c43-b120-fccaf6323aec
1693333373181_ce:75a6cc4a-08eb-48ae-9146-cb7746f55752
1693333373416_ce:fd519703-bada-401c-abec-6c2801364d76
1693333373734_ce:ee136839-1899-4865-a484-269d824175ea
1693333373777_ce:65c39136-4364-4012-b648-bfac4de62368
1693333377836_ce:b9d98c59-0c89-4b58-9e0c-5b6887d829be
1693333379937_ce:703bbc06-14e6-4131-9e7c-c15b1c565959
1693333515428_ce:d3fd5dae-b19d-4af3-a79f-c18e0fa773d7
1693333515439_ce:5ba0328a-44b4-4a36-a9c8-629abab073aa
1693333518543_ce:26a0e84b-2bea-4284-b6f5-84732b044027
1693333518873_ce:befe79cf-7cbf-4545-95c2-8e1b665a79ef
1693333519017_ce:a73ce889-9b35-4cb4-bf0f-0b71375891e7
1693333522044_ce:ce6d2038-1fac-4e94-a5aa-0bb487e5c8e0
1693333522665_ce:f8201f70-9b04-4f90-8521-e34fae1668ef
1693333522784_ce:b0ce0cd8-d99a-4091-b5fd-bd421057b5ca
1693333522896_ce:9a32dca8-1ef4-44a8-9f06-256e1a048ec7
1693333523444_ce:3f850051-6ca1-4527-b560-23a8535710ca
1693333523729_ce:d9a4a454-185f-4fd4-8ae4-a95c6a2f5201
1693333524894_ce:507fa9de-25aa-4a9e-b151-447b95b81b5e
1693333526706_ce:2b1e8ec2-0621-47e5-aff9-f149b9085eef
1693333526731_ce:645693bf-32f1-40bd-b75d-d588dfd72919
1693333527094_ce:bc7e3580-a026-4725-86f5-72241f4924aa
1693333527913_ce:b84f52a5-b7d0-4f62-9fec-6c1b5918be84
1693333535459_ce:4099c5c1-5496-452a-8062-aeca1ac75317
1693333536646_ce:d01e8bd3-5f3d-4c81-b264-1f1918c2bae9
1693333542553_ce:9f80dfc7-5bec-431d-aa59-3ccd062e01d2
1693333543576_ce:a600b8c1-2961-47e4-a82e-6e766c6d6246
1693333544130_ce:03eec7d8-d6eb-4b36-97f6-fceaf1f7f0d2
1693333545078_ce:e668b6b8-19a0-4c09-96d6-eba502df73f4
1693333545125_ce:6e104003-141a-4c94-9049-b411cac5b502
1693333545496_ce:8dc6eff7-61c5-4628-a0cb-4edbabb6a664
1693333545496_ce:ae5b3e65-4054-4c70-9c50-78904f7cd9a1
1693333545670_ce:18236531-fbad-402d-b38a-e759dbaade47
1693333546641_ce:9532251d-5e0b-4883-bb8f-2266fc2a081a
1693333557691_ce:688e8e5a-0685-49d9-adb0-52ae0c9cc4b9
1693333559226_ce:0e93afb1-eda3-43ae-8aac-268c2d179cf8
1693333559456_ce:fa956853-2440-4ac5-a84d-ab4c469b1fbc
1693333559457_ce:a3860ed1-e5f8-43a3-b886-758f4575aaeb
1693333560038_ce:f8a4c3a5-787a-40d5-b5f0-61ef5a5eb8e9
1693333560454_ce:106e489e-a487-4b08-9a8e-876079f6ad76
1693333561043_ce:7d0dd0df-c931-4e65-91f7-42d9c95fd9ae
1693333561381_ce:b72e31de-e397-417d-be8d-699c97ac0c37
1693333565746_ce:89f7f285-cb24-42f1-900f-b0ee61305078
1693333566326_ce:88a90411-8aaa-4123-b2c3-f4fc36680506
1693333570197_ce:bd66bf09-fca8-4a04-80a1-29344fd76748
1693333570337_ce:be390529-eb90-4118-a738-502b1a9ec834
1693333570903_ce:e3657a48-f4be-49cf-a231-6b59f56fa1e0
1693333571409_ce:b76350cd-1079-4e03-8bc2-d480ca2fe608
1693333571791_ce:80974ad8-69e0-4a6d-b6cf-93c3286b6a18
1693333572149_ce:870499ad-e283-4d7b-be11-897926425dde
1693333573582_ce:7226b01a-4809-437f-85b0-d4f222e7fd29
1693333573671_ce:8dd5118a-3744-49bb-b80c-4880248f2a77
1693333573738_ce:c9d5d269-2493-49c4-8633-8e3155b26b94
1693333574934_ce:301affa2-db25-4b14-9a53-20abb514ef56
1693333575374_ce:0bb38ed9-a021-40a6-80d9-940cb6f17b6a
1693333613357_ce:65b93449-1316-4207-af3b-d6635a8648d0
1693333613629_ce:3f018b45-a015-482f-98ad-09af64f94e9f
1693333614514_ce:78047b25-64da-443c-b8f7-f349bddd307d
1693333615144_ce:d5b803cd-f33d-4234-be92-03643bab4856
1693333615487_ce:b6fb0033-c715-4b44-a109-735cf7925f6b
1693333615487_ce:dc42604b-c49d-40c2-ad21-4c5a758807da
1693333616208_ce:c70bd751-16fc-4a6f-9235-0b80ae394c3b
1693333616434_ce:902f5894-8d47-4516-bcc3-ecc076d57adb
1693333617394_ce:0f414a67-3ae5-40de-82f4-4430ac6f8704
1693333617667_ce:71805389-c21c-4dc7-abcc-2502975cf4c9
1693333617853_ce:ecd20a4f-f9d9-450b-8833-30be4c6f8a10
1693333618333_ce:ec027f33-a86a-4f7a-bfbb-f2dd6e6b6776
1693333618382_ce:4cbd3519-885f-4fea-a336-fe3670a2bddc
1693333618741_ce:75522b9f-d98f-49f1-b2e2-6c27b668c332
1693333619384_ce:3a378ff4-9bfe-456a-9079-eed2255267f9
1693333619564_ce:809c6591-1ba3-4a00-b044-bf425312338f
1693333659205_ce:6d2ef43a-4cc1-4ccb-bdd0-86c1c654fe5a
1693333697321_ce:5b042c7b-4b81-4b79-a3f5-36261ea60f06
1693333697540_ce:bc41cbe0-2e66-4a28-a4ef-c52ae9fcf7c4
1693333697808_ce:a59fc195-dc2c-4a90-b435-62b2be67b442
1693333698586_ce:2dbaf069-e37a-4ef3-922e-a15b26bd484d
1693333699897_ce:46d87dd6-eb6b-4b98-8dd9-a91c925679a4
1693333700421_ce:c9f2e1f4-2f16-4799-9b69-4bd180e87d79
1693333701321_ce:7968891b-7b4a-466a-a908-d822b727ab09
1693333701378_ce:b5517b43-72a1-40ab-b8e9-8f196cc62867
1693333701677_ce:83acedf1-af2a-4ed7-afc6-2eb86894bb8d
1693333702231_ce:ca362dba-730c-4642-b246-c325204f15be
1693333703114_ce:5cbc6dc7-0989-4ca2-bb6a-c5ff1b677dcc
1693333703628_ce:cf733600-6898-47dc-9a3c-6d45158a9a27
1693333704589_ce:faf47448-1949-4438-aee0-1813a9d39065
1693333704680_ce:606b50f9-9f9b-43fe-8de0-1f8f3479261c
1693333704733_ce:d4ac3744-5059-4375-bbb2-5cd3dd51b862
1693333705165_ce:ed39584e-52ca-494c-8a2f-76581c1eaab8
1693333705213_ce:0273d559-85d6-4048-94b3-3115f0c40128
1693333705759_ce:2d9e0c5c-62a3-44a3-9015-00b7167c0074
1693333706478_ce:fc739ae1-a2c4-477d-a3ca-f62c77e89ac2
1693333706568_ce:688301f7-7279-4401-ba05-c102fa769434
1693333707316_ce:16433b37-d547-4a91-bf08-126b7f93e7aa
1693333707679_ce:f37918df-7770-41ff-932f-68853084b869
1693333707836_ce:e68296b8-3f33-4a10-b9e6-95955ba7b07e
1693333708000_ce:18e88021-6af1-45e9-b731-c844e9db1998
1693333708362_ce:4d6533db-d31a-4655-acbe-d735bc52adf0
1693333708591_ce:e42aeda2-f6ce-419e-aba8-44623bef3558
1693333709267_ce:6d85b84f-bcc4-467f-bed1-e08f24dbe133
1693333709760_ce:b2cf3bfd-c8f7-4c78-9044-d2118f4af96b
1693333711284_ce:b7942668-5e98-49a2-8dd2-d84e3550e023
1693333711285_ce:a1520b3b-aede-451d-b971-87c3dd7f7aed
1693333711511_ce:df5824c4-db19-4878-a031-8afe871f169c
1693333711710_ce:97465a9f-2499-470d-bda9-ee9acefc5db4
1693333711745_ce:5961a82f-bcec-49a2-b750-b98a965594c6
1693333711996_ce:b1724bfa-e3cc-4d84-876f-0353ad5a1265
1693333712190_ce:50019148-975b-4cd0-bc98-ed72e0a9dce0
1693333712544_ce:f0316e40-61c5-483a-83fc-a88d2e89de81
1693333712611_ce:90f89c01-0246-461c-8b65-831463dfcc70
1693333712673_ce:df97537e-5ece-45a0-9128-e1b072860fa4
1693333713328_ce:43d74fe3-d138-4507-a67b-af4a8708ea57
1693333713716_ce:6acb2a1d-08f7-4d46-a54b-246dd9f0c3cc
1693333714011_ce:07c8b2c6-c59a-411f-be91-258533bd0f03
1693333715142_ce:53601e5a-fcf6-4e7c-806a-b5e2a0bb60dd
1693333715323_ce:8bb38829-71aa-4d8b-8266-8e2d0467b701
1693333901053_ce:f8e0f061-a68d-406a-9850-954354500ecc
1693334861719_ce:eeefdb23-e62b-43ad-b7fa-9cfde79417c5
1693335082298_ce:cce7b079-8a13-431b-b961-e54fec85f2f5
1693335128074_ce:1e8bf61e-8067-436e-b32e-305b14e8c561
1693336305115_ce:0a53f1cf-b057-4f5d-9fa1-3b0db26f38b5
1693336628196_ce:df26dc52-1ddd-4c90-9f95-d09b8e649b0e
1693336720465_ce:582970fe-649c-4d86-8975-5e87371aa49d
1693336721284_ce:68e10d67-1ff6-4305-8b4e-6b06e1a25deb
1693336722342_ce:9cbcf557-1527-43e0-8952-32b59cc347ae
1693336725209_ce:ccaf29c6-c5a5-4ab2-8043-55c23ad71fa7
1693336737411_ce:d69f717d-581e-4dd0-bf85-bd4427fb2c66
1693336754680_ce:53908f9e-c3b2-42f1-a812-15597e00e72d
1693336905661_ce:15a8105d-103c-4c37-a4ed-d427db47cf72
1693337501413_ce:58e47eb4-e857-4f97-9d4a-e6656da3e35b
1693337501531_ce:0c711f85-eb37-425f-92c2-59e2350543b6
1693339046963_ce:5b5a2159-3e1a-47bf-92de-b2331ee1402e
1693339094056_ce:aae13859-cee1-4cf8-a3d6-d7cab6f09bea
1693339094353_ce:35286449-938f-40b8-830c-fb4a0b273d28
1693339385234_ce:09a5d7d8-97bb-4a1c-a260-7db5073be0fc
1693339391674_ce:714e9bb3-0f54-4a04-a9a2-89b5b1544f6f
1693339584059_ce:7932e2c7-2e05-4c56-8b6b-02ec37c2d694
1693339943356_ce:c77ad786-e1f8-4ee9-911c-6494fbd42194
1693340497612_ce:0fc7166c-b315-423a-91d9-75783215b777
1693340498487_ce:d8efd49f-2588-4885-b3dd-829f17cea51b
1693341202772_ce:42d4bc1b-ebbf-4a64-9772-0baf687917d7
1693341202852_ce:95f7421a-9456-4401-82b0-99a0d4201553
1693342922497_ce:083e7c49-0e6f-4077-862a-37b2034f496f
1693342933240_ce:f95330fa-7a26-4285-867e-6ac8a2c56f1c
1693342933486_ce:4f10920c-c007-4055-ba91-040a3cbc1ca2
1693343490218_ce:f741a389-68fb-46f1-9c3f-ca8e5c4d7111
1693343490684_ce:acceadef-3821-459d-9c4a-37d28e1a86ea
1693344055567_ce:db8382a3-fbdb-4e86-9399-f3c8d3579ab9
1693344131677_ce:351d80ed-44c7-4ba3-bf8f-1bf5508c764c
1693344682258_ce:22e63892-a723-4417-825c-07da6ebb7a49
1693344683497_ce:09cda002-3c07-401d-b0bf-884d430a832e
1693345893801_ce:d1920639-a14a-4f00-9622-622864b61670
1693347329696_ce:8aa2ec8c-a755-40e6-b6ca-2a98918148e5
1693347358484_ce:db7cc62b-9f22-49e5-b5fa-871b9402928c
1693347401559_ce:dced126c-e564-4c06-869e-1698a6fa4e26
1693347404735_ce:a65408d6-3441-43cb-bde9-1c354b8c3c76
1693347406297_ce:905feb40-f7a3-4f0f-8327-f311758dc562
1693347407473_ce:7b4c9adf-c0cf-4e0a-a903-ec88fa5c9f2d
1693347477736_ce:632a8604-d394-46be-a65b-34212db3b5fa
1693347478006_ce:196e70d6-6979-4bfd-8467-b8e568614708
1693347478007_ce:4df7db14-7665-4c4c-8670-f390f737c1f1
1693350112909_ce:ff1676a2-bfd7-4ab4-a894-13e5d1d6a0af
1693351262805_ce:acd9d78b-6295-4b63-b60f-b81d54b10976
1693351843119_ce:ec6e756f-34eb-423c-8b97-ecea3f0ae194
1693351849340_ce:858c0358-4e46-4f32-aadf-dc5da083bfc9
1693351852796_ce:469418b8-cbfc-4e3e-8c18-d677092e985b
1693351867630_ce:3078dd7e-2f3d-4e60-a685-a7a1cf5c1b2c
1693351867965_ce:b04fdbda-6f09-4b81-8b50-804a978c7a11
1693351868447_ce:55fe87d0-5bf5-41c0-88c9-276b028c66df
1693351877736_ce:394bd38a-4f62-4495-9348-b5ceb8e22035
1693351879819_ce:2b207027-9d3b-4b2a-b4bf-dc5aeb77f8e2
1693351881812_ce:27e852de-bb62-4983-bd0d-a676afde604f
1693353250290_ce:75848cc9-5281-4152-908f-75ce5f295f26
1693353722905_ce:8d066e45-57e8-4d96-9f56-8a83c2a0aed8
1693353727289_ce:5ea8cb30-f671-49a8-a2ef-d20f543c0505
1693353727983_ce:f50e3bdb-d92b-4d3b-89fa-6cc601693a8f
1693354988910_ce:b2e4087c-1ad5-4e05-8596-d36d4fc5fbcc
1693361802978_ce:09675d54-2abd-4f66-9bb5-e9ba730a586a
1693361803137_ce:122ba8b0-d2ef-4250-a77b-f4af7dd8709e
1693361803367_ce:9beac782-8c05-459e-ba5d-247e98fc70c2
1693361804736_ce:47f5d0b3-145a-4ec5-9d27-5d434d902d06
1693361804870_ce:0989b147-79b7-4935-b966-ad01fe31ef1c
1693361806680_ce:18e4f1cb-0f04-4cd4-91f9-e165ead32389
1693361828920_ce:c158fb6e-e691-441c-aba3-a16a024eb9a3
1693361829879_ce:a191897b-d0f0-41d9-88a3-b88ea03b472e
1693361830858_ce:cffa53a0-26db-4119-bf8c-a9583cccb88f
1693362370857_ce:4943f1b6-c2b2-48a1-bdcf-d147c8106b44
1693362372407_ce:8897d25f-1c40-4052-bd58-9a4c846afa2d
1693362372421_ce:dda7cbb5-3cc8-49a5-a245-9f4ad141b856
1693362393230_ce:5497b6b0-6457-4f3b-b9b0-26b9e51400ae
1693362817310_ce:158b7996-2df7-4b46-9fee-d484c808ddcc
1693362818317_ce:96ab25f8-65fa-4cf8-8317-f29800af572c
1693362852244_ce:acaad848-6a44-4979-9a33-1e357d71683e
1693362852410_ce:0eebe5b2-dac8-4c0a-a01b-4cd675234f81
1693362917257_ce:0408e7b8-79ed-435c-9daa-c6eaaad64a3a
1693362917580_ce:93cbb5c1-adbf-4299-8db7-f35fc380ebda
1693363289749_ce:8a533887-6a60-4983-9cee-e4be9fb165a3
1693363290410_ce:1a8e426e-94c5-4cb6-9b4f-bf83750add18
1693364049090_ce:441f0574-1f70-4165-be8e-ac6aef2399ef
1693366066660_ce:d8d1da2e-df39-4824-9642-2c2394d20493
1693366270280_ce:342ff62d-2462-47b5-9cd5-885de582be7d
1693366741741_ce:08828f73-180e-413f-9e4f-b1c9b6e53a5e
1693368008689_ce:113a4a55-e0b0-44b0-86cd-a00bef73aac7
1693368008807_ce:fda1cba0-22af-447d-b1d1-48cbeaf559fd
1693373513723_ce:b8291fc7-b2b7-4657-b470-5b3cff24cd85
1693373513735_ce:f485e8e6-daba-4852-9d2f-d872d208e135
1693375676881_ce:312d767c-dbb4-416e-975f-9e41d47cce41
1693376532106_ce:be094083-26a1-4dbd-a8d3-e96e69cd67fb
1693378302401_ce:3020fb19-7b46-40e7-a90d-216cbb5ecde3
1693378973964_ce:f18f6cc1-85bf-46a5-baf5-a73182d7d51f
1693378974916_ce:b1c92b91-5fad-49fe-b664-e795dd87ba40
1693380103391_ce:5bdf8418-cab2-4d19-b08b-c8449a4937b4
1693380452068_ce:95ba92a8-8f51-4009-91d5-a3c05c5d621f
1693380458273_ce:557e1419-0a11-41e2-a734-606b2fd98433
1693380458675_ce:08183ad9-65cf-4353-9b98-74bbf5bbc4fe
1693380459137_ce:67244409-9e18-404a-a9b3-66ec6fba69ea
1693380459728_ce:650cf17c-292d-40f7-941d-a1b19ec3b0f1
1693380459729_ce:d885b29c-a8a3-403e-b919-7cf959352828
1693380459775_ce:ac9e2e18-e8c1-4428-81a5-5f7aa42832cb
1693380460125_ce:c5966fed-70d5-4917-bf31-54bbc4440afc
1693380460876_ce:f315b865-3ef3-4934-867d-96705987369f
1693380461731_ce:c37535e1-cb1e-41a3-83c7-b1d7eb84bb96
1693380462233_ce:b7ec27b5-a811-48f5-9194-af4ef0a8193f
1693380462588_ce:6833b9d4-70f7-40d0-9809-d8ad318d9be9
1693380463392_ce:b5eb3207-2dd0-4f96-8ab1-25c993273d35
1693380464436_ce:169858ca-05e9-4dab-ad00-341cfebae31b
1693380464699_ce:790adea7-f004-40c2-87d2-ac60b23dbf78
1693380465080_ce:4d4a0db8-66cb-4403-86d0-8a1b9db758fb
1693380466403_ce:71ffbb12-5b24-4f75-a8b5-ffd5c81f128e
1693380466824_ce:05295679-1b19-4d6f-9693-9b62dd7b0a04
1693380466928_ce:e509bffe-7686-4f7e-89f1-105569b736b7
1693380466991_ce:f503b7ac-4f52-4b6a-8ed2-b11e8ae6acad
1693380467090_ce:4e0840bd-9b02-404b-82e6-b995eaff9f07
1693380467404_ce:b463ef1d-b382-4902-9434-581bd2f8d97d
1693380468047_ce:6c4954f7-bd38-4374-b607-34a862bbcda3
1693380468488_ce:66c7c803-8737-4459-b55e-2614d86e8c10
1693380469150_ce:886753a4-76be-4876-b343-f609c17fe7a9
1693380469865_ce:1d679acc-8e26-4c35-b401-f5cddde47430
1693380470882_ce:d09e5075-a396-4c98-a019-a2083589ff3b
1693380471020_ce:5ead0b43-1280-4e9c-bcdc-8d0eec61d0b1
1693381322783_ce:019d7768-4abc-49f4-960b-fe3a2c838339
1693389922712_ce:7f852137-36f2-4d92-bc4a-11a52a2d6937
1693389923254_ce:50fe7c54-5a78-47e4-ba32-396e4b2c9aad
1693389941934_ce:b4c351bb-fcb5-4479-8de5-3833ed9487e0
1693390077396_ce:760bdbfe-fa61-463b-88b0-e9bb5b74d988
1693390662188_ce:4c96948c-9ec3-4175-86d8-050680af158b
1693390662550_ce:d623f2af-9bce-4e7b-8912-2030ff9ee544
1693390662866_ce:90d43095-1e87-41f0-b556-15c12aa25b4d
1693390901975_ce:9fff8859-98af-4509-bf4c-03d0599dd8e2
1693390903577_ce:6caa1718-73b7-44c6-8764-fa0a2ab3401c
1693390911542_ce:0d0e7038-5397-49cb-9283-84480447acba
1693391492944_ce:eb168b8b-035f-4708-b586-5941c2435cec
1693391495439_ce:2fe21bc3-388f-4ea5-b5a6-aaf13ae48319
1693391820340_ce:5c9771b5-efea-4e52-8a50-1375ae216eef
1693392134109_ce:35d76353-3afc-4ba5-9334-84b56871da2f
1693392696283_ce:2777d783-5ca8-4cd7-bb08-25b264fc8c2a
1693393360163_ce:f656ddfa-41d3-47f0-b47a-97373d73d73b
1693393360828_ce:6b89767b-197e-49ff-ad32-ca40f8ae6257
1693393638156_ce:985a8d4c-dc5f-4af6-ab9d-ca96d8ee6571
1693393638327_ce:70dd32a1-b59a-48dc-977e-a680d27a684d
1693393648018_ce:98b8abd1-dd07-4b02-b962-533c7bd3fe5d
1693393648280_ce:23e06e0a-1397-480a-91ff-88ccfc386975
1693394806234_ce:d75bfdd3-4553-46dc-9562-7f209ef61f92
1693395421216_ce:13a1421d-9dd7-4b66-bc62-f851aa25906f
1693395425506_ce:8fd4596b-5ed2-4d87-a465-193b55c2d8ee
1693395719513_ce:535c9fd1-b221-45a2-9eac-caeff210d1d7
1693396328348_ce:e0fc132f-431f-4200-8668-f94eed771fb5
1693397236439_ce:ae623080-e046-4e52-8740-f5c70409dad0
1693399064342_ce:70ae5e37-8780-4462-9486-61e168016685
1693399614055_ce:b0451eb7-d8c5-4cc7-a8e1-eb551484989a
1693399614121_ce:bdc4968c-67cb-4006-9d84-998928e8cf8a
1693400273323_ce:84fc1123-45a9-4458-b75f-b638009fed81
1693400631780_ce:fc70c86f-3fdc-4c8e-9c1d-dd5600da22b1
1693401712286_ce:4f4c90e3-7ba5-42df-b1dd-41505ffd49d4
1693402011529_ce:30aa02b0-2bed-4117-aae1-7b4cfbc57e76
1693402338410_ce:b5e9de65-440c-4261-b8c6-aabbc347136b
1693403072946_ce:4cb26dc2-ef07-4baf-bef4-23e5385d8ad8
1693403510976_ce:977b0f50-231b-4fc3-bb6e-2998bffd6412
1693403511571_ce:7c45b696-2ea0-4832-9f92-7048b5960bc5
1693403511847_ce:7b611d7f-d7a0-4456-bc15-21e9ee168897
1693403513404_ce:5644e002-9d08-49f0-905c-a0d037478bfd
1693403684103_ce:86b41ca3-f4be-47c9-b803-ddf90a366b59
1693404435288_ce:0f6181da-848a-4433-a89f-2f92aaee8abe
1693404692109_ce:448d28d8-6f63-489c-9843-854110aae6f8
1693405858724_ce:0c8d697b-4201-490c-999e-5a900449d848
1693406069136_ce:d856d4dd-073e-4f2c-b5c7-933f62d990b3
1693406500066_ce:4bd9f200-bf67-4dde-9782-be48ad4b48a7
1693406647184_ce:80e5778f-66a4-40f6-899d-06ba75ad2b0b
1693406656808_ce:e8ce7cf5-6a31-433e-a312-7c7f89b8f994
1693406942488_ce:cc8bc5d4-d97d-4141-a7d6-1c5b215309f2
1693407029943_ce:9dddb707-529e-4d45-8d29-a4ec3f639857
1693407203724_ce:25dc0641-36ef-489d-955d-aed75beb71d1
1693408288320_ce:d5ce4ae6-b20e-491c-b03a-7d8d7ad2cb9b
1693409844999_ce:55e49c6f-a31f-43e0-9d7c-5134a928c54b
1693409845364_ce:d7f7ab16-077a-491c-b6e2-f4b6b1dfc22b
1693410213836_ce:9dc4ec15-d62b-4d85-8232-36971fa80a31
1693410715977_ce:6dfb29a6-393a-4cf0-9911-e00b3cb52dbd
1693411469532_ce:3a0f2868-4a77-49b4-b331-75fd8f702fe8
1693411469752_ce:deff9dec-3953-405a-a4de-eb6f8d68d840
1693411611818_ce:ebcf8930-6d1f-4637-9ec1-6161e1b69b3e
1693411642597_ce:1bf6727b-b0ed-4cce-ba51-5b604f98a679
1693412000796_ce:298a28ff-af55-4e2f-9fa1-352670bb5a81
1693412000875_ce:2ed40c86-4012-47ce-9c3d-cb7603866ce6
1693412009298_ce:17751095-d460-48ee-bd00-d9fb899c26a4
1693412293381_ce:9be1a4f8-5170-4b0f-9f42-581cdcc9cdab
1693412550870_ce:2bb47bcf-1e20-4353-9b80-5f6ee9e32f5f
1693412551154_ce:154cd61a-8aec-416e-8464-68627056e7d9
1693412551212_ce:0bfa26e1-f6ca-4be4-8f18-aca42b5e400a
1693412551257_ce:ac0fa05f-9077-4776-8ba3-0c6949f2e421
1693413185809_ce:227e0ef6-fe00-4032-a432-77c619f3b6f4
1693413188433_ce:9ba4e091-1e83-4095-9f1f-c7a55b8cd5d6
1693413360627_ce:04af1fc5-60c0-46c4-b439-84c281052262
1693413360716_ce:d1997704-7986-4d74-9e2d-7b331441b794
1693413360761_ce:8ea67567-ca9c-4639-985d-78c7c095f63e
1693413360801_ce:191ac107-3d44-4db1-af21-7dc3a0cb3fec
1693413360834_ce:3c3c0961-35f4-48ef-959d-efbdbe28037e
1693413362881_ce:beae3165-e469-4416-a733-3e7438ae84a9
1693413455510_ce:78ea26f9-0965-41ec-932b-42b88a8ec532
1693413456293_ce:ff7604e1-e2a3-4e0e-8641-463f0a89fdf7
1693413735059_ce:3ca767e1-c15e-45f3-970c-05034a6bbf46
1693414340538_ce:9c9b9785-4ae9-4c23-9cee-702a3654fb5a
1693414342746_ce:6d29e3d9-4964-4659-afda-ee0ec46b5562
1693414624411_ce:9fd1dd5e-f442-48f7-ba23-ccdc2a1b73dd
1693415584433_ce:cda13090-23f7-4b1b-a540-c593f2f4ce89
1693415586505_ce:ae93226f-78b0-4bd9-b3ab-32e39d46c8d4
1693416081008_ce:711f9b87-e4d8-42dd-a253-3be857dc825a
1693416699600_ce:2ee0b7a7-93c2-41bc-b86e-3103c7d2b97c
1693416967066_ce:1faf38e3-89d1-4c60-aab3-17cb95e6bdfa
1693416967136_ce:856c343e-bb3d-42a9-8274-361917ecf133
1693416967139_ce:a51d2d55-af3d-458f-aeed-d9e2c31e1e45
1693416967335_ce:a06ec593-02cb-484e-9dd4-742843b3ee2d
1693416968449_ce:3ec30eb0-00e6-40c2-bf14-332b46d5212f
1693416968450_ce:ab95cddc-ab6a-43ad-82fe-de6d1e229c9a
1693417304237_ce:15e17638-6a2c-42a6-a024-d8948d59e5e3
1693417408710_ce:2bf69fad-53cd-437c-b259-fbc11b78a85b
1693417409091_ce:35fdc8f6-5b07-4939-b510-025afb11e00f
1693417662711_ce:1047ae67-7c58-4942-a5f0-fb5bae57e4c7
1693419223059_ce:a723073b-663b-450d-9918-df9d404f8be6
1693419434253_ce:01fb1441-dee9-4881-aeb9-d30bef0bcf4c
1693419435450_ce:705d9905-7461-4250-9cd7-02cc6c0c4abf
1693419435451_ce:34e52736-af6b-4c5f-aaa1-64ea74c5fb77
1693419436730_ce:7462abef-bb9c-4f85-b430-0342bfa78aaa
1693419437011_ce:4c51e699-7442-4183-a801-81eb44fc1fe3
1693419439433_ce:354bdb45-72a5-4c00-bef4-71e50718cd41
1693419440925_ce:203607b4-ef47-49a8-90f7-99240e49b6d7
1693419442120_ce:29c6b80b-8113-4a8e-b803-ee77547ac701
1693419442127_ce:4bc9149c-9f7e-4354-aad1-3abae9a0b203
1693419442588_ce:b09a0a2b-92ed-4120-b290-f14d7fbf958e
1693419443954_ce:7892bce3-da06-401b-9346-6862dfa80a78
1693419445653_ce:35d2dfd0-1e2d-4af8-87d9-5ed6ace6d93a
1693419445750_ce:30962531-4dea-469e-8ccb-003b213ce54f
1693419447497_ce:cf61e908-1069-42e1-94c9-28021326afa4
1693419447645_ce:bb69c495-9c0e-48ae-af84-56a453577fae
1693419449709_ce:1a10b633-257e-467e-8f1a-ed8d0aac0b8a
1693419468103_ce:ed04a2d2-ae38-4c7a-9b3f-88730c4998e5
1693419468308_ce:9029e36b-2a0a-4db8-8575-8a1742a67809
1693419469287_ce:417ef3c9-3aa3-4206-9ebc-0e15262cb72d
1693419470572_ce:dd6b88bf-3385-430b-92c2-cadf73976cf2
1693419470844_ce:f197cdd0-7a76-480d-bc5f-c45b10414784
1693419471345_ce:8eb48a01-15c7-4a72-9e27-2311522e8d67
1693419472330_ce:aea43661-e942-4b76-ae13-b3bf541c8991
1693419472331_ce:63f8826f-a071-4e64-a51a-0e3f95c7d3ec
1693419475335_ce:207f57cf-d404-47fe-a904-d1359e554ba9
1693419477138_ce:b6ef5a78-ba73-4108-a1e3-85dc22f3f0ee
1693419478185_ce:2229099a-e6dc-449a-845d-a2e252387462
1693419478672_ce:162e01fb-f112-41f0-b762-1e83e97f7e48
1693419479132_ce:3ea17a7f-0eab-4989-be0a-afc99406ff35
1693419479142_ce:00b9a0ad-31d6-49fa-929f-dbc8506d3e9a
1693419479229_ce:9fcbe35f-362d-4dca-964e-6e8d4fdf5bec
1693419810564_ce:e5da2ab1-b59c-48c1-913d-32e17ac74332
1693419815951_ce:2f3b3917-fabb-48b7-8d2c-caa07f203992
1693419818035_ce:d2fa289e-c954-4027-adb2-b412ac808529
1693419965064_ce:8b25ff9b-9130-45c0-90c9-5864023e4842
1693422266319_ce:3fed4d49-c2fa-4592-be06-4df68a3ef677
1693422266567_ce:f3890ff5-b412-44f7-b532-d2d8dcf08d80
1693422418016_ce:3d26e7fb-dcc1-4195-adbc-16bffc533186
1693422753753_ce:45bf9c03-bc38-49a1-8479-7add00fb16bb
1693423461947_ce:7dff1ffa-5b52-404b-9cb2-fe3e9bccad07
1693423621173_ce:6509e66d-8d12-4aa4-a7e7-a76862ecf733
1693423889723_ce:da1f14bd-5cff-429a-857b-e9ab5f8f9ed9
1693423903401_ce:1c97a6b1-d158-4ebf-a412-426229fa8a4c
1693424055374_ce:868b5703-3cf1-4a5b-8363-6f7fd584d636
1693424275704_ce:76839d95-4cdc-4f0f-a588-5e345d0f8e6c
1693424275854_ce:cc75dcd8-896f-451a-971e-063f1cdb19bc
1693424585814_ce:743899c0-fc15-4ac6-b303-faf6cdea9608
1693424642762_ce:b8cf77b7-bdaa-4c80-b31d-37a1739c5c1d
1693424813718_ce:4cc4dce2-27a2-43f3-b952-5114813dccbd
1693424814824_ce:c6c9c572-652a-4612-b562-d010e7256a51
1693424818682_ce:7d5de8ad-c84d-4de2-801a-865b31bd60bf
1693425441906_ce:d4e77930-27bc-4e71-9164-49caf2dd98c5
1693425822268_ce:498bae61-6f4d-40a3-89d3-618f4cf79c01
1693425960580_ce:f005dc7b-5ee9-4043-a59f-e489e9eacb3e
1693426008766_ce:de444992-d5d9-4395-8733-fdae6d60351c
1693426022901_ce:d8ef9e49-fc4a-4884-b520-d07d78d422f1
1693426363783_ce:536da430-cbc8-469d-9795-4db3f3106162
1693426363987_ce:68a316e4-15e1-42de-80d9-2f4f63021834
1693426621798_ce:ea0a30d0-b722-4800-a02a-2b9ab0049b90
1693426625220_ce:5624182f-fbbd-4dab-ba39-12ef23508f51
1693426942108_ce:19ef21f7-a50d-464c-9d73-8abaddc9ebd9
1693427261240_ce:99566de5-8e60-4e80-85df-c7e3040ea3b6
1693427265714_ce:ca1e7e68-0945-4c7f-bb05-a6cead650f9a
1693427484272_ce:3cfe1786-6acc-4de1-985b-af81d7f8fd4e
1693427484548_ce:39b42815-8f44-4c11-960b-386c13534a3b
1693428256897_ce:b5c24a3f-9da8-4f6c-bd8b-9f1e855119d9
1693428257059_ce:f5250c3e-28b7-403a-b2b0-0b558298a21b
1693428433240_ce:45ae8a63-8c37-46c3-836c-0fa9c6c41dc9
1693428433955_ce:d9470d80-a123-4d67-9e80-ee15cb186109
1693428768700_ce:cf8dc92e-8800-4543-90b0-25dc76b24b82
1693429442517_ce:5384377d-21ee-4e48-8e8b-f1061dc142eb
1693429444216_ce:69412e73-bde1-446f-9a8a-1881fc3915fe
1693429458789_ce:3023a310-f012-4b64-857c-2dc9af834b73
1693429616283_ce:b4286f75-10a3-4ba5-87ce-6133366ef837
1693429624704_ce:0be6ac9a-2938-48ae-99d7-77ab432d62c7
1693429663038_ce:ea5f4ddd-44d1-4bd7-abe3-5ecc57ed094b
1693429663183_ce:63054436-894e-4672-a3b6-65b723809af4
1693429937144_ce:9c3afe37-a048-4783-8bee-200616791bd9
1693429937916_ce:1702c600-d2e4-4f56-844e-df101134bddc
1693429937922_ce:964e04d6-596c-4dde-be69-3d0f6b604f79
1693430251152_ce:39c9bdc5-115f-4a09-a56a-8126e790c2be
1693430511466_ce:9d225697-9ad3-4399-b9ab-df9e7b871a79
1693430516888_ce:58e62c3d-fe81-45c2-8c65-eefe37f2e890
1693430517106_ce:7da700b4-7f9f-4aed-8d42-4634f9f7ee0b
1693431194836_ce:1e90ab43-ff36-4e63-8d73-c09dbc1e387d
1693431215385_ce:f1e83dc1-aa83-4640-a0aa-380874a75d79
1693431766807_ce:d7eb1fa5-060b-442f-a097-aa65df63e851
1693431777811_ce:4ce576aa-abe4-47c7-b3cf-592cf69797f0
1693432064293_ce:515e3170-b9c7-4d25-844b-e8d83b93fceb
1693432580888_ce:bf803459-3095-4ddd-8f77-ed58e942209f
1693433021886_ce:31e91169-67ad-4bce-8a41-1b918630dc95
1693433223674_ce:88c7e2d7-2386-471a-bb87-0f5ae43a77c3
1693433225351_ce:2ecf088e-64ec-4c16-b9d2-b90510055bfe
1693433533196_ce:08c69ebd-8459-4f1a-8e9e-a725ac0137e0
1693434108877_ce:72694ffe-102b-4278-9274-68727c8afe74
1693435341517_ce:81ada642-44f9-4cfb-b7ac-1098592073c2
1693435341578_ce:8e5f3090-8a9e-4434-9766-7134ab9d1cdc
1693435601412_ce:156fa3cd-bc58-49d3-be47-b658bb0f5b7c
1693436780805_ce:1a1bad45-f8e4-4011-8892-6612b7069712
1693436817907_ce:d333f263-76e8-448d-8be9-c7960c3ac4cb
1693438256631_ce:9c9e2ac6-3b43-4252-b773-0964d7823395
1693438366616_ce:82f12bcb-9ff0-4a1c-8108-ac6621dad124
1693438368588_ce:bd3b3f62-9cc3-4a0d-9f94-245ce4fc0000
1693449239958_ce:70fd00bd-c99e-4940-800b-216daa0ac20b
1693449240137_ce:ab88218f-0c4f-4878-9168-bc74daba9e67
1693449860424_ce:107b68f0-7490-41cb-bafd-08982e827bcc
1693449860741_ce:51ff7b0c-7ce1-45ff-a83c-01f9a64526b7
1693449860742_ce:1d2d200f-2c70-4253-8c00-dbcf1a28c8f8
1693449860949_ce:5a387907-415f-43ee-b1de-83de6f60b5e6
1693450276387_ce:0434e58b-7c43-43e1-8719-61d728efbd32
1693450276761_ce:45f52512-a0b0-4cf1-bd61-10e066e12d73
1693450277051_ce:3f6d4b08-875e-4b2e-a85c-59139e6312f5
1693450277344_ce:67936f6a-7602-46e5-83d0-c7646a38e59a
1693450277349_ce:4b85dcfc-1a89-4068-8a94-b12ee65472a3
1693450337412_ce:48b0fa21-eb69-4c52-a035-e9bf0de4ddfb
1693450337728_ce:762a8e2c-0679-4df5-aa5b-483ce8566f6a
1693450337732_ce:944c3ebc-9be9-41cf-9fd8-80fb8fd7c2e9
1693450338214_ce:ca049f16-d696-4d21-b727-d1e03002fb81
1693450378042_ce:deba8305-658b-40a8-8c65-67d584cb65de
1693450378100_ce:6c8d2fc2-010e-4440-a6d9-c7d5264cd014
1693450378430_ce:248d58cb-35d0-4200-9654-5e0ae930734a
1693453459143_ce:90298aec-bafb-4731-a424-69ae01d32398
1693453459586_ce:de190ee8-0d34-4fe0-a3ba-bfc3e7252cbc
1693455852427_ce:d41a605c-6100-4fe1-9adb-8346e5421240
1693455852996_ce:9a957571-1962-4ddd-9b3e-ca6fa7e7adaf
1693458466691_ce:fe928d6b-028e-429a-8901-21b55c8c77ae
1693458467602_ce:07f1ee8c-01db-49f9-86d5-b16c56ebb521
1693458468904_ce:e91a0711-1ee0-47bb-88b0-87f747263a07
1693459523856_ce:e9dcd1be-0f33-46c8-ac6a-fcb4ad255bd0
1693460301664_ce:259ca802-40ea-479e-bc14-7d0d25ff8cd2
1693460326259_ce:a058b23d-de67-47f1-9bce-d51a47c9eb49
1693460326572_ce:49321853-510b-49e7-aaff-b84cc47cc6b7
1693460326604_ce:f77e6280-7c35-4108-be93-de768e66c70e
1693460326670_ce:05ebaadf-8454-4e18-ac53-340a969a0697
1693460326729_ce:1d111b09-dd1c-4f6e-a165-3a9009471f98
1693461876146_ce:dc8473fd-c52c-47a2-8d42-8a3dca4b42fa
1693461876195_ce:c0f22a38-0fed-48dc-99d6-111f35392991
1693461876564_ce:c7f3a7b9-f725-4458-abf3-9f17e6daa78a
1693461876675_ce:59e0f6f0-6b1a-4e90-ac20-adb072102878
1693461876793_ce:1a73d16c-808a-4589-9811-936d8123d1bb
1693462031250_ce:bb017ac3-90e9-4424-97f6-9ef75e9723b6
1693462692050_ce:900c748e-40e7-4514-b6d0-1bd69ddb5eca
1693462714349_ce:f8aec231-a35d-481d-8c65-5b5eedff6da3
1693462714920_ce:d49411db-06fb-4c55-8245-c81da3bb7347
1693462715872_ce:3d55746d-6bb3-488f-997b-63fd0e153143
1693462716498_ce:b2277b42-612a-46c3-9973-c86f60840d99
1693462717639_ce:132a96ba-55af-409a-8dda-43aa605553ef
1693466297134_ce:37b730b2-083b-449f-967f-081ecab60e34
1693466313188_ce:5c10ad74-8c12-45c2-863a-0d6e3c5ebdb5
1693466316669_ce:0f5b73ef-3ff2-4797-beec-f99658c36049
1693466317532_ce:71c85062-5061-4601-aeb2-fb0064410ecb
1693466323336_ce:a6532dbc-42ab-4f3e-9387-88626e3dc339
1693466323748_ce:f00ca9ed-423e-46fc-84ec-40f591630174
1693467041372_ce:ec5fca6c-da8c-47ab-b93b-c0ea3fec421b
1693467041627_ce:eefb0862-2d51-4ca7-bb87-91f0683850c5
1693467041676_ce:6e874b79-307d-4705-8177-2762fff38a7f
1693467041995_ce:d82867fb-81dd-4e66-afb3-295c98409f90
1693467043252_ce:11148ebd-97d3-48ca-b063-63b20ca3b72b
1693467043495_ce:73fe86f9-e884-42b2-9d71-d5bfa3e47d0b
1693467044437_ce:8040a441-0d67-43a7-82e3-7aae83155c05
1693467045184_ce:11731774-c88e-43b7-ab11-e902c5ccd64b
1693467612966_ce:99be63ba-120f-4ced-91a4-9d414a173b0a
1693467613231_ce:7676c131-7778-41d4-9c52-1f3237d072c6
1693467802181_ce:383075ec-d149-45ea-bced-bfe740b07a4b
1693468208204_ce:b13c1e81-0d40-4daa-a740-f344474f2ded
1693470036766_ce:0b50c505-f95a-49b8-9f52-4edc6d423c5e
1693470038118_ce:554f9e7f-5e71-4c1f-8227-efe700c6ee2d
1693470040768_ce:c03b2b60-26eb-44dd-8a52-23f8851f0b4c
1693470040849_ce:ebe23998-2685-44ea-b976-61c8949dabfb
1693470042421_ce:c7afbc11-2825-44d6-ab4b-9c73c37e3aa8
1693470044667_ce:8f2ad8dd-c9f3-4647-9727-d014f2516c74
1693470050388_ce:183238f3-38b9-4073-a2ff-4068a099da93
1693470067618_ce:3d658431-4238-4e8d-ae63-759f0b12d277
1693473641173_ce:e5c8de5f-41cf-4820-b403-e3e0c38364f8
1693473642705_ce:ea2ffc79-0533-49d0-968f-666878a4d700
1693473661179_ce:14b7e65c-5a7b-44ba-b1bd-91d5ca763d88
1693473661661_ce:3b9c714c-5f1d-43ee-a21f-a1775560ef11
1693473662429_ce:b8292747-b7f5-4f9f-9224-b9d365c0e503
1693473662430_ce:bca16e79-768d-4593-9dbf-9c3180ec2639
1693473663001_ce:5480d0db-4aa9-4f26-9d8f-0ecbe918ef77
1693473665128_ce:2ffb62a8-f866-42c6-b30a-fabe355301ad
1693473665513_ce:bbad51ef-e9ad-4917-bc07-6143782744cb
1693473666464_ce:7cc0cb03-9bdc-4bf8-a95f-ee6070482889
1693477121339_ce:0b0e3c26-c45d-41f0-9abf-91c5253130ba
1693477122830_ce:7b9c3367-972c-4cb8-81bd-ad95ceac982e
1693480683432_ce:a4e72225-71a9-4a10-bd5c-e1ab7d6c3369
1693480684584_ce:9134e151-473a-4eb8-a401-a704dd36a99a
1693480685261_ce:02b844ed-ae73-49df-ab9a-79b00b4f0fe7
1693480686143_ce:6b828dd6-de38-4059-b76f-86a553ec5dfd
1693480686565_ce:34cd71ac-93f6-4240-a168-6930b73cbf42
1693480687028_ce:f8b87dab-31a9-40e0-b756-5fc73003953e
1693480687615_ce:b89410a0-580b-4ff8-b9c0-9a24a99a8169
1693480690780_ce:73c12595-4284-47c5-a777-dbca1f1abc15
1693480691175_ce:a4d246b9-3899-4a20-b11d-09812bef247b
1693480693224_ce:39849fa0-4043-40bb-a7da-998d75d94b80
1693480693296_ce:cc66a014-e5a6-4d65-9671-4858da5d18d0
1693480693434_ce:4326abf4-6ff7-409e-98d2-b39680d45e80
1693480694484_ce:9872fc01-fafb-449e-8742-4e58715e1c94
1693480696463_ce:aa0e0b68-de7e-4195-99d8-6de33698a9df
1693480696878_ce:a55e5208-3b52-4382-9082-87168580021f
1693480697476_ce:e87229a7-a1d0-45ba-bd51-d3bf234495c0
1693480697553_ce:7296cd28-fe51-439b-a39a-cca0a60c54ac
1693480699719_ce:e6270442-9576-4d96-bcd9-658bc04a5cc5
1693481672690_ce:40da2f6a-f87a-4127-944a-2dddcf8dea8b
1693481672696_ce:268e9bab-3353-4e0b-b5ad-a20a1522cc23
1693483067546_ce:723196c9-c145-49e7-b49b-0739534ad8df
1693483067594_ce:85aca8d5-4038-47a8-87c9-46fabb86d066
1693483067861_ce:587120ad-c43f-4e19-b7b6-64692faa0623
1693483067973_ce:64391cf1-ca52-40fc-ad2b-82e2bf8e5427
1693483068026_ce:65dc6bd3-09d4-4b8d-936f-ed54504d8f0b
1693483068064_ce:9864bd84-225a-41fa-a6e5-26a8cff11ecc
1693483068073_ce:fe05d9ae-163c-4559-9b93-2e9ac43514bb
1693483068158_ce:27ededdf-fa0e-4fcc-8fa0-2ab13c278761
1693483068200_ce:d2e69123-5f09-4c72-a6a2-0878bab19ce4
1693483068202_ce:9849b038-ac1e-4798-9594-f074fec8614e
1693483068267_ce:d2bc66e0-f7bd-458e-81c1-f0675817714a
1693483068358_ce:38d971a6-e94d-4598-896f-12c386b77ca2
1693483068359_ce:25fdb679-78f8-4e8d-b15f-a8971e9fff38
1693483068359_ce:56bedac4-6fd4-49c4-8f87-7ab04015a43f
1693483068395_ce:597eddc4-6770-48a8-8409-8dbab7886047
1693483068472_ce:e23d2bd9-44f2-4d65-86e3-ed900ef897ac
1693483068567_ce:124007ff-b436-4384-b6e4-7c52165f953e
1693483068568_ce:272d7371-3073-4f8d-bc0d-07aa9d952463
1693483068628_ce:d5701576-fcf4-40d4-a4d5-852613ef5a96
1693483068760_ce:c5641b11-9c4a-4591-9925-241b45d7c323
1693483069433_ce:abe7abf4-4899-4155-a291-bb73bce5d154
1693483069480_ce:eb23e0b4-cb7b-4652-816f-2638ee06e31d
1693483069491_ce:4ab27aba-c574-4c69-a43c-762f2f4e04d7
1693483070553_ce:c14540dc-5caa-42e7-bd0c-c88b5517d3de
1693483071525_ce:bd43bf09-f012-45bf-8086-0d106764a315
1693483071913_ce:a1e0144e-9d97-4da5-8630-281f73f51ef5
1693483072056_ce:314978ae-cbfd-48f0-bbfe-e10a87f851a7
1693483072056_ce:d48ae727-0f95-46c1-8b98-4e58509147a4
1693483072314_ce:0e10568d-e9f2-4277-8d62-b1a1cd09e6ec
1693483072723_ce:b1c80756-4e1a-422d-8f36-781497d92b4a
1693483073295_ce:2e351bd0-1dfc-400f-b9ff-f7dee88737c4
1693483073295_ce:c8471ee3-c197-4985-a707-dcca9b1b573c
1693483073653_ce:6ee9bf36-7314-4b24-b09f-75d5ae8b3632
1693483074088_ce:8d95f12f-6b9b-418f-aaf4-c571b468ca72
1693483074166_ce:1d4aa70c-a1c5-4413-a180-3de17750d71b
1693483074290_ce:1f73c29a-1931-4e90-8f04-83f60c1ad5a0
1693483074438_ce:58a92ef2-25db-4f44-aa5a-0217ffbb75e6
1693483074781_ce:130fa0ba-ce3f-4c44-8410-6abc5e1ac85a
1693483075032_ce:68d70c87-cde3-4e0f-8dd5-0e0abf64cc7a
1693483075034_ce:68cfbe9e-fddc-4efb-a697-1649819a2db0
1693483075045_ce:16a8691e-1543-458a-ac73-0ecfe1f9b4ed
1693483075069_ce:ec3ce308-7644-4766-8091-e02ca7fbc824
1693483075107_ce:6227315a-0708-46ea-95d7-33e2061e1026
1693483075134_ce:6182adc5-7bd9-46ed-aeee-afb123958edb
1693483075254_ce:6c4ebdd8-3c27-458d-ae2f-ff1483957f19
1693483075368_ce:39a47857-69b5-4f14-904f-d42128efd767
1693483075369_ce:9759386c-b2d4-4247-bf4a-f0e371a1df96
1693483075454_ce:9dd3fe2d-d34c-47f5-a96e-6b67228d68e1
1693483075602_ce:c6dbc4d8-bb73-485a-8605-53af00501346
1693483075603_ce:30a0af8f-e5a0-45e6-b6c0-c1d2b8fae6ef
1693483075604_ce:0524bb76-c28a-4acd-8d49-3b21d7a91dda
1693483075797_ce:2ad26a95-cf90-4d61-b506-9b2c28597849
1693483075797_ce:599e479c-57b4-406c-9eec-cb444101a18a
1693483075949_ce:c20ef24f-ec07-4b57-a73b-24c3af760aa8
```
