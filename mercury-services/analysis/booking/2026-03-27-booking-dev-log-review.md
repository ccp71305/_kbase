# Booking-dev ECS Task Log Review

- Date: 2026-03-27
- ECS task ARN: `arn:aws:ecs:us-east-1:081020446316:task/ANEINWEBSVC-001/aac68eede1d644afa3e0052b729919bd`
- Log group: `inttra-int-lg-bkapi`
- Log stream: `Booking-latest-dev/Booking-dev-Container/aac68eede1d644afa3e0052b729919bd`

## Initial log prompts

- 1) Published message to topic
- 2) Email processing done for workflowId
- 3) Watermill OB sent for workflowId
- 4) Emails via subscription processed for workflowId
- 5) Watermill metadata sent to sqs
- 6) Uploaded watermill payload to bucket inttra-int-workspace
- 7) EDI/SQS OB sent for workflowId
- 8) transformer Uploaded to bucket
- 9) Uploading object to s3:
- 10) Number of coded parties
- 11) Logs from com.inttra.mercury.filters.MercuryRequestLoggingFilter (request URI only, excluding /booking/services/ping)
- 12) Creating booking in state
- 13) Created new booking
- 14) Booking life cycle started
- 15) The following paths were found for the configured resources
- 16) Listener com.inttra.mercury.booking.common.listener.SQSListener starting
- 17) Starting InttraServer
- 18) Creating TemplateSummary composite-key repository for table
- 19) Creating Template composite-key repository for table
- 20) Creating SpotRatesToInttraRefDetail partition-key repository for table
- 21) Creating SpotRatesDetail partition-key repository for table
- 22) Creating RapidReservation composite-key repository for table
- 23) Creating SequenceId partition-key repository for table
- 24) Creating UniqueId partition-key repository for table
- 25) Creating BookingDetail composite-key repository for table
- 26) SNS NotificationService created successfully for topic
- 27) Creating SNS NotificationService using cloud-sdk-aws factory
- 28) Creating Booking EmailService with templates list
- 29) Creating SES client with default configuration and List of template files
- 30) S3 StorageClient created successfully
- 31) Resolved AWS credentials using provider
- 32) Creating S3 StorageClient using cloud-sdk-aws factory
- 33) SQS MessagingClient created successfully
- 34) Creating SQS MessagingClient using cloud-sdk-aws factory
- 35) Resolved AWS region from DefaultAwsRegionProviderChain
- 36) Using DefaultCredentialsProvider for DynamoDbClientConfig
- 37) Created client with endpoint

## Startup assessment

Application startup was **OK**. The task reached normal startup milestones: OpenSearch/Jest client creation, DynamoDB repository creation, SQS/SNS/S3/SES client initialization, resource registration, listener startup, and `Booking life cycle started`. No startup failure was found in this task stream.

## Summary by requested prompt

### 1) Published message to topic

- Count: `14`
- Detail lines:
  - INFO  [dw-30 - POST /booking/request] [2026-03-27 21:06:31.900] User: 100524 COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:31.927]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:32.052]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:32.368]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:33.094]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:33.202]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [outbound] [2026-03-27 21:06:34.248]   com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:42.918] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:42.937] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.138] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.508] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.526] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.654] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.670] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.notification.impl.SnsService: Published message to topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event
10.11.12.240 - - [27/Mar/2026:21:06:43 +0000] "POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100 HTTP/1.1" 200 4 "-" "Jersey/3.1.10 (HttpUrlConnection 17.0.18)" 862


### 2) Email processing done for workflowId

- Count: `3`
- Detail lines:
  - INFO  [outbound] [2026-03-27 21:06:33.075]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for subscription 9925786a-53c9-4c51-b70e-c8dc6870d373 

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.478] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for subscription 25f045fa-6d0d-45ef-b927-7525c19d2a2c 

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.635] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for subscription e3ae9efb-f215-4090-8237-27daee696ec9 


### 3) Watermill OB sent for workflowId

- Count: `1`
- Detail lines:
  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.634] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Watermill OB sent for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 and subscription e3ae9efb-f215-4090-8237-27daee696ec9


### 4) Emails via subscription processed for workflowId

