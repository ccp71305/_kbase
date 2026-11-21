# AWS CLI basics: options, identity, credentials

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="1-options"></a>
## Options that appear in every command

| Option | Meaning |
|---|---|
| `--profile 642960533737_INTTRA2-QATeam` | Which named profile in `~/.aws/config` to use. This one is an **SSO profile** for the QA account `642960533737`, role `INTTRA2-QATeam`. Without `--profile` the CLI uses `default`, which here is the INT account |
| `--region us-east-1` | The AWS region. S3 commands work without it; SQS, ECS, CloudWatch and Logs need it |
| `--query '<JMESPath>'` | Filters the JSON answer on the client before printing. Examples: `Attributes` (one field), `services[].{name:serviceName}` (reshape a list), `sort_by(Datapoints,&Timestamp)` (sort). It saves reading whole answers |
| `--output text` / `json` / `table` | How to print: `text` is tab-separated (good for shell variables and `awk`), `json` is the raw structure, `table` is for reading by eye |
| `2>&1`, `\| head`, `\| cut -c1-200` | Shell only: merge errors into the output, keep the first lines, shorten long lines |

Shell helpers used with them: `P=642960533737_INTTRA2-QATeam` and `B=https://sqs.us-east-1.amazonaws.com/642960533737` are plain variables, so commands stay short (`$P`, `$B/<queue>`). `$(cygpath -w <path>)` turns a Git Bash path (`/c/Users/...`) into a Windows path (`C:\Users\...`): the AWS CLI is a Windows program and cannot read `/c/...` paths in `file://`.

<a id="2-identity"></a>
## Who am I, which profiles exist

```bash
aws sts get-caller-identity --profile $P            # R
```
STS (Security Token Service) answers with the account, the user or role ARN and an id for the credentials the CLI is using. It is the first check after an SSO login: it proves the profile works and shows which account it reaches. Result 2026-11-19: account `642960533737`, role `AWSReservedSSO_INTTRA2-QATeam_…`.

```bash
aws configure list-profiles                          # R (local only)
```
Lists the profile names in `~/.aws/config` and `~/.aws/credentials`. No call to AWS. Here: `default`, `081020446316_INTTRA-Dev-Engg` (INT), `642960533737_INTTRA2-QATeam` (QA).

```bash
aws sts get-caller-identity --profile $P                                                   # R
```
First check of the day: the SSO login was still valid (account `642960533737`, role `AWSReservedSSO_INTTRA2-QATeam_…`). An expired login answers `Token has expired and refresh failed`; then `aws sso login --profile $P` (opens the browser). `--profile qa` fails with "config profile (qa) could not be found": the profile is named after the account and role, see `aws configure list-profiles` (§2).

<a id="ms"></a>
## Times in milliseconds

`$P=642960533737_INTTRA2-QATeam` as everywhere. `ms(){ date -u -d "$1" +%s000; }` is a small Bash function: `date -u -d "<text>"` reads a date given as text in **UTC** (`-u`), `+%s` prints it as seconds since 1970, and the literal `000` appended turns seconds into the milliseconds that `--start-time` / `--end-time` expect. Example: `$(ms "2026-11-19 17:50:00")`.

<a id="7-credentials"></a>
## Credentials for the local service

```bash
eval "$(aws configure export-credentials --profile $P --format env)"
```
`export-credentials` prints the profile's current temporary credentials (from the SSO login) as `export AWS_ACCESS_KEY_ID=…`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. `eval` runs those lines in the current shell, so only that shell and the Java process it starts get them; nothing is written to a file, and they are never printed. Both SDK v1 and SDK 2.x read these environment variables first, so the old and the new build see the same identity. They expire with the SSO session.
