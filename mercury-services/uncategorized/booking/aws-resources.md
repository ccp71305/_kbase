# AWS Resources — Production (`_pr_` / `-pr-`) Environment

**Account:** `642960533737`  
**Region:** `us-east-1`  
**Profile:** `642960533737_INTTRA2-QATeam`  
**Generated:** 2026-05-27  
**Filter:** Resources matching `_pr_` or `-pr-` naming convention

---

## DynamoDB Tables (10)

| # | Table Name |
|---|-----------|
| 1 | `inttra2_pr_CargoVisibilitySubscription` |
| 2 | `inttra2_pr_controlnumber_sequence` |
| 3 | `inttra2_pr_network_service_blacklisted_email` |
| 4 | `inttra2_pr_network_service_connections_auditTrail` |
| 5 | `inttra2_pr_network_service_message_register` |
| 6 | `inttra2_pr_network_service_optionalvalidations` |
| 7 | `inttra2_pr_network_service_subscriptions` |
| 8 | `inttra2_pr_os_realtime_cache` |
| 9 | `inttra2_pr_schedules_pro_staging` |
| 10 | `inttra2_pr_watermill_offset` |

---

## S3 Buckets (42)

| # | Bucket Name |
|---|------------|
| 1 | `inttra2-pr-api` |
| 2 | `inttra2-pr-bounce-emails` |
| 3 | `inttra2-pr-bounced-emails` |
| 4 | `inttra2-pr-dp-os-stage` |
| 5 | `inttra2-pr-dp-transaction-tracking` |
| 6 | `inttra2-pr-dp-tt-stage` |
| 7 | `inttra2-pr-dp-tx-error-stage` |
| 8 | `inttra2-pr-dp-tx-stage` |
| 9 | `inttra2-pr-es-snapshots` |
| 10 | `inttra2-pr-gis-delivery` |
| 11 | `inttra2-pr-glue-logs` |
| 12 | `inttra2-pr-inbound-pickup` |
| 13 | `inttra2-pr-network-entity-partner` |
| 14 | `inttra2-pr-osng-workspace` |
| 15 | `inttra2-pr-outbound-delivery` |
| 16 | `inttra2-pr-reprocess-out` |
| 17 | `inttra2-pr-s3-auth-tokens-archive` |
| 18 | `inttra2-pr-s3-booking-bulkconttrackingevent-dpipeline-logs` |
| 19 | `inttra2-pr-s3-booking-bulkconttrackingevent-dynamodb-import` |
| 20 | `inttra2-pr-s3-booking-bulkconttrackingevent-query-results` |
| 21 | `inttra2-pr-s3-booking-bulkconttrackingevent-tables` |
| 22 | `inttra2-pr-s3-booking-containertrackingevent-dpipeline-logs` |
| 23 | `inttra2-pr-s3-booking-containertrackingevent-dynamodb-import` |
| 24 | `inttra2-pr-s3-booking-containertrackingevent-query-results` |
| 25 | `inttra2-pr-s3-booking-containertrackingevent-tables` |
| 26 | `inttra2-pr-s3-bookingdetail-historyload` |
| 27 | `inttra2-pr-s3-bookingdetail-s3archive` |
| 28 | `inttra2-pr-s3-bookingdetail-s3report` |
| 29 | `inttra2-pr-s3-bookingdetail-s3soarchive` |
| 30 | `inttra2-pr-s3-ebldetail-s3archive` |
| 31 | `inttra2-pr-s3-ebldocuments` |
| 32 | `inttra2-pr-s3-optionalvalidations-s3archive` |
| 33 | `inttra2-pr-s3-registrationdetail-s3archive` |
| 34 | `inttra2-pr-s3-subscriptions-s3archive` |
| 35 | `inttra2-pr-s3-tt-s3archive` |
| 36 | `inttra2-pr-s3-webbl-s3archive` |
| 37 | `inttra2-pr-si-s3archive` |
| 38 | `inttra2-pr-tx-tracking-report` |
| 39 | `inttra2-pr-watermill-cargoscreen` |
| 40 | `inttra2-pr-watermill-gps` |
| 41 | `inttra2-pr-workspace` |
| 42 | `inttra2-pr-workspace-filtered` |

