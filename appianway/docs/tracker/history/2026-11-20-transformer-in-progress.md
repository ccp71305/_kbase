# 2026-11-20: transformer in progress (before PR #9)

← [History index](README.md) · [Tracker home](../README.md)

> Snapshot as written at the time (the tracker README's Now and Next steps).

### Now

- **Feature branch** `feature/WI01124532-aws-sdk-upgrade` at **`222d58be`** (splitter merge, PR #8, 2026-11-20 01:25 UTC). Last full green build: `337cf1a7` (10:31 min, all 26 units; the two later splitter commits are test-only).
- **Step 3:** dispatcher ✅ and splitter ✅ merged. **transformer in progress** (branch `WI01124532-aws-sdk-upgrade-transformer` from `222d58be`, local): characterization (golden test, DynamoDB Local parity), pairs 1–2 (task on queue messages; control numbers on the cloud-sdk repository), shared additions (DynamoDB client configuration, table creation) and pair 3 (wiring on `CloudServicesModule`, health checks, `create-table`, pom) committed; 659 tests green, golden wire files reproduced unchanged on the cloud fakes; SDK CloudWatch metrics dropped ([D45](../decisions.md#d45)); `create-table` is never run by CI (Jenkins log), kept and made idempotent. Next: known-defect tests, full build, pre-review, PR, runtime test 6. Log: [steps/step-3-transformer.md](../steps/step-3-transformer.md).
- **Runtime verification** (local runs against QA, [runtime-verification.md](../runtime-verification.md)): tests 1 event-writer, 2 error-processor, 4 dispatcher (with the graceful shutdown check) and 5 splitter **passed**; test 3 email-sender **partly** (the send to be tried on INT). Logs per service: [runtime/](../runtime/README.md). Reusable inputs for the next services (QA traces with every service's real input, splitter's test-5 outputs as transformer inputs, production shapes): [runtime/fixtures/](../runtime/README.md).
- **Build worktree** `C:\Users\arijit.kundu\projects\appianway-build` is detached at `e36bc10f` ([G4](../rules.md#g4)).

### Next steps

1. **transformer:** read the design page and the review summary's defects, characterize v1 (golden test), then the red/green pairs, as in the [service recipe](../README.md#service-recipe); runtime test 6 from [splitter's test-5 outputs](../runtime/fixtures/test5-splitter-outputs/README.md) (expected results: QA's own transformer events in the two traces).
2. **Runtime verification on INT:** email-sender's actual send through the ECS task (Arijit); [A27](../actions.md#a27) optional.
3. **Before distributor-rest:** [A5](../closed-items.md#a5) raise the shared bearer-token security defect with QA.
4. **Open follow-ups:**
   - [A28](../closed-items.md#a28) add the shutdown drain to ingestor and watermill-publisher when they migrate.
   - Move the test helpers each service now copies (`TestQueueMessage`, 6 copies; the shared SDK v1 class list of the boundary test; the `TypeLiteral` client keys) into functional-testing or shared.
   - Commons asks: [F15](../findings.md#f15) and [F17](../findings.md#f17) (storage and email `close()` do nothing); cloud-sdk logs routine storage calls at INFO (each service overrides it); [F21](../findings.md#f21) missing key logged at ERROR (U15, low); [F25](../findings.md#f25) the same probe retried 3 times: check the ECS health-check timeout.
5. **Before every commit:** `git config user.email` is the WTG address; the subject starts with `WI01124532` ([rules](../rules.md)).

