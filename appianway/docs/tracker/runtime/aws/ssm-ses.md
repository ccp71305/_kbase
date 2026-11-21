# SSM Parameter Store and SES commands (read)

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="5b-ssm"></a>
## SSM Parameter Store (read)

```bash
MSYS_NO_PATHCONV=1 aws ssm get-parameters --profile $P --region us-east-1     --names /inttra2/qa/appianway/networkservices/authclientid /inttra2/qa/appianway/networkservices/authclientsecret     --with-decryption --query '{found:Parameters[].Name,invalid:InvalidParameters}' --output json
```
Checks that the parameters a service reads at startup exist and that the role may read them. `--with-decryption` asks for the decrypted `SecureString` values (it needs `kms:Decrypt`, so it proves the service could read them too), but `--query` prints **only the names** found and the names not found (`InvalidParameters`): the secrets never reach the screen or a log. `MSYS_NO_PATHCONV=1` stops Git Bash from turning `/inttra2/...` into a Windows path. Used before test 4 (dispatcher reads the Network Services client id and secret).

<a id="5a-ses"></a>
## SES (read)

```bash
aws sesv2 get-account --profile $P --region us-east-1 --query '{prod:ProductionAccessEnabled,sending:SendingEnabled,quota:SendQuota}'
aws sesv2 get-email-identity --profile $P --region us-east-1 --email-identity no-reply@appianway-beta.inttra.com     --query '{verified:VerifiedForSendingStatus,type:IdentityType}' --output text
```
`get-account`: whether the account is out of the SES sandbox (`ProductionAccessEnabled`; in the sandbox only verified recipients can receive) and its sending quota. `get-email-identity`: whether a sender address or domain is verified for sending (`NotFoundException` = not an identity in this account). Neither shows whether **your** role may send: that is IAM (`ses:SendEmail` on the identity), and the QATeam role does not have it (test 3).

<a id="ssm-names-only"></a>
### Test 10: both Watermill parameters exist, names only (R)

```bash
MSYS_NO_PATHCONV=1 aws ssm get-parameters --profile $P --region us-east-1 \
  --names /inttra2/qa/appianway/watermill-grpc/se/username /inttra2/qa/appianway/watermill-grpc/se/password \
  --with-decryption --query '{found: Parameters[].Name, invalid: InvalidParameters}' --output json
```

`--query` keeps only the names found and the names not found, so no value is printed although `--with-decryption` is what the service asks for. `MSYS_NO_PATHCONV=1`: without it Git Bash turns an argument starting with `/` into a Windows path (`C:/Program Files/Git/inttra2/...`), and SSM reports both names as invalid.
