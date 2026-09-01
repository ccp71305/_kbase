# RESUME NOTE — ION-16663 visibility prod outbound-query branch

**Status:** work is uncommitted in the working tree on `develop`. Nothing pushed yet. Machine
restart is safe — working-tree changes persist on disk.

## Goal (what to finish)
Create branch, put the changes on it as **one single commit** (message must contain `ION-16663`),
push to remote with upstream tracking.

- **Target branch name:** `bugfix/ION-16663-visibility-prod-ob-query`
- **Base:** latest `origin/develop`
- **Commit message must contain:** `ION-16663`
- **Docs are NOT tracked/committed** (`visibility/docs/*` is gitignored) — do not add any docs.

## Files to include in the commit (exactly these 6 — all tracked, currently modified)
1. `visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDao.java`
2. `visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoIT.java`
3. `visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoTest.java`
4. `visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/OutboundSingleTransactionProcessor.java`
5. `visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGenerator.java`
6. `visibility/visibility-outbound/src/test/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGeneratorTest.java`

> Do NOT commit any untracked junk (`.claude/`, `.mcp.json`, `NUL`, `__pycache__/`, `confluence_*`,
> `*.py`, `owasp-reports/`, `mercury-services.code-workspace`, etc.) or any `visibility/docs/*.md`.

## What changed
- **My changes (ION-16663 hardening):**
  - `OutboundSingleTransactionProcessor.getInboundContainerEvent(...)` and
    `OutboundGenerator.getInboundContainerEvent(...)`: added a lower-bound input guard at the top:
    ```java
    if (Strings.isNullOrEmpty(inboundContainerEventId)) {
        throw new IllegalArgumentException("Invalid inbound container event ID - must not be null or empty");
    }
    ```
    (Guava `Strings` already imported in both files.)
  - `OutboundGeneratorTest`: added `throwsWhenInboundContainerEventIdIsInvalid()` (assertj
    `assertThatThrownBy`) + import `static org.assertj.core.api.Assertions.assertThatThrownBy;`.
- **Pre-existing uncommitted changes (also part of ION-16663, keep them):**
  - `ContainerEventOutboundDao.java` — outbound-query fix: partition+sort-key query with
    `sequenceNumber >= <cursor>_g`, `.limit(1000)`/`.maxResultSize(1000)`, client-side
    re-verification of both bounds (`removeIf`), and same-millisecond boundary trimming.
  - `ContainerEventOutboundDaoTest.java` / `ContainerEventOutboundDaoIT.java` — tests for the above.

## Git divergence snapshot (as of this note)
- Current branch: `develop`, working tree dirty (the 6 files above).
- `develop` vs `origin/develop`: **0 ahead / 3 behind** (already `git fetch`ed).
- The 3 new remote commits do **not** touch these files → clean fast-forward, stash-pop won't conflict.

## Resume steps (copy/paste)
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services
git stash push -m ion16663 -- `
  visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDao.java `
  visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoIT.java `
  visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoTest.java `
  visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/OutboundSingleTransactionProcessor.java `
  visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGenerator.java `
  visibility/visibility-outbound/src/test/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGeneratorTest.java

git checkout develop
git pull --ff-only origin develop
git switch -c bugfix/ION-16663-visibility-prod-ob-query
git stash pop

git add `
  visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDao.java `
  visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoIT.java `
  visibility/visibility-commons/src/test/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDaoTest.java `
  visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/OutboundSingleTransactionProcessor.java `
  visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGenerator.java `
  visibility/visibility-outbound/src/test/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGeneratorTest.java

git commit -m "ION-16663 Harden visibility outbound query: bound/order first 1000 records and guard invalid inbound container event id" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

git push -u origin bugfix/ION-16663-visibility-prod-ob-query
```

## Still TODO after resume (verification — was interrupted, builds were slow)
- Run and confirm green BEFORE relying on the branch:
  ```powershell
  mvn -q -pl visibility/visibility-outbound,visibility/visibility-commons -am test `
    "-Dtest=OutboundGeneratorTest,ContainerEventOutboundDaoTest" "-Dsurefire.failIfNoSpecifiedTests=false"
  ```
  (New test `throwsWhenInboundContainerEventIdIsInvalid` was not yet confirmed passing — the maven
  reactor build was too slow and got stopped.)
- If a full check is wanted, also run the DAO integration tests (`*IT`) via `mvn verify` for
  `visibility-commons`.

## Notes / open items
- Optional follow-up discussed but NOT done: make the DAO ordering explicit (set ascending
  `ScanIndexForward` in `DefaultQuerySpec`) + a test asserting the returned 1000 are in sort-key
  order. Ordering currently relies on DynamoDB's default ascending sort-key order.
- Separate, unrelated ticket **ION-16650** (GSI throughput-0) analysis lives in
  `visibility/docs/2026-08-24-visibiliy-prod-issue.md` — keep it OUT of this ION-16663 commit.
