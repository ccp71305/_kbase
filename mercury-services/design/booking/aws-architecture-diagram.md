# INTTRA2 Production Architecture — Network & Component Diagram

**Account:** `642960533737` | **Region:** `us-east-1` | **Environment:** Production (`pr`)  
**Generated:** 2026-05-27

---

## 1. High-Level Architecture Overview

This diagram shows the overall topology: load balancers → ECS clusters → messaging → storage.

```mermaid
graph TB
    subgraph INTERNET["☁️ Internet / External Partners"]
        ExtUsers["External Users / Carriers"]
        BizTalk["BizTalk On-Prem"]
    end

    subgraph LB_LAYER["🔀 Load Balancers"]
        ALB_APPWAY["ALB-PR-APPWAY-WS<br/>(internet-facing, ALB)"]
        ALB_PTUI["alb-pr-ptui-ecs<br/>(internet-facing, ALB)"]
        ALB_PROXY["ALB-PR-PROXY<br/>(internal, ALB)"]
        ALB_API["alb-pr-api-internal<br/>(internal, ALB)"]
        NLB_DP["nlb-prod-dp-haproxy<br/>(internet-facing, NLB)"]
        NLB_BIZ["nlb-pr-biztalk<br/>(internal, NLB)"]
        NLB_PTUI["NLB-PTUI-PR-NJHQ-WS<br/>(internal, NLB)"]
    end

    subgraph ECS_LAYER["📦 ECS Clusters"]
        ECS_APWY["ANEPRAPWY-001/002<br/>AppianWay Processing"]
        ECS_BK["ANEPRBK-001<br/>Booking API"]
        ECS_AUTH["ANEPRAUTH-001<br/>Auth & Network"]
        ECS_CONTIVO["ANEPRCONTIVO-001/002/CE<br/>Transformation"]
        ECS_OSNG["ANEPROSNG-001/003<br/>Ocean Schedules"]
        ECS_VIS["ANEPRVIS-001/002<br/>Visibility"]
        ECS_WEBSVC["ANEPRWEBSVC-001<br/>Web Services"]
        ECS_PROXY["ANEPRPROXY-001<br/>HAProxy"]
        ECS_PI["ANEPRPI-001<br/>Platform Integration"]
        ECS_DPDE["ANEPRDPDE-001<br/>Data Pipeline"]
        ECS_DPHAP["ANEPRDPHAP-001<br/>DP HAProxy"]
    end

    subgraph MSG_LAYER["📨 Messaging (SNS → SQS)"]
        SNS["SNS Topics (47)"]
        SQS["SQS Queues (122)"]
    end

    subgraph COMPUTE_LAYER["⚡ Serverless"]
        LAMBDA["Lambda Functions (30)"]
        EVENTBRIDGE["EventBridge Rules (8)"]
    end

    subgraph DATA_LAYER["💾 Storage"]
        DYNAMO["DynamoDB Tables (10)"]
        S3["S3 Buckets (42)"]
    end

    subgraph OBSERVABILITY["📊 Observability"]
        CW["CloudWatch Log Groups (61)"]
    end

    subgraph SECURITY["🔐 IAM"]
        IAM_ROLES["IAM Roles (145+)"]
    end

    ExtUsers --> ALB_APPWAY & ALB_PTUI & NLB_DP
    BizTalk --> NLB_BIZ
    ALB_APPWAY --> ECS_APWY
    ALB_PTUI --> ECS_WEBSVC
    ALB_PROXY --> ECS_PROXY
    ALB_API --> ECS_BK & ECS_AUTH
    NLB_DP --> ECS_DPHAP
    NLB_BIZ --> ECS_CONTIVO
    NLB_PTUI --> ECS_WEBSVC

    ECS_APWY --> SNS & SQS
    ECS_BK --> SNS & SQS & DYNAMO
    ECS_AUTH --> DYNAMO
    ECS_CONTIVO --> SQS
    ECS_OSNG --> SQS & S3
    ECS_VIS --> SQS & DYNAMO
    ECS_WEBSVC --> SQS & S3

    SNS --> SQS
    SQS --> ECS_APWY & LAMBDA
    EVENTBRIDGE --> LAMBDA
    LAMBDA --> DYNAMO & S3 & SQS
    
    ECS_LAYER --> CW
    LAMBDA --> CW
    IAM_ROLES -.->|assumes| ECS_LAYER & LAMBDA
```

---

## 2. ECS Clusters & Services — Detailed Breakdown

This diagram expands each ECS cluster to show individual services running inside.

