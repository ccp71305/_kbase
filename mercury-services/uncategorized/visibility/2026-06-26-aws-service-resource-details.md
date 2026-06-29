# Visibility – AWS Service & Resource Details (QA / CVT / Production)

**Author:** Arijit Kundu · **Date:** 2026-06-26
**AWS Account:** `642960533737` (INTTRA2) · **Region:** `us-east-1`
**Profile used:** `642960533737_INTTRA2-QATeam` (SSO role `AWSReservedSSO_INTTRA2-QATeam`)
**Scope:** `visibility` module and all sub-modules. **Read-only** AWS CLI queries only (no table scans, no mutations).

> **Note on environments.** QA, CVT and Production all live in the **same** AWS account `642960533737`.
> The `int` environment lives in a *different* account (`081020446316`) and is **out of scope** for this profile.
> Environment is encoded in resource names by a short prefix — see the prefix map below. CVT is the trap: its
> application config points DynamoDB at the **`inttra2_test`** prefix, not `inttra2_cv`.

---

## 1. Environment → naming-prefix map

| Logical env | Config dir | DynamoDB prefix (`dynamoDbConfig.environment`) | SQS/SNS prefix | S3 / ES / RDS prefix | ECS clusters |
|-------------|-----------|-----------------------------------------------|----------------|----------------------|--------------|
| **QA** | `conf/qa` | `inttra2_qa` | `inttra2_qa_` | `inttra2-qa-` / `qa-` | `ANEQAVIS-001`, `ANEQAVIS-002` |
| **CVT** | `conf/cvt` | **`inttra2_test`** ⚠ (except WM-subscription → `inttra2_cv`) | `inttra2_cv_` | `inttra2-cv-` / `cv-` | `ANECVVIS-001`, `ANECVVIS-002` |
| **PROD** | `conf/prod` | `inttra2_prod` (except `CargoVisibilitySubscription` table is `inttra2_pr_…`) | `inttra2_pr_` | `inttra2-pr-` / `pr-` | `ANEPRVIS-001`, `ANEPRVIS-002` |
| _(INT – ref only)_ | `conf/int` | `inttra_int` | `inttra_int_` | account `081020446316` | n/a (other account) |