---

## Lambda Functions (30)

### Underscore naming (`_pr_`) — 11

| # | Function Name |
|---|--------------|
| 1 | `inttra2_pr_lambda_bl_es_stream` |
| 2 | `inttra2_pr_lambda_pi_bl_stream` |
| 3 | `inttra2_pr_lambda_pi_si_stream` |
| 4 | `inttra2_pr_lambda_pi_statusevents_stream` |
| 5 | `inttra2_pr_lambda_ses_observability_logger` |
| 6 | `inttra2_pr_lambda_si_es_stream` |
| 7 | `inttra2_pr_lambda_si_s3` |
| 8 | `handle-inttra2_pr_sqs_bridgeob_pu_dlq-msg` |
| 9 | `handle-inttra2_pr_sqs_ce_match_dlq-msg` |
| 10 | `handle-inttra2_pr_sqs_ce_validate_dlq-msg` |
| 11 | `handle-inttra2_pr_sqs_pi_bl_es_dlq-msg` |

### Hyphen naming (`-pr-`) — 19

| # | Function Name |
|---|--------------|
| 1 | `inttra2-pr-lambda-auth-SS3ArchiveLambda` |
| 2 | `inttra2-pr-lambda-auth-StreamTriggerLambda` |
| 3 | `inttra2-pr-lambda-booking-outbound` |
| 4 | `inttra2-pr-lambda-booking-partner-integration` |
| 5 | `inttra2-pr-lambda-bookingdetail-CargoScreen` |
| 6 | `inttra2-pr-lambda-bookingdetail-ElasticsearchLambda` |
| 7 | `inttra2-pr-lambda-bookingdetail-S3ArchiveLambda` |
| 8 | `inttra2-pr-lambda-bookingdetail-SendLambda` |
| 9 | `inttra2-pr-lambda-optionalvalidations-S3ArchiveLambda` |
| 10 | `inttra2-pr-lambda-optionalvalidations-SendLambda` |
| 11 | `inttra2-pr-lambda-registrationdetail-S3Archive` |
| 12 | `inttra2-pr-lambda-start-os-collector-ecs-tasks` |
| 13 | `inttra2-pr-lambda-start-os-staging` |
| 14 | `inttra2-pr-lambda-subscriptions-S3ArchiveLambda` |
| 15 | `inttra2-pr-lambda-subscriptions-SendLambda` |
| 16 | `inttra2-pr-lambda-visibility-error-email` |
| 17 | `inttra2-pr-lambda-visibility-outbound-poller` |
| 18 | `inttra2-pr-lambda-visibility-pending-start` |
| 19 | `inttra2-pr-lambda-visibility-s3-archive` |

---

## SQS Queues (122)

### Underscore naming (`_pr_`) — Standard Queues