```mermaid
graph LR
    subgraph ANEPRAPWY_001["ANEPRAPWY-001 — AppianWay Message Processing (23 services)"]
        direction TB
        subgraph APWY_INGEST["Ingest"]
            ingestor["ingestor-prod"]
            ce_ingestor["ce-ingestor-prod"]
        end
        subgraph APWY_DISTRIBUTE["Distribute"]
            distributor["distributor-prod"]
            distributor_rest["distributor-rest-prod"]
            dispatcher["dispatcher-prod (×3)"]
        end
        subgraph APWY_BOOKING["Booking Processing"]
            bk_inbound["BookingInboundConsumer"]
            bk_bridge["BookingBridge-prod"]
            cargo_screen["CargoScreenConsumer"]
            PIBK["PIBK-prod"]
        end
        subgraph APWY_VISIBILITY["Visibility Processing"]
            cv_events["CargoVisibilityEventsProcessor"]
            cv_subs["CargoVisibilitySubscriptionProcessor"]
            vis_inbound["VisibilityInboundConsumer"]
            vis_wm["VisibilityWMInboundProcessor"]
            itv_gps["ITV-GPS-Consumer"]
        end
        subgraph APWY_PI["Platform Integration"]
            pisi_in["PISI_IN-prod"]
            pisi_out["PISI_OUT-prod"]
            pibl_in["PIBL_IN-prod"]
        end
        subgraph APWY_WATERMILL["Watermill Publishers"]
            wm_pub["watermill-publisher-prod"]
            wm_bk["WatermillPublisherBooking"]
            wm_cvs["WatermillPublisherCargoVisSubscription"]
        end
        subgraph APWY_SUPPORT["Support Services"]
            event_writer["event-writer-prod"]
            error_proc["error-processor-prod"]
            email_sender["email-sender-prod"]
        end
    end

    subgraph ANEPRAPWY_002["ANEPRAPWY-002 — Splitters"]
        splitter["splitter-prod"]
        ce_splitter["ce-splitter-prod"]
    end

    subgraph ANEPRBK_001["ANEPRBK-001 — Booking"]
        booking["Booking-prod"]
    end

    subgraph ANEPRAUTH_001["ANEPRAUTH-001 — Auth & Network"]
        auth["Auth-prod"]
        net_svc["Network-Services-prod"]
    end

    subgraph ANEPRCONTIVO["ANEPRCONTIVO-001/002/CE — Transformation"]
        transformer["transformer-prod"]
        os_transformer["os-transformer-prod"]
        ce_transformer["ce-transformer-prod"]
    end

    subgraph ANEPROSNG["ANEPROSNG-001/003 — Ocean Schedules"]
        os_inbound["OS-Inbound-prod"]
        os_ppg["OS-Pro-PortPairGenerator"]
        os_cma["OS-Pro-Collector-cma"]
        os_maersk["OS-Pro-Collector-maersk"]
        os_msc["OS-Pro-Collector-msc"]
        os_evergreen["OS-Pro-Collector-evergreen"]
        os_hmm["OS-Pro-Collector-hmm"]
        os_zim["OS-Pro-Collector-zim"]
        os_others["+ 6 more carriers"]
    end

    subgraph ANEPRVIS["ANEPRVIS-001/002 — Visibility"]
        vis_api["Visibility-prod (API)"]
        vis_pending["VisibilityPending"]
        vis_outbound["VisibilityOutbound"]
        vis_matcher["VisibilityMatcher"]
        vis_itv["Visibility-ITV-GPS-Processor"]
    end

    subgraph ANEPRWEBSVC["ANEPRWEBSVC-001 — Web Services (21 services)"]
        direction TB
        subgraph WEBSVC_CORE["Core APIs"]
            txtrack["TxTracking-prod"]
            registration["Registration-prod"]
            ssr["SelfServiceReports-prod"]
            rates["Rates-prod"]
            vas["VAS-prod"]
            webbl["WebBL-prod"]
            bol["BillOfLading-prod"]
            si["SI-prod"]
            osng["OSNG-prod"]
            bk_cs["BookingCargoScreen"]
        end
        subgraph WEBSVC_PTUI["PTUI Portal Services"]
            ptui_bk["PTUI-BK"]
            ptui_bl["PTUI-BL"]
            ptui_si["PTUI-SI"]
            ptui_rt["PTUI-RT"]
            ptui_admin["PTUI-Admin"]
            ptui_portal["PTUI-PortalServices"]
            ptui_data["PTUI-DataServices"]
            ptui_reports["PTUI-Reports"]
            ptui_rpt_svc["PTUI-ReportServices"]
            ptui_bl_svc["PTUI-BLServices"]
            ptui_admin_svc["PTUI-AdminServices"]
        end
    end

    subgraph ANEPRPROXY["ANEPRPROXY-001 — Proxy"]
        haproxy["ha-proxy-prod"]
        haproxy_cl["ha-proxy-ComplianceLink"]
    end

    subgraph ANEPRPI["ANEPRPI-001 — Platform Integration"]
        pise_out["PISE_OUT-prod"]
    end

    subgraph DPDE["ANEPRDPDE-001 / ANEPRDPHAP-001"]
        dpde["DPDE-prod"]
        dp_haproxy["dp-haproxy-prod"]
    end
```

---

## 3. Message Flow — SNS → SQS → Consumers

This diagram shows how messages flow from publishers through SNS fan-out to SQS queues, consumed by ECS services and Lambda functions.

