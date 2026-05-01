# Visibility Module — AWS SDK 2.x Upgrade Plan

> **Status**: Planning  
> **Date**: 2026-03-30  
> **Module**: `visibility/` (multi-module Maven project — 11 sub-modules)  
> **Target**: Migrate from AWS SDK v1 (`dynamo-client`, `AmazonS3`, `AmazonSQS`, `AmazonSNS`, etc.) to `cloud-sdk-api` + `cloud-sdk-aws` (AWS SDK 2.x)  
> **Commons Version**: `1.0.22-SNAPSHOT`  
> **Agent Model**: Claude Opus 4.6  
> **Session ID**: `6fd63aa02b1c4a75` (MCP Context Server — "Visibility Module - AWS 2.x Upgrade Plan")  
> **Prompt**: `.github/prompts/visibility-aws-upgrade-plan.prompt.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Branch & Git Strategy](#2-branch--git-strategy)
3. [Pre-Requisites](#3-pre-requisites)
4. [Upgrade Phases](#4-upgrade-phases)
5. [Phase 1 — POM & Dependency Changes](#5-phase-1--pom--dependency-changes)
6. [Phase 2 — visibility-commons (Shared Library)](#6-phase-2--visibility-commons-shared-library)
7. [Phase 3 — Dropwizard Services](#7-phase-3--dropwizard-services)
8. [Phase 4 — Lambda Functions](#8-phase-4--lambda-functions)
9. [Phase 5 — Booking Dependency Alignment](#9-phase-5--booking-dependency-alignment)
10. [DynamoDB Model Migration Details](#10-dynamodb-model-migration-details)
11. [SQS Migration Details](#11-sqs-migration-details)
12. [S3 Migration Details](#12-s3-migration-details)
13. [SNS Migration Details](#13-sns-migration-details)
14. [SES Migration Details](#14-ses-migration-details)
15. [SSM Parameter Store Migration](#15-ssm-parameter-store-migration)
16. [Lambda Events Migration](#16-lambda-events-migration)
17. [Unit Test Plan](#17-unit-test-plan)
18. [Integration Test Plan](#18-integration-test-plan)
19. [Verification Strategy](#19-verification-strategy)
20. [Risk & Mitigation](#20-risk--mitigation)
21. [Appendix A — File Change Matrix](#appendix-a--file-change-matrix)
22. [Appendix B — Tooling Commands Used](#appendix-b--tooling-commands-used)

---

> **Session Context for Agents**  
> To resume this work, load session `6fd63aa02b1c4a75` via MCP Context Server:  
> ```
> session_get(session_id="6fd63aa02b1c4a75")
> ```  
> This session contains 9 entries covering: initial analysis, architectural decisions, git analysis (booking commit scope, develop delta, zero-overlap confirmation), branch strategy, all document corrections, and a comprehensive final summary with implementation details.  
> **Skills**: `java-refactoring`, `session-context`, `git-operations`  
> **Prompt used to generate this plan**: `.github/prompts/visibility-aws-upgrade-plan.prompt.md`  
> **Current state analysis**: `visibility/docs/DESIGN-curr-state.md`  
> **Confluence design doc**: `visibility/docs/CONFLUENCE-visibility.md`

---

## 1. Executive Summary

The visibility module is the largest multi-module service in the mercury-services monorepo, consisting of **11 sub-modules** (6 Dropwizard services, 4 AWS Lambda functions, 1 shared library). All sub-modules currently use **AWS SDK v1** via the deprecated `dynamo-client` library (`DynamoDBCrudRepository`) and direct AWS SDK v1 client classes (`AmazonS3`, `AmazonSQS`, etc.).

The upgrade will replace all legacy AWS SDK v1 dependencies with the `cloud-sdk-api` (vendor-neutral interfaces) and `cloud-sdk-aws` (AWS SDK v2 implementations) libraries from `mercury-services-commons:1.0.22-SNAPSHOT`, following the same patterns successfully applied in **webbl**, **booking-bridge**, **booking**, **network**, **auth**, **registration**, **tx-tracking**, **self-service-reports**, and **db-migration** modules.

### Key Metrics
- **DynamoDB Entity Classes**: 6 (ContainerEvent, ContainerEventOutbound, ContainerEventPending, ContainerTrackingEvent, BookingDetailVisibility, **CargoVisibilitySubscription**) + nested model classes with `@DynamoDBDocument`
- **DAO Classes**: 6 DynamoDB DAOs + 2 MySQL DAOs (MyBatis — unchanged)
- **SQS Processors**: 7 (one per Dropwizard service) + Lambda producers
- **S3 Clients**: Used in 8+ sub-modules
- **SNS Clients**: Used in 6+ sub-modules
- **Existing Tests**: 134 test files
- **Current commons version**: `1.R.01.021`
- **Target commons version**: `1.0.22-SNAPSHOT` (for cloud-sdk-api and cloud-sdk-aws only; commons artifact remains at `1.R.01.021`)

### Reference Modules
The following upgraded modules serve as implementation references (in chronological order of merge to develop):
1. **webbl** — Single Dropwizard service with DynamoDB, SQS, SNS, S3, SES
2. **booking-bridge** — Single Dropwizard service with DynamoDB, SQS, SNS
3. **booking** — Complex module with 7 DynamoDB tables, Lambdas, SQS/SNS/S3/SES (feature branch `feature/ION-14382-bk3-aws-upgrade-2`)

---

## 2. Branch & Git Strategy

The booking module AWS upgrade (branch `feature/ION-14382-bk3-aws-upgrade-2`, commit `74f36e7a71`) has not yet been merged to `develop`, but visibility-commons depends on booking models (`com.inttra.mercury:booking:2.1.8.M`). The upgraded booking models are needed during visibility development. Rather than waiting for the booking PR to merge, we use a **cherry-pick + rebase-drop** strategy.

### Verified Facts (as of 2026-03-30)
- Booking feature branch has **exactly 1 commit** ahead of develop: `74f36e7a71 ION-14382 bk3 aws upgrade changes`
- That commit changes **223 files exclusively in `booking/`** — zero visibility, zero db-migration, zero network files
- `develop` is **11 commits ahead** of the booking branch base (`abee9cc33d`), including ION-15057 and ION-14875 changes
- The new develop commits touch **5 visibility files** (ION-15057: `CargoVisibilityEventProcessor`, `CargoVisibilitySubscriptionProcessor` + tests, `visibility/pom.xml`) — these will already be in the visibility branch since it starts from latest develop
- **Zero file overlap** between the booking commit and the new develop commits, so cherry-pick is conflict-free
- One new develop commit (`43a5f917ff` ION-15057) touches `booking/` files, but different files than those in the booking AWS commit, so no conflict

### Strategy: Cherry-Pick + Rebase-Drop

```
Timeline:

  develop ──────────────────────────────────────────────[booking merges here]──────>
      │                                                          │
      │ (1) create branch                                        │
      ▼                                                          │
  feature/visibility-aws-sdk-2x-upgrade                          │
      │                                                          │
      │ (2) cherry-pick 74f36e7a71                               │
      │     (booking commit — provides upgraded models)          │
      ▼                                                          │
  [booking commit]                                               │
      │                                                          │
      │ (3) visibility upgrade commits                           │
      │     (all phases 1-5 work)                                │
      ▼                                                          │
  [commit A] [commit B] ... [commit N]                           │
      │                                                          │
      │ (4) when booking merges to develop:                      │
      │     git rebase -i develop                                │
      │     → DROP the cherry-picked booking commit              │
      │     (it's now redundant — develop has it)                │
      ▼                                                          │
  [commit A'] [commit B'] ... [commit N']  ← only visibility changes
      │
      └─▶ PR: shows ONLY visibility changes
```

### Step-by-Step Commands

#### (1) Create visibility branch and cherry-pick booking commit
```bash
# Ensure develop is up to date
git checkout develop
git pull origin develop

# Create visibility feature branch
git checkout -b feature/visibility-aws-sdk-2x-upgrade

# Cherry-pick the single booking commit
git cherry-pick 74f36e7a71

# Verify: should show 1 commit (the cherry-picked booking commit)
git log --oneline develop..HEAD
```

#### (2) Do all visibility work
All visibility upgrade work goes on top as separate commits (Phases 1-5 of this plan).

#### (3) Pre-PR rebase (when booking merges to develop)
```bash
# Update develop
git checkout develop
git pull origin develop

# Rebase visibility branch onto updated develop (interactive)
git checkout feature/visibility-aws-sdk-2x-upgrade
git rebase -i develop

# In the interactive editor:
#   - The cherry-picked booking commit will appear first
#   - Change its action from 'pick' to 'drop'
#   - All other (visibility) commits remain as 'pick'
#   Example:
#     drop 74f36e7 ION-14382 bk3 aws upgrade changes    ← DROP this
#     pick abc1234 Phase 1: POM dependency changes        ← KEEP
#     pick def5678 Phase 2: visibility-commons migration   ← KEEP
#     ...

# Force push (safe)
git push --force-with-lease
```

#### (4) If develop needs rebasing before booking merges
If `develop` gets other changes (not booking) that you need, you can rebase anytime — just keep the booking cherry-pick commit as the first commit so it's easy to identify and drop later.
```bash
git rebase -i develop
# Keep all commits including the booking cherry-pick
# Only drop it when booking has actually merged to develop
```

### Why This Works
- **During development**: The cherry-picked booking commit gives you the upgraded booking models (cloud-sdk annotations, `BookingDetail` with `@DynamoDbBean`, etc.) so visibility can compile and test against them
- **Booking commit is self-contained**: All 223 files are exclusively in `booking/` — no visibility, db-migration, or network files are touched, so the cherry-pick has no side-effects outside booking
- **At PR time**: After the rebase-drop, the PR diff only shows visibility-specific changes. The booking commit is gone because develop already has those identical changes
- **No merge conflicts**: Zero file overlap between the booking commit and new develop commits; cherry-pick onto latest develop is guaranteed conflict-free. Dropping it during interactive rebase is equally clean since git replays only the visibility commits on top of the new develop

### Edge Case: Booking Not Yet Merged When PR Is Ready
If the visibility work finishes before booking merges to develop:
1. Keep the cherry-picked booking commit on the branch
2. Open a **draft PR** — it will show booking files + visibility files in the diff, but the booking changes are clearly isolated in `booking/` only (223 files)
3. When booking merges, rebase-drop and mark PR as ready for review
4. Alternatively, set the PR **base branch** to `feature/ION-14382-bk3-aws-upgrade-2` temporarily — this will show only the visibility diff since the booking commit is the common ancestor. Switch base back to `develop` after booking merges

---

## 3. Pre-Requisites

1. **mercury-services-commons `1.0.22-SNAPSHOT`** must be available in the Maven repository.

2. **DynamoDB Local** must be available for integration testing (provided by `dynamo-integration-test` from mercury-services-commons).

3. **Feature branch**: Create feature branch `feature/visibility-aws-sdk-2x-upgrade` from `develop`, then cherry-pick booking commit `74f36e7a71` (see [Branch & Git Strategy](#2-branch--git-strategy)).

4. **Booking commit available**: Fetch `origin/feature/ION-14382-bk3-aws-upgrade-2` so commit `74f36e7a71` is available locally for cherry-pick.

---

## 4. Upgrade Phases

The upgrade will be executed in the following order, compiling and testing after each phase:

| Phase | Scope | Dependencies | Verification |
|-------|-------|-------------|--------------|
| **Phase 0** | Branch Setup | Cherry-pick booking commit onto new branch | `mvn compile -pl booking -am` |
| **Phase 1** | POM & Dependency Changes | Parent + all sub-modules | `mvn compile -pl visibility -am` |
| **Phase 2** | visibility-commons | Core shared library | `mvn test -pl visibility/visibility-commons` |
| **Phase 3** | Dropwizard Services (6) | visibility-commons | `mvn test` per sub-module |
| **Phase 4** | Lambda Functions (4) | visibility-commons | `mvn test` per sub-module |
| **Phase 5** | Booking Dependency Alignment | visibility-commons (BookingDao, BookingService) | `mvn verify` full module |

### Dependency Order (build order)
```
visibility-commons          ← FIRST (all others depend on this)
  ├── visibility-inbound
  ├── visibility-matcher
  ├── visibility-outbound
  ├── visibility-pending
  ├── visibility-wm-inbound-processor
  ├── visibility-itv-gps-processor
  ├── visibility-s3-archiver
  ├── visibility-error-email
  ├── visibility-pending-start
  └── visibility-outbound-poller
```

---

## 5. Phase 1 — POM & Dependency Changes

### 5.1 Parent POM (`visibility/pom.xml`)

**Add properties:**
```xml
<mercury.cloudsdk.version>1.0.22-SNAPSHOT</mercury.cloudsdk.version>
```

**Keep existing:**
```xml
<mercury.commons.version>1.R.01.021</mercury.commons.version>
<!-- mercury.dynamodbclient.version will be REMOVED -->
```

**Remove property:**
```xml
<!-- REMOVE: <mercury.dynamodbclient.version>1.R.01.021</mercury.dynamodbclient.version> -->
```

### 5.2 visibility-commons POM

**Add dependencies:**
```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <version>${mercury.cloudsdk.version}</version>
</dependency>
```

**Remove dependency:**
```xml
<!-- REMOVE dynamo-client -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-client</artifactId>
    <version>${mercury.dynamodbclient.version}</version>
</dependency>
```

**Add test dependency (for integration tests if placed in commons):**
```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-integration-test</artifactId>
    <version>${mercury.cloudsdk.version}</version>
    <scope>test</scope>
</dependency>
```

**Update booking dependency** (once booking AWS upgrade is merged):
```xml
<!-- Update to cloud-sdk-compatible version -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>booking</artifactId>
    <version>${booking.cloudsdk.version}</version> <!-- TBD after booking merge -->
</dependency>
```

### 5.3 Each Dropwizard Sub-Module POM

Add `dynamo-integration-test` in test scope for sub-modules that will have DynamoDB integration tests:

```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>dynamo-integration-test</artifactId>
    <version>${mercury.cloudsdk.version}</version>
    <scope>test</scope>
</dependency>
```

### 5.4 Lambda Sub-Module POMs

Lambda sub-modules (`visibility-s3-archiver`, `visibility-error-email`, `visibility-pending-start`, `visibility-outbound-poller`) need the same cloud-sdk dependencies. These come transitively from `visibility-commons` for most cases, but direct dependencies may be needed for factory classes.

---

## 6. Phase 2 — visibility-commons (Shared Library)

This is the **most critical phase** — all other sub-modules depend on visibility-commons.

### 6.1 DynamoDB Model Migration

Migrate all DynamoDB entity classes from SDK v1 annotations to SDK v2 Enhanced Client annotations.

#### 6.1.1 ContainerEvent (`container_events` table)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "container_events")` | `@DynamoDbBean` + `@Table(name = "container_events")` |
| `@DynamoDBHashKey(attributeName = "id")` | `@DynamoDbPartitionKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"..."})` |
| `@DynamoDBTypeConverted(converter = ContainerEventSubmissionConverter.class)` | `@DynamoDbConvertedBy(ContainerEventSubmissionAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = ContainerEventEnrichedPropertiesConverter.class)` | `@DynamoDbConvertedBy(ContainerEventEnrichedPropertiesAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = MetaDataConverter.class)` | `@DynamoDbConvertedBy(MetaDataAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = GISOutboundDetailsConverter.class)` | `@DynamoDbConvertedBy(GISOutboundDetailsAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = SubscriptionConverter.class)` | `@DynamoDbConvertedBy(SubscriptionAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = DateToEpochMilliSecond.class)` | `@DynamoDbConvertedBy(DateEpochMilliSecondAttributeConverter.class)` |
| `@DynamoDBTypeConverted(converter = DateToIso8601.class)` | `@DynamoDbConvertedBy(DateIso8601AttributeConverter.class)` |
| TTL via `expiresOn` | `@TTL(name = "expiresOn")` + `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |

**Nested model classes** (previously `@DynamoDBDocument`): Remove `@DynamoDBDocument` annotations. The SDK v2 Enhanced Client with `@DynamoDbConvertedBy` uses Jackson-based `AttributeConverter` implementations that serialize/deserialize nested objects as JSON strings.

**Classes requiring `@DynamoDBDocument` removal:**
- `ContainerEventSubmission`
- `ContainerEventEnrichedProperties`  
- `ContainerEventOutboundMetaData`
- `GISOutboundDetails`
- `MatchedBooking`
- `Location`, `TransportationLocation`, `TransportationDetail`, `TransportationDate`
- `EquipmentDetail`, `VesselDetail`, `VesselCoordinates`
- `TransactionParty`, `Reference`
- Various enum classes (`Channel`, `EmptyIndicatorCode`, `LocationType`, etc.)

#### 6.1.2 ContainerEventOutbound (`container_events_outbound` table)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "container_events_outbound")` | `@DynamoDbBean` + `@Table(name = "container_events_outbound")` |
| `@DynamoDBHashKey` on `integrationProfileFormatId` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` on `sequenceNumber` | `@DynamoDbSortKey` |
| Converter annotations | `@DynamoDbConvertedBy(...)` equivalents |

#### 6.1.3 ContainerEventPending (`container_events_pending` table)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "container_events_pending")` | `@DynamoDbBean` + `@Table(name = "container_events_pending")` |
| `@DynamoDBHashKey` on `createDate` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` on `inboundContainerEventId` | `@DynamoDbSortKey` |

#### 6.1.4 ContainerTrackingEvent (`container_events` table — shared table, different model)

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "container_events")` | `@DynamoDbBean` + `@Table(name = "container_events")` |
| `@DynamoDBHashKey(attributeName = "id")` | `@DynamoDbPartitionKey` |
| Multiple GSI annotations | `@DynamoDbSecondaryPartitionKey(indexNames = {...})` |

#### 6.1.6 CargoVisibilitySubscription (`CargoVisibilitySubscription` table)

**Location**: `visibility-wm-inbound-processor/src/main/java/com/inttra/mercury/cargo/visibility/model/CargoVisibilitySubscription.java`

> **Note**: This entity is NOT in `visibility-commons` — it resides in `visibility-wm-inbound-processor`. Its model migration is documented here for completeness alongside the other DynamoDB entities, but the actual code change happens during Phase 3 (Section 7.5).

| Before (SDK v1) | After (SDK v2) |
|---|---|
| `@DynamoDBTable(tableName = "CargoVisibilitySubscription")` | `@DynamoDbBean` + `@Table(name = "CargoVisibilitySubscription")` |
| `@DynamoDBHashKey(attributeName = "id")` | `@DynamoDbPartitionKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "bookingNumber-index")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"bookingNumber-index"})` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "subscriptionReference-index")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"subscriptionReference-index"})` |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` on `expiresOn` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |
| `@DynamoDBTypeConvertedEnum` on `state` (SubscriptionState) | Remove (Enhanced Client handles enums as strings by default) |
| `@DynamoDBTypeConvertedEnum` on `type` (SubscriptionSource) | Remove (Enhanced Client handles enums as strings by default) |
| `implements DynamoHashKey<String>` | Remove (no longer needed with cloud-sdk) |