| # | Queue Name | Has DLQ |
|---|-----------|---------|
| 1 | `inttra2_pr_bounced_emails` | No |
| 2 | `inttra2_pr_sqs_aw_bridge_uploads_tracking` | ✅ |
| 3 | `inttra2_pr_sqs_bk_inbound` | ✅ |
| 4 | `inttra2_pr_sqs_booking_bridge_inbound` | ✅ |
| 5 | `inttra2_pr_sqs_booking_cargo_screen` | ✅ |
| 6 | `inttra2_pr_sqs_bridge_gis` | ✅ |
| 7 | `inttra2_pr_sqs_bridgeob_pu` | ✅ |
| 8 | `inttra2_pr_sqs_bridgeob_pu_temp_20200806` | No |
| 9 | `inttra2_pr_sqs_cargo_visibility_subscription_watermill` | ✅ |
| 10 | `inttra2_pr_sqs_ce_cw_event_inbound` | ✅ |
| 11 | `inttra2_pr_sqs_ce_cw_subscription_inbound` | ✅ |
| 12 | `inttra2_pr_sqs_ce_enrich` | ✅ |
| 13 | `inttra2_pr_sqs_ce_inbound` | ✅ |
| 14 | `inttra2_pr_sqs_ce_match` | ✅ |
| 15 | `inttra2_pr_sqs_ce_outbound` | ✅ |
| 16 | `inttra2_pr_sqs_ce_outbound_ipf` | ✅ |
| 17 | `inttra2_pr_sqs_ce_pending` | ✅ |
| 18 | `inttra2_pr_sqs_ce_to_s3` | ✅ |
| 19 | `inttra2_pr_sqs_ce_validate` | ✅ |
| 20 | `inttra2_pr_sqs_ce_wm_inbound` | ✅ |
| 21 | `inttra2_pr_sqs_cfast_batch_dynamo` | ✅ |
| 22 | `inttra2_pr_sqs_cfast_batch_inbound` | ✅ |
| 23 | `inttra2_pr_sqs_dispatcher_pu` | ✅ |
| 24 | `inttra2_pr_sqs_ebldocuments` | ✅ |
| 25 | `inttra2_pr_sqs_email_outbound` | ✅ |
| 26 | `inttra2_pr_sqs_event` | ✅ |
| 27 | `inttra2_pr_sqs_file_delivery` | ✅ |
| 28 | `inttra2_pr_sqs_ident_sec_pu` | ✅ |
| 29 | `inttra2_pr_sqs_ingest` | ✅ |
| 30 | `inttra2_pr_sqs_ingestor_ce` | ✅ |
| 31 | `inttra2_pr_sqs_os_collector` | ✅ |
| 32 | `inttra2_pr_sqs_os_fullfiller` | ✅ |
| 33 | `inttra2_pr_sqs_os_inbound` | ✅ |
| 34 | `inttra2_pr_sqs_os_inbound_temp` | No |
| 35 | `inttra2_pr_sqs_os_loader` | ✅ |
| 36 | `inttra2_pr_sqs_os_outbound` | ✅ |
| 37 | `inttra2_pr_sqs_os_port_pair_generator` | ✅ |
| 38 | `inttra2_pr_sqs_os_staging` | ✅ |
| 39 | `inttra2_pr_sqs_osifc` | ✅ |
| 40 | `inttra2_pr_sqs_osng_aggregator` | ✅ |
| 41 | `inttra2_pr_sqs_pi_bl_es` | ✅ |
| 42 | `inttra2_pr_sqs_pi_si` | ✅ |
| 43 | `inttra2_pr_sqs_pi_si_es` | ✅ |
| 44 | `inttra2_pr_sqs_pi_si_s3` | ✅ |
| 45 | `inttra2_pr_sqs_pi_statusevents` | ✅ |
| 46 | `inttra2_pr_sqs_pi_statusevents_pu` | ✅ |
| 47 | `inttra2_pr_sqs_reportbridge_bookingdetail_inbound` | ✅ |
| 48 | `inttra2_pr_sqs_rest_delivery` | ✅ |
| 49 | `inttra2_pr_sqs_router` | ✅ |
| 50 | `inttra2_pr_sqs_si_inbound` | ✅ |
| 51 | `inttra2_pr_sqs_splitter_ce_pu` | ✅ |
| 52 | `inttra2_pr_sqs_splitter_pu` | ✅ |
| 53 | `inttra2_pr_sqs_subscription_errors` | ✅ |
| 54 | `inttra2_pr_sqs_transformer_ce` | ✅ |
| 55 | `inttra2_pr_sqs_transformer_ce_inbound` | ✅ |
| 56 | `inttra2_pr_sqs_transformer_inbound` | ✅ |
| 57 | `inttra2_pr_sqs_transformer_inbound_dlq_temp` | No |
| 58 | `inttra2_pr_sqs_transformer_os_inbound` | ✅ |
| 59 | `inttra2_pr_sqs_watermill_bk` | ✅ |
| 60 | `inttra2_pr_sqs_watermill_cargoscreen` | ✅ |
| 61 | `inttra2_pr_sqs_watermill_ce` | ✅ |
| 62 | `inttra2_pr_sqs_watermill_itv_gps` | ✅ |
| 63 | `inttra2_pr_sqs_webbl_pdf_inbound` | ✅ |
| 64 | `inttra2_pr_sqs_webbl_zip_inbound` | ✅ |