```mermaid
graph LR
    subgraph PUBLISHERS["📤 Publishers (ECS Services)"]
        PUB_INGEST["Ingestor"]
        PUB_DISPATCH["Dispatcher"]
        PUB_DISTRIB["Distributor"]
        PUB_TRANS["Transformer"]
        PUB_WM["Watermill Publishers"]
        PUB_SPLIT["Splitter"]
    end

    subgraph SNS_TOPICS["📢 SNS Topics"]
        sns_inbound["sns_inbound"]
        sns_event["sns_event"]
        sns_event_ce["sns_event_ce"]
        sns_pi_si["sns_pi_si"]
        sns_pi_bl["sns_pi_bl"]
        sns_pi_se["sns_pi_statusevents"]
        sns_osifc["sns_osifc"]
        sns_os_ppg["sns_os_port_pair_generator"]
        sns_ebldocs["sns_ebldocuments"]
        sns_wm_cs["sns_watermill_cargoscreen"]
        sns_wm_gps["sns_watermill_itv_gps"]
        sns_bk_detail["sns_bookingdetail_TableStreamTopic"]
        sns_sub_stream["sns_subscriptions_TableStreamTopic"]
        sns_ov_stream["sns_optionalvalidations_TableStreamTopic"]
        sns_reprocess["inttra2-pr-reprocess-ob-bookings"]
    end

    subgraph SQS_QUEUES["📬 SQS Queues (key flows)"]
        sqs_ingest["sqs_ingest"]
        sqs_event["sqs_event"]
        sqs_router["sqs_router"]
        sqs_split["sqs_splitter_pu"]
        sqs_ce_split["sqs_splitter_ce_pu"]
        sqs_dispatch["sqs_dispatcher_pu"]
        sqs_trans["sqs_transformer_inbound"]
        sqs_ce_trans["sqs_transformer_ce_inbound"]
        sqs_os_trans["sqs_transformer_os_inbound"]
        sqs_bk_in["sqs_bk_inbound"]
        sqs_bk_bridge["sqs_booking_bridge_inbound"]
        sqs_bk_cs["sqs_booking_cargo_screen"]
        sqs_vis_ce["sqs_ce_inbound"]
        sqs_vis_match["sqs_ce_match"]
        sqs_vis_out["sqs_ce_outbound"]
        sqs_vis_pend["sqs_ce_pending"]
        sqs_vis_val["sqs_ce_validate"]
        sqs_vis_enr["sqs_ce_enrich"]
        sqs_os_in["sqs_os_inbound"]
        sqs_os_col["sqs_os_collector"]
        sqs_os_stg["sqs_os_staging"]
        sqs_os_ldr["sqs_os_loader"]
        sqs_os_ob["sqs_os_outbound"]
        sqs_pisi["sqs_pi_si"]
        sqs_pibl["sqs_pi_bl_es"]
        sqs_pise["sqs_pi_statusevents"]
        sqs_email["sqs_email_outbound"]
        sqs_file_del["sqs_file_delivery"]
        sqs_rest_del["sqs_rest_delivery"]
        sqs_wm_bk["sqs_watermill_bk"]
        sqs_wm_ce["sqs_watermill_ce"]
        sqs_wm_cs["sqs_watermill_cargoscreen"]
        sqs_wm_gps["sqs_watermill_itv_gps"]
        sqs_bk_s3["inttra2-pr-sqs-bookingdetail-s3"]
        sqs_sub_s3["inttra2-pr-sqs-subscriptions-s3"]
        sqs_ov_s3["inttra2-pr-sqs-optionalvalidations-s3"]
    end

    subgraph CONSUMERS["📥 Consumers"]
        CON_INGEST["Ingestor (ECS)"]
        CON_EVENT["Event Writer (ECS)"]
        CON_ROUTER["Router (ECS)"]
        CON_SPLIT["Splitter (ECS)"]
        CON_DISPATCH["Dispatcher (ECS)"]
        CON_TRANS["Transformer (ECS)"]
        CON_BK["BookingInboundConsumer (ECS)"]
        CON_BRIDGE["BookingBridge (ECS)"]
        CON_CS["CargoScreenConsumer (ECS)"]
        CON_VIS_IN["VisibilityInboundConsumer (ECS)"]
        CON_VIS_MATCH["VisibilityMatcher (ECS)"]
        CON_VIS_OUT["VisibilityOutbound (ECS)"]
        CON_VIS_PEND["VisibilityPending (ECS)"]
        CON_OS["OS-Inbound (ECS)"]
        CON_PISI["PISI_IN (ECS)"]
        CON_PIBL["PIBL_IN (ECS)"]
        CON_EMAIL["EmailSender (ECS)"]
        CON_FILE["FileDelivery (ECS)"]
        CON_WM["Watermill Publishers (ECS)"]
        CON_LAMBDA["Lambda Functions"]
    end

    PUB_INGEST --> sns_inbound
    PUB_DISPATCH --> sqs_dispatch
    PUB_DISTRIB --> sqs_router & sqs_file_del & sqs_rest_del
    PUB_TRANS --> sns_event & sns_event_ce
    PUB_WM --> sqs_wm_bk & sqs_wm_ce & sqs_wm_cs & sqs_wm_gps
    PUB_SPLIT --> sqs_dispatch

    sns_inbound --> sqs_ingest & sqs_trans & sqs_ce_trans & sqs_os_trans
    sns_event --> sqs_event & sqs_split & sqs_bk_in
    sns_event_ce --> sqs_ce_split & sqs_vis_ce
    sns_pi_si --> sqs_pisi
    sns_pi_bl --> sqs_pibl
    sns_bk_detail --> sqs_bk_s3
    sns_sub_stream --> sqs_sub_s3
    sns_ov_stream --> sqs_ov_s3

    sqs_ingest --> CON_INGEST
    sqs_event --> CON_EVENT
    sqs_router --> CON_ROUTER
    sqs_split --> CON_SPLIT
    sqs_dispatch --> CON_DISPATCH
    sqs_trans --> CON_TRANS
    sqs_bk_in --> CON_BK
    sqs_bk_bridge --> CON_BRIDGE
    sqs_bk_cs --> CON_CS
    sqs_vis_ce --> CON_VIS_IN
    sqs_vis_match --> CON_VIS_MATCH
    sqs_vis_out --> CON_VIS_OUT
    sqs_vis_pend --> CON_VIS_PEND
    sqs_os_in --> CON_OS
    sqs_pisi --> CON_PISI
    sqs_pibl --> CON_PIBL
    sqs_email --> CON_EMAIL
    sqs_wm_bk & sqs_wm_ce --> CON_WM
    sqs_bk_s3 & sqs_sub_s3 & sqs_ov_s3 --> CON_LAMBDA
```