**DynamoDB Table**: `CargoVisibilitySubscription`
**Primary Key**: `id` (String, hash key)
**GSIs**:
- `bookingNumber-index` (Hash: bookingNumber)
- `subscriptionReference-index` (Hash: subscriptionReference)

**TTL**: `expiresOn` (epoch seconds) — add `implements Expires` + `@TTL(name = "expiresOn")`

**Nested `@DynamoDBDocument` classes to migrate** (in same package `com.inttra.mercury.cargo.visibility.model`):

| Class | Key DynamoDB Annotations | Migration Action |
|---|---|---|
| `Reference` | `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` on `referenceType` (ReferenceType) | Remove `@DynamoDBDocument` and `@DynamoDBTypeConvertedEnum` — serialized via parent entity's `AttributeConverter` |
| `TransportLeg` | `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` on `stage`, `mode`, `means`, `transportMode` | Remove annotations — serialized via parent entity's `AttributeConverter` |
| `Location` | `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` on `locationType`, `identifierType` | Remove annotations |
| `LocationDate` | `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` on `type`, `dateFormat`, `@DynamoDBIgnore` on `getLocalDateTime()` | Remove `@DynamoDBDocument`/`@DynamoDBTypeConvertedEnum`; `@DynamoDBIgnore` → `@DynamoDbIgnore` or `@JsonIgnore` (already has `@JsonIgnore`) |