- Count: `3`
- Detail lines:
  - INFO  [outbound] [2026-03-27 21:06:33.075]   com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for inttra company 1000 : []

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.478] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for inttra company -100 : []

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.635] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for inttra company -100 : []


### 5) Watermill metadata sent to sqs

- Count: `1`
- Detail lines:
  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.634] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.WatermillService: Watermill metadata sent to sqs https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_watermill_bk for workflowId : 331e0700-4066-4add-96c0-816a1ab31fb3


### 6) Uploaded watermill payload to bucket inttra-int-workspace

- Count: `0`

### 7) EDI/SQS OB sent for workflowId

- Count: `1`
- Detail lines:
  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.477] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: EDI/SQS OB sent for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 and subscription 25f045fa-6d0d-45ef-b927-7525c19d2a2c


### 8) transformer Uploaded to bucket

- Count: `1`
- Detail lines:
  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.377] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.TransformerService: transformer Uploaded to bucket: inttra-int-workspace , fileKey: 331e0700-4066-4add-96c0-816a1ab31fb3/450fe56d-6f33-46de-965b-4ff95850e418for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3


### 9) Uploading object to s3:

- Count: `2`
- Detail lines:
  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.149] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.storage.impl.S3StorageClient: Uploading object to S3: bucket='inttra-int-workspace', key='331e0700-4066-4add-96c0-816a1ab31fb3/450fe56d-6f33-46de-965b-4ff95850e418'

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.549] Client: booking_app COMPANY: 1000 com.inttra.mercury.cloudsdk.storage.impl.S3StorageClient: Uploading object to S3: bucket='inttra-int-workspace', key='watermill_331e0700-4066-4add-96c0-816a1ab31fb3/654545b1-9bcf-4d27-a2f5-d6012005a01a'


### 10) Number of coded parties

- Count: `3`
- Detail lines:
  - INFO  [outbound] [2026-03-27 21:06:31.929]   com.inttra.mercury.booking.model.Booking: Number of coded parties is 3 across all booking versions for booking id = 76c9b33cbf8d4499b2b88e66b8496224, sequence number = m_1774645591583_REQUEST_2011967001 and InttraReference number = 2011967001

  - INFO  [outbound] [2026-03-27 21:06:32.223]   com.inttra.mercury.booking.model.Booking: Number of coded parties is 3 across all booking versions for booking id = 76c9b33cbf8d4499b2b88e66b8496224, sequence number = m_1774645591583_REQUEST_2011967001 and InttraReference number = 2011967001

  - INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.117] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.model.Booking: Number of coded parties is 3 across all booking versions for booking id = 76c9b33cbf8d4499b2b88e66b8496224, sequence number = m_1774645591583_REQUEST_2011967001 and InttraReference number = 2011967001


### 11) Logs from com.inttra.mercury.filters.MercuryRequestLoggingFilter (request URI only, excluding /booking/services/ping)

- Count: `7`
- URIs:
  - `/"`
  - `/booking/2011967001`
  - `/booking/outbound/2011967001?versionnumber=`
  - `/booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100`
  - `/booking/request`
  - `/booking/search/simple`
  - `/booking/search/summary?rangeInDays=7`

### 12) Creating booking in state

- Count: `1`
- Detail lines:
  - DEBUG [dw-30 - POST /booking/request] [2026-03-27 21:06:31.583] User: 100524 COMPANY: 1000 com.inttra.mercury.booking.service.BookingService: Creating booking in state REQUEST


### 13) Created new booking

- Count: `1`
- Detail lines:
  - INFO  [dw-30 - POST /booking/request] [2026-03-27 21:06:31.701] User: 100524 COMPANY: 1000 com.inttra.mercury.booking.service.BookingService: Created new booking 2011967001 in state REQUEST for workflowId 


### 14) Booking life cycle started

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:50.118]   com.inttra.mercury.booking.config.BookingAppLifecycleListener: Booking life cycle started