---

## 4. Lambda Functions & Triggers

```mermaid
graph TB
    subgraph TRIGGERS["⏰ Triggers"]
        DDB_STREAMS["DynamoDB Streams"]
        EB_CRON["EventBridge Cron Rules"]
        SNS_TRIGGER["SNS Notifications"]
        SQS_DLQ["SQS Dead Letter Queues"]
    end

    subgraph LAMBDA_UNDERSCORE["⚡ Lambda (_pr_) — Stream Processors"]
        l_pi_si["lambda_pi_si_stream"]
        l_pi_bl["lambda_pi_bl_stream"]
        l_pi_se["lambda_pi_statusevents_stream"]
        l_si_es["lambda_si_es_stream"]
        l_bl_es["lambda_bl_es_stream"]
        l_si_s3["lambda_si_s3"]
        l_ses["lambda_ses_observability_logger"]
    end

    subgraph LAMBDA_DLQ_HANDLERS["⚡ Lambda — DLQ Handlers"]
        h_bridgeob["handle-sqs_bridgeob_pu_dlq"]
        h_ce_match["handle-sqs_ce_match_dlq"]
        h_ce_val["handle-sqs_ce_validate_dlq"]
        h_pibl["handle-sqs_pi_bl_es_dlq"]
    end

    subgraph LAMBDA_HYPHEN["⚡ Lambda (-pr-) — Business Logic"]
        subgraph LAMBDA_AUTH["Auth"]
            l_auth_s3["lambda-auth-SS3ArchiveLambda"]
            l_auth_stream["lambda-auth-StreamTriggerLambda"]
        end
        subgraph LAMBDA_BOOKING["Booking"]
            l_bk_s3["lambda-bookingdetail-S3ArchiveLambda"]
            l_bk_es["lambda-bookingdetail-ElasticsearchLambda"]
            l_bk_send["lambda-bookingdetail-SendLambda"]
            l_bk_cs["lambda-bookingdetail-CargoScreen"]
            l_bk_out["lambda-booking-outbound"]
            l_bk_pi["lambda-booking-partner-integration"]
        end
        subgraph LAMBDA_VIS["Visibility"]
            l_vis_ob["lambda-visibility-outbound-poller"]
            l_vis_err["lambda-visibility-error-email"]
            l_vis_s3["lambda-visibility-s3-archive"]
            l_vis_start["lambda-visibility-pending-start"]
        end
        subgraph LAMBDA_SUBS["Subscriptions & Validations"]
            l_sub_s3["lambda-subscriptions-S3ArchiveLambda"]
            l_sub_send["lambda-subscriptions-SendLambda"]
            l_ov_s3["lambda-optionalvalidations-S3ArchiveLambda"]
            l_ov_send["lambda-optionalvalidations-SendLambda"]
        end
        subgraph LAMBDA_REG["Registration"]
            l_reg_s3["lambda-registrationdetail-S3Archive"]
        end
        subgraph LAMBDA_OS["Ocean Schedules"]
            l_os_col["lambda-start-os-collector-ecs-tasks"]
            l_os_stg["lambda-start-os-staging"]
        end
    end

    subgraph TARGETS["🎯 Targets"]
        ES["Elasticsearch"]
        S3_ARCHIVE["S3 Archive Buckets"]
        DDB_TABLES["DynamoDB Tables"]
        SQS_OUT["SQS Outbound Queues"]
        SES["SES (Email)"]
        ECS_TASKS["ECS Task Management"]
    end

    DDB_STREAMS --> l_pi_si & l_pi_bl & l_pi_se & l_si_es & l_bl_es
    DDB_STREAMS --> l_auth_stream & l_bk_es & l_bk_send & l_sub_send & l_ov_send
    SNS_TRIGGER --> l_si_s3 & l_bk_s3 & l_sub_s3 & l_ov_s3 & l_auth_s3 & l_reg_s3 & l_vis_s3
    SQS_DLQ --> h_bridgeob & h_ce_match & h_ce_val & h_pibl

    EB_CRON -->|"cron-visibility-*"| l_vis_ob & l_vis_err & l_vis_start
    EB_CRON -->|"lambda-start-os-staging-cwevent"| l_os_stg
    EB_CRON -->|"gluecrawler-*"| ES

    l_pi_si & l_pi_bl & l_si_es & l_bl_es --> ES
    l_bk_es --> ES
    l_bk_s3 & l_sub_s3 & l_ov_s3 & l_auth_s3 & l_reg_s3 & l_vis_s3 --> S3_ARCHIVE
    l_si_s3 --> S3_ARCHIVE
    l_bk_send & l_sub_send & l_ov_send --> SQS_OUT
    l_vis_err --> SES
    l_os_col & l_os_stg --> ECS_TASKS
    l_ses --> SES
```

---