**Enums referenced** (all in same package — no DynamoDB annotations, just Jackson `@JsonIgnoreProperties`):
`SubscriptionState`, `SubscriptionSource`, `ReferenceType`, `TransportStageType`, `TransportModeType`, `TransportMeansType`, `TransportMode`, `LocationType`, `LocationIdentifierType`, `LocationDateType`, `DateFormat`

**Important**: The `watermill-publisher/watermill-cargo-visibility-subscription/` module has a SECOND version of this model with MORE GSIs (`bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`, `subscriptionReference-index`) and an additional `@DynamoDBIndexRangeKey` on `carrierScac`. The watermill-publisher module is outside the visibility upgrade scope, but both modules share the same DynamoDB table. The visibility-wm-inbound-processor version is the one being migrated here; the watermill-publisher version would need separate attention when that module is upgraded.

#### 6.1.7 BookingDetailVisibility

This class may reference the booking module's `BookingDetail` entity. If the booking module's models are upgraded, this class will need to align with the new annotations. This is handled in Phase 5.

### 6.2 AttributeConverter Implementations

Create new `AttributeConverter<T>` implementations to replace SDK v1 `DynamoDBTypeConverter` classes. These use Jackson ObjectMapper to serialize/deserialize complex nested objects as JSON strings stored in DynamoDB.

**New converters to create** (in `visibility-commons/.../model/containerEvent/converters/`):

| Converter Class | Target Type | Pattern |
|---|---|---|
| `ContainerEventSubmissionAttributeConverter` | `ContainerEventSubmission` | Jackson JSON ↔ String |
| `ContainerEventEnrichedPropertiesAttributeConverter` | `ContainerEventEnrichedProperties` | Jackson JSON ↔ String |
| `MetaDataAttributeConverter` | `MetaData` (commons) | Jackson JSON ↔ String |
| `GISOutboundDetailsAttributeConverter` | `GISOutboundDetails` | Jackson JSON ↔ String |
| `SubscriptionAttributeConverter` | `List<Subscription>` | Jackson JSON ↔ String |
| `DateEpochMilliSecondAttributeConverter` | `Date` | Date ↔ Long (epoch millis) |
| `DateIso8601AttributeConverter` | `Date` | Date ↔ String (ISO 8601) |
| `DateEpochSecondAttributeConverter` | `Date` | Date ↔ Long (epoch seconds) — for TTL |
| `ContainerTrackingEventMessageAttributeConverter` | `ContainerTrackingEventMessage` | Jackson JSON ↔ String |

**Additional converters for CargoVisibilitySubscription** (in `visibility-wm-inbound-processor/.../model/converters/`):

| Converter Class | Target Type | Pattern |
|---|---|---|
| `ReferencesAttributeConverter` | `List<Reference>` | Jackson JSON ↔ String (with `TypeReference<List<Reference>>`) |
| `TransportLegsAttributeConverter` | `List<TransportLeg>` | Jackson JSON ↔ String (with `TypeReference<List<TransportLeg>>`) |