### Underscore naming (`_pr_`) — FIFO Queues

| # | Queue Name | Has DLQ |
|---|-----------|---------|
| 1 | `inttra2_pr_sqs_emr_shapi.fifo` | ✅ |

### Hyphen naming (`-pr-`) — 10

| # | Queue Name | Has DLQ |
|---|-----------|---------|
| 1 | `inttra2-pr-sqs-auth-token-s3-archive` | ✅ |
| 2 | `inttra2-pr-sqs-booking-partner-integration` | ✅ |
| 3 | `inttra2-pr-sqs-bookingdetail-s3` | ✅ |
| 4 | `inttra2-pr-sqs-optionalvalidations-s3` | ✅ |
| 5 | `inttra2-pr-sqs-subscriptions-s3` | ✅ |

---

## SNS Topics (47)

### Email/SES Topics

| # | Topic Name |
|---|-----------|
| 1 | `inttra2_pr_evgm_rpt_aws` |
| 2 | `inttra2_pr_evgm_rpt_dba` |
| 3 | `inttra2_pr_no_reply_appianway_inttra_com` |
| 4 | `inttra2_pr_no_reply_booking_inttra_com` |
| 5 | `inttra2_pr_no_reply_container_event_inttra_com` |
| 6 | `inttra2_pr_no_reply_developer_inttra_com` |
| 7 | `inttra2_pr_no_reply_idc_inttra_com` |
| 8 | `inttra2_pr_no_reply_info_e2open_com` |
| 9 | `inttra2_pr_no_reply_login_inttra_com` |
| 10 | `inttra2_pr_no_reply_notification_inttra_com` |
| 11 | `inttra2_pr_no_reply_os_inttra_com` |
| 12 | `inttra2_pr_no_reply_registration_inttra_com` |
| 13 | `inttra2_pr_no_reply_ssr_inttra_com` |
| 14 | `inttra2_pr_ses_delivery` |

### Service Integration Topics (`_pr_`)

| # | Topic Name |
|---|-----------|
| 1 | `inttra2_pr_sns_auth_token_archive` |
| 2 | `inttra2_pr_sns_biztalk_alarm` |
| 3 | `inttra2_pr_sns_booking_BulkContTrackingEvent_ImportEventsPipelineFailureTopic` |
| 4 | `inttra2_pr_sns_booking_BulkContTrackingEvent_ImportEventsPipelineSuccessTopic` |
| 5 | `inttra2_pr_sns_booking_ContainerTrackingEvent_ImportEventsPipelineFailureTopic` |
| 6 | `inttra2_pr_sns_booking_ContainerTrackingEvent_ImportEventsPipelineSuccessTopic` |
| 7 | `inttra2_pr_sns_bookingdetail_TableStreamTopic` |
| 8 | `inttra2_pr_sns_dpde_error` |
| 9 | `inttra2_pr_sns_dpde_msc` |
| 10 | `inttra2_pr_sns_dynamodb_container_events` |
| 11 | `inttra2_pr_sns_ebldocuments` |
| 12 | `inttra2_pr_sns_event` |
| 13 | `inttra2_pr_sns_event_ce` |
| 14 | `inttra2_pr_sns_inbound` |
| 15 | `inttra2_pr_sns_optionalvalidations_TableStreamTopic` |
| 16 | `inttra2_pr_sns_os_port_pair_generator` |
| 17 | `inttra2_pr_sns_osifc` |
| 18 | `inttra2_pr_sns_pi_bl` |
| 19 | `inttra2_pr_sns_pi_si` |
| 20 | `inttra2_pr_sns_pi_statusevents` |
| 21 | `inttra2_pr_sns_reportbridge_booking_topic` |
| 22 | `inttra2_pr_sns_start_os_collector` |
| 23 | `inttra2_pr_sns_start_osng_aggregator` |
| 24 | `inttra2_pr_sns_start_osng_loader` |
| 25 | `inttra2_pr_sns_start_osng_outbound` |
| 26 | `inttra2_pr_sns_start_osng_staging` |
| 27 | `inttra2_pr_sns_subscriptions_TableStreamTopic` |
| 28 | `inttra2_pr_sns_watermill_cargoscreen` |
| 29 | `inttra2_pr_sns_watermill_itv_gps` |
| 30 | `inttra2_pr_sqs_ce_inbound_dlq-depth` |
| 31 | `inttra2_pr_upsert_udl_booking_current_failed` |
| 32 | `inttra2_sns_pr_evgm` |