## 5. Data Storage — DynamoDB & S3

```mermaid
graph TB
    subgraph DYNAMO["🗄️ DynamoDB Tables"]
        subgraph DDB_NETWORK["Network Service"]
            ddb_blacklist["network_service_blacklisted_email"]
            ddb_audit["network_service_connections_auditTrail"]
            ddb_msg_reg["network_service_message_register"]
            ddb_ov["network_service_optionalvalidations"]
            ddb_subs["network_service_subscriptions"]
        end
        subgraph DDB_BOOKING["Booking"]
            ddb_cv_sub["CargoVisibilitySubscription"]
            ddb_ctrl["controlnumber_sequence"]
        end
        subgraph DDB_OS["Ocean Schedules"]
            ddb_os_cache["os_realtime_cache"]
            ddb_os_stg["schedules_pro_staging"]
        end
        subgraph DDB_SHARED["Shared"]
            ddb_wm_off["watermill_offset"]
        end
    end

    subgraph S3_BUCKETS["🪣 S3 Buckets"]
        subgraph S3_ARCHIVE["Archive Buckets"]
            s3_bk_arch["s3-bookingdetail-s3archive"]
            s3_bk_so["s3-bookingdetail-s3soarchive"]
            s3_ebl_arch["s3-ebldetail-s3archive"]
            s3_reg_arch["s3-registrationdetail-s3archive"]
            s3_sub_arch["s3-subscriptions-s3archive"]
            s3_tt_arch["s3-tt-s3archive"]
            s3_webbl_arch["s3-webbl-s3archive"]
            s3_ov_arch["s3-optionalvalidations-s3archive"]
            s3_auth_arch["s3-auth-tokens-archive"]
            s3_si_arch["si-s3archive"]
        end
        subgraph S3_REPORTS["Report & History"]
            s3_bk_rpt["s3-bookingdetail-s3report"]
            s3_bk_hist["s3-bookingdetail-historyload"]
            s3_tx_rpt["tx-tracking-report"]
        end
        subgraph S3_MESSAGING["Message & Delivery"]
            s3_api["api"]
            s3_inbound["inbound-pickup"]
            s3_outbound["outbound-delivery"]
            s3_reprocess["reprocess-out"]
            s3_gis["gis-delivery"]
        end
        subgraph S3_CT_EVENTS["Container Tracking Events"]
            s3_ct_pipe["s3-booking-containertrackingevent-*<br/>(4 buckets: dpipeline-logs,<br/>dynamodb-import, query-results, tables)"]
            s3_bulk_pipe["s3-booking-bulkconttrackingevent-*<br/>(4 buckets: dpipeline-logs,<br/>dynamodb-import, query-results, tables)"]
        end
        subgraph S3_OS["Ocean Schedules"]
            s3_osng["osng-workspace"]
            s3_dp_os["dp-os-stage"]
        end
        subgraph S3_INFRA["Infrastructure"]
            s3_es_snap["es-snapshots"]
            s3_glue["glue-logs"]
            s3_workspace["workspace"]
            s3_workspace_f["workspace-filtered"]
        end
        subgraph S3_EMAIL["Email"]
            s3_bounce["bounce-emails"]
            s3_bounced["bounced-emails"]
        end
        subgraph S3_MISC["Other"]
            s3_ebl_docs["s3-ebldocuments"]
            s3_net_part["network-entity-partner"]
            s3_dp_tx["dp-tx-stage / dp-tx-error-stage"]
            s3_dp_tt["dp-tt-stage / dp-transaction-tracking"]
            s3_wm_cs["watermill-cargoscreen"]
            s3_wm_gps["watermill-gps"]
        end
    end

    subgraph CONSUMERS_DATA["Consumers"]
        ECS_SVC["ECS Services"]
        LAMBDA_FN["Lambda Functions"]
        GLUE["Glue ETL Jobs"]
        SNOWFLAKE["Snowflake<br/>(via S3 cross-account)"]
    end

    ECS_SVC --> DYNAMO
    ECS_SVC --> S3_MESSAGING
    LAMBDA_FN --> S3_ARCHIVE
    LAMBDA_FN --> DYNAMO
    GLUE --> S3_REPORTS & S3_INFRA
    SNOWFLAKE --> S3_ARCHIVE
```

---

## 6. IAM Roles — Categorized