> **Note**: The nested `Reference`, `TransportLeg`, `Location`, `LocationDate` classes contain enum fields that were previously handled by `@DynamoDBTypeConvertedEnum`. After removal, these enums will be serialized/deserialized by the Jackson ObjectMapper in the parent `AttributeConverter` using their default enum names (e.g., `SUBMITTED`, `APPROVED`). No additional per-enum converter is needed.

**Reference implementation** (from booking module):
```java
public class ContainerEventSubmissionAttributeConverter implements AttributeConverter<ContainerEventSubmission> {
    private static final ObjectMapper MAPPER = new ObjectMapper()
        .registerModule(new JavaTimeModule())
        .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

    @Override
    public AttributeValue transformFrom(ContainerEventSubmission input) {
        try {
            return AttributeValue.builder().s(MAPPER.writeValueAsString(input)).build();
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Failed to serialize", e);
        }
    }

    @Override
    public ContainerEventSubmission transformTo(AttributeValue input) {
        try {
            return MAPPER.readValue(input.s(), ContainerEventSubmission.class);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Failed to deserialize", e);
        }
    }

    @Override
    public EnhancedType<ContainerEventSubmission> type() {
        return EnhancedType.of(ContainerEventSubmission.class);
    }

    @Override
    public AttributeValueType attributeValueType() {
        return AttributeValueType.S;
    }
}
```

### 6.3 DAO Migration

Migrate all 5 DynamoDB DAO classes **in visibility-commons** from `DynamoDBCrudRepository` (dynamo-client) to wrapping `DatabaseRepository` (cloud-sdk-api). The 6th DAO (`CargoVisibilitySubscriptionDao`) is in `visibility-wm-inbound-processor` and is migrated in Phase 3 (Section 7.5).

#### ContainerEventDao

**Before:**
```java
public class ContainerEventDao extends DynamoDBCrudRepository<ContainerEvent, DynamoHashKey<String>> {
    // Uses DynamoDBMapper internally
}
```

**After:**
```java
public class ContainerEventDao {
    private final DatabaseRepository<ContainerEvent, DefaultPartitionKey<String>> repository;

    @Inject
    public ContainerEventDao(DatabaseRepository<ContainerEvent, DefaultPartitionKey<String>> repository) {
        this.repository = repository;
    }

    public ContainerEvent save(ContainerEvent event) {
        return repository.save(event);
    }

    public Optional<ContainerEvent> getSingleById(String id) {
        return repository.findById(new DefaultPartitionKey<>(id), true);
    }

    // Migrate query(), findAll(), etc. using repository.query(IndexQuery) for GSI queries
}
```

**Same pattern for:**
- `ContainerEventOutboundDao` → `DatabaseRepository<ContainerEventOutbound, DefaultCompositeKey<String, String>>`
- `ContainerEventPendingDao` → `DatabaseRepository<ContainerEventPending, DefaultCompositeKey<String, String>>`
- `ContainerTrackingEventDao` → `DatabaseRepository<ContainerTrackingEvent, DefaultPartitionKey<String>>`
- `BookingDao` → `DatabaseRepository<BookingDetailVisibility, DefaultCompositeKey<String, String>>`

### 6.4 SQS Migration (SqsMessageHandler → cloud-sdk MessagingClient)

The visibility module has a custom SQS polling framework in `visibility-commons`:
- `SqsMessageHandler` — polling loop
- `SqsMessageHandlerManager` — lifecycle management
- `StatusEventProcessor<T>` — processor interface

**Migration approach:**

Replace the internal SQS client wrapper (`com.inttra.mercury.visibility.common.processor.sqs`) with `cloud-sdk-api MessagingClient<String>`:

1. **Create `SQSClient` wrapper** (like booking/webbl pattern):
   ```java
   public class SQSClient {
       private final MessagingClient<String> messagingClient;

       @Inject
       public SQSClient(MessagingClient<String> messagingClient) {
           this.messagingClient = messagingClient;
       }

       public List<QueueMessage<String>> receiveMessage(String queueUrl, int maxMessages, int waitTime) {
           ReceiveMessageOptions options = ReceiveMessageOptions.builder()
               .maxNumberOfMessages(maxMessages)
               .waitTimeSeconds(waitTime)
               .build();
           return messagingClient.receiveMessages(queueUrl, options);
       }

       public void sendMessage(String queueUrl, String content) {
           messagingClient.sendMessage(queueUrl, content);
       }

       public void deleteMessage(String queueUrl, String receiptHandle) {
           messagingClient.deleteMessage(queueUrl, receiptHandle);
       }
   }
   ```

2. **Update `SqsMessageHandler`** to use `SQSClient` (cloud-sdk) instead of `com.amazonaws.services.sqs.model.Message`.

3. **Update `StatusEventProcessor<T>` interface**: Change parameter from `com.amazonaws.services.sqs.model.Message` to `QueueMessage<String>`.

4. **Update all processors** (7 total) to accept `QueueMessage<String>` and use `getPayload()` instead of `getBody()`.

### 6.5 S3 Migration

Replace `AmazonS3` / `AmazonS3ClientBuilder` with `cloud-sdk-api StorageClient`.

**Create/Update `S3WorkspaceService`:**
```java
public class S3WorkspaceService {
    private final StorageClient storageClient;

    @Inject
    public S3WorkspaceService(StorageClient storageClient) {
        this.storageClient = storageClient;
    }

    public String getContent(String bucket, String key) {
        StorageObject obj = storageClient.getObject(bucket, key);
        // Read InputStream from obj.getContent()
    }

    public void putObject(String bucket, String key, String content) {
        storageClient.putObject(bucket, key, content);
    }
}
```

### 6.6 SNS Migration

Replace custom `SNSClient` (SDK v1) with cloud-sdk-api `NotificationService`.

**Create `SNSClient` wrapper:**
```java
public class SNSClient {
    private final NotificationService notificationService;

    @Inject
    public SNSClient(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    public void sendMessage(String topicArn, String message) {
        notificationService.publish(topicArn, message);
    }
}
```

### 6.7 Guice Module Changes

**Create new Guice modules** (following webbl/booking pattern):

1. **`VisibilityDynamoModule`** — Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig`, creates `DatabaseRepository` instances via `DynamoRepositoryFactory`, provides all DAO instances.

2. **`VisibilityMessagingModule`** — Provides `MessagingClient<String>` via `MessagingClientFactory.createDefaultStringClient()`, provides `NotificationService` via `NotificationClientFactory.createDefaultClient(topicArn)`.

3. **`VisibilityStorageModule`** — Provides `StorageClient` via `StorageClientFactory.createDefaultS3Client()`.

4. **Update `VisibilityApplicationInjector`** — Remove `DynamoDBModule` binding (old), install new modules above.

### 6.8 Configuration Changes

**Add `BaseDynamoDbConfig` to `VisibilityApplicationConfig`:**
```java
@JsonProperty("dynamoDbConfig")
private BaseDynamoDbConfig dynamoDbConfig;
```

**Update YAML configs** (`conf/{env}/config.yaml`) for all Dropwizard services:
```yaml
dynamoDbConfig:
  environment: "inttra_{env}_visibility"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true