### Hyphen naming (`-pr-`) — 1

| # | Topic Name |
|---|-----------|
| 1 | `inttra2-pr-reprocess-ob-bookings` |

---

## CloudWatch Log Groups (61)

### Lambda Log Groups (`_pr_`)

| # | Log Group |
|---|----------|
| 1 | `/aws/lambda/handle-inttra2_pr_sqs_bridgeob_pu_dlq-msg` |
| 2 | `/aws/lambda/handle-inttra2_pr_sqs_ce_match_dlq-msg` |
| 3 | `/aws/lambda/handle-inttra2_pr_sqs_ce_validate_dlq-msg` |
| 4 | `/aws/lambda/handle-inttra2_pr_sqs_pi_bl_es_dlq-msg` |
| 5 | `/aws/lambda/inttra2_pr_lambda_bl_es_stream` |
| 6 | `/aws/lambda/inttra2_pr_lambda_booking_BulkContTrackingEvent_ImportEvents` |
| 7 | `/aws/lambda/inttra2_pr_lambda_booking_ContainerTrackingEvent_CreateTables` |
| 8 | `/aws/lambda/inttra2_pr_lambda_booking_ContainerTrackingEvent_ExtractEvents` |
| 9 | `/aws/lambda/inttra2_pr_lambda_booking_ContainerTrackingEvent_ImportEvents` |
| 10 | `/aws/lambda/inttra2_pr_lambda_booking_ContainerTrackingEvent_S3Unzip` |
| 11 | `/aws/lambda/inttra2_pr_lambda_pi_bl_stream` |
| 12 | `/aws/lambda/inttra2_pr_lambda_pi_si_stream` |
| 13 | `/aws/lambda/inttra2_pr_lambda_pi_statusevents_stream` |
| 14 | `/aws/lambda/inttra2_pr_lambda_ses_observability_logger` |
| 15 | `/aws/lambda/inttra2_pr_lambda_si_es_stream` |
| 16 | `/aws/lambda/inttra2_pr_lambda_si_s3` |
| 17 | `sns/us-east-1/642960533737/inttra2_pr_sns_inbound` |

### Lambda Log Groups (`-pr-`)

| # | Log Group |
|---|----------|
| 1 | `/aws/lambda/inttra2-pr-lambda-auth-SS3ArchiveLambda` |
| 2 | `/aws/lambda/inttra2-pr-lambda-auth-StreamTriggerLambda` |
| 3 | `/aws/lambda/inttra2-pr-lambda-booking-outbound` |
| 4 | `/aws/lambda/inttra2-pr-lambda-booking-partner-integration` |
| 5 | `/aws/lambda/inttra2-pr-lambda-bookingdetail-CargoScreen` |
| 6 | `/aws/lambda/inttra2-pr-lambda-bookingdetail-ElasticsearchLambda` |
| 7 | `/aws/lambda/inttra2-pr-lambda-bookingdetail-S3ArchiveLambda` |
| 8 | `/aws/lambda/inttra2-pr-lambda-bookingdetail-SendLambda` |
| 9 | `/aws/lambda/inttra2-pr-lambda-optionalvalidations-S3ArchiveLambda` |
| 10 | `/aws/lambda/inttra2-pr-lambda-optionalvalidations-SendLambda` |
| 11 | `/aws/lambda/inttra2-pr-lambda-registrationdetail-S3Archive` |
| 12 | `/aws/lambda/inttra2-pr-lambda-start-os-collector-ecs-tasks` |
| 13 | `/aws/lambda/inttra2-pr-lambda-start-os-staging` |
| 14 | `/aws/lambda/inttra2-pr-lambda-subscriptions-S3ArchiveLambda` |
| 15 | `/aws/lambda/inttra2-pr-lambda-subscriptions-SendLambda` |
| 16 | `/aws/lambda/inttra2-pr-lambda-visibility-error-email` |
| 17 | `/aws/lambda/inttra2-pr-lambda-visibility-outbound-poller` |
| 18 | `/aws/lambda/inttra2-pr-lambda-visibility-pending-start` |
| 19 | `/aws/lambda/inttra2-pr-lambda-visibility-s3-archive` |

