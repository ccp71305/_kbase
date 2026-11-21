# Bash and PowerShell cheat sheet

← [How-to index](README.md) · [Tracker home](../README.md)


All PowerShell lines below were run on 2026-11-17 and give the same answers as the Bash versions. Set up first:

```powershell
$f = "C:\Users\arijit.kundu\OneDrive - WiseTech Global\Documents\platform\aws-upgrade\1.0.39-SNAPSHOT.log"
```

| Task | Git Bash | PowerShell |
|---|---|---|
| Line count | `wc -l "$f"` → 45205 | `(Get-Content $f).Count` → 45206 (counts a last line without a newline; `wc` counts newline characters) |
| File size | `wc -c "$f"` | `(Get-Item $f).Length` |
| Search with line numbers | `grep -nE 'A\|B' "$f"` | `Select-String -Path $f -Pattern 'A\|B' -CaseSensitive` (output is `path:line:text`; `$_.LineNumber`, `$_.Line`) |
| Fixed text, no regex | `grep -F 'deploy:3.1.0' "$f"` | `Select-String -Path $f -Pattern 'deploy:3.1.0' -SimpleMatch` |
| Count matches | `grep -c 'deploy:3.1.0:deploy-file' "$f"` → 6 | `(Select-String -Path $f -Pattern 'deploy:3.1.0:deploy-file' -SimpleMatch).Count` → 6 |
| Invert match | `grep -v sample` | `Where-Object { $_ -notmatch 'sample' }` |
| First N results | `… \| head -80` | `… \| Select-Object -First 80` |
| Lines 95–96 | `sed -n '95,96p' "$f"` | `Get-Content $f \| Select-Object -Skip 94 -First 2` or `(Get-Content $f)[94..95]` (0-based index) |
| Cut long lines | `cut -c1-250` | `ForEach-Object { $_.Substring(0, [Math]::Min(250, $_.Length)) }` |
| HTTP status + body | `curl -s -m 15 -w "%{http_code}" URL` | `curl.exe -s -m 15 -w "%{http_code}" URL` (type **`curl.exe`**: in Windows PowerShell 5.1, plain `curl` is an alias for `Invoke-WebRequest`) |
| Read XML fields | `curl … \| grep timestamp` | `(Invoke-RestMethod $url).metadata.versioning.snapshot` → `timestamp 20261117.055030, buildNumber 1` (the XML is parsed into objects) |
| List jar entries | `unzip -l api.jar` | `tar -tf api.jar` (Windows `tar` reads zip files), or `[System.IO.Compression.ZipFile]::OpenRead($jar).Entries.FullName` after `Add-Type -AssemblyName System.IO.Compression.FileSystem` |
| Method in a class | `javap -cp api.jar <class> \| grep getObjectSize` | `javap -cp $jar <class> \| Select-String getObjectSize` |
| Loop | `for a in x y; do echo $a; done` | `foreach ($a in 'x','y') { $a }` |
| Exit code | `echo $?` | `$LASTEXITCODE` (native programs), `$?` (True/False) |

Gotchas:

- `Select-String` is **case-insensitive** by default. Add `-CaseSensitive` to behave like `grep`.
- `(Get-Content $f | Measure-Object -Line).Lines` gives **45105** because it skips blank lines. Use `.Count` instead.
- Quote paths with spaces in both shells. In Bash, use `"$f"` every time the variable is used. In PowerShell, quote only when assigning; `$f` stays one argument after that.
- `gh api … --jq '…'` works the same in PowerShell 7 with single quotes around the jq expression.