```

### 6.9 SNSMapper Migration

The `SNSMapper` class in visibility-commons deserializes SNS notification messages wrapping DynamoDB Stream events. This uses `com.amazonaws.services.lambda.runtime.events.SNSEvent.SNS`. With `aws-lambda-java-events:3.14.0+`, the import paths and API may differ. Verify and update the parsing logic.

---

## 7. Phase 3 — Dropwizard Services

Each Dropwizard service needs Guice module updates and processor migration. The pattern is the same for each:

### 7.1 visibility-inbound

**Changes:**
- Update `VisibilityInboundApplicationInjector` to install `VisibilityDynamoModule`, `VisibilityMessagingModule`, `VisibilityStorageModule`
- Remove old `DynamoDBModule`, `SQSModule`, `SNSModule` bindings
- Migrate `InboundEdiProcessor` to use `QueueMessage<String>`
- Migrate `S3WorkspaceService` calls (already in commons)
- Migrate SES email — already uses AWS SDK v2 `SesClient` directly; migrate to `cloud-sdk-api EmailService` via `EmailClientFactory.createDefaultSesClient()`
- Create `VisibilityEmailModule` (like `WebBLEmailModule`)
- Update `CreateTables` command — create `VisibilityDynamoDbAdminCommand` following booking/webbl pattern for table creation via `DynamoRepositoryFactory`

### 7.2 visibility-matcher

**Changes:**
- Update `VisibilityMatcherApplicationInjector`
- Migrate `MatchingProcessor` to use `QueueMessage<String>`
- Migrate `SNSMapper` calls for DynamoDB Stream event parsing

### 7.3 visibility-outbound

**Changes:**
- Update `VisibilityOutboundApplicationInjector`
- Migrate `OutboundSingleTransactionProcessor` and `OutboundMultiTransactionProcessor`
- S3 upload calls migrate to `StorageClient`

### 7.4 visibility-pending

**Changes:**
- Update `VisibilityPendingApplicationInjector`
- Migrate `PendingSqsProcessor` (extends `AbstractMatcher`)

### 7.5 visibility-wm-inbound-processor

**Changes:**
- Update `VisibilityWMEventApplicationInjector`
- Migrate `WMEventProcessor` and all `MessageTypeProcessor` implementations
- **Migrate `CargoVisibilitySubscription` DynamoDB entity** (see Section 6.1.6 for annotation mapping):
  - Replace `@DynamoDBTable` → `@DynamoDbBean` + `@Table`
  - Replace `@DynamoDBHashKey` → `@DynamoDbPartitionKey`
  - Replace `@DynamoDBIndexHashKey` → `@DynamoDbSecondaryPartitionKey`
  - Replace `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` → `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)`
  - Remove `@DynamoDBTypeConvertedEnum` from `state` and `type` fields
  - Remove `implements DynamoHashKey<String>`
  - Add `implements Expires` + `@TTL(name = "expiresOn")` for TTL support
  - Remove `@DynamoDBDocument` from nested classes: `Reference`, `TransportLeg`, `Location`, `LocationDate`
  - Remove `@DynamoDBTypeConvertedEnum` from nested classes (11 enum fields total across Reference, TransportLeg, Location, LocationDate)
  - Create `ReferencesAttributeConverter` and `TransportLegsAttributeConverter` for `List<Reference>` and `List<TransportLeg>` fields
- **Migrate `CargoVisibilitySubscriptionDao`** from `DynamoDBCrudRepository<CargoVisibilitySubscription, DynamoHashKey<String>>` to wrapping `DatabaseRepository<CargoVisibilitySubscription, DefaultPartitionKey<String>>`:
  - `findById(id)` → `repository.findById(new DefaultPartitionKey<>(id), true)`
  - `findBySubscriptionReference(ref)` → `repository.query(IndexQuery.builder().indexName("subscriptionReference-index").partitionKeyValue(ref).build())` + load full objects + sort by modifiedOn desc
  - `save(subscription)` → `repository.save(subscription)`
- **Update `CargoVisibilitySubscriptionProcessor`** — no direct DynamoDB annotation changes, but constructor injection of new DAO type
- **Register `CargoVisibilitySubscription.class`** in `VisibilityDynamoModule` (or a sub-module-specific Guice module) for table creation via `DynamoRepositoryFactory`

### 7.6 visibility-itv-gps-processor

**Changes:**
- Update `VisibilityGPSEventApplicationInjector`
- Migrate `GPSEventProcessor`
- Migrate S3 event parsing from `com.amazonaws.services.s3.event.S3EventNotification` to appropriate cloud-sdk parsing

---

## 8. Phase 4 — Lambda Functions

Lambda functions differ from Dropwizard services because they create AWS clients directly (no Guice DI container in Lambda cold start). Follow the **booking `S3ArchiveHandler`** pattern.

### 8.1 visibility-s3-archiver

**Current**: Uses DynamoDB Document API (`DynamoDB`, `Table`, `GetItemSpec`, `Item`) + `AmazonS3` directly.

**Migration:**
1. Replace DynamoDB Document API with `DynamoRepositoryFactory.createEnhancedRepository()` (like booking Lambda)
2. Replace `AmazonS3` with `StorageClientFactory.createDefaultS3Client()`
3. Update `SQSEvent` / `SNSEvent` parsing (embedded models from `aws-lambda-java-events:3.16.1`)
4. Replace `AttributeValue` imports from `com.amazonaws.services.dynamodbv2.model.*` with `com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue` (Lambda event models)

### 8.2 visibility-error-email

**Current**: Uses SSM Parameter Store (`AWSSimpleSystemsManagement`) for secrets, custom subscription REST client.

**Migration:**
1. Replace SSM with `cloud-sdk-api` parameter store API if available, otherwise use AWS SDK v2 `SsmClient` directly
2. Replace email sending if applicable
3. Update Guice injector (`HandlerSupport.createInjector()`)

### 8.3 visibility-pending-start

**Current**: Uses `AmazonSQS` to send PendingFilter messages to SQS.

**Migration:**
1. Replace `AmazonSQS` with `MessagingClientFactory.createDefaultStringClient()` → `MessagingClient<String>`
2. Update message sending to use `messagingClient.sendMessage(queueUrl, json)`

### 8.4 visibility-outbound-poller

**Current**: Uses `AmazonSQS` for sending + SSM for parameter resolution + direct JDBC to MySQL.

**Migration:**
1. Replace `AmazonSQS` with `MessagingClient<String>` via factory
2. Replace SSM with SDK v2 or cloud-sdk paramstore API
3. JDBC to MySQL remains unchanged (not an AWS service migration)

---

## 9. Phase 5 — Booking Dependency Alignment

The `visibility-commons` module depends on `com.inttra.mercury:booking:2.1.8.M` for cross-module booking data access. Thanks to the cherry-pick strategy (see [Branch & Git Strategy](#2-branch--git-strategy)), the upgraded booking code is already available on the visibility branch from the very start.

This phase handles aligning the visibility code with the upgraded booking models that are present in the cherry-picked commit.

### What the cherry-picked booking commit provides:
- Upgraded `BookingDetail` entity with `@DynamoDbBean` / `@DynamoDbPartitionKey` annotations (cloud-sdk)
- Upgraded booking DAOs using `DatabaseRepository` pattern
- Upgraded booking Guice modules (`BookingDynamoModule`, `BookingMessagingModule`, etc.)
- Upgraded booking converters (`AttributeConverter` implementations for booking models)
- **Note**: The booking commit only changes `booking/` files (223 files). It does NOT change any visibility files.

### Actions (with booking code already on branch):
1. **Align `BookingDetailVisibility`** — ensure its annotations are compatible with the booking module's migrated `BookingDetail` entity (both using `@DynamoDbBean`)
2. **Migrate `BookingDao`** in visibility-commons — convert from `DynamoDBCrudRepository<BookingDetailVisibility, ...>` to `DatabaseRepository<BookingDetailVisibility, DefaultCompositeKey<String, String>>`
3. **Verify `BookingServiceImpl`** works with the new DAO pattern
4. **Run integration tests** to verify cross-table reads

### Note on booking dependency version
The booking module is a sibling module in the same monorepo (not a published Maven artifact in this context). The `<dependency>` in `visibility-commons/pom.xml` uses version `2.1.8.M` which resolves within the reactor build. Since both booking and visibility are built together, the cherry-picked booking code is compiled as part of `mvn compile -pl visibility -am`. No version change is needed until the booking upgrade is formally merged and versioned.

---

## 10. DynamoDB Model Migration Details

### 10.1 Annotation Mapping Reference

| SDK v1 Annotation | SDK v2 / cloud-sdk Annotation |
|---|---|
| `@DynamoDBTable(tableName = "...")` | `@DynamoDbBean` + `@Table(name = "...")` |
| `@DynamoDBHashKey` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` | `@DynamoDbSortKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"..."})` |
| `@DynamoDBIndexRangeKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondarySortKey(indexNames = {"..."})` |
| `@DynamoDBVersionAttribute` | `@DynamoDbVersionAttribute` |
| `@DynamoDBTypeConverted(converter = X.class)` | `@DynamoDbConvertedBy(XAttributeConverter.class)` |
| `@DynamoDBDocument` | Remove (nested beans use `@DynamoDbBean` or are serialized via `AttributeConverter`) |
| `@DynamoDBTypeConvertedEnum` | Remove (Enhanced Client handles enums as strings by default) |
| `@DynamoDBAutoGeneratedTimestamp` | Remove (handle in application code or converter) |

