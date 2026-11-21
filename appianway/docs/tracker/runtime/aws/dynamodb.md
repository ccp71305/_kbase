# DynamoDB commands

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="sequence-table"></a>
## The control-number sequence table (all R)

```bash
aws dynamodb describe-table --profile $P --region us-east-1 --table-name inttra2_qa_controlnumber_sequence \
    --query 'Table.{keys:KeySchema,items:ItemCount,status:TableStatus}' --output json                          # R
aws dynamodb scan --profile $P --region us-east-1 --table-name inttra2_qa_controlnumber_sequence --consistent-read --output json   # R
aws dynamodb get-item --profile $P --region us-east-1 --table-name inttra2_qa_controlnumber_sequence \
    --key '{"keyId":{"S":"SequenceId"}}' --consistent-read --query 'Item.[id.N,version.N]' --output text           # R
```
The control-number sequence table. `describe-table` shows the key (`keyId`, partition key) and the approximate item count (1). `scan` reads every item (fine for a one-item table; never on a big one); `get-item` reads one item by its full key. `--key` is DynamoDB's typed JSON: `{"<attribute>":{"S":"<string value>"}}` (`S` string, `N` number). `--consistent-read` returns the latest write (the default is eventually consistent and could miss a write made a second before). `Item.[id.N,version.N]` picks the two numbers. Read before and after each build's run: `100029603000`/29603 → `100029604000`/29604 (v1) → `100029605000`/29605 (new build): each start takes one block of 1,000 numbers ([test 6](../transformer.md#test-6)).
