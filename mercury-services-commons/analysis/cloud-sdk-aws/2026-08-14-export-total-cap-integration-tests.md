# D-2 — `export()` total-result cap + integration tests

- **Date:** 2026-08-14
- **Jira:** ION-16431
- **Gap:** D-2 (High) from `visibility/docs/2026-08-12-visibility-shared-http-client-dynamo-refactoring.md` §5.3
- **Module:** `cloud-sdk-aws`
- **Session:** `ad3af3d400334445`

## Background

commons PR #48 (ION-16431) applied a total-result cap to `EnhancedDynamoRepository.query(QuerySpec)`
using a lazy early-return over the enhanced client's `PageIterable`, but the same v1→v2 semantic
inversion remained live in `export(projectionExpression, limit)`. There, `limit` was passed straight
to `ScanEnhancedRequest.limit(...)` (a **per-page** size) and the code then drained **every** page via
`table.scan(req).items().stream().collect(toList())` — an unbounded full-table scan with a Javadoc that
actively misdescribed `limit` as a total "maximum number of items to return".

## Change

### Source (`EnhancedDynamoRepository.export`)

`limit` is now treated as a **total result cap**, mirroring the proven `query()` pattern:

- `capped = limit != null && limit > 0`; only then is the per-page `limit` set on the request.
- Iterate `table.scan(...)` pages and early-`return` as soon as `results.size() >= resultCap`. Because
  `PageIterable`/`ScanIterable` is lazy, no further `Scan` RPC is issued — both heap and consumed RCUs
  are bounded.
- `null`/non-positive `limit` means unbounded (documented as a production hazard).
- Javadoc corrected to state that `limit` is a total cap, not a page size.

### Tests (`EnhancedDynamoRepositoryIT` → new `@Nested ExportIntegrationTests`)

DynamoDB-Local end-to-end coverage:

- `limit == null` returns all items with full attributes populated.
- `limit` smaller than / equal to / greater than total count returns the correct bounded size.
- non-positive `limit` (`0`, `-1`, `-100`, parameterized) is treated as unbounded.
- empty table returns an empty list.
- projection populates only requested attributes; non-projected attributes are `null`.
- projection-expression parsing tolerates blank/embedded/trailing-empty segments.
- blank projection returns full items.
- projection combined with a total cap returns capped, projected items.

## Verification

`mvn -pl cloud-sdk-aws -am verify -Dit.test=EnhancedDynamoRepositoryIT` → failsafe summary
`completed=61, failures=0, errors=0, skipped=0`.