### 10.2 TTL Attribute

For entity classes with TTL (auto-expiration):
- Add `implements Expires` interface (from cloud-sdk-api)
- Use `@TTL(name = "expiresOn")` annotation
- Use `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` on the TTL field

### 10.3 GSI Queries

All GSI queries in the DAOs need to be migrated from `DynamoDBCrudRepository.query()` to `DatabaseRepository.query(IndexQuery)`:

```java
// Before (SDK v1):
DynamoDBQueryExpression<ContainerEvent> query = new DynamoDBQueryExpression<>()
    .withIndexName("bookingNumber-index")
    .withKeyConditionExpression("bookingNumber = :bk")
    .withExpressionAttributeValues(Map.of(":bk", new AttributeValue().withS(bookingNum)));
List<ContainerEvent> results = query(query);

// After (SDK v2):
List<ContainerEvent> results = repository.query(
    IndexQuery.builder()
        .indexName("bookingNumber-index")
        .partitionKeyValue(bookingNum)
        .build()
);
```

### 10.4 DynamoDB Table Management Command

Create `VisibilityDynamoDbAdminCommand` (Dropwizard CLI command) following the webbl `CreateTables` pattern:

```java
public class VisibilityDynamoDbAdminCommand extends ConfiguredCommand<VisibilityApplicationConfig> {
    private static final List<Class<?>> ENTITY_CLASSES = List.of(
        ContainerEvent.class,
        ContainerEventOutbound.class,
        ContainerEventPending.class,
        ContainerTrackingEvent.class,
        CargoVisibilitySubscription.class
    );

    // Uses DynamoRepositoryFactory to create/describe tables
}
```

---

## 11. SQS Migration Details

### 11.1 Message Type Change

All 7 SQS processors change from:
```java
void process(com.amazonaws.services.sqs.model.Message message)
// message.getBody()
```
to:
```java
void process(QueueMessage<String> message)
// message.getPayload()
```

### 11.2 SQS Client Construction

**Before** (in Guice modules):
```java
AmazonSQSClientBuilder.standard().build();
```

**After:**
```java
MessagingClient<String> sqs = MessagingClientFactory.createDefaultStringClient();
```

### 11.3 DLQ Handling

The current DLQ logic in `SqsMessageHandler` sends failed messages to a DLQ URL (convention: append `_dlq` to original queue URL). This logic is preserved — the `MessagingClient.sendMessage()` method is used to send to the DLQ.

---

## 12. S3 Migration Details

### 12.1 Read Operations

**Before:**
```java
S3Object s3Object = amazonS3.getObject(bucket, key);
String content = IOUtils.toString(s3Object.getObjectContent());
```

**After:**
```java
StorageObject storageObject = storageClient.getObject(bucket, key);
String content = new BufferedReader(new InputStreamReader(storageObject.getContent()))
    .lines().collect(Collectors.joining("\n"));
```

### 12.2 Write Operations

**Before:**
```java
amazonS3.putObject(bucket, key, content);
```

**After:**
```java
storageClient.putObject(bucket, key, content);
```

### 12.3 S3 Event Parsing (GPS Processor)

The `GPSEventProcessor` parses S3 event notifications from SNS messages. Replace `com.amazonaws.services.s3.event.S3EventNotification` parsing with the Lambda event model's `S3Event` from `aws-lambda-java-events`.

---

## 13. SNS Migration Details

### 13.1 SNS Publishing

**Before:**
```java
snsClient.publish(topicArn, message);
```

**After:**
```java
notificationService.publish(topicArn, message);
```

### 13.2 SNS Event Publisher

The `SNSEventPublisher` in visibility-commons (or per-service) follows the same pattern as booking's `SNSEventPublisher`:
```java
public class SNSEventPublisher implements EventPublisher {
    private final NotificationService notificationService;
    private final String topicArn;

    @Override
    public void publishEvent(List<Event> events) {
        String json = objectMapper.writeValueAsString(events);
        notificationService.publish(topicArn, json);
    }
}
```

---

## 14. SES Migration Details

The `visibility-inbound` module already uses AWS SDK v2 `SesClient` directly. Migrate to `cloud-sdk-api EmailService`:

**Before:**
```java
SesClient sesClient = SesClient.create();
sesClient.sendEmail(request);
```

**After:**
```java
EmailService emailService = EmailClientFactory.createDefaultSesClient(templateFiles);
emailService.sendTemplateEmail(templateName, data, recipients);
```

Create a `VisibilityEmailModule` Guice module (following `WebBLEmailModule` pattern).

---

## 15. SSM Parameter Store Migration

Lambda functions (`visibility-error-email`, `visibility-outbound-poller`) use `AWSSimpleSystemsManagement` (SDK v1) for reading secrets from SSM Parameter Store.

**Migration options:**
1. Use `cloud-sdk-api` paramstore API (`com.inttra.mercury.cloudsdk.paramstore.api`) if it provides the needed functionality
2. Directly use AWS SDK v2 `SsmClient` if cloud-sdk doesn't cover this

Check `mercury-services-commons/cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/paramstore/api` for available interfaces.

---

## 16. Lambda Events Migration

### 16.1 aws-lambda-java-events Version

The parent POM already has `aws-lambda-java-events.version` at `3.16.1`. Ensure all Lambda sub-modules use this version.

### 16.2 DynamoDB Stream Event Parsing

In `aws-lambda-java-events:3.x`, DynamoDB stream event models are embedded:
- `com.amazonaws.services.lambda.runtime.events.DynamodbEvent`
- `com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue`
- `com.amazonaws.services.lambda.runtime.events.models.dynamodb.OperationType`

Verify that `OperationType` comparison changes:
```java
// SDK 1.x style:
record.getEventName().equals(OperationType.INSERT.toString())

// SDK 2.x style (lambda-events 3.x):
OperationType.INSERT.name().equals(record.getEventName())
```

### 16.3 SQSEvent

`SQSEvent` and `SQSEvent.SQSMessage` remain the same in `aws-lambda-java-events:3.x`.

---

## 17. Unit Test Plan

### 17.1 Existing Test Inventory (134 files)

| Sub-Module | Test Files | Focus Areas |
|---|---|---|
| visibility-commons | 47 | DAOs, Converters, Network services, SQS handler, S3 service, SNS mapper |
| visibility-inbound | 35 | Processors, Config, Email, Mapper, CreateTables, Subscription |
| visibility-matcher | 18 | MatchingProcessor, TransactionSearch, Subscription |
| visibility-outbound | 15 | Outbound processors, GIS generation |
| visibility-pending | 5 | PendingSqsProcessor |
| visibility-wm-inbound-processor | 7 | WM processors, Cargo visibility |
| visibility-itv-gps-processor | 2 | GPS processor |
| visibility-s3-archiver | 1 | S3Archiver Lambda |
| visibility-error-email | 5 | Error email Lambda, subscription, paramstore |
| visibility-pending-start | 1 | Pending start Lambda |
| visibility-outbound-poller | 1 | Outbound poller Lambda |

