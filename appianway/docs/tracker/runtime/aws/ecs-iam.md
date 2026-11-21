# ECS and IAM commands (all R)

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="3-ecs"></a>
## ECS: clusters, services, tasks, task definitions (all R)

```bash
aws ecs list-clusters --profile $P --region us-east-1 --output text
```
Lists the ARNs of every ECS cluster in the account. The QA account also holds CVT (`ANECV*`) and PROD (`ANEPR*`) clusters; the QA AppianWay ones are `ANEQAAPWY-001` and `ANEQAAPWY-002`. (Since Arijit's rule, listings across clusters are not repeated.)

```bash
aws ecs list-services --profile $P --region us-east-1 --cluster ANEQAAPWY-001 --output text
```
Lists the services (long-running task groups) in one cluster. `--cluster` takes the cluster name or ARN.

```bash
aws ecs describe-services --profile $P --region us-east-1 --cluster ANEQAAPWY-001 \
    --services event-writer-qa error-processor-qa email-sender-qa dispatcher-qa \
    --query 'services[].{name:serviceName,desired:desiredCount,running:runningCount,taskDef:taskDefinition}' --output table
```
Details of up to 10 services: desired and running task counts, and the task definition revision in use (for example `AppianWay-event-writer-latest-qa-Task:5`). The `--query` keeps four fields.

```bash
aws ecs describe-task-definition --profile $P --region us-east-1 --task-definition AppianWay-event-writer-latest-qa-Task:5 \
    --query 'taskDefinition.containerDefinitions[0].logConfiguration.options' --output json
```
The container settings of one task definition revision (`family:revision`). Used to find where the service logs: group `inttra2-qa-lg-app-way`, stream prefix `AppianWay-event-writer-latest-qa`.

```bash
aws ecs list-tasks --profile $P --region us-east-1 --cluster ANEQAAPWY-001 --service-name event-writer-qa --query taskArns --output text
```
The running tasks of a service. The last part of the ARN is the task id, which also ends the task's log stream name.

```bash
aws ecs describe-tasks --profile $P --region us-east-1 --cluster ANEQAAPWY-001 --tasks dff5528c913e4cd996908721cf55fd81     --query 'tasks[0].{last:lastStatus,started:startedAt,stopped:stoppedReason,container:containers[0].lastStatus,exit:containers[0].exitCode}'
aws ecs describe-services --profile $P --region us-east-1 --cluster ANEQAAPWY-001 --services event-writer-qa     --query 'services[0].events[0:3].[createdAt,message]' --output text
```
`describe-tasks` shows one task's state; a stopped task keeps `stoppedReason` for about an hour (here: "Host EC2 (instance i-095c596e376849f4c) terminated"). The service's `events` list is ECS's own log of what it did (started a replacement task, reached a steady state), newest first.

<a id="11-iam-simulate"></a>
## Checking a task role's permissions without running anything (2026-11-20, all R)

Used for PR #9 (transformer): does QA's ECS task role allow every AWS action the new build makes? The local run uses the SSO role, which proves the calls work but not that the service's own role may make them. `simulate-principal-policy` evaluates the role's policies for a list of actions and resources and calls nothing.

```bash
P=642960533737_INTTRA2-QATeam
# 1. Which role does the service run as? (read the task definition, change nothing)
aws ecs describe-task-definition --profile $P --region us-east-1 \
    --task-definition AppianWay-transformer-latest-qa-Task \
    --query 'taskDefinition.{rev:revision,taskRole:taskRoleArn,exec:executionRoleArn}' --output json
# -> rev 6, taskRole arn:aws:iam::642960533737:role/INTTRA2-ECS-QA-Transformer-Task

R=arn:aws:iam::642960533737:role/INTTRA2-ECS-QA-Transformer-Task
# 2. DynamoDB on the sequence table
aws iam simulate-principal-policy --profile $P --policy-source-arn $R \
    --action-names dynamodb:GetItem dynamodb:PutItem dynamodb:Scan dynamodb:DescribeTable \
    --resource-arns arn:aws:dynamodb:us-east-1:642960533737:table/inttra2_qa_controlnumber_sequence \
    --query 'EvaluationResults[].[EvalActionName,EvalDecision]' --output text
# 3. One action on each queue in the service's QA properties (one call per queue, see the note)
for q in $(grep -h -o 'inttra2_qa_sqs_[a-z_]*' ../../transformer/conf/qa/transformer.properties | sort -u); do
  printf '%s\t' $q
  aws iam simulate-principal-policy --profile $P --policy-source-arn $R --action-names sqs:SendMessage \
      --resource-arns arn:aws:sqs:us-east-1:642960533737:$q --query 'EvaluationResults[0].EvalDecision' --output text
done
# 4. The parameters, by their real ARNs (the names are the values of networkservices.clientId / clientSecret)
aws iam simulate-principal-policy --profile $P --policy-source-arn $R --action-names ssm:GetParameter ssm:GetParameters \
    --resource-arns arn:aws:ssm:us-east-1:642960533737:parameter/inttra2/qa/appianway/networkservices/authclientid \
                    arn:aws:ssm:us-east-1:642960533737:parameter/inttra2/qa/appianway/networkservices/authclientsecret \
    --query 'EvaluationResults[].ResourceSpecificResults[].[EvalResourceName,EvalResourceDecision]' --output text
```

| Part | Meaning |
|---|---|
| `ecs describe-task-definition --task-definition <family>` | Without `:<revision>` it reads the latest **active** revision. `taskRoleArn` is the role the containers' AWS calls use; `executionRoleArn` (here none) is only for pulling images and writing logs |
| `iam simulate-principal-policy` | Evaluates the identity policies attached to `--policy-source-arn` (a user, group or role). Read-only: needs `iam:SimulatePrincipalPolicy` and `iam:GetContextKeysForPrincipalPolicy`, which the QATeam role has |
| `--action-names a b c` | Space-separated `service:Action` names; one result per action |
| `--resource-arns x y` | Resources to evaluate against. Without it the resource is `*`, and a policy written for specific ARNs then shows `implicitDeny` (that happened for SSM before the real parameter ARNs were given) |
| `EvalDecision` | `allowed`, `explicitDeny` (a Deny statement matched) or `implicitDeny` (no statement allows it) |
| `ResourceSpecificResults[]` | The per-resource decisions when several `--resource-arns` are given; `EvalResourceName` names each one |
| One call per queue | With several resources, the top-level result shows the matching statement's resource **pattern** (`arn:aws:sqs:${Region}:${Account}:${QueueName}`) instead of each queue; one call per queue prints a clear row each |
| `grep -h -o 'inttra2_qa_sqs_[a-z_]*' … \| sort -u` | `-o` prints only the matched queue names, `-h` drops the file name, `sort -u` removes duplicates: the queue list from the service's own QA configuration |

Limits: the simulation covers identity policies only, not the resource policies on the queues, the bucket or the KMS key. Those are unchanged by the upgrade, because v1 calls the same resources. Result for transformer: every action allowed (see [transformer test 6, step 21](../transformer.md#test-6)).
