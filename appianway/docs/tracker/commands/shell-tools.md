# Searching and probing: grep, curl

← [Index](README.md)

Used to find where something comes from before a test. `sed`, `tr`, `unzip` and `printf` are explained where they are used ([AWS logs](../runtime/aws/logs-metrics.md), [build worktree](build-worktree.md#two-jars)).

<a id="maven-site"></a>
## Looking for artifacts on the internal Maven site (VPN)

```bash
B=https://inttra-ci.dev.e2open.com/maven2/contivo/maps
curl -s -m 20 "$B/"; curl -s -m 20 "$B/visibility/"
curl -s -m 15 -o /dev/null -w "%{http_code} %{size_download}\n" "$B/booking/IFTMBF_D99B_IN_V1.jar"
```

`curl` sends an HTTP GET (read only). `-s` silent (no progress bar), `-m 20` gives up after 20 seconds, `-o /dev/null` throws the body away, `-w "…"` prints values after the transfer: `%{http_code}` (200 found, 404 not found) and `%{size_download}` (bytes). The site answers a folder URL with a list of names: `maps/` holds only `visibility`, and `visibility/` only `IFTSTA_D99B_IN_V1.jar` and `IFTSTA_D99B_IN_V1_STRUCT.jar`, the two maps `build.sh` and `build_pr.sh` download. Every booking map name tried (under `booking/`, `bookings/`, `bk/`, `Booking/`, `visibility/` and the root) answered 404. The booking maps reach the ECS hosts' `/app01/maps` some other way (the task definition mounts the host's `/app01`; `run.sh` starts java with `-Dcontivo.runtime.classpath=/app01/maps`).

<a id="grep-code"></a>
## Finding where a value comes from in the code

```bash
grep -rn "_STRUCT\|getMapName\|mapName\|contivo\.runtime" transformer/src/main/java
```

Found where the map names come from: `InboundTransformation` takes the map from the integration profile format (`ipf.getTransformer()`) and the structural-validation map as `<map>_STRUCT` (none for the XML booking map). `-r` recursive, `-n` line numbers, `\|` "or" in basic grep regex, `\.` a literal dot.