### 17.2 Tests Requiring Migration

All tests that mock AWS SDK v1 classes need migration:

1. **DAO Tests** (5 files in commons, 1+ per sub-module): Replace `DynamoDBCrudRepository` mocks with `DatabaseRepository` mocks
2. **SQS Tests** (SqsMessageHandlerTest, processor tests): Replace `com.amazonaws.services.sqs.model.Message` with `QueueMessage<String>` mocks
3. **S3 Tests** (S3WorkspaceServiceTest): Replace `AmazonS3` mocks with `StorageClient` mocks
4. **SNS Tests**: Replace direct SNS client mocks with `NotificationService` mocks
5. **Lambda Tests**: Update event model classes
6. **Injector/Config Tests**: Update Guice module bindings

### 17.3 New Tests Required

| Test | Sub-Module | Description |
|---|---|---|
| `VisibilityDynamoModuleTest` | commons or inbound | Test Guice DynamoDB module configuration |
| `VisibilityMessagingModuleTest` | commons or inbound | Test SQS/SNS module configuration |
| `VisibilityStorageModuleTest` | commons or inbound | Test S3 module configuration |
| `*AttributeConverterTest` (per converter) | commons | Test each new AttributeConverter round-trip serialization |
| `VisibilityDynamoDbAdminCommandTest` | inbound | Test table creation command |
| `ReferencesAttributeConverterTest` | wm-inbound-processor | Test List<Reference> round-trip serialization |
| `TransportLegsAttributeConverterTest` | wm-inbound-processor | Test List<TransportLeg> round-trip serialization |
| `CargoVisibilitySubscriptionDaoTest` | wm-inbound-processor | Test DAO methods with mocked DatabaseRepository |

### 17.4 Test Migration Pattern

```java
// Before (SDK v1 mock):
@Mock private DynamoDBCrudRepository<ContainerEvent, DynamoHashKey<String>> mockRepo;

// After (cloud-sdk mock):
@Mock private DatabaseRepository<ContainerEvent, DefaultPartitionKey<String>> mockRepo;

// Before (SQS mock):
Message message = new Message();
message.setBody("{...}");

// After (cloud-sdk mock):
QueueMessage<String> message = mock(QueueMessage.class);
when(message.getPayload()).thenReturn("{...}");
when(message.getReceiptHandle()).thenReturn("receipt-handle");
```

---

## 18. Integration Test Plan

### 18.1 DynamoDB Integration Tests

Use `BaseDynamoDbIT` from `dynamo-integration-test` (mercury-services-commons) with embedded DynamoDB Local.

**New integration test classes to create:**

| Test Class | Sub-Module | Tables Tested | Test Count (estimate) |
|---|---|---|---|
| `ContainerEventDaoIT` | commons or inbound | `container_events` | 8-12 tests |
| `ContainerEventOutboundDaoIT` | commons or inbound | `container_events_outbound` | 6-8 tests |
| `ContainerEventPendingDaoIT` | commons or inbound | `container_events_pending` | 6-8 tests |
| `ContainerTrackingEventDaoIT` | commons or inbound | `container_events` | 4-6 tests |
| `CargoVisibilitySubscriptionDaoIT` | wm-inbound-processor | `CargoVisibilitySubscription` | 6-8 tests |
| `VisibilityDynamoDbAdminCommandIT` | inbound | All tables | 8-12 tests |

**Integration test pattern** (from webbl `BLDaoIT`):
```java
@Category(IntegrationTests.class)
public class ContainerEventDaoIT extends BaseDynamoDbIT {

    private ContainerEventDao dao;

    @Override
    protected List<Class<?>> entityClasses() {
        return List.of(ContainerEvent.class);
    }

    @BeforeEach
    void setUp() {
        DatabaseRepository<ContainerEvent, DefaultPartitionKey<String>> repo =
            createPartitionKeyRepository(ContainerEvent.class);
        dao = new ContainerEventDao(repo);
    }

    @Test
    void shouldSaveAndRetrieveContainerEvent() {
        ContainerEvent event = buildTestEvent();
        dao.save(event);

        Optional<ContainerEvent> result = dao.getSingleById(event.getId());
        assertThat(result).isPresent();
        assertThat(result.get().getId()).isEqualTo(event.getId());
    }

    @Test
    void shouldQueryByGSI() {
        // Test GSI queries (bookingNumber-index, blNumber-index, etc.)
    }

    @Test
    void shouldHandleTTL() {
        // Test TTL attribute is set correctly
    }
}
```

### 18.2 Integration Test Execution

```bash
# Run DynamoDB integration tests
mvn verify -pl visibility/visibility-commons -am -Dtest=none -DfailIfNoTests=false -Dit.test="*IT"

# Or for specific test
mvn verify -pl visibility/visibility-inbound -am -Dtest=none -DfailIfNoTests=false -Dit.test=ContainerEventDaoIT
```

---

## 19. Verification Strategy

### 19.1 Per-Phase Verification

| Phase | Command | Expected Outcome |
|---|---|---|
| Phase 1 | `mvn compile -pl visibility -am` | All 11 sub-modules compile |
| Phase 2 | `mvn test -pl visibility/visibility-commons` | All commons unit tests pass |
| Phase 3 (each) | `mvn test -pl visibility/visibility-{submodule}` | All sub-module tests pass |
| Phase 4 (each) | `mvn test -pl visibility/visibility-{lambda}` | All Lambda tests pass |
| Phase 5 | `mvn test -pl visibility/visibility-commons` | Booking integration tests pass |
| Final | `mvn verify -pl visibility -am` | ALL tests pass (unit + integration) |

### 19.2 Test Coverage Verification

```bash
# Run with coverage report
mvn verify -pl visibility -am -Djacoco.skip=false
```

Ensure test coverage does not decrease from pre-upgrade baseline.

### 19.3 Smoke Test (Local)

```bash
# Build executable JAR
mvn package -pl visibility/visibility-inbound -am

# Start with local config
java -jar visibility/visibility-inbound/target/visibility-inbound-1.0.jar server visibility/visibility-inbound/conf/int/config.yaml
```

---

## 20. Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Booking dependency not yet merged to develop | Cherry-pick may cause rebase conflicts | Use cherry-pick + rebase-drop strategy; booking commit is always the first commit so it's easy to identify and drop during interactive rebase |
| Complex nested model serialization changes | DynamoDB read/write failures | Thorough AttributeConverter tests + integration tests with real DynamoDB Local |
| DynamoDB Document API in S3 Archiver Lambda | Different migration path from DynamoDBMapper | Use `DynamoRepositoryFactory` directly in Lambda (no Guice) |
| SQS processor pattern heavily customized | Risk of breaking polling/DLQ logic | Keep `SqsMessageHandler` structure; only swap client internals |
| 134 test files to update | Large surface area for test breakage | Migrate tests alongside production code per phase |
| GSI query patterns | Different API surface between SDK v1 and v2 | Use `IndexQuery` builder from cloud-sdk-api; test each GSI |
| Transitive dependency conflicts | Maven shade plugin issues | Careful exclusion management in POMs |
| SNS/DynamoDB Stream event parsing | Changed import paths in lambda-events 3.x | Verify import compatibility; update `SNSMapper` |
| CargoVisibilitySubscription split model | Same DynamoDB table accessed by 2 modules with DIFFERENT model classes (visibility-wm-inbound-processor has 2 GSIs, watermill-publisher has 3 GSIs + range key) | Only upgrade the visibility-wm-inbound-processor version; watermill-publisher upgrade is separate. Verify that SDK v2 model with 2 GSIs can still read items written by the SDK v1 model with 3 GSIs (it can — extra GSI attributes are stored on the item regardless of model) |
| CargoVisibilitySubscription nested @DynamoDBDocument classes | 4 nested classes (Reference, TransportLeg, Location, LocationDate) with 11 enum fields using @DynamoDBTypeConvertedEnum need careful migration | Create dedicated AttributeConverters for `List<Reference>` and `List<TransportLeg>`; ensure Jackson enum serialization matches DynamoDB stored values |