### Infrastructure / Service Log Groups (`-pr-`)

| # | Log Group |
|---|----------|
| 1 | `/aws/es/inttra2-pr-es-tx-tracker` |
| 2 | `/aws/kinesisfirehose/aws-waf-logs-pr-ilogs-es-useast1` |
| 3 | `/aws/kinesisfirehose/aws-waf-logs-pr-us-east-1` |
| 4 | `inttra2-pr-lg-app-way` |
| 5 | `inttra2-pr-lg-auth` |
| 6 | `inttra2-pr-lg-bkapi` |
| 7 | `inttra2-pr-lg-dp-haproxy` |
| 8 | `inttra2-pr-lg-evgm-rpt` |
| 9 | `inttra2-pr-lg-ha-proxy` |
| 10 | `inttra2-pr-lg-ha-proxy-compliance` |
| 11 | `inttra2-pr-lg-net-svc` |
| 12 | `inttra2-pr-lg-osng` |
| 13 | `inttra2-pr-lg-osng-appway` |
| 14 | `inttra2-pr-lg-osng-ldr` |
| 15 | `inttra2-pr-lg-osng-start-loader-task` |
| 16 | `inttra2-pr-lg-osng-start-os-collector-task` |
| 17 | `inttra2-pr-lg-osng-start-outbound-task` |
| 18 | `inttra2-pr-lg-osng-start-staging-task` |
| 19 | `inttra2-pr-lg-pi` |
| 20 | `inttra2-pr-lg-ptui` |
| 21 | `inttra2-pr-lg-rates` |
| 22 | `inttra2-pr-lg-rates-batch` |
| 23 | `inttra2-pr-lg-ssr-task` |
| 24 | `inttra2-pr-lg-visibility` |
| 25 | `inttra2-pr-ptui-nlb` |

---

## EventBridge Rules (8)

| # | Rule Name |
|---|----------|
| 1 | `inttra-pr-gluecrawler-si-lambda` |
| 2 | `inttra-pr-gluecrawler-tt-lambda` |
| 3 | `inttra2-pr-cron-visibility-error-email` |
| 4 | `inttra2-pr-cron-visibility-outbound-poller` |
| 5 | `inttra2-pr-cron-visibility-pending-start` |
| 6 | `inttra2-pr-ebl-gluecrawler-lambda` |
| 7 | `inttra2-pr-glue-crawler-exclusions-lambda` |
| 8 | `inttra2-pr-lambda-start-os-staging-cwevent` |

---

## Secrets Manager

No secrets found matching `_pr_` or `-pr-` filter.

## SSM Parameter Store

No parameters found matching `_pr_` or `-pr-` filter.

## Kinesis Streams

No streams found matching `_pr_` or `-pr-` filter.

## Step Functions

No state machines found matching `_pr_` or `-pr-` filter.

---

## Summary

| AWS Service | `_pr_` Count | `-pr-` Count | Total |
|------------|-------------|-------------|-------|
| DynamoDB Tables | 10 | 0 | **10** |
| S3 Buckets | 0 | 42 | **42** |
| Lambda Functions | 11 | 19 | **30** |
| SQS Queues | 112 | 10 | **122** |
| SNS Topics | 46 | 1 | **47** |
| CloudWatch Log Groups | 17 | 44 | **61** |
| EventBridge Rules | 0 | 8 | **8** |
| Secrets Manager | 0 | 0 | **0** |
| SSM Parameter Store | 0 | 0 | **0** |
| Kinesis Streams | 0 | 0 | **0** |
| Step Functions | 0 | 0 | **0** |
| **Total** | **196** | **124** | **320** |