```mermaid
graph TB
    subgraph IAM_ECS["🔐 ECS Task Roles (73 roles)"]
        direction TB
        ecs_auth["INTTRA2-ECS-PR-Auth-Task"]
        ecs_bk["INTTRA2-ECS-PR-BKAPI-Task"]
        ecs_bl["INTTRA2-ECS-PR-BL-Task"]
        ecs_booking_cs["INTTRA2-ECS-PR-Booking-CargoScreen-Task"]
        ecs_bk_inb["INTTRA2-ECS-PR-Booking-Inbound-Consumer-Task"]
        ecs_bridge["INTTRA2-ECS-PR-BookingBridge-Task"]
        ecs_dispatch["INTTRA2-ECS-PR-Dispatcher-Task"]
        ecs_distrib["INTTRA2-ECS-PR-Distributor-Task"]
        ecs_distrib_r["INTTRA2-ECS-PR-Distributor-Rest-Task"]
        ecs_email["INTTRA2-ECS-PR-EmailSender-Task"]
        ecs_error["INTTRA2-ECS-PR-ErrorProcessor-Task"]
        ecs_event["INTTRA2-ECS-PR-EventWriter-Task"]
        ecs_ingest["INTTRA2-ECS-PR-Ingestor-Task"]
        ecs_ingest_ce["INTTRA2-ECS-PR-Ingestor-CE-Task"]
        ecs_net["INTTRA2-ECS-PR-NetworkServices-Task"]
        ecs_more["... +58 more ECS task roles"]
    end

    subgraph IAM_LAMBDA["🔐 Lambda Execution Roles (35 roles)"]
        lam_auth_s3["INTTRA2-LAMBDA-PR-AUTH-S3-ARCHIVE"]
        lam_auth_ddb["INTTRA2-LAMBDA-PR-AUTH-DDB-STREAM"]
        lam_bk_cs["INTTRA2-LAMBDA-PR-BK-CARGOSCREEN"]
        lam_bk_ddb["INTTRA2-LAMBDA-PR-BK-DDB-STREAM"]
        lam_bk_s3["INTTRA2-LAMBDA-PR-BK-S3-ARCHIVE"]
        lam_bk_es["INTTRA2-LAMBDA-PR-BK-ES-DELETE"]
        lam_bk_search["INTTRA2-LAMBDA-PR-BK-SEARCH"]
        lam_bl_es["INTTRA2-LAMBDA-PR-BL-ES-STREAM"]
        lam_vis_email["INTTRA2-LAMBDA-PR-Visibility-Error-Email"]
        lam_vis_ob["INTTRA2-PR-Visibility-Outbound-Lambda"]
        lam_ses["INTTRA2-LAMBDA-PR-SES-Observability-Logger"]
        lam_more["... +24 more Lambda roles"]
    end

    subgraph IAM_GLUE["🔐 Glue ETL Roles (18 roles)"]
        glue_bk["INTTRA2-GLUE-PR-BK-CRAWLER-ROLE"]
        glue_bk_etl["INTTRA2-GLUE-PR-BK-ETL-JOB-ROLE"]
        glue_ebl["INTTRA2-GLUE-PR-EBL-CRAWLER-ROLE"]
        glue_si["INTTRA2-GLUE-PR-SI-CRAWLER-ROLE"]
        glue_tt["INTTRA2-GLUE-PR-TT-ETL-JOB-ROLE"]
        glue_os["INTTRA2-GLUE-PR-OS-ETL-JOB-ROLE"]
        glue_osng["INTTRA2-GLUE-PR-OSNG-CRAWLER-ROLE"]
        glue_more["... +11 more Glue roles"]
    end

    subgraph IAM_INFRA["🔐 Infrastructure Roles"]
        snow_bk["INTTRA2-Snowflake-S3-PR-BookingArchive-Role"]
        snow_ebl["INTTRA2-Snowflake-S3-PR-EBLDetailArchive-Role"]
        snow_si["INTTRA2-Snowflake-S3-PR-SIArchive-Role"]
        snow_tt["INTTRA2-Snowflake-S3-PR-TTArchive-Role"]
        snow_webbl["INTTRA2-Snowflake-S3-PR-WEBBLArchive-Role"]
        es_snap["INTTRA2-PR-ES-SNAPSHOTS"]
        cognito["INTTRA2-PR-CognitoAccessForAmazonES"]
        kibana["INTTRA2-PR-Kibana-Cognito-Role"]
        bounce["INTTRA2-PR-Bounce-Emails-*"]
        dphap["INTTRA2-PR-DPHAP"]
    end

    subgraph SERVICES["AWS Services"]
        svc_ecs["Amazon ECS"]
        svc_lambda["AWS Lambda"]
        svc_glue["AWS Glue"]
        svc_snowflake["Snowflake"]
    end

    IAM_ECS -->|"assumed by"| svc_ecs
    IAM_LAMBDA -->|"assumed by"| svc_lambda
    IAM_GLUE -->|"assumed by"| svc_glue
    IAM_INFRA -->|"assumed by"| svc_snowflake
```

---

## 7. CloudWatch Log Groups — Service Mapping