---

## Appendix A — File Change Matrix

### visibility-commons (Shared Library)

| File | Change Type | Description |
|---|---|---|
| `pom.xml` | Modify | Add cloud-sdk deps, remove dynamo-client |
| `ContainerEvent.java` | Modify | SDK v2 annotations |
| `ContainerEventOutbound.java` | Modify | SDK v2 annotations |
| `ContainerEventPending.java` | Modify | SDK v2 annotations |
| `ContainerTrackingEvent.java` | Modify | SDK v2 annotations |
| `BookingDetailVisibility.java` | Modify | SDK v2 annotations (Phase 5) |
| `ContainerEventSubmission.java` | Modify | Remove `@DynamoDBDocument` |
| `ContainerEventEnrichedProperties.java` | Modify | Remove `@DynamoDBDocument` |
| `GISOutboundDetails.java` | Modify | Remove `@DynamoDBDocument` |
| `MatchedBooking.java` | Modify | Remove `@DynamoDBDocument` |
| `ContainerEventOutboundMetaData.java` | Modify | Remove `@DynamoDBDocument` |
| All nested model classes (~20) | Modify | Remove `@DynamoDBDocument` if present |
| `ContainerEventDao.java` | Rewrite | Use DatabaseRepository |
| `ContainerEventOutboundDao.java` | Rewrite | Use DatabaseRepository |
| `ContainerEventPendingDao.java` | Rewrite | Use DatabaseRepository |
| `ContainerTrackingEventDao.java` | Rewrite | Use DatabaseRepository |
| `BookingDao.java` | Rewrite | Use DatabaseRepository |
| `*Converter.java` (existing) | Modify/Replace | Convert to SDK v2 AttributeConverter |
| `S3WorkspaceService.java` | Rewrite | Use StorageClient |
| `SqsMessageHandler.java` | Modify | Use MessagingClient<String> |
| `SqsMessageHandlerManager.java` | Modify | Update types |
| `StatusEventProcessor.java` | Modify | Change Message type to QueueMessage<String> |
| `VisibilityApplicationInjector.java` | Modify | Install new Guice modules |
| `VisibilityApplicationConfig.java` | Modify | Add BaseDynamoDbConfig |
| `SNSMapper.java` | Modify | Update event model imports |
| New: `VisibilityDynamoModule.java` | Create | DynamoDB Guice module |
| New: `VisibilityMessagingModule.java` | Create | SQS/SNS Guice module |
| New: `VisibilityStorageModule.java` | Create | S3 Guice module |
| New: `SQSClient.java` | Create | cloud-sdk SQS wrapper |
| New: `SNSClient.java` | Create | cloud-sdk SNS wrapper |
| New: `*AttributeConverter.java` (~9) | Create | SDK v2 DynamoDB converters |

### Per Dropwizard Service (6 total)

| File | Change Type |
|---|---|
| `pom.xml` | Modify (add test deps) |
| `*ApplicationInjector.java` | Modify (install new modules) |
| `*Processor.java` | Modify (QueueMessage<String>) |
| Config YAML files | Modify (add dynamoDbConfig) |

### visibility-wm-inbound-processor (additional — CargoVisibilitySubscription)

| File | Change Type | Description |
|---|---|---|
| `CargoVisibilitySubscription.java` | Modify | SDK v2 annotations (`@DynamoDbBean`, `@DynamoDbPartitionKey`, `@DynamoDbSecondaryPartitionKey`, `@DynamoDbConvertedBy`, `@TTL`), remove `DynamoHashKey<String>` |
| `Reference.java` | Modify | Remove `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` |
| `TransportLeg.java` | Modify | Remove `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` (4 enum fields) |
| `Location.java` | Modify | Remove `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` (2 enum fields) |
| `LocationDate.java` | Modify | Remove `@DynamoDBDocument`, `@DynamoDBTypeConvertedEnum` (2 enum fields), update `@DynamoDBIgnore` |
| `SubscriptionState.java` | No change | Enum — no DynamoDB annotations |
| `SubscriptionSource.java` | No change | Enum — no DynamoDB annotations |
| `ReferenceType.java` | No change | Enum — no DynamoDB annotations |
| `TransportStageType.java` | No change | Enum — no DynamoDB annotations |
| `TransportModeType.java`, `TransportMeansType.java`, `TransportMode.java` | No change | Enums — no DynamoDB annotations |
| `LocationType.java`, `LocationIdentifierType.java`, `LocationDateType.java`, `DateFormat.java` | No change | Enums — no DynamoDB annotations |
| `CargoVisibilitySubscriptionDao.java` | Rewrite | Use `DatabaseRepository<CargoVisibilitySubscription, DefaultPartitionKey<String>>` |
| `CargoVisibilitySubscriptionProcessor.java` | Modify | Update DAO constructor type |
| New: `ReferencesAttributeConverter.java` | Create | `List<Reference>` ↔ JSON String |
| New: `TransportLegsAttributeConverter.java` | Create | `List<TransportLeg>` ↔ JSON String |
| New: `CargoVisibilitySubscriptionDaoIT.java` | Create | Integration test for CargoVisibilitySubscription DynamoDB operations |

### Per Lambda Function (4 total)

| File | Change Type |
|---|---|
| `pom.xml` | Modify (add cloud-sdk deps) |
| Lambda handler class | Rewrite (factory-based client creation) |
| SSM resolution classes | Modify (SDK v2 or cloud-sdk paramstore) |

---

## Appendix B — Tooling Commands Used

The following commands were used during the planning phase to gather context:

### Session Management (MCP Context Server)
```
session_list(project="mercury-services", status="active")
  → Found existing session 6fd63aa02b1c4a75

session_get(session_id="6fd63aa02b1c4a75")
  → Loaded session context for "Visibility Module - AWS 2.x Upgrade Plan"

session_add_context(...)
  → Logged progress, findings, and model info throughout the session
```

### File System Exploration
```bash
# List visibility module structure
list_dir(visibility/)
list_dir(visibility/docs/)
list_dir(visibility/visibility-commons/)
list_dir(visibility/visibility-inbound/)
list_dir(visibility/visibility-outbound/)

# Read current state analysis
read_file(visibility/docs/DESIGN-curr-state.md)

# Read reference design documents
read_file(webbl/docs/DESIGN.md)
read_file(webbl/docs/CONFLUENCE-webbl.md)
read_file(booking-bridge/docs/DESIGN.md)
read_file(booking-bridge/docs/CONFLUENCE_DESIGN_DOC.md)
read_file(booking/docs/CONFLUENCE_DESIGN_DOC.md)  # from develop branch
```

### Git Operations
```bash
# Fetch booking feature branch
git fetch origin feature/ION-14382-bk3-aws-upgrade-2

# Show files on booking feature branch
git show FETCH_HEAD:booking/docs/

# Read booking design doc from feature branch
git_show_file(repo_path, "booking/docs/DESIGN-AWS2x.md", ref="FETCH_HEAD")
```

### Code Search
```bash
# Count and list all test files
find visibility -name "*Test*.java" -o -name "*IT.java" | wc -l
  → 134 test files

# Find all Java source files
find visibility -name "*.java" | head -80

# Search DynamoDB annotations
grep -r "@DynamoDBTable|@DynamoDBHashKey|DynamoDBCrudRepository" visibility/visibility-commons/

# Examine cloud-sdk-api package structure
find mercury-services-commons/cloud-sdk-api/src/main/java -type d
```

### POM Analysis
```bash
# Read parent and sub-module POMs
read_file(visibility/pom.xml)
read_file(visibility/visibility-commons/pom.xml)
read_file(visibility/visibility-inbound/pom.xml)
```

---

*End of Plan Document*