### 15) The following paths were found for the configured resources

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:50.090]   io.dropwizard.jersey.DropwizardResourceConfig: The following paths were found for the configured resources:

    GET     /booking/carrier-spot-rates/isSpotRateBooking/{inttraReferenceId} (com.inttra.mercury.booking.carrierspotrates.resource.CarrierSpotRatesResource$$EnhancerByGuice$$855687b)
    POST    /booking/carrier-spot-rates/saveLinkToInttraRef (com.inttra.mercury.booking.carrierspotrates.resource.CarrierSpotRatesResource$$EnhancerByGuice$$855687b)
    GET     /booking/carrier-spot-rates/{inttraCompanyId} (com.inttra.mercury.booking.carrierspotrates.resource.CarrierSpotRatesResource$$EnhancerByGuice$$855687b)
    GET     /booking/dgs/undg/{undg} (com.inttra.mercury.booking.dgs.resource.DangerousGoodsResource$$EnhancerByGuice$$866f2dd)
    POST    /booking/outbound/partnerintegration (com.inttra.mercury.booking.outbound.resources.OutboundResource$$EnhancerByGuice$$8114364)
    GET     /booking/outbound/{inttraReferenceId} (com.inttra.mercury.booking.outbound.resources.OutboundResource$$EnhancerByGuice$$8114364)
    POST    /booking/outbound/{inttraReferenceNumber}/email (com.inttra.mercury.booking.outbound.resources.OutboundResource$$EnhancerByGuice$$8114364)
    POST    /booking/outbound/{inttraReferenceNumber}/reprocess (com.inttra.mercury.booking.outbound.resources.OutboundResource$$EnhancerByGuice$$8114364)
    GET     /booking/ov/{carrierId} (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    POST    /booking/rapid-reservation (com.inttra.mercury.booking.rapidreservation.resource.RapidReservationResource$$EnhancerByGuice$$8218044)
    DELETE  /booking/rapid-reservation/{inttraCompanyId} (com.inttra.mercury.booking.rapidreservation.resource.RapidReservationResource$$EnhancerByGuice$$8218044)
    GET     /booking/rapid-reservation/{inttraCompanyId} (com.inttra.mercury.booking.rapidreservation.resource.RapidReservationResource$$EnhancerByGuice$$8218044)
    POST    /booking/rapid-reservation/{inttraCompanyId}/{name}/add-range (com.inttra.mercury.booking.rapidreservation.resource.RapidReservationResource$$EnhancerByGuice$$8218044)
    POST    /booking/request (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    GET     /booking/search/bookingforBL (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    GET     /booking/search/hasaccess (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    POST    /booking/search/simple (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    GET     /booking/search/summary (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    GET     /booking/search/{inttraReferenceNumber} (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    POST    /booking/search/{inttraReferenceNumber}/reindex (com.inttra.mercury.booking.resources.SearchResource$$EnhancerByGuice$$802c49f)
    GET     /booking/services/ping (com.inttra.mercury.resources.InttraServerResource$$EnhancerByGuice$$7bad619)
    GET     /booking/services/version (com.inttra.mercury.resources.InttraServerResource$$EnhancerByGuice$$7bad619)
    GET     /booking/template (com.inttra.mercury.booking.template.TemplateResource)
    DELETE  /booking/template/{name} (com.inttra.mercury.booking.template.TemplateResource)
    GET     /booking/template/{name} (com.inttra.mercury.booking.template.TemplateResource)
    PUT     /booking/template/{name} (com.inttra.mercury.booking.template.TemplateResource)
    DELETE  /booking/{inttraReferenceId} (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    GET     /booking/{inttraReferenceId} (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    POST    /booking/{inttraReferenceId}/acknowledge (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/acknowledge/validate (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/amend (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    POST    /booking/{inttraReferenceId}/cancel (com.inttra.mercury.booking.resources.CustomerBookingResource$$EnhancerByGuice$$7d234a0)
    POST    /booking/{inttraReferenceId}/confirm (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/confirm/validate (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/decline (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/decline/validate (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/replace (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceId}/replace/validate (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)
    POST    /booking/{inttraReferenceNumber}/s3archive (com.inttra.mercury.booking.resources.CarrierBookingResource$$EnhancerByGuice$$7c5191e)



### 16) Listener com.inttra.mercury.booking.common.listener.SQSListener starting

- Count: `1`
- Detail lines:
  - INFO  [pool-22-thread-1] [2026-03-27 20:51:49.092]   com.inttra.mercury.booking.common.listener.SQSListener: Listener com.inttra.mercury.booking.common.listener.SQSListener starting.


### 17) Starting InttraServer

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:49.088]   io.dropwizard.core.server.ServerFactory: Starting InttraServer


### 18) Creating TemplateSummary composite-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:49.057]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating TemplateSummary composite-key repository for table: inttra_int_booking_Template


### 19) Creating Template composite-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:49.044]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating Template composite-key repository for table: inttra_int_booking_Template


### 20) Creating SpotRatesToInttraRefDetail partition-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.979]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating SpotRatesToInttraRefDetail partition-key repository for table: inttra_int_booking_SpotRatesToInttraRefDetail


### 21) Creating SpotRatesDetail partition-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.943]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating SpotRatesDetail partition-key repository for table: inttra_int_booking_SpotRatesDetail


### 22) Creating RapidReservation composite-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.931]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating RapidReservation composite-key repository for table: inttra_int_booking_RapidReservation


### 23) Creating SequenceId partition-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.861]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating SequenceId partition-key repository for table: inttra_int_booking_SequenceId


### 24) Creating UniqueId partition-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.624]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating UniqueId partition-key repository for table: inttra_int_booking_UniqueId


### 25) Creating BookingDetail composite-key repository for table

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:47.759]   com.inttra.mercury.booking.config.BookingDynamoModule: Creating BookingDetail composite-key repository for table: inttra_int_booking_BookingDetail


### 26) SNS NotificationService created successfully for topic

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.441]   com.inttra.mercury.booking.config.BookingMessagingModule: SNS NotificationService created successfully for topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event


### 27) Creating SNS NotificationService using cloud-sdk-aws factory

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.388]   com.inttra.mercury.booking.config.BookingMessagingModule: Creating SNS NotificationService using cloud-sdk-aws factory


### 28) Creating Booking EmailService with templates list

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.224]   com.inttra.mercury.booking.config.BookingEmailSenderModule: Creating Booking EmailService with templates list [RequestAmendTemplate.json, CancelTemplate.json, DeclineReplaceTemplate.json, InternalErrorTemplate.json, PendingConfirmTemplate.json, ValidationErrorTemplate.json]


### 29) Creating SES client with default configuration and List of template files

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.224]   com.inttra.mercury.cloudsdk.email.factory.EmailClientFactory: Creating SES client with default configuration and List of template files


### 30) S3 StorageClient created successfully

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.223]   com.inttra.mercury.booking.config.BookingMessagingModule: S3 StorageClient created successfully


### 31) Resolved AWS credentials using provider

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.216]   com.inttra.mercury.cloudsdk.storage.impl.S3StorageClient: Resolved AWS credentials using provider: DefaultCredentialsProvider(providerChain=LazyAwsCredentialsProvider(delegate=Lazy(value=AwsCredentialsProviderChain(credentialsProviders=[SystemPropertyCredentialsProvider(), EnvironmentVariableCredentialsProvider(), WebIdentityTokenCredentialsProvider(), ProfileCredentialsProvider(profileName=default, profileFile=ProfileFile(sections=[])), ContainerCredentialsProvider(), InstanceProfileCredentialsProvider()]))))


### 32) Creating S3 StorageClient using cloud-sdk-aws factory

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.126]   com.inttra.mercury.booking.config.BookingMessagingModule: Creating S3 StorageClient using cloud-sdk-aws factory


### 33) SQS MessagingClient created successfully

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.125]   com.inttra.mercury.booking.config.BookingMessagingModule: SQS MessagingClient created successfully


### 34) Creating SQS MessagingClient using cloud-sdk-aws factory

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:48.037]   com.inttra.mercury.booking.config.BookingMessagingModule: Creating SQS MessagingClient using cloud-sdk-aws factory


### 35) Resolved AWS region from DefaultAwsRegionProviderChain

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:47.748]   com.inttra.mercury.cloudsdk.database.config.BaseDynamoDbConfig: Resolved AWS region from DefaultAwsRegionProviderChain: us-east-1


### 36) Using DefaultCredentialsProvider for DynamoDbClientConfig

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:47.749]   com.inttra.mercury.cloudsdk.database.config.BaseDynamoDbConfig: Using DefaultCredentialsProvider for DynamoDbClientConfig


### 37) Created client with endpoint

- Count: `1`
- Detail lines:
  - INFO  [main] [2026-03-27 20:51:47.252]   com.inttra.mercury.cloudsdk.aws.module.JestModule: Created client with endpoint https://search-inttra-int-es-bk-search-nbigubh4436bqk67srjemj25uu.us-east-1.es.amazonaws.com, signer ASIARFXJR4ZWPSFZZIVM, region us-east-1


## Raw matching log lines grouped by workflowId

### WorkflowId `c75efe70-88a9-4599-8a55-ee81a66d4138`

```text
INFO  [outbound] [2026-03-27 21:06:31.927]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Outbound processing started for inttraRef 2011967001 with workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 and JVM free memory 157 MB

```
```text
INFO  [outbound] [2026-03-27 21:06:32.053]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Start - Subscription processing for InttraRef# 2011967001, InttraCompanyID: 1000 and workflowId: c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.334]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions count after condition evaluation (Non-Grouped ) 1 for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.335]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Non-grouped subscriptions with condition evaluation true are : 9925786a-53c9-4c51-b70e-c8dc6870d373 for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.338]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions count after condition evaluation (Grouped ) is 0 for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.339]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions after condition evaluation (Grouped ) is  for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.343]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Begin Supplement OB for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.343]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: End Supplement OB for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:32.904]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Sending aperak for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for subscription 9925786a-53c9-4c51-b70e-c8dc6870d373

```
```text
INFO  [outbound] [2026-03-27 21:06:32.904]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: APERAK ==> IB file ediId for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for subscription 9925786a-53c9-4c51-b70e-c8dc6870d373 is null 

```
```text
INFO  [outbound] [2026-03-27 21:06:32.904]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: APERAK ==> IB file ftpID for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for subscription 9925786a-53c9-4c51-b70e-c8dc6870d373 is null 

```
```text
INFO  [outbound] [2026-03-27 21:06:33.074]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: APERAK ==> subscription EDI id CU2100 for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 

```
```text
INFO  [outbound] [2026-03-27 21:06:33.074]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: APERAK ==> subscription ftp id CU2100 for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 

```
```text
INFO  [outbound] [2026-03-27 21:06:33.075]   com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for inttra company 1000 : []

```
```text
INFO  [outbound] [2026-03-27 21:06:33.075]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138 for subscription 9925786a-53c9-4c51-b70e-c8dc6870d373 

```
```text
INFO  [outbound] [2026-03-27 21:06:33.094]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: End - Subscription processing for InttraRef# 2011967001, InttraCompanyID: 1000 and workflowId: c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:33.094]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Start - Subscription processing for InttraRef# 2011967001, InttraCompanyID: 800388 and workflowId: c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:33.183]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: End - Subscription processing for InttraRef# 2011967001, InttraCompanyID: 800388 and workflowId: c75efe70-88a9-4599-8a55-ee81a66d4138

```
```text
INFO  [outbound] [2026-03-27 21:06:34.249]   com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Outbound processing completed for workflowId c75efe70-88a9-4599-8a55-ee81a66d4138

```

### WorkflowId `331e0700-4066-4add-96c0-816a1ab31fb3`

```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.117] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions count after condition evaluation (Non-Grouped ) 2 for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.117] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Non-grouped subscriptions with condition evaluation true are : 25f045fa-6d0d-45ef-b927-7525c19d2a2c, e3ae9efb-f215-4090-8237-27daee696ec9 for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.117] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions count after condition evaluation (Grouped ) is 0 for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.118] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Subscriptions after condition evaluation (Grouped ) is  for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.118] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Begin Supplement OB for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.118] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: End Supplement OB for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.142] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: includeEnhancements preference for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 is []

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.142] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.ServiceHelper: Removing CustomsBroker from the Request message for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.143] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.ServiceHelper: Removing ShipmentIdentifyingNumber from the Request message for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.377] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.TransformerService: transformer Uploaded to bucket: inttra-int-workspace , fileKey: 331e0700-4066-4add-96c0-816a1ab31fb3/450fe56d-6f33-46de-965b-4ff95850e418for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.477] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: EDI/SQS OB sent for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 and subscription 25f045fa-6d0d-45ef-b927-7525c19d2a2c

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.478] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for inttra company -100 : []

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.478] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for subscription 25f045fa-6d0d-45ef-b927-7525c19d2a2c 

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.586] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.WatermillService: Uploaded watermill payload to bucket  inttra-int-workspace , fileKey: watermill_331e0700-4066-4add-96c0-816a1ab31fb3/654545b1-9bcf-4d27-a2f5-d6012005a01afor workflowId : 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.634] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.WatermillService: Watermill metadata sent to sqs https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_watermill_bk for workflowId : 331e0700-4066-4add-96c0-816a1ab31fb3

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.634] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Watermill OB sent for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 and subscription e3ae9efb-f215-4090-8237-27daee696ec9

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.635] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundEmailService: Emails via subscription processed for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for inttra company -100 : []

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:43.635] Client: booking_app COMPANY: 1000 com.inttra.mercury.booking.outbound.services.OutboundServiceImpl: Email processing done for workflowId 331e0700-4066-4add-96c0-816a1ab31fb3 for subscription e3ae9efb-f215-4090-8237-27daee696ec9 

```

## Raw request-filter URI log lines

```text
INFO  [dw-30 - GET /booking/search/summary?rangeInDays=7] [2026-03-27 21:04:39.876] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/search/summary?rangeInDays=7]
10.11.13.38 - - [27/Mar/2026:21:04:40 +0000] "GET /booking/search/summary?rangeInDays=7 HTTP/1.1" 200 172 "https://my-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 624

```
```text
INFO  [dw-30 - OPTIONS /booking/request] [2026-03-27 21:06:05.440] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/request]
10.11.15.104 - - [27/Mar/2026:21:06:05 +0000] "OPTIONS /booking/request HTTP/1.1" 200 13 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 15

```
```text
INFO  [dw-35 - POST /booking/request] [2026-03-27 21:06:05.723] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/request]

```
```text
INFO  [dw-30 - POST /booking/request] [2026-03-27 21:06:31.368] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/request]

```
```text
INFO  [dw-30 - GET /booking/2011967001] [2026-03-27 21:06:39.086] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/2011967001]

```
```text
INFO  [dw-35 - GET /booking/outbound/2011967001?versionnumber=] [2026-03-27 21:06:39.095] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/outbound/2011967001?versionnumber=]
10.11.10.86 - - [27/Mar/2026:21:06:39 +0000] "GET /booking/outbound/2011967001?versionnumber= HTTP/1.1" 200 2726 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 252
10.11.13.38 - - [27/Mar/2026:21:06:39 +0000] "GET /booking/2011967001 HTTP/1.1" 200 2709 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 263

```
```text
INFO  [dw-37 - POST /booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100] [2026-03-27 21:06:42.861] Client: booking_app COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.com/booking/outbound/partnerintegration?bookingId=76c9b33cbf8d4499b2b88e66b8496224&sequenceNumber=m_1774645591583_REQUEST_2011967001&piInttraCompanyId=-100]

```
```text
INFO  [dw-35 - OPTIONS /booking/search/simple] [2026-03-27 21:06:55.157] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/search/simple]
10.11.15.104 - - [27/Mar/2026:21:06:55 +0000] "OPTIONS /booking/search/simple HTTP/1.1" 200 13 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 3

```
```text
INFO  [dw-37 - POST /booking/search/simple] [2026-03-27 21:06:55.415] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/search/simple]

```
```text
INFO  [dw-35 - POST /booking/search/simple] [2026-03-27 21:06:58.618] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/search/simple]
10.11.12.240 - - [27/Mar/2026:21:06:58 +0000] "POST /booking/search/simple HTTP/1.1" 200 910 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 177

```
```text
INFO  [dw-35 - GET /booking/outbound/2011967001?versionnumber=] [2026-03-27 21:07:02.830] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/outbound/2011967001?versionnumber=]

```
```text
INFO  [dw-37 - GET /booking/2011967001] [2026-03-27 21:07:02.836] User: 100524 COMPANY: 1000 com.inttra.mercury.filters.MercuryRequestLoggingFilter: request:[URI:http://api-alpha.inttra.e2open.com/booking/2011967001]
10.11.13.38 - - [27/Mar/2026:21:07:02 +0000] "GET /booking/2011967001 HTTP/1.1" 200 2709 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 129
10.11.10.86 - - [27/Mar/2026:21:07:02 +0000] "GET /booking/outbound/2011967001?versionnumber= HTTP/1.1" 200 2726 "https://booking-alpha.inttra.e2open.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0" 143

```
