# This file provides the details of aws commands to leverage and reviewing the code changes related to aws dynamo db in this PR

## Files to reference

- .github/skills/pr-reviews/pr-context.md

this file provides the context of the PR and details of the code changes in this PR. It also provides the details of the files changed in this PR and the relevant git commands to review the code changes in this PR. You can refer to this file to get the context of the PR and to review the code changes in this PR.

- .github/skills/pr-reviews/full-diff.patch

this file contains the complete diff for the commit in this PR. 
You can refer to this file to see the code differences for all the files changed in this PR. This will help you review the code changes in a more efficient way without having to load the entire diff in memory or navigate through multiple files

- .github/skills/aws-skills/inttra_int_booking_BookingDetail.json

this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_BookingDetail which is the main table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes. 
You can then review in detail the BookingDetail class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_SpotRatesToInttraRefDetail.json

this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_SpotRatesToInttraRefDetail which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes.
You can then review in detail the SpotRatesToInttraRefDetail class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_RapidReservation.json

this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_RapidReservation which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes. 
You can then review in detail the RapidReservation class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_SequenceId.json
this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_SequenceId which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes.
You can then review in detail the SequenceId class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_UniqueId.json
this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_UniqueId which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes.
You can then review in detail the UniqueId class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_Template.json
this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_Template which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes.
You can then review in detail the Template class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

- .github/skills/aws-skills/inttra_int_booking_SpotRatesDetail.json
this file contains the output of the aws cli command to describe the dynamo db table inttra_int_booking_SpotRatesDetail which is another table that is being changed in this PR.
You can refer to this file to see the details of the table with all its attributes and indexes.
You can then review in detail the SpotRatesDetail class and make sure all attributes and indexes are correctly mapped and captured so that no functionality is lost.
Review the related code changes in the booking module and make sure all the changes are consistent with the table structure and the attributes and indexes defined in the table.
Make sure old annotations that are removed are not needed and that the new annotations and the new way of defining the hash and sort keys are correctly implemented and working as expected.
Make sure all converters are compliant and working as expected with the new annotations and the existing table definitions and that there are no gaps in functionality due to the code changes in this PR.
This will help you ensure that the code changes are correct and that there are no gaps or missing functionality due to the code changes in this PR.

## aws commands

- aws dynamodb describe-table \
  --table-name inttra_int_booking_BookingDetail \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_SpotRatesDetail \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_SpotRatesToInttraRefDetail \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_RapidReservation \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_SequenceId \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_UniqueId \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager

- aws dynamodb describe-table \
  --table-name inttra_int_booking_Template \
  --profile INTTRA-Dev-Engg-081020446316 \
  --no-cli-pager
