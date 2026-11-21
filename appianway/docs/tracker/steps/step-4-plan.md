# Step 4 plan — watermill (recommended order)

Written 2026-11-20 after step 3 closed (PR #12 merged, `36a14ced`). Start a new chat from the [tracker README](../README.md); read this page, then the [modules-in-question doc](../../../2026-06-30-appianway-wm-itv-modules-in-question.md) §0, §9 and §13.

## What is left

Counts from `src/main` on `36a14ced`: files that use SDK v1 or the `shared` v1 classes, files that touch DynamoDB.

| Module | Main classes | SDK v1 files | DynamoDB files | Tests | Notes |
|---|---|---|---|---|---|
| watermill-publisher | 30 | 9 | 0 | 6 | SQS, S3, SNS, parameter store through `shared`; publishes SE events to Watermill (gRPC). Closest to the step 3 services |
| watermill/consumer-framework | 13 | 0 | 4 | | Watermill gRPC consumer loop; **offsets in DynamoDB** (`watermill_offset`) |
| watermill/consumer-commons | 12 | 5 | 5 | | Shared consumer pieces; dynamo-client `DynamoDbConfig` / `DynamoDBCrudRepository` |
| watermill/visibility-inbound-consumer | 22 | 2 | 2 | 19 | Feeds mercury-services visibility |
| watermill/booking-inbound-consumer | 56 | 2 | 2 | 25 | Largest consumer, well tested |
| watermill/itv-gps-consumer | 16 | 5 | 7 | 6 | |
| watermill/cargoscreen-consumer | 23 | 8 | 9 | 2 | Most DynamoDB, fewest tests: golden test matters most |
| watermill/billoflading (ebl- and registration-inbound-consumers) | 8 | 2 | 8 | | In scope ([D49](../decisions.md#d49)). Consumers of the deprecated dynamo-client:1.0 ([memory: dynamo-client deprecated]) |

DynamoDB features in use: SDK v1 `DynamoDBMapper` (`@DynamoDBTable`, `@DynamoDBTypeConverted` ×6), the dynamo-client `@DynamoDBStream` annotation (×4), `DynamoHashKey`, `DynamoDBCrudRepository`. Target: cloud-sdk `DatabaseRepository` with `@Table`, `DefaultPartitionKey` / `DefaultCompositeKey`, `DefaultQuerySpec`, the attribute converters and `DynamoRepositoryConfig` / `DynamoDbClientConfig`, as mercury-services booking (31 classes) and visibility already do.

## Reference material (mercury-services)

- booking: `../mercury-services/booking/docs/DESIGN-AWS2x.md`, `2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md`, `2026-03-27-aws-upgrade-branch-migration-summary.md`.
- visibility: `../mercury-services/visibility/docs/2026-05-31-visibility-aws-upgrade-copilot.md`, `2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md`, `2026-04-17-booking-sdk-upgrade-impact-on-visibility.md`.
- Use them for the **mapping patterns** (entity annotations, key classes, converters, query specs, repository config, `dynamo-integration-test`). Don't copy their test style: here each module keeps the golden-test-first recipe.

## Recommended order

| Wave | PR | Why this order |
|---|---|---|
| 4a | ✅ **watermill-publisher** ([PR #13](https://github.com/wtg-e2open/INTTRA.appianway/pull/13) merged `9537d1c1`, [log](step-4a-watermill-publisher.md)) | No DynamoDB; same recipe as step 3 plus the [A28](../closed-items.md#a28) shutdown drain. Low risk; clears the last ETL-style service |
| 4b | **consumer platform:** consumer-framework + consumer-commons | Every consumer depends on it. Moves the offset store and the dynamo-client repository to cloud-sdk `DatabaseRepository`. Golden test: the exact DynamoDB items written and read (table, keys, attribute names and **types**), on DynamoDB Local (commons `dynamo-integration-test`) |
| 4c-1 | **visibility-inbound-consumer** | Smallest consumer with good tests; the mercury-services visibility docs map directly |
| 4c-2 | **booking-inbound-consumer** | Largest but best tested; booking docs map directly |
| 4c-3 | **itv-gps-consumer** | |
| 4c-4 | **cargoscreen-consumer** | Most DynamoDB and only 2 tests: write the golden test with the most care |
| 4d | **billoflading** consumers | Same platform; check the dynamo-client:1.0 resolution first |
| 5 | Remove SDK v1 from `shared` and the v1 fakes | After every module is off them; the boundary tests prove it |
| — | Final PR feature → `develop` | |

## What is different from step 3 (design these first, in 4b)

1. **Item compatibility is the golden test.** Old and new code must read each other's items: a v1 writer and a v2 reader (and back) run side by side during a deploy. Check:
    - attribute names;
    - number vs string types;
    - date converters (epoch seconds vs ISO string);
    - empty strings and nulls (SDK v1 mapper skips nulls; check the cloud-sdk default);
    - converted (JSON) attributes.
2. **The offset store is the consumers' state.** A wrong key or type means re-reading or skipping Watermill events. Test the round trip of an offset written by the v1 code.
3. **`@DynamoDBStream`**: find what reads that stream and whether the table's stream settings depend on the code (they should not: no environment change).
4. **The Watermill connection (gRPC)** stays as is; only AWS moves.

## Decisions for Arijit (before the runtime tests)

All answered 2026-11-20:

- **QA offsets:** a local consumer may use QA's consumer id and advance QA's offsets ([D46](../decisions.md#d46)).
- **QA DynamoDB writes:** allowed as each runtime test needs, data only ([D47](../decisions.md#d47)).
- **watermill-publisher:** verify up to the publish call; never publish to the e2open staging broker ([D48](../decisions.md#d48)).
- **billoflading:** in scope, wave 4d ([D49](../decisions.md#d49)).

## Working method

Unchanged (service recipe): golden test on v1 → red/green → known defects as disabled tests → full build in the worktree → pre-review (code-review, high) → PR doc → PR → Copilot → runtime test. One PR per row above; a new chat per wave keeps the context small. The tracker README "Resume here" line is the hand-over.