```mermaid
graph TB
    subgraph CW_ECS["📊 ECS Service Logs (25 log groups)"]
        lg_appway["inttra2-pr-lg-app-way"]
        lg_auth["inttra2-pr-lg-auth"]
        lg_bkapi["inttra2-pr-lg-bkapi"]
        lg_netsvc["inttra2-pr-lg-net-svc"]
        lg_osng["inttra2-pr-lg-osng"]
        lg_osng_aw["inttra2-pr-lg-osng-appway"]
        lg_osng_ldr["inttra2-pr-lg-osng-ldr"]
        lg_pi["inttra2-pr-lg-pi"]
        lg_ptui["inttra2-pr-lg-ptui"]
        lg_rates["inttra2-pr-lg-rates"]
        lg_rates_b["inttra2-pr-lg-rates-batch"]
        lg_ssr["inttra2-pr-lg-ssr-task"]
        lg_vis["inttra2-pr-lg-visibility"]
        lg_haproxy["inttra2-pr-lg-ha-proxy"]
        lg_haproxy_c["inttra2-pr-lg-ha-proxy-compliance"]
        lg_dp_hap["inttra2-pr-lg-dp-haproxy"]
        lg_evgm["inttra2-pr-lg-evgm-rpt"]
        lg_osng_tasks["inttra2-pr-lg-osng-start-*-task (4)"]
        lg_nlb["inttra2-pr-ptui-nlb"]
    end

    subgraph CW_LAMBDA["📊 Lambda Logs (36 log groups)"]
        subgraph CW_LAM_UNDERSCORE["_pr_ Lambda Logs (17)"]
            cwl_streams["/aws/lambda/inttra2_pr_lambda_*_stream (6)"]
            cwl_ct["/aws/lambda/inttra2_pr_lambda_booking_ContainerTracking* (4)"]
            cwl_bulk["/aws/lambda/inttra2_pr_lambda_booking_BulkContTracking* (1)"]
            cwl_dlq["/aws/lambda/handle-inttra2_pr_sqs_*_dlq-msg (4)"]
            cwl_ses["/aws/lambda/inttra2_pr_lambda_ses_observability_logger"]
            cwl_sns["sns/us-east-1/.../inttra2_pr_sns_inbound"]
        end
        subgraph CW_LAM_HYPHEN["-pr- Lambda Logs (19)"]
            cwl_auth_lam["/aws/lambda/inttra2-pr-lambda-auth-* (2)"]
            cwl_bk_lam["/aws/lambda/inttra2-pr-lambda-booking* (4)"]
            cwl_ov_lam["/aws/lambda/inttra2-pr-lambda-optionalvalidations-* (2)"]
            cwl_sub_lam["/aws/lambda/inttra2-pr-lambda-subscriptions-* (2)"]
            cwl_reg_lam["/aws/lambda/inttra2-pr-lambda-registrationdetail-* (1)"]
            cwl_vis_lam["/aws/lambda/inttra2-pr-lambda-visibility-* (4)"]
            cwl_os_lam["/aws/lambda/inttra2-pr-lambda-start-os-* (2)"]
        end
    end

    subgraph CW_INFRA["📊 Infrastructure Logs"]
        cwl_es["/aws/es/inttra2-pr-es-tx-tracker"]
        cwl_waf["/aws/kinesisfirehose/aws-waf-logs-pr-* (2)"]
    end

    subgraph SERVICES_CW["Services Emitting Logs"]
        ECS_ALL["ECS Services (60+)"]
        LAMBDA_ALL["Lambda Functions (30)"]
        ES_SVC["Elasticsearch"]
        WAF_SVC["WAF / Kinesis Firehose"]
    end

    ECS_ALL --> CW_ECS
    LAMBDA_ALL --> CW_LAMBDA
    ES_SVC --> cwl_es
    WAF_SVC --> cwl_waf
```

---

## 8. EventBridge Rules — Scheduled Triggers

```mermaid
graph LR
    subgraph EB_RULES["⏰ EventBridge Rules"]
        eb_vis_err["inttra2-pr-cron-visibility-error-email"]
        eb_vis_ob["inttra2-pr-cron-visibility-outbound-poller"]
        eb_vis_start["inttra2-pr-cron-visibility-pending-start"]
        eb_os_stg["inttra2-pr-lambda-start-os-staging-cwevent"]
        eb_glue_si["inttra-pr-gluecrawler-si-lambda"]
        eb_glue_tt["inttra-pr-gluecrawler-tt-lambda"]
        eb_glue_ebl["inttra2-pr-ebl-gluecrawler-lambda"]
        eb_glue_excl["inttra2-pr-glue-crawler-exclusions-lambda"]
    end

    subgraph TARGETS_EB["🎯 Lambda Targets"]
        t_vis_err["lambda-visibility-error-email"]
        t_vis_ob["lambda-visibility-outbound-poller"]
        t_vis_start["lambda-visibility-pending-start"]
        t_os_stg["lambda-start-os-staging"]
        t_glue["Glue Crawler Lambdas"]
    end

    eb_vis_err -->|"cron schedule"| t_vis_err
    eb_vis_ob -->|"cron schedule"| t_vis_ob
    eb_vis_start -->|"cron schedule"| t_vis_start
    eb_os_stg -->|"cron schedule"| t_os_stg
    eb_glue_si & eb_glue_tt & eb_glue_ebl & eb_glue_excl -->|"cron schedule"| t_glue

    t_vis_err -->|"sends"| SES["SES Email"]
    t_vis_ob -->|"polls"| DDB["DynamoDB"]
    t_vis_start -->|"triggers"| SQS["SQS ce_pending"]
    t_os_stg -->|"starts"| ECS_TASK["ECS OS-Staging Task"]
    t_glue -->|"starts"| GLUE_CRAWL["Glue Crawlers"]
```

---

## Component Explanations

### Load Balancers
| Load Balancer | Type | Scheme | Purpose |
|--------------|------|--------|---------|
| **ALB-PR-APPWAY-WS** | ALB | Internet-facing | Main entry point for AppianWay message processing services (EDI inbound/outbound, API calls from partners) |
| **alb-pr-ptui-ecs** | ALB | Internet-facing | Portal/UI services (PTUI web applications — booking, BL, SI, tracking, admin, reports) |
| **ALB-PR-PROXY** | ALB | Internal | Internal HAProxy reverse proxy routing traffic between internal services |
| **alb-pr-api-internal** | ALB | Internal | Internal API gateway for service-to-service calls (booking API, auth, network) |
| **nlb-prod-dp-haproxy** | NLB | Internet-facing | Data Pipeline HAProxy — high-throughput carrier data ingestion (EDI, XML) |
| **nlb-pr-biztalk** | NLB | Internal | BizTalk integration — on-premises BizTalk server connectivity for legacy EDI |
| **NLB-PTUI-PR-NJHQ-WS** | NLB | Internal | PTUI internal NLB for NJ headquarters web services |