See [§12 Findings](#12-findings--discrepancies) for the prefix anomalies (⚠).

---

## 2. AWS services used by the Visibility platform

| Service | Purpose in Visibility | Config key(s) |
|---------|-----------------------|---------------|
| **DynamoDB** | Primary store for container events, outbound payloads, pending events, booking details, cargo-visibility subscriptions | `dynamoDbConfig.environment` |
| **SQS** | Pipeline messaging between inbound → matcher → pending → outbound + WM/ITV ingestion | `*SqsConfig.url/dlqUrl` |
| **SNS** | Event audit logging (`sns_event`, `sns_event_ce`) + DynamoDB-stream fan-out to S3 archiver | `eventLoggingConfig.snsEventTopicArn` |
| **S3** | Workspace (large payload offload), GIS/EDI outbound delivery, container-event archive | `s3WorkspaceConfig.bucket`, `outboundS3Bucket*` |
| **OpenSearch / Elasticsearch 6.8** | Booking search (`bk-search`) for matching; transaction-tracking index (`tx-tracker`) | `esConfiguration`, `esTrackingConfig` |
| **RDS Aurora MySQL** | `ContainerEvent` relational DB (outbound thresholds, enrichment, IPF metadata) | `database`, `readOnlyDatabase` |
| **Oracle (on-prem, via RDS-style JDBC)** | Legacy INTTRA core DB (read) — *not AWS-managed* | `inttraDatabase` |
| **SSM Parameter Store** | DB credentials & OAuth client secrets at runtime (`${awsps:/…}`) | `${awsps:…}` placeholders |
| **KMS** | Encryption keys for SQS / S3 / RDS / SNS / DynamoDB SSE | (referenced by ARN/alias) |
| **SES** | Error-notification e-mail | `emailSenderConfig`, Visibility-API-SES policy |
| **ECS (EC2 launch type)** | Runs the 5 long-running services | task definitions §4 |
| **Lambda** | s3-archiver, outbound-poller, pending-start, error-email, DLQ handlers | §10 |
| **CloudWatch Logs** | Application & Lambda logs | §10 |

---

## 3. Module → AWS-resource matrix

Sub-modules: `visibility-commons` (shared lib), `visibility-inbound`, `visibility-wm-inbound-processor`,
`visibility-matcher`, `visibility-outbound`, `visibility-pending`, `visibility-s3-archiver`,
`visibility-pending-start`, `visibility-error-email`, `visibility-outbound-poller`, `visibility-itv-gps-processor`.

| Module | Deployed as | DynamoDB | SQS (consumes → produces) | SNS | S3 | OpenSearch | RDS | SSM | SES |
|--------|-------------|----------|---------------------------|-----|-----|------------|-----|-----|-----|
| **visibility-commons** | _library_ (linked by all) | all DAOs (ContainerEventDao, …, BookingDao) | `SqsMessageHandler(Manager)` | `SNSMapper`, `EventLogHandler` | `S3WorkspaceService` | `ESConfiguration` | DAO layer | resolver | — |
| **visibility-inbound** | ECS svc **`Visibility-{env}`** (cluster *VIS-002*) | container_events, booking_BookingDetail | `ce_validate`, `pi_statusevents`, `cargo_visibility_subscription_watermill` → `ce_outbound` | `sns_event` / `sns_event_ce` | `*-workspace` | `bk-search`, `tx-tracker` | Aurora R/W + RO + Oracle | db + auth creds | — |
| **visibility-matcher** | ECS svc **`VisibilityMatcher-{env}`** (*VIS-001*) | container_events, booking_BookingDetail (+ ContainerTrackingEvent) | `ce_match` → `ce_pending`, `ce_outbound` | `sns_event_ce` | — | `bk-search` | — | auth | — |
| **visibility-pending** | ECS svc **`VisibilityPending-{env}`** (*VIS-001*) | container_events_pending, container_events | `ce_pending` → `ce_outbound` | `sns_event_ce` | — | `bk-search` | — | auth | — |
| **visibility-outbound** | ECS svc **`VisibilityOutbound-{env}`** (*VIS-001*) | container_events_outbound | `ce_outbound`, `ce_outbound_ipf` → `transformer_ce` | `sns_event_ce` | `*-workspace`, `*-gis-delivery` | `bk-search` | Aurora R/W + RO | db + auth | — |
| **visibility-itv-gps-processor** | ECS svc **`Visibility-ITV-GPS-Processor-{env}`** (*VIS-001*) | container_events | `watermill_itv_gps` | `sns_event_ce` | workspace | — | — | auth | — |
| **visibility-wm-inbound-processor** | ⚠ no dedicated ECS svc found | CargoVisibilitySubscription | `ce_cw_event_inbound`, `ce_cw_subscription_inbound`, `ce_wm_inbound` | `sns_event_ce` | — | — | — | auth | — |
| **visibility-s3-archiver** | Lambda **`…-lambda-visibility-s3-archive`** | reads container_events (stream) | — | subscribes `sns_dynamodb_container_events` | writes `*-workspace` | — | — | — | — |
| **visibility-outbound-poller** | Lambda **`…-lambda-visibility-outbound-poller`** | — | → `ce_outbound_ipf` | — | — | — | Aurora (poll thresholds) | yes | — |
| **visibility-pending-start** | Lambda **`…-lambda-visibility-pending-start`** | container_events_pending | → `ce_pending` | — | — | — | — | — | — |
| **visibility-error-email** | Lambda **`…-lambda-visibility-error-email`** | — | DLQ trigger | — | — | — | — | yes | **SES send** |

> SDK: all runtime modules use the internal **`cloud-sdk-aws`** wrapper (AWS SDK **2.x**); ES access uses the
> Elasticsearch 6.8 `RestHighLevelClient` with SigV4 signing. Lambdas use `aws-lambda-java-events` + SDK 2.x.

### 3.1 End-to-end data flow

```mermaid
flowchart LR
  EDI[/EDI & PI status events/] -->|sqs ce_validate / pi_statusevents| INB[Visibility-API\n(inbound)]
  WM[/Watermill: Shippeo, CargoWise/] -->|ce_wm_inbound\nce_cw_event/subscription| WMP[wm-inbound-processor]
  ITV[/ITV GPS/] -->|watermill_itv_gps| GPS[ITV-GPS-Processor]
  INB -->|ce_match| MAT[Matcher]
  MAT -->|ce_pending| PEN[Pending]
  MAT -->|ce_outbound| OUT[Outbound]
  PEN -->|ce_outbound| OUT
  OUT -->|transformer_ce| XFM[/EDI transformer/]
  OUT --> GIS[(S3 gis-delivery)]
  INB & MAT & PEN & OUT & GPS -->|sns_event_ce| AUD[(SNS audit)]
  INB & MAT & PEN & OUT --> DDB[(DynamoDB)]
  DDB -. stream .-> SNS2[sns_dynamodb_container_events] --> ARC[Lambda s3-archive] --> WS[(S3 workspace)]
  POLL[Lambda outbound-poller] -->|ce_outbound_ipf| OUT
  INB & MAT & PEN --> ES[(OpenSearch bk-search / tx-tracker)]
```

---

## 4. ECS deployment topology

Launch type **EC2** for all visibility services. Container images come from ECR
`081020446316.dkr.ecr.us-east-1.amazonaws.com/centos:<Service>-<env>` (CentOS-based, image tag per service).

| Env | Cluster | Service | Task definition | Desired/Running | Task role |
|-----|---------|---------|-----------------|-----------------|-----------|
| QA | ANEQAVIS-002 | `Visibility-qa` | `Visibility-latest-qa-Task:2` | 2 / 2 | `INTTRA2-ECS-QA-Visibility-API-Task` |
| QA | ANEQAVIS-001 | `VisibilityMatcher-qa` | `VisibilityMatcher-latest-qa-Task:1` | 1 / 1 | `INTTRA2-ECS-QA-TT-Matcher-Task` |
| QA | ANEQAVIS-001 | `VisibilityPending-qa` | `VisibilityPending-latest-qa-Task:1` | 1 / 1 | `INTTRA2-ECS-QA-TT-Pending-Task` |
| QA | ANEQAVIS-001 | `VisibilityOutbound-qa` | `VisibilityOutbound-latest-qa-Task:1` | 1 / 1 | `INTTRA2-ECS-QA-TT-Outbound-Task` |
| QA | ANEQAVIS-001 | `Visibility-ITV-GPS-Processor-qa` | `Visibility-ITV-GPS-Processor-latest-qa-Task:1` | 1 / 1 | `INTTRA2-ECS-QA-Visibility-ITV-GPS-Processor` |
| CVT | ANECVVIS-002 | `Visibility-cvt` | `Visibility-latest-cvt-Task:1` | 1 / 1 | `INTTRA2-ECS-CV-Visibility-API-Task` |
| CVT | ANECVVIS-001 | `VisibilityMatcher-cvt` | `VisibilityMatcher-latest-cvt-Task:2` | 1 / 1 | `INTTRA2-ECS-CV-TT-Matcher-Task` |
| CVT | ANECVVIS-001 | `VisibilityPending-cvt` | `VisibilityPending-latest-cvt-Task:2` | 1 / 1 | `INTTRA2-ECS-CV-TT-Pending-Task` |
| CVT | ANECVVIS-001 | `VisibilityOutbound-cvt` | `VisibilityOutbound-latest-cvt-Task:2` | 1 / 1 | `INTTRA2-ECS-CV-TT-Outbound-Task` |
| CVT | ANECVVIS-001 | `Visibility-ITV-GPS-Processor-cvt` | `Visibility-ITV-GPS-Processor-latest-cvt-Task:1` | 1 / 1 | `INTTRA2-ECS-CV-Visibility-ITV-GPS-Processor` |
| PROD | ANEPRVIS-002 | `Visibility-prod` | `Visibility-latest-prod-Task:5` | 2 / 2 | `INTTRA2-ECS-PR-Visibility-API-Task` |
| PROD | ANEPRVIS-001 | `VisibilityMatcher-prod` | `VisibilityMatcher-latest-prod-Task:1` | **8 / 8** | `INTTRA2-ECS-PR-TT-Matcher-Task` |
| PROD | ANEPRVIS-001 | `VisibilityPending-prod` | `VisibilityPending-latest-prod-Task:1` | **8 / 8** | `INTTRA2-ECS-PR-TT-Pending-Task` |
| PROD | ANEPRVIS-001 | `VisibilityOutbound-prod` | `VisibilityOutbound-latest-prod-Task:1` | **8 / 8** | `INTTRA2-ECS-PR-TT-Outbound-Task` |
| PROD | ANEPRVIS-001 | `Visibility-ITV-GPS-Processor-prod` | `Visibility-ITV-GPS-Processor-latest-prod-Task:1` | 2 / 2 | `INTTRA2-ECS-PR-Visibility-ITV-GPS-Processor` |

> **Pattern:** `*VIS-001` clusters host the 4 pipeline workers (Matcher/Pending/Outbound/ITV-GPS); `*VIS-002`
> clusters host the single inbound **Visibility** API service. Prod runs each pipeline worker at 8 tasks.
> A dedicated ECS service for **wm-inbound-processor** was **not** found in the VIS clusters (its queues exist) — see [§12](#12-findings--discrepancies).

---

## 5. DynamoDB

### 5.1 Table inventory & naming pattern

**Pattern:** `<dynamoDbConfig.environment>_<logical-name>` (e.g. `inttra2_qa_container_events`).
All visibility tables are **PROVISIONED** capacity (no on-demand). SSE = AWS-managed KMS where noted.

| Logical table | Hash / Range key | GSIs | Stream | Used by |
|---------------|------------------|------|--------|---------|
| `container_events` | `id` | 5 (blNumber, equipmentIdentifier, bookingNumber, bkInttraReferenceNumber+equipmentIdentifier, siInttraReferenceNumber) — all KEYS_ONLY | **KEYS_ONLY** (→ s3-archive) | inbound, matcher, pending, outbound, itv-gps |
| `container_events_outbound` | `integrationProfileFormatId` / `sequenceNumber` | none | none | outbound, matcher |
| `container_events_pending` | `createDate` / `inboundContainerEventId` | none | none | pending, pending-start |
| `booking_BookingDetail` | `bookingId` / `sequenceNumber` | 4 (bookerId_shipmentId, carrierId_carrierReferenceNumber, INTTRA_REFERENCE_NUMBER_INDEX, carrierScac_carrierReferenceNumber) | **KEYS_ONLY** | inbound, matcher (read) |
| `booking_ContainerTrackingEvent` | `hashKey` / `sortKey` | 1 (inttraReferenceNumber_equipmentId) | **NEW_IMAGE** | matcher (read) |
| `CargoVisibilitySubscription` | `id` | 3–4 (billOfLading-carrierScac, bookingNumber-carrierScac, bookingNumber, subscriptionReference) | none | wm-inbound-processor |

### 5.2 Per-environment table state (live values at capture)

| Table (full name) | Env | Items | Size | RCU / WCU | SSE | Created |
|-------------------|-----|-------|------|-----------|-----|---------|
| `inttra2_qa_container_events` | QA | 1,661,054 | 7.8 GB | 25 / 200 | ENABLED | 2019-07-18 |
| `inttra2_qa_container_events_outbound` | QA | 10,973,959 | 19.9 GB | 48 / 200 | ENABLED | 2021-04-26 |
| `inttra2_qa_container_events_pending` | QA | 16,196 | 1.5 MB | 50 / 50 | ENABLED | 2021-11-19 |
| `inttra2_qa_booking_BookingDetail` | QA | 15,599,996 | 204 GB | 200 / 100 | ENABLED | 2018-04-25 |
| `inttra2_qa_booking_ContainerTrackingEvent` | QA | 36 | 8 KB | 5 / 5 | ENABLED | 2018-06-19 |
| `inttra2_qa_CargoVisibilitySubscription` | QA | 26,978 | 27 MB | 5 / 5 | (default) | 2026-01-19 |
| `inttra2_test_container_events` | **CVT** | 10,524,602 | 40.7 GB | 25 / 200 | ENABLED | 2019-08-07 |
| `inttra2_test_container_events_outbound` | **CVT** | 139,714 | 149 MB | 25 / 22 | ENABLED | 2021-08-12 |
| `inttra2_test_container_events_pending` | **CVT** | 83,725 | 8.1 MB | 25 / 25 | ENABLED | 2021-12-09 |
| `inttra2_test_booking_BookingDetail` | **CVT** | 532,259 | 8.1 GB | 5 / 5 | ENABLED | 2018-07-17 |
| `inttra2_test_booking_ContainerTrackingEvent` | **CVT** | 0 | 0 | 5 / 5 | ENABLED | 2018-07-09 |
| `inttra2_cv_CargoVisibilitySubscription` | **CVT** | 97 | 151 KB | 5 / 5 | (default) | 2026-02-05 |
| `inttra2_prod_container_events` | PROD | **1,787,202,818** | **10.2 TB** | 971 / 2010 | ENABLED | 2019-07-26 |
| `inttra2_prod_container_events_outbound` | PROD | **2,704,799,056** | **2.88 TB** | 25 / 200 | ENABLED | 2021-08-14 |
| `inttra2_prod_container_events_pending` | PROD | 6,950,507 | 674 MB | 100 / 100 | ENABLED | 2021-12-11 |
| `inttra2_prod_booking_BookingDetail` | PROD | 144,789,328 | **2.79 TB** | 15000 / 633 | ENABLED | 2018-07-17 |
| `inttra2_prod_booking_ContainerTrackingEvent` | PROD | 269,864,479 | 97.8 GB | 20 / 500 | ENABLED | 2018-07-12 |
| `inttra2_pr_CargoVisibilitySubscription` | PROD | **0** ⚠ | 0 | 5 / 5 | (default) | 2026-02-21 |

---

## 6. SQS

All visibility queues are standard (non-FIFO). Most encrypt with KMS alias `alias/inttra2/<env>/sqs`;
WM/ITV queues use dedicated multi-region keys (`mrk-…`); transformer queues use SQS-managed SSE (`sse-sqs`).
Every primary queue has a redrive policy to a matching `_dlq`. (Wait-time, visibility-timeout, retention shown.)

| Queue (suffix, per-env prefix) | Owner module | VisTimeout | Retention | Wait | Encryption | Notes |
|--------------------------------|--------------|-----------|-----------|------|------------|-------|
| `sqs_ce_validate` (+`_dlq`) | inbound | 300 s | 4 d (dlq 14 d) | 0–5 s | KMS `…/sqs` | inbound EDI validation |
| `sqs_ce_match` (+`_dlq`) | matcher | 300 s | 4 d | 0 s | KMS `…/sqs` | |
| `sqs_ce_pending` (+`_dlq`) | pending | **43200 s** (12 h) | 4 d | 0 s | KMS `…/sqs` | long visibility window |
| `sqs_ce_outbound` (+`_dlq`) | outbound | 300 s | 4 d | 0 s | KMS `…/sqs` | |
| `sqs_ce_outbound_ipf` (+`_dlq`) | outbound / poller | 1800 s | 4 d (dlq 14 d) | 5 s | KMS `…/sqs` | multi-transaction IPF |
| `sqs_pi_statusevents` (+`_dlq`) | inbound | 30 s | 4 d (dlq 14 d) | 5 s | KMS `…/sqs` | **PROD backlog ≈7.33 M msgs** ⚠ |
| `sqs_cargo_visibility_subscription_watermill` (+`_dlq`) | inbound / wm | 60 s | 4 d | 0 s | KMS `…/sqs` | |
| `sqs_ce_cw_event_inbound` (+`_dlq`) | wm-inbound | 60 s | 4 d | 0 s | KMS `…/sqs` | CargoWise events |
| `sqs_ce_cw_subscription_inbound` (+`_dlq`) | wm-inbound | 60 s | 4 d | 0 s | KMS `…/sqs` | CargoWise subscriptions |
| `sqs_ce_wm_inbound` (+`_dlq`) | wm-inbound (Shippeo) | 300 s | 4 d | 20 s | KMS `mrk-…` | long-poll |
| `sqs_watermill_itv_gps` (+`_dlq`) | itv-gps | 300 s | 4 d | 20 s | KMS `mrk-…` | long-poll |
| `sqs_transformer_ce` (+`_dlq`) | outbound → transformer | 60 s | 4 d | 0 s | sse-sqs | downstream EDI transformer |

> **Backlogs at capture:** `inttra2_pr_sqs_pi_statusevents` ≈ **7,332,622** messages; `inttra2_qa_sqs_ce_outbound_ipf_dlq` ≈ 10,080; `inttra2_qa_sqs_pi_statusevents_dlq` = 1. All others ≈ 0.
> The account also has many non-visibility CE/PI/transformer/watermill queues (booking, OSNG, etc.) — excluded here.

---

## 7. SNS

| Topic (per env) | Subs | Encryption (KMS) | Role in Visibility |
|-----------------|------|------------------|--------------------|
| `inttra2_<env>_sns_event` | 2 | MRK (per-env) | legacy event audit (inbound) |
| `inttra2_<env>_sns_event_ce` | 2 | MRK (per-env) | container-event audit log (all services publish) |
| `inttra2_<env>_sns_dynamodb_container_events` | 2 | none | DynamoDB-stream fan-out → s3-archive Lambda |

Delivery policy on all: linear backoff, 3 retries, 20 s min/max delay. Per-env KMS keys: QA `mrk-f7dd2389…`, CV `mrk-ca89d26f…`, PR `mrk-d7af38a0…`.

---

## 8. S3

| Bucket | Env | Purpose | Encryption (KMS, bucket-key) | Lifecycle |
|--------|-----|---------|------------------------------|-----------|
| `inttra2-qa-workspace` | QA | payload offload / archive | `mrk-894a4ff5…` | expire @ 90 d (+ delete-marker cleanup @ 30 d) |
| `inttra2-qa-gis-delivery` | QA | GIS/EDI outbound (`app/ob/315_IFTSTA_STAGE`) | `mrk-894a4ff5…` | none |
| `inttra2-cv-workspace` | CVT | payload offload / archive | `mrk-c5858588…` | expire @ 30 d |
| `inttra2-cv-gis-delivery` | CVT | GIS/EDI outbound | `mrk-c5858588…` | none |
| `inttra2-pr-workspace` | PROD | payload offload / archive | `mrk-fcb7d538…` | expire @ 365 d |
| `inttra2-pr-gis-delivery` | PROD | GIS/EDI outbound | `mrk-fcb7d538…` | none |

All buckets are in `us-east-1` (LocationConstraint null), enforce KMS SSE with bucket keys, and block `SSE-C`.

---

## 9. OpenSearch (Elasticsearch 6.8) & RDS

### 9.1 OpenSearch domains (engine `Elasticsearch_6.8`, EBS gp2, encryption-at-rest ON)

| Domain | Env | Use | Instances | Dedicated masters | EBS | Zone-aware |
|--------|-----|-----|-----------|-------------------|-----|------------|
| `inttra2-qa-es-bk-search` | QA | booking match search | 3 × `m5.large.search` | 3 × m5.large | 50 GB | yes |
| `inttra2-qa-es-tx-tracker` | QA | tx-tracking (`txtrack-event-*`) | 3 × `m5.2xlarge.search` | none | 150 GB | yes |
| `inttra2-cv-es-bk-search` | CVT | booking match search | 3 × `m5.large.search` | none | 35 GB | no |
| `inttra2-cv-es-tx-tracker` | CVT | tx-tracking | 2 × `m5.large.search` | none | 150 GB | yes |
| `inttra2-pr-es-bk-search` | PROD | booking match search | 5 × `m5.large.search` | 3 × m5.large | 300 GB | yes |
| `inttra2-pr-es-tx-tracker` | PROD | tx-tracking | 6 × `m5.4xlarge.search` | 3 × m5.large | 3072 GB | yes |

> ⚠ Security note: `EnforceHTTPS = false` and `NodeToNodeEncryption = false` on all six domains (TLS policy `Policy-Min-TLS-1-2-PFS-2023-10` set but not enforced). Access is IAM/SigV4-gated. ES 6.8 is EOL — flagged elsewhere for upgrade.

### 9.2 RDS Aurora MySQL (`ContainerEvent` DB, engine `8.0.mysql_aurora.3.10.3`, encrypted, not public)

| Cluster | Env | Writer / Reader instances | Instance class | Backup retention | KMS |
|---------|-----|---------------------------|----------------|------------------|-----|
| `qa-network-db-cluster` | QA | `…-us-east-1c` (writer) + `…-us-east-1d` | `db.r7g.large` | 1 d | `key/70d92364-…` (shared) |
| `cv-network-db-cluster` | CVT | `cv-network-db` (writer) + `…-us-east-1c` | `db.t4g.medium` | 7 d | `key/70d92364-…` |
| `pr-network-db-cluster` | PROD | `…-us-east-1c` (writer) + `pr-network-db` | `db.r7g.xlarge` | 7 d | `key/70d92364-…` |

Writer endpoint `…cluster-cnxcksehojac…`; reader endpoint `…cluster-ro-cnxcksehojac…` (port 3306, DB `ContainerEvent`). JDBC driver `software.aws.rds.jdbc.mysql.Driver` (failover-aware). Inbound also reads a legacy on-prem **Oracle** DB (`inttraDatabase`, not AWS).

---

## 10. CloudWatch Logs

### 10.1 Log groups

| Log group | Used by | Retention | Stored (approx) |
|-----------|---------|-----------|-----------------|
| **`inttra2-ecs-logs`** | **All ECS visibility services** (QA+CVT, and prod workers) via `awslogs` driver | 400 d | ~3.0 TB (shared, all apps) |
| **`inttra2-pr-lg-visibility`** | PROD `Visibility-prod` API only | 400 d | ~1.37 TB |
| `/aws/lambda/inttra2-<env>-lambda-visibility-s3-archive` | s3-archiver Lambda | 14 d | qa 28 MB · cv 74 MB · pr **29.9 GB** |
| `/aws/lambda/inttra2-<env>-lambda-visibility-outbound-poller` | outbound-poller Lambda | 14 d | qa 11 MB · cv 6.7 MB · pr 76 MB |
| `/aws/lambda/inttra2-<env>-lambda-visibility-pending-start` | pending-start Lambda | 14 d | ~1.4–2.8 MB |
| `/aws/lambda/inttra2-<env>-lambda-visibility-error-email` | error-email Lambda | 14 d | ~0.16–0.94 MB |
| `/aws/lambda/handle-inttra2_<env>_sqs_ce_{validate,match}_dlq-msg` | DLQ message handlers | 120–400 d | small |
| `/aws/route53/visibility.inttra.com` | Route53 query logging | 90 d | 53 MB |

> **Where each ECS service logs.** All five services write to `inttra2-ecs-logs` **except** the prod
> `Visibility-prod` API which writes to `inttra2-pr-lg-visibility`. Stream prefix = `<Service>-latest-<env>`,
> so log streams look like `Visibility-latest-prod/Visibility-prod-Container/<task-id>`,
> `VisibilityMatcher-latest-qa/VisibilityMatcher-qa-Container/<task-id>`, etc.

| Service | awslogs-group | Stream prefix |
|---------|---------------|---------------|
| `Visibility-{qa,cvt}` | `inttra2-ecs-logs` | `Visibility-latest-{env}` |
| `Visibility-prod` | `inttra2-pr-lg-visibility` | `Visibility-latest-prod` |
| `VisibilityMatcher-{env}` | `inttra2-ecs-logs` | `VisibilityMatcher-latest-{env}` |
| `VisibilityPending-{env}` | `inttra2-ecs-logs` | `VisibilityPending-latest-{env}` |
| `VisibilityOutbound-{env}` | `inttra2-ecs-logs` | `VisibilityOutbound-latest-{env}` |
| `Visibility-ITV-GPS-Processor-{env}` | `inttra2-ecs-logs` | `Visibility-ITV-GPS-Processor-latest-{env}` |

### 10.2 Log format & levels

Dropwizard console appender pattern (from `config.yaml`):
`%-5p [%t] [%d{yyyy-MM-dd HH:mm:ss.SSS}] %X{USER} %X{COMPANY} %c: %msg%n`
→ each line begins with the **level token** (`INFO `, `WARN `, `ERROR`, `DEBUG`). Root level `INFO`
(`com.inttra.mercury.visibility` = `DEBUG` in QA inbound); AWS SDK (`com.amazonaws`) pinned to `ERROR`.

### 10.3 Useful CloudWatch Logs Insights queries

Run against `inttra2-ecs-logs` (filter by stream prefix) or `inttra2-pr-lg-visibility`.

```sql
-- Error/Warn volume over time, bucketed (start here)
fields @timestamp, @message
| filter @message like /(?i)\b(ERROR|WARN)\b/
| stats count(*) as hits by bin(5m), @logStream
| sort hits desc
```

```sql
-- Only ERROR lines for one service (set stream prefix accordingly)
fields @timestamp, @logStream, @message
| filter @logStream like /VisibilityMatcher-latest-prod/
| filter @message like /ERROR/
| sort @timestamp desc
| limit 200
```

```sql
-- Top exception classes (Java stack traces)
fields @message
| filter @message like /Exception|Throwable|Caused by/
| parse @message /(?<exClass>[\w.]+(Exception|Error))/
| stats count(*) as occurrences by exClass
| sort occurrences desc
```

```sql
-- SQS / DynamoDB / ES failure signatures
fields @timestamp, @message
| filter @message like /(?i)(throttl|ProvisionedThroughput|timeout|connection reset|SdkClientException|503 Service|circuit)/
| stats count(*) as n by bin(15m)
| sort @timestamp desc
```

```sql
-- DLQ / retry / give-up signals in the pipeline
fields @timestamp, @logStream, @message
| filter @message like /(?i)(dead.?letter|moved to dlq|retry exhausted|giving up|redrive)/
| sort @timestamp desc | limit 100
```

```sql
-- Per-level breakdown for an env (all visibility streams in shared group)
fields @message
| filter @logStream like /-latest-qa/
| parse @message /^(?<lvl>\w+)\s/
| stats count(*) as n by lvl
| sort n desc
```

```sql
-- Throughput: events processed per minute (adjust the marker string to a known INFO log line)
fields @timestamp
| filter @message like /(?i)(processed|published to sns|persisted container event)/
| stats count(*) as processed by bin(1m)
| sort @timestamp asc
```

> Tip (CLI): scope cost with `--log-stream-name-prefix` on `aws logs filter-log-events`, or
> `aws logs start-query --log-group-name inttra2-ecs-logs --start-time … --query-string '…'`.

---

## 11. IAM task roles & permissions

Each ECS service runs under a per-env, per-service **task role** with a set of customer-managed policies
(`INTTRA2-<ENV>-<service>-<SERVICE>`), plus a shared `INTTRA2-<ENV>-Mercury-Standard-Task` and the AWS ECS
service/autoscale managed roles. Policies are **least-privilege, scoped to that env's resource names**.

| Task role | Attached policies (besides ECS + Mercury-Standard) | Resource scope (from policy docs) |
|-----------|----------------------------------------------------|-----------------------------------|
| `…-Visibility-API-Task` | `…-Visibility-API-DDB`, `-S3`, `-SQS`, `-SNS`, `-ES`, `-SES` | DDB `container_events(+outbound)`; S3 `*-workspace`; SQS `ce_match/outbound/validate/pi_statusevents/cargo_subscription`; SNS `sns_event(_ce)`; ES `bk-search`+`tx-tracker`; SES from `no-reply@container-event-*.inttra.com` |
| `…-TT-Matcher-Task` | `…-TT-Matcher-DDB`, `-ES`, `-SQS`, `-SNS` | DDB `container_events*`+`booking_BookingDetail*` (RW + index Query/Scan); ES `bk-search`; SQS match/pending/outbound; SNS event_ce |
| `…-TT-Pending-Task` | `…-TT-Pending-DDB`, `-ES`, `-SQS`, `-SNS` | DDB pending/container_events; ES; SQS pending/outbound; SNS event_ce |
| `…-TT-Outbound-Task` | `…-TT-Outbound-DDB`, `-S3`, `-SQS`, `-SNS` | DDB container_events_outbound; S3 workspace+gis-delivery; SQS outbound/outbound_ipf/transformer; SNS event_ce |
| `…-Visibility-ITV-GPS-Processor` | `…-ITG-GPS-Processor-DDB`, `-S3`, `-SQS`, `-SNS` | DDB container_events; SQS watermill_itv_gps; SNS event_ce; S3 |
| _shared_ `…-Mercury-Standard-Task` | (on every role) | SSM `parameter/inttra2/<env>/*`; KMS Encrypt/Decrypt/GenerateDataKey (`*`); CloudWatch `PutMetricData`; S3 read `inttra-deployment`, `inttra-config/<env>/*` |

**Representative permission detail (QA Visibility-API):**

- **DDB** (`v2`): `BatchGetItem, DescribeTable, GetItem, ListTables, Query, Scan, UpdateItem` on `inttra2_qa_container_events`, `…_container_events_outbound` (+ `/index/*`).
- **S3**: full object RW + `ListBucket*` on `inttra2-qa-workspace` (+ `/*`).
- **SQS** (`v5`): `ReceiveMessage, SendMessage, DeleteMessage, ChangeMessageVisibility, GetQueue*, ListQueues, PurgeQueue` on the 5 inbound/outbound queues (+ DLQs).
- **SNS** (`v2`): `Publish` to `inttra2_qa_sns_event` / `…_sns_event_ce`.
- **ES** (`v2`): `ESHttp{Get,Put,Post,Delete,Head}` + `DescribeElasticsearchDomain*` on `inttra2-qa-es-bk-search/*` and `…-tx-tracker/*`.
- **SES** (`v2`): `SendEmail/SendRawEmail` from `no-reply@container-event-beta.inttra.com` to `*@{inttra.com,e2open.com,wisetechglobal.com}` only.

> Matcher's `-ES` policy is narrower (`bk-search` domain root only, no `/*`); Matcher/Pending `-DDB` use wildcard
> table prefixes (`inttra2_qa_container_events*`, `inttra2_qa_booking_BookingDetail*`) including streams (`GetRecords`/`GetShardIterator`).
> An ECS **task-execution role** (for ECR pull + log push) is also attached to every task definition.

---

## 12. Findings & discrepancies

1. **CVT uses the `inttra2_test` DynamoDB prefix.** All CVT visibility services read/write `inttra2_test_*`
   tables (shared with the `test` env), **not** `inttra2_cv_*`. Only the WM-subscription processor overrides
   to `inttra2_cv` → `inttra2_cv_CargoVisibilitySubscription` (97 items). Confirm this is intentional.
2. **PROD `CargoVisibilitySubscription` naming mismatch.** Prod `cargo-visibility-subscription-processor.yaml`
   sets `environment: inttra2_prod`, which derives table `inttra2_prod_CargoVisibilitySubscription` — **that
   table does not exist**. The only prod table is `inttra2_pr_CargoVisibilitySubscription`, which is **empty
   (0 items, created 2026-02-21)**. Prod CW-subscription flow is likely not landing data — verify.
3. **wm-inbound-processor has no dedicated ECS service** in the VIS clusters, yet its queues
   (`ce_cw_event_inbound`, `ce_cw_subscription_inbound`, `ce_wm_inbound`) exist and CVT's `ce_cw_event_inbound`
   had messages. Confirm where this app is deployed (separate cluster / on-demand / bundled).
4. **PROD `pi_statusevents` backlog** ≈ 7.33 M messages at capture — investigate consumer health.
5. **OpenSearch domains don't enforce HTTPS / node-to-node encryption**, and run EOL ES 6.8.
6. **Lambda log retention is only 14 days**, while prod s3-archive logs grow ~30 GB — short window for forensics.
7. QA Aurora backup retention is **1 day** (vs 7 days for CVT/PROD).

---

## 13. Reusable query reference

All commands run with `export AWS_PROFILE=642960533737_INTTRA2-QATeam AWS_PAGER=""` (region `us-east-1`).
On Git Bash, prefix SSM path calls with `MSYS_NO_PATHCONV=1` to stop `/inttra2/...` being mangled to a Windows path.

### 13.1 Repo search (code/config discovery)

| # | Tool | Query | Purpose |
|---|------|-------|---------|
| R1 | Glob | `visibility/**/*.{yml,yaml}` | find all config files |
| R2 | Grep | `sqs|sns|dynamo|s3|\.es\.amazonaws|rds\.amazonaws|awsps|bucket|Arn|region|endpointUrl` in `**/conf/**/*.yaml` | extract AWS refs per env |
| R3 | Grep | `environment:` in `*/conf/<env>/*.yaml` | get `dynamoDbConfig.environment` prefix per module/env |
| R4 | Grep | `@DynamoDBTable`, `TableName`, DAO classes | map DynamoDB tables → Java classes |

### 13.2 AWS CLI (read-only) — discovery

| # | Command | Purpose |
|---|---------|---------|
| A1 | `aws sts get-caller-identity` | confirm account/role |
| A2 | `aws dynamodb list-tables` | enumerate all tables |
| A3 | `aws sqs list-queues --queue-name-prefix inttra2_<env>_sqs_<x>` | enumerate queues by prefix (avoid 1000-cap) |
| A4 | `aws sns list-topics` | enumerate topics |
| A5 | `aws opensearch list-domain-names` | enumerate ES/OpenSearch domains |
| A6 | `aws s3api list-buckets --query 'Buckets[?contains(Name,\`workspace\`)||contains(Name,\`gis-delivery\`)].Name'` | filter relevant buckets |
| A7 | `aws rds describe-db-clusters` / `describe-db-instances` | Aurora topology |
| A8 | `aws ecs list-clusters` → grep `VIS` | find visibility clusters |
| A9 | `aws logs describe-log-groups` | enumerate log groups |

### 13.3 AWS CLI (read-only) — detail per resource

| # | Command | Purpose |
|---|---------|---------|
| D1 | `aws dynamodb describe-table --table-name <t>` (`KeySchema, GSIs, StreamSpecification, ProvisionedThroughput, SSEDescription, ItemCount, TableSizeBytes`) | table config |
| D2 | `aws sqs get-queue-attributes --queue-url <u> --attribute-names QueueArn ApproximateNumberOfMessages VisibilityTimeout MessageRetentionPeriod RedrivePolicy ReceiveMessageWaitTimeSeconds KmsMasterKeyId SqsManagedSseEnabled` | queue config |
| D3 | `aws sns get-topic-attributes --topic-arn <a>` | topic subs/encryption/policy |
| D4 | `aws opensearch describe-domain --domain-name <d>` | cluster/EBS/encryption/endpoint |
| D5 | `aws s3api get-bucket-encryption / get-bucket-versioning / get-bucket-lifecycle-configuration / get-bucket-location` | bucket config |
| D6 | `aws ssm get-parameters-by-path --path /inttra2/<env> --recursive --query 'Parameters[].{Name:Name,Type:Type}'` | list param **names only** (never `get-parameter`/values) |
| D7 | `aws ecs list-services --cluster <c>` → `aws ecs describe-services --cluster <c> --services …` | services + task def + counts |
| D8 | `aws ecs describe-task-definition --task-definition <fam:rev> --query 'taskDefinition.{taskRole,execRole,containers:containerDefinitions[].{image,logConfiguration}}'` | image, log group, roles |
| D9 | `aws iam list-attached-role-policies --role-name <r>` / `list-role-policies` | role → policy names |
| D10 | `aws iam get-policy --policy-arn <a> --query Policy.DefaultVersionId` → `aws iam get-policy-version …` | actual actions/resources |
| D11 | `aws logs describe-log-streams --log-group-name <g> --order-by LastEventTime --descending` | sample streams |
| D12 | `aws logs start-query` / `filter-log-events --log-stream-name-prefix <p>` | run Insights / scoped tail |

> **Guardrails honoured:** only `list`/`describe`/`get-*attributes`/`get-queue-attributes`/`get-policy*`
> read APIs were used. No `dynamodb scan`/`query`, no `sqs receive-message`, no `ssm get-parameter` value reads,
> no mutations.
