# Elasticsearch (Amazon OpenSearch Service) reads

← [AWS commands index](README.md) · [Runtime index](../README.md)

The AWS CLI cannot call an Elasticsearch domain's data API (it only manages domains), and the requests must be SigV4-signed. So ingestor's test used a small Java tool, [EsRead.java](../fixtures/test7-ingestor/EsRead.java), that signs **exactly as ingestor does**: the same `aws-signing-request-interceptor` and Apache HTTP client, taken from ingestor's own shaded jar, with the credentials from the default chain (the SSO credentials exported into the shell). It only reads: GET, or POST to `_search` / `_count` (it refuses a body for any other path).

```bash
P=642960533737_INTTRA2-QATeam
ES=https://search-inttra2-qa-es-tx-tracker-mu26gj3twl5io444fqids6ahee.us-east-1.es.amazonaws.com
eval "$(aws configure export-credentials --profile $P --format env)"; export AWS_REGION=us-east-1 MSYS_NO_PATHCONV=1
java -cp ingestor-v2.jar EsRead.java $ES "/_cluster/health"                                   # R
java -cp ingestor-v2.jar EsRead.java $ES "/_cat/indices/txtrack-*?h=index,docs.count&s=index"   # R
echo '{"query":{"prefix":{"workflowId":"wi01124532-rt-ing-"}}}' > q-prefix.json
java -cp ingestor-v2.jar EsRead.java $ES "/txtrack-event-*/_count" q-prefix.json               # R
java -cp ingestor-v2.jar EsRead.java $ES "/txtrack-event-*/_search" q-ev-v1.json > out/events-v1.json   # R
```

| Part | Meaning |
|---|---|
| `java -cp ingestor-v2.jar EsRead.java …` | Java 11+ runs a single source file directly ("source-file mode"); `-cp` puts ingestor's shaded jar on the classpath, so the tool uses the same signer, SDK v1 credentials classes and HTTP client versions as the service |
| `MSYS_NO_PATHCONV=1` | Git Bash turns an argument starting with `/` into a Windows path (`/_cluster/health` became `C:/Program Files/Git/_cluster/health`, the first attempt's error); this switches that off for the command |
| `/_cluster/health` | Cluster status; the first proof that the domain is reachable and accepts the role's signed requests |
| `/_cat/indices/txtrack-*?h=index,docs.count&s=index` | One line per index matching the pattern: `h=` the columns, `s=` sort |
| `/<index pattern>/_count` + `{"query":…}` | Number of matching documents (pre-check before writing: 0) |
| `/<index pattern>/_search` + `{"size":500,"query":…}` | The matching documents (`hits.hits[]._source`); `size` raises the default of 10 |
| `{"prefix":{"workflowId":"wi01124532-rt-ing-v1-"}}` | `workflowId` is a `keyword` in the event mapping (`txtrack-event-mapping-template.json`), so a prefix query finds every marked event document |
| `{"ids":{"values":[…]}}` | The aggregates have the workflow id as document id; `_id` does not take a prefix query (the first attempt: `query_shard_exception`), so the ids are listed |
| `{"terms":{"eventId.keyword":[…]}}` | `eventId` is mapped dynamically (text with a `.keyword` sub-field): exact match on the 104 real event ids, to find QA's own documents |

Result 2026-11-20: reachable; [test 7](../ingestor.md#test-7).