### ECS Clusters
| Cluster | Service Domain | Key Responsibility |
|---------|---------------|-------------------|
| **ANEPRAPWY-001** | AppianWay (23 svcs) | Core message processing hub — ingestion, distribution, dispatching, platform integration, watermill publishing, booking bridge, visibility event processing |
| **ANEPRAPWY-002** | AppianWay Splitters | Message splitting — breaks large batched messages into individual units for parallel processing |
| **ANEPRBK-001** | Booking API | REST API for booking operations — create, update, cancel shipment bookings |
| **ANEPRAUTH-001** | Auth & Network | Authentication/authorization service + network/partner management service |
| **ANEPRCONTIVO-001/002/CE** | Contivo Transformation | EDI message transformation — converts between internal XML format and carrier-specific EDI formats (standard, ocean schedules, container events) |
| **ANEPROSNG-001/003** | Ocean Schedules NG | Next-gen ocean schedules — collectors fetch schedules from 13+ carriers (Maersk, MSC, CMA, etc.), port pair generation, staging |
| **ANEPRPI-001** | Platform Integration | Outbound platform integration — publishes status events to external systems |
| **ANEPRVIS-001/002** | Visibility | Container visibility — event matching, pending event management, outbound delivery, ITV/GPS tracking |
| **ANEPRWEBSVC-001** | Web Services (21 svcs) | All web-facing APIs — TxTracking, Registration, Rates, VAS, WebBL, BillOfLading, SI, OSNG, PTUI portal services |
| **ANEPRPROXY-001** | HAProxy | Reverse proxy + ComplianceLink proxy for routing and SSL termination |
| **ANEPRDPDE-001** | Data Pipeline | Data pipeline distribution engine — routes transformed data to downstream systems |
| **ANEPRDPHAP-001** | DP HAProxy | Data pipeline HAProxy — load balances carrier connections |

### DynamoDB Tables
| Table | Domain | Purpose |
|-------|--------|---------|
| `CargoVisibilitySubscription` | Visibility | Stores cargo visibility subscriptions — which customers are subscribed to tracking events for which containers/bookings |
| `controlnumber_sequence` | Booking | Auto-incrementing control number sequences for EDI interchange/group/transaction set numbers |
| `network_service_blacklisted_email` | Network | Email addresses blacklisted from receiving system notifications |
| `network_service_connections_auditTrail` | Network | Audit trail for partner connection changes (who connected/disconnected, when, approval status) |
| `network_service_message_register` | Network | Message routing registry — maps carrier SCAC codes to processing rules and delivery endpoints |
| `network_service_optionalvalidations` | Network | Configurable validation rules per carrier/customer — which optional EDI validations to enforce |
| `network_service_subscriptions` | Network | Service subscriptions — which customers are subscribed to which services (booking, tracking, schedules, etc.) |
| `os_realtime_cache` | Ocean Schedules | Cache for real-time ocean schedule lookups — avoids re-fetching from carriers for frequently requested routes |
| `schedules_pro_staging` | Ocean Schedules | Staging area for schedule data being processed — intermediate state before publishing to search index |
| `watermill_offset` | Shared | Watermill message processing offsets — tracks consumer group position for exactly-once processing semantics |

### Key Message Flows
1. **Inbound EDI Flow:** External Partner → NLB/ALB → Ingestor → SNS `sns_inbound` → SQS `sqs_transformer_inbound` → Transformer (ECS) → SNS `sns_event` → SQS fan-out → multiple consumers
2. **Booking Flow:** Booking API (REST) → SQS `sqs_bk_inbound` → BookingInboundConsumer → DynamoDB + Elasticsearch → BookingBridge → SQS → Dispatcher → Distributor → outbound delivery
3. **Visibility Flow:** Container events → SQS `sqs_ce_inbound` → VisibilityInboundConsumer → SQS `sqs_ce_validate` → validate → `sqs_ce_enrich` → enrich → `sqs_ce_match` → match → `sqs_ce_outbound` → outbound
4. **Ocean Schedules Flow:** EventBridge cron → Lambda starts OS-Collectors (per carrier) → carrier APIs → SQS `sqs_os_inbound` → OS-Inbound → staging → loader → outbound
5. **Archive Flow:** DynamoDB Streams → SNS `*_TableStreamTopic` → SQS `*-s3` → Lambda `*-S3ArchiveLambda` → S3 archive buckets → Snowflake (cross-account)

### Dead Letter Queue (DLQ) Strategy
Every SQS queue has a corresponding `_dlq` queue. Messages that fail processing after max retries land in the DLQ. Four Lambda functions (`handle-*_dlq-msg`) automatically process DLQ messages for critical queues:
- `bridgeob_pu_dlq` — failed booking bridge outbound messages
- `ce_match_dlq` — failed container event matching
- `ce_validate_dlq` — failed container event validation
- `pi_bl_es_dlq` — failed bill of lading Elasticsearch indexing

### Snowflake Integration
Five dedicated IAM roles (`INTTRA2-Snowflake-S3-PR-*-Role`) enable Snowflake to read from S3 archive buckets for analytics:
- Booking archives, EBL detail archives, SI archives, TT archives, WebBL archives
