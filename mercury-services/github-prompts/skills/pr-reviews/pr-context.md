# PR Context – Booking Module

- The PR is for booking module changes for AWS upgrade to use the cloud-sdk libraries.
- No existing functionality is changed as part of this PR. All AWS SDK v1 code is refactored to use the cloud-sdk libraries. There are no new features or user stories implemented as part of this PR.
- The cloud-sdk libraries are available in the mercury-services-commons repository and are consumed as dependencies in the booking module. 
- The cloud-sdk libraries are already used in some other modules like network, auth, booking-bridge, registration etc. 
- The AWS services used in the booking module include S3, DynamoDB, SQS, SNS, SES. All interactions with these services are refactored to use the cloud-sdk libraries.
- The feature branch is feature/ION-14382-bk3-aws-upgrade
- The PR link is <https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/878/overview>
You can open a new browser window and navigate to the PR link to review the code changes or you can check git log and diffs locally.
- the commit id is <https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/878/commits/5e675d639b13e8d71cd88be67e7be4b42bc3327d>

## the files changed in this PR include

booking/docs/DESIGN-AWS2x.md
booking/pom.xml
booking/src/main/java/com/inttra/mercury/booking/BookingApplication.java
booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDao.java
booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDao.java
booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/model/canonical/SpotRatesDetail.java
booking/src/main/java/com/inttra/mercury/booking/carrierspotrates/model/canonical/SpotRatesToInttraRefDetail.java
booking/src/main/java/com/inttra/mercury/booking/common/listener/SQSListener.java
booking/src/main/java/com/inttra/mercury/booking/common/messaging/SNSClient.java
booking/src/main/java/com/inttra/mercury/booking/common/messaging/SQSClient.java
booking/src/main/java/com/inttra/mercury/booking/common/s3/S3WorkspaceService.java
booking/src/main/java/com/inttra/mercury/booking/common/s3/WorkspaceService.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingApplicationInjector.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingApplicationModule.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingConfig.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingDynamoModule.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingEmailConfig.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingEmailSenderModule.java
booking/src/main/java/com/inttra/mercury/booking/config/BookingMessagingModule.java
booking/src/main/java/com/inttra/mercury/booking/config/ElasticsearchConfig.java
booking/src/main/java/com/inttra/mercury/booking/dao/BookingDetailDao.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/BookingDynamoDbAdminCommand.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/BookingStateConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/ContractAttributeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/ContractTypeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/CreateTables.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/DeleteTables.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/DynamoSupport.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/ListOfChargeTypeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/LocalDateTimeTypeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/QuantityTypeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/S3Archive.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/SpotRatesConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/ConditionListAttributeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/RangeAttributeConverter.java
booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/SpotRatesAttributeConverter.java
booking/src/main/java/com/inttra/mercury/booking/elasticsearch/CreateIndex.java
booking/src/main/java/com/inttra/mercury/booking/elasticsearch/DeleteIndex.java
booking/src/main/java/com/inttra/mercury/booking/elasticsearch/RebuildIndex.java
booking/src/main/java/com/inttra/mercury/booking/exceptions/DBRecordNotFoundException.java
booking/src/main/java/com/inttra/mercury/booking/externalwrapper/exception/UnrecoverableAWSException.java
booking/src/main/java/com/inttra/mercury/booking/inbound/BookingProcessorTask.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/ConfirmPendingMessage.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCCharge.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipment.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipmentHaulage.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCEquipmentIdentifier.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulageDate.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulageParty.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCHaulagePoint.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/BCReference.java
booking/src/main/java/com/inttra/mercury/booking/inbound/confirmation/artifacts/Split.java
booking/src/main/java/com/inttra/mercury/booking/inbound/decline/DeclineMessage.java
booking/src/main/java/com/inttra/mercury/booking/inbound/decline/DeclineReplaceMessage.java
booking/src/main/java/com/inttra/mercury/booking/lambda/HandlerSupport.java
booking/src/main/java/com/inttra/mercury/booking/lambda/IndexerHandler.java
booking/src/main/java/com/inttra/mercury/booking/lambda/S3ArchiveHandler.java
booking/src/main/java/com/inttra/mercury/booking/model/BookingDetail.java
booking/src/main/java/com/inttra/mercury/booking/model/BookingRequestContract.java
booking/src/main/java/com/inttra/mercury/booking/model/CancelMessage.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/AcidConcentration.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Address.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/AirFlow.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Charge.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Contact.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Country.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/DangerousGoods.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Date.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Dimension.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Equipment.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/EquipmentHaulage.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HaulageDate.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HaulagePoint.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/HumidityPercentage.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Leg.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/NetworkLocation.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/NetworkParticipant.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/RadioactivityMeasure.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/ReeferHandling.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Temperature.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionParty.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionReference.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/ValueAddedServiceOffer.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Volume.java
booking/src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/Weight.java
booking/src/main/java/com/inttra/mercury/booking/model/DateToEpochSecond.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Atmosphere.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/BaseParty.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/CargoLine.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/ChargeParty.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Document.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/EquipmentReference.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/EquipmentSizeCode.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/GoodsReference.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/Location.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/LocationAdditionalInfo.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/LocationDate.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/ManifestFiler.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/MarksAndNumber.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/OutOfGaugeDetails.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/OuterPackage.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/PackageDetails.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/PartyIdentifier.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SimpleParty.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SpecialServices.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SplitGoodsDetails.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/SplitHazardousGoodsDetails.java
booking/src/main/java/com/inttra/mercury/booking/model/INTTRACommon/Artifacts/TransportLocation.java
booking/src/main/java/com/inttra/mercury/booking/model/SOBookingRequestContract.java
booking/src/main/java/com/inttra/mercury/booking/model/SOCancelContract.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BREquipment.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BREquipmentHaulage.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulageDate.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulageParty.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRHaulagePoint.java
booking/src/main/java/com/inttra/mercury/booking/model/request/artifacts/BRReference.java
booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/Country.java
booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/CountryIdentifier.java
booking/src/main/java/com/inttra/mercury/booking/networkservices/geography/model/Geography.java
booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java
booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java
booking/src/main/java/com/inttra/mercury/booking/outbound/email/OutboundEmailSender.java
booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/CancelEmailVariablesConverter.java
booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/ConfirmPendingEmailVariablesConverter.java
booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/DeclineReplaceEmailVariablesConverter.java
booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/RequestAmendEmailVariablesConverter.java
booking/src/main/java/com/inttra/mercury/booking/outbound/model/EnrichedAttributes.java
booking/src/main/java/com/inttra/mercury/booking/outbound/model/MultiVersionAttributes.java
booking/src/main/java/com/inttra/mercury/booking/outbound/model/NotificationCollector.java
booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundEmailService.java
booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImpl.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/Condition.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/Range.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/model/RapidReservation.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDao.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/resource/RapidReservationResource.java
booking/src/main/java/com/inttra/mercury/booking/rapidreservation/service/RapidReservationService.java
booking/src/main/java/com/inttra/mercury/booking/resources/CustomerBookingResource.java
booking/src/main/java/com/inttra/mercury/booking/service/BookingService.java
booking/src/main/java/com/inttra/mercury/booking/template/TemplateResource.java
booking/src/main/java/com/inttra/mercury/booking/template/model/Template.java
booking/src/main/java/com/inttra/mercury/booking/template/model/TemplateSummary.java
booking/src/main/java/com/inttra/mercury/booking/template/persistence/TemplateDao.java
booking/src/main/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDao.java
booking/src/main/java/com/inttra/mercury/booking/template/service/TemplateService.java
booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java
booking/src/main/java/com/inttra/mercury/booking/util/SequenceId.java
booking/src/main/java/com/inttra/mercury/booking/util/SequenceIdDao.java
booking/src/main/java/com/inttra/mercury/booking/util/SequenceIdProvider.java
booking/src/main/java/com/inttra/mercury/booking/util/TaskIdGenerator.java
booking/src/main/java/com/inttra/mercury/booking/util/UniqueId.java
booking/src/main/java/com/inttra/mercury/booking/util/UniqueIdDao.java
booking/src/test/java/com/inttra/mercury/booking/AbstractIntegrationTest.java
booking/src/test/java/com/inttra/mercury/booking/NetworkServiceIntegrationTest.java
booking/src/test/java/com/inttra/mercury/booking/ServerSupport.java
booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesDaoTest.java
booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/carrierspotrates/dao/SpotRatesToInttraRefDaoTest.java
booking/src/test/java/com/inttra/mercury/booking/common/listener/SQSListenerTest.java
booking/src/test/java/com/inttra/mercury/booking/common/messaging/SNSClientTest.java
booking/src/test/java/com/inttra/mercury/booking/common/messaging/SQSClientTest.java
booking/src/test/java/com/inttra/mercury/booking/common/s3/S3WorkspaceServiceTest.java
booking/src/test/java/com/inttra/mercury/booking/config/BookingConfigTest.java
booking/src/test/java/com/inttra/mercury/booking/config/BookingMessagingModuleTest.java
booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoQueryTest.java
booking/src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/BookingDynamoDbAdminCommandIT.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/ContractAttributeConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/CreateTablesTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/DeleteTablesTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/S3ArchiveTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/ConditionListAttributeConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/RangeAttributeConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/SpotRatesAttributeConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/elasticsearch/CreateIndexTest.java
booking/src/test/java/com/inttra/mercury/booking/elasticsearch/DeleteIndexTest.java
booking/src/test/java/com/inttra/mercury/booking/flow/FlowStep.java
booking/src/test/java/com/inttra/mercury/booking/flow/FlowTestModule.java
booking/src/test/java/com/inttra/mercury/booking/inbound/BookingProcessorTaskIntegrationTest.java
booking/src/test/java/com/inttra/mercury/booking/inbound/BookingProcessorTaskTest.java
booking/src/test/java/com/inttra/mercury/booking/lambda/HandlerSupportTest.java
booking/src/test/java/com/inttra/mercury/booking/lambda/S3ArchiveHandlerTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/email/LegalTermsEmailTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/email/OutBoundEmailSenderTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/email/converter/RequestAmendEmailVariablesConverterTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/resources/OutboundResourceTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceAddnlTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImplTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTest.java
booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTestBase.java
booking/src/test/java/com/inttra/mercury/booking/outbound/services/TransformerServiceTest.java
booking/src/test/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/rapidreservation/persistence/RapidReservationDaoTest.java
booking/src/test/java/com/inttra/mercury/booking/rapidreservation/resource/RapidReservationResourceTest.java
booking/src/test/java/com/inttra/mercury/booking/rapidreservation/service/RapidReservationServiceTest.java
booking/src/test/java/com/inttra/mercury/booking/resources/CustomerBookingResourceTest.java
booking/src/test/java/com/inttra/mercury/booking/service/BookingServiceIntegrationTest.java
booking/src/test/java/com/inttra/mercury/booking/service/BookingServiceTest.java
booking/src/test/java/com/inttra/mercury/booking/template/TemplateResourceTest.java
booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/template/persistence/TemplateSummaryDaoTest.java
booking/src/test/java/com/inttra/mercury/booking/util/SequenceIdDaoIT.java
booking/src/test/java/com/inttra/mercury/booking/util/UniqueIdDaoIT.java

## Complete diff for the commit in this PR

- please load the file named "full-diff.patch" in this folder to see the complete diff for the commit in this PR. This will help you review the code changes in a more efficient way.

- refer to this file for the code differences. This is made readily available to you, so that you can easily review the code changes without having to load the entire diff in memory or navigate through multiple files.

- come back to this file often to check the context and details of the changes to address any review comments or questions you may have about the code changes in this PR.

## Relevant git commands you may want to use to review the code changes in this PR

- git --no-pager show --pretty="" --name-only 5e675d639b13e8d71cd88be67e7be4b42bc3327d

## Commit and other details for this PR

- commit 5e675d639b13e8d71cd88be67e7be4b42bc3327d 
- (HEAD -> feature/ION-14382-bk3-aws-upgrade, origin/feature/ION-14382-bk3-aws-upgrade)

