# ION-14382 Booking AWS SDK v2 Upgrade — Branch Migration Summary

**Date**: 2026-03-27  
**Ticket**: ION-14382  
**Source branch**: `feature/ION-14382-bk3-aws-upgrade` (commit `6cdba47f53`)  
**Target branch**: `feature/ION-14382-bk3-aws-upgrade-2` (commit `74f36e7a71`)  
**Base**: `develop` at `abee9cc33d` (latest as of 2026-03-27)

## Why the Migration

The original feature branch (`feature/ION-14382-bk3-aws-upgrade`) diverged from `develop` by ~50 commits (PRs #926–#938). Jenkins CI was failing because:

- `develop` added 172 new lines to `OutboundServiceImplTest.java` (3 new test methods using `EmailSenderConfig`)
- The feature branch replaced `EmailSenderConfig` → `BookingEmailConfig` as part of the AWS upgrade
- Git auto-merged textually without conflict markers, but the result **would not compile** because the new tests from `develop` referenced the removed `EmailSenderConfig` class

## What Was Done

1. Updated local `develop` to latest `origin/develop` (`abee9cc33d`)
2. Created new branch `feature/ION-14382-bk3-aws-upgrade-2` from `develop`
3. Cherry-picked the single AWS upgrade commit (`6cdba47f53`)
4. Fixed 2 remaining `EmailSenderConfig` → `BookingEmailConfig` references in `OutboundServiceImplTest.java` (lines 309, 393) that the auto-merge left incorrect
5. Amended commit with correct message: `ION-14382 bk3 aws upgrade changes`

## Conflict Resolution

5 files were modified on both branches. Resolution:

| File | Develop Change | Feature Change | Resolution |
|------|---------------|----------------|------------|
| `OutboundServiceImplTest.java` | +172 lines (3 new test methods) | `EmailSenderConfig` → `BookingEmailConfig` | Auto-merged + manual fix of 2 stale references |
| `OutboundServiceImpl.java` | +3 lines (supplementation logic) | AWS SDK imports/API changes | Auto-merged cleanly |
| `EnrichedAttributes.java` | 2 ins/2 del | DynamoDB annotation changes | Auto-merged cleanly |
| `ConfirmPendingEmailVariablesConverterTest.java` | 4 ins/4 del | Email config class change | Auto-merged cleanly |
| `RequestAmendEmailVariablesConverterTest.java` | 4 ins/4 del | Email config class change | Auto-merged cleanly |

## Verification Results

| Check | Result |
|-------|--------|
| Compilation (`mvn compile -pl booking -am`) | ✅ Zero errors |
| Unit tests (Surefire) | ✅ 1837 run, 0 failures, 0 errors, 1 skipped |
| Integration tests (Failsafe — non-IT) | ✅ 931 run, 0 failures, 0 errors, 9 skipped |
| Integration tests (Failsafe — DynamoDB IT) | ✅ 138 run, 0 failures, 0 errors |
| Integration tests (Failsafe — full IT suite) | ✅ 149 run, 0 failures, 0 errors |
| Application startup | ✅ All modules initialized, all endpoints registered |
| **Total tests** | **2768+ run, 0 failures, 0 errors** |

## Change Scope (223 files, all in booking module)

### Modified (179 files)
- **Build/Config**: `pom.xml`, `build.sh`, `BookingApplicationInjector`, `BookingApplicationModule`, `BookingConfig`, `ElasticsearchConfig`
- **DynamoDB/DAO**: `BookingDetailDao`, `SpotRatesDao`, `SpotRatesToInttraRefDao`, all type converters, `RapidReservationDao`, `TemplateDao`, `TemplateSummaryDao`, `SequenceIdDao`, `UniqueIdDao`
- **Model classes**: `BookingDetail`, `SpotRatesDetail`, `SpotRatesToInttraRefDetail`, `RapidReservation`, `Condition`, `Range`, `Template`, `TemplateSummary`, `SequenceId`, `UniqueId`, 40+ Common/INTTRA model artifacts
- **Messaging**: `SQSListener`, `SQSClient`, `SNSClient`, `S3WorkspaceService`, `WorkspaceService`
- **Outbound/Email**: `OutboundEmailSender`, 4 email variable converters, `EnrichedAttributes`, `MultiVersionAttributes`, `OutboundServiceImpl`, `OutboundEmailService`
- **Lambda**: `HandlerSupport`, `IndexerHandler`, `S3ArchiveHandler`
- **Elasticsearch**: `CreateIndex`, `DeleteIndex`, `Indexer`, `RebuildIndex`
- **Inbound**: `BookingProcessorTask`, `ConfirmPendingMessage`, `DeclineMessage`, `DeclineReplaceMessage`, confirmation artifacts
- **Tests**: ~60 modified test files across all areas

### Added (37 files)
- **New Guice modules**: `BookingDynamoModule`, `BookingEmailConfig`, `BookingEmailSenderModule`, `BookingMessagingModule`
- **New converters**: `ContractAttributeConverter`, `AuditAttributeConverter`, `ConditionListAttributeConverter`, `EnrichedAttributesConverter`, `LegacyMapConverter`, `MetaDataConverter`, `RangeAttributeConverter`, `SpotRatesAttributeConverter`
- **New classes**: `BookingDynamoDbAdminCommand`, `DBRecordNotFoundException`, `FlexibleDateDeserializer`
- **New integration tests (9)**: `SpotRatesDaoIT`, `SpotRatesToInttraRefDaoIT`, `BookingDetailDaoIT`, `BookingDynamoDbAdminCommandIT`, `RapidReservationDaoIT`, `TemplateDaoIT`, `TemplateSummaryDaoIT`, `SequenceIdDaoIT`, `UniqueIdDaoIT`
- **New unit tests (12)**: `SQSClientTest`, `BookingMessagingModuleTest`, `ContractAttributeConverterTest`, 7 converter tests, `IndexerJettyFreeTest`, `FlexibleDateDeserializerTest`

### Deleted (7 files)
- Legacy DynamoDB admin classes: `CreateTables`, `DeleteTables`, `DynamoSupport`, `S3Archive`
- Their tests: `CreateTablesTest`, `DeleteTablesTest`, `S3ArchiveTest`

## Git History

```
74f36e7a71 (HEAD -> feature/ION-14382-bk3-aws-upgrade-2) ION-14382 bk3 aws upgrade changes
abee9cc33d (origin/develop, develop) Pull request #938: Feature/ION-15057
...full develop history intact...
```

Single clean commit on top of latest `develop`. All develop commits preserved in history.

## Complete File List in Commit (223 files)

**Commit**: `74f36e7a71` on branch `feature/ION-14382-bk3-aws-upgrade-2`  
**Legend**: A = Added, M = Modified, D = Deleted

### Added Files (37)

```
A  booking/docs/DESIGN-AWS2x.md
A  booking/src/main/java/com/inttra/mercury/booking/config/BookingDynamoModule.java
A  booking/src/main/java/com/inttra/mercury/booking/config/BookingEmailConfig.java
A  booking/src/main/java/com/inttra/mercury/booking/config/BookingEmailSenderModule.java
A  booking/src/main/java/com/inttra/mercury/booking/config/BookingMessagingModule.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/BookingDynamoDbAdminCommand.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/ContractAttributeConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/ConditionListAttributeConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/RangeAttributeConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/SpotRatesAttributeConverter.java
A  booking/src/main/java/com/inttra/mercury/booking/exceptions/DBRecordNotFoundException.java
A  booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java
A  booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/common/messaging/SQSClientTest.java
A  booking/src/test/java/com/inttra/mercury/booking/config/BookingMessagingModuleTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/BookingDynamoDbAdminCommandIT.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/ContractAttributeConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/ConditionListAttributeConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/RangeAttributeConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/SpotRatesAttributeConverterTest.java
A  booking/src/test/java/com/inttra/mercury/booking/elasticsearch/IndexerJettyFreeTest.java
A  booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java
A  booking/src/test/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/util/SequenceIdDaoIT.java
A  booking/src/test/java/com/inttra/mercury/booking/util/UniqueIdDaoIT.java
```

### Deleted Files (7)

```
D  booking/src/main/java/com/inttra/mercury/booking/dynamodb/CreateTables.java
D  booking/src/main/java/com/inttra/mercury/booking/dynamodb/DeleteTables.java
D  booking/src/main/java/com/inttra/mercury/booking/dynamodb/DynamoSupport.java
D  booking/src/main/java/com/inttra/mercury/booking/dynamodb/S3Archive.java
D  booking/src/test/java/com/inttra/mercury/booking/dynamodb/CreateTablesTest.java
D  booking/src/test/java/com/inttra/mercury/booking/dynamodb/DeleteTablesTest.java
D  booking/src/test/java/com/inttra/mercury/booking/dynamodb/S3ArchiveTest.java
```

### Modified Files (179)

#### Build & Config
```
M  booking/build.sh
M  booking/pom.xml
M  booking/src/main/java/com/inttra/mercury/booking/BookingApplication.java
M  booking/src/main/java/com/inttra/mercury/booking/config/BookingApplicationInjector.java
M  booking/src/main/java/com/inttra/mercury/booking/config/BookingApplicationModule.java
M  booking/src/main/java/com/inttra/mercury/booking/config/BookingConfig.java
M  booking/src/main/java/com/inttra/mercury/booking/config/ElasticsearchConfig.java
```

#### DynamoDB & Data Layer
```
M  booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDao.java
M  booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDao.java
M  booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/model/canonical/SpotRatesDetail.java
M  booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/model/canonical/SpotRatesToInttraRefDetail.java
M  booking/src/main/java/com/inttra/mercury/booking/dao/BookingDetailDao.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/BookingStateConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/ContractTypeConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/ListOfChargeTypeConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/LocalDateTimeTypeConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/QuantityTypeConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/dynamodb/SpotRatesConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/Condition.java
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/Range.java
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/RapidReservation.java
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDao.java
M  booking/src/main/java/com/inttra/mercury/booking/template/model/Template.java
M  booking/src/main/java/com/inttra/mercury/booking/template/model/TemplateSummary.java
M  booking/src/main/java/com/inttra/mercury/booking/template/persistence/TemplateDao.java
M  booking/src/main/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDao.java
M  booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java
M  booking/src/main/java/com/inttra/mercury/booking/util/SequenceId.java
M  booking/src/main/java/com/inttra/mercury/booking/util/SequenceIdDao.java
M  booking/src/main/java/com/inttra/mercury/booking/util/SequenceIdProvider.java
M  booking/src/main/java/com/inttra/mercury/booking/util/TaskIdGenerator.java
M  booking/src/main/java/com/inttra/mercury/booking/util/UniqueId.java
M  booking/src/main/java/com/inttra/mercury/booking/util/UniqueIdDao.java
```

#### Messaging & S3
```
M  booking/src/main/java/com/inttra/mercury/booking/common/listener/SQSListener.java
M  booking/src/main/java/com/inttra/mercury/booking/common/messaging/SNSClient.java
M  booking/src/main/java/com/inttra/mercury/booking/common/messaging/SQSClient.java
M  booking/src/main/java/com/inttra/mercury/booking/common/s3/S3WorkspaceService.java
M  booking/src/main/java/com/inttra/mercury/booking/common/s3/WorkspaceService.java
```

#### Outbound / Email
```
M  booking/src/main/java/com/inttra/mercury/booking/outbound/email/OutboundEmailSender.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/CancelEmailVariablesConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/ConfirmPendingEmailVariablesConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/DeclineReplaceEmailVariablesConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/RequestAmendEmailVariablesConverter.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/model/EnrichedAttributes.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/model/MultiVersionAttributes.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/model/NotificationCollector.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundEmailService.java
M  booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImpl.java
```

#### Lambda & Elasticsearch
```
M  booking/src/main/java/com/inttra/mercury/booking/elasticsearch/CreateIndex.java
M  booking/src/main/java/com/inttra/mercury/booking/elasticsearch/DeleteIndex.java
M  booking/src/main/java/com/inttra/mercury/booking/elasticsearch/Indexer.java
M  booking/src/main/java/com/inttra/mercury/booking/elasticsearch/RebuildIndex.java
M  booking/src/main/java/com/inttra/mercury/booking/externalwrapper/exception/UnrecoverableAWSException.java
M  booking/src/main/java/com/inttra/mercury/booking/lambda/HandlerSupport.java
M  booking/src/main/java/com/inttra/mercury/booking/lambda/IndexerHandler.java
M  booking/src/main/java/com/inttra/mercury/booking/lambda/S3ArchiveHandler.java
```

#### Inbound Processing
```
M  booking/src/main/java/com/inttra/mercury/booking/inbound/BookingProcessorTask.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/ConfirmPendingMessage.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCCharge.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipment.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipmentHaulage.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipmentIdentifier.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulageDate.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulageParty.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulagePoint.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCReference.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/Split.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/decline/DeclineMessage.java
M  booking/src/main/java/com/inttra/mercury/booking/inbound/decline/DeclineReplaceMessage.java
```

#### Model Classes — Common Artifacts
```
M  booking/src/main/java/com/inttra/mercury/booking/model/BookingDetail.java
M  booking/src/main/java/com/inttra/mercury/booking/model/BookingRequestContract.java
M  booking/src/main/java/com/inttra/mercury/booking/model/CancelMessage.java
M  booking/src/main/java/com/inttra/mercury/booking/model/DateToEpochSecond.java
M  booking/src/main/java/com/inttra/mercury/booking/model/SOBookingRequestContract.java
M  booking/src/main/java/com/inttra/mercury/booking/model/SOCancelContract.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/AcidConcentration.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Address.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/AirFlow.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Charge.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Contact.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Country.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/DangerousGoods.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Date.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Dimension.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Equipment.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/EquipmentHaulage.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HaulageDate.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HaulagePoint.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HumidityPercentage.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Leg.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/NetworkLocation.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/NetworkParticipant.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/RadioactivityMeasure.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/ReeferHandling.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Temperature.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionParty.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionReference.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/ValueAddedServiceOffer.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Volume.java
M  booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Weight.java
```

#### Model Classes — INTTRA Common Artifacts
```
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Atmosphere.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/BaseParty.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/CargoLine.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/ChargeParty.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Document.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/EquipmentReference.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/EquipmentSizeCode.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/GoodsReference.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Location.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/LocationAdditionalInfo.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/LocationDate.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/ManifestFiler.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/MarksAndNumber.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/OutOfGaugeDetails.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/OuterPackage.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/PackageDetails.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/PartyIdentifier.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SimpleParty.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SpecialServices.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SplitGoodsDetails.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SplitHazardousGoodsDetails.java
M  booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/TransportLocation.java
```

#### Model Classes — Request Artifacts
```
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BREquipment.java
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BREquipmentHaulage.java
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulageDate.java
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulageParty.java
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulagePoint.java
M  booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRReference.java
```

#### Network Services Models
```
M  booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/Country.java
M  booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/CountryIdentifier.java
M  booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/Geography.java
M  booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java
M  booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java
```

#### Service & Resource Layer
```
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/resource/RapidReservationResource.java
M  booking/src/main/java/com/inttra/mercury/booking/rapidreservation/service/RapidReservationService.java
M  booking/src/main/java/com/inttra/mercury/booking/resources/CustomerBookingResource.java
M  booking/src/main/java/com/inttra/mercury/booking/service/BookingService.java
M  booking/src/main/java/com/inttra/mercury/booking/template/service/TemplateService.java
M  booking/src/main/java/com/inttra/mercury/booking/template/TemplateResource.java
```

#### Test Files — Unit Tests
```
M  booking/src/test/java/com/inttra/mercury/booking/AbstractIntegrationTest.java
M  booking/src/test/java/com/inttra/mercury/booking/NetworkServiceIntegrationTest.java
M  booking/src/test/java/com/inttra/mercury/booking/ServerSupport.java
M  booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDaoTest.java
M  booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDaoTest.java
M  booking/src/test/java/com/inttra/mercury/booking/common/listener/SQSListenerTest.java
M  booking/src/test/java/com/inttra/mercury/booking/common/messaging/SNSClientTest.java
M  booking/src/test/java/com/inttra/mercury/booking/common/s3/S3WorkspaceServiceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/config/BookingConfigTest.java
M  booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoQueryTest.java
M  booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoTest.java
M  booking/src/test/java/com/inttra/mercury/booking/elasticsearch/CreateIndexTest.java
M  booking/src/test/java/com/inttra/mercury/booking/elasticsearch/DeleteIndexTest.java
M  booking/src/test/java/com/inttra/mercury/booking/elasticsearch/IndexerUnitTest.java
M  booking/src/test/java/com/inttra/mercury/booking/flow/FlowStep.java
M  booking/src/test/java/com/inttra/mercury/booking/flow/FlowTestModule.java
M  booking/src/test/java/com/inttra/mercury/booking/inbound/BookingProcessorTaskIntegrationTest.java
M  booking/src/test/java/com/inttra/mercury/booking/inbound/BookingProcessorTaskTest.java
M  booking/src/test/java/com/inttra/mercury/booking/lambda/HandlerSupportTest.java
M  booking/src/test/java/com/inttra/mercury/booking/lambda/S3ArchiveHandlerTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/email/LegalTermsEmailTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/email/OutBoundEmailSenderTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/email/converter/ConfirmPendingEmailVariablesConverterTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/email/converter/RequestAmendEmailVariablesConverterTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/resources/OutboundResourceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceAddnlTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImplTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTestBase.java
M  booking/src/test/java/com/inttra/mercury/booking/outbound/services/TransformerServiceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDaoTest.java
M  booking/src/test/java/com/inttra/mercury/booking/rapidreservation/resource/RapidReservationResourceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/rapidreservation/service/RapidReservationServiceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/resources/CustomerBookingResourceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/service/BookingServiceIntegrationTest.java
M  booking/src/test/java/com/inttra/mercury/booking/service/BookingServiceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/template/TemplateResourceTest.java
M  booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDaoTest.java
```
