# Dependency-Check Version Bump Runbook (Windows / PowerShell 7)

Last performed: 2026-09-01 — upgraded 12.2.2 → 13.0.0

## Install layout

```
C:\dependency-check\
    dependency-check-12.2.1\
    dependency-check-12.2.2\
    dependency-check-13.0.0\
    dependency-check-current  ->  dependency-check-13.0.0   (directory symlink, RELATIVE target)
```

`PATH` points at `C:\dependency-check\dependency-check-current\bin`, so bumping a version
means repointing one symlink — never editing `PATH`.

## Steps

### 1. Extract the new release

Unzip into `C:\dependency-check\` so it becomes `C:\dependency-check\dependency-check-<ver>\`.
Rename if the zip nests an extra folder level.

### 2. Confirm what is actually on PATH

```powershell
Get-Command dependency-check | Format-List Name, Source
# -> Name   : dependency-check.bat
# -> Source : C:\dependency-check\dependency-check-current\bin\dependency-check.bat
```

### 3. Inspect the current symlink

```powershell
Get-Item C:\dependency-check\dependency-check-current |
    Select-Object FullName, LinkType, Target
# -> FullName                                     LinkType     Target
# -> --------                                     --------     ------
# -> C:\dependency-check\dependency-check-current SymbolicLink dependency-check-12.2.2
```

Note the `Target` — it is **relative** (e.g. `dependency-check-12.2.2`, not a full path).
Recreate it the same way to keep the install portable.

### 4. List what is available

```powershell
Get-ChildItem C:\dependency-check -Directory | Select-Object Name
# -> Name
# -> ----
# -> dependency-check-12.2.1
# -> dependency-check-12.2.2
# -> dependency-check-13.0.0
# -> dependency-check-current
```

### 5. Sanity-check the new folder

```powershell
Test-Path "C:\dependency-check\dependency-check-<ver>\bin\dependency-check.bat"
```

**Stop if this is `False`** — the zip nested an extra folder level and the target needs adjusting.

### 6. Carry over the NVD cache

Use `robocopy`, **not** `Copy-Item` (see Gotchas).

```powershell
$src = 'C:\dependency-check\dependency-check-<oldver>\data'
$dst = 'C:\dependency-check\dependency-check-<ver>\data'

Remove-Item "$dst\*" -Recurse -Force
robocopy $src $dst /E
```

Verify the structure mirrors the old install:

```powershell
Get-ChildItem $dst | Select-Object Mode, Name
```

Expected:

```
d---- cache
d---- oss_cache
-a--- jsrepository.json
-a--- jsrepository.json.properties
-a--- odc.mv.db
-a--- publishedSuppressions.xml
-a--- publishedSuppressions.xml.properties
```

### 7. Repoint the symlink (elevated PowerShell)

```powershell
Push-Location 'C:\dependency-check'
[System.IO.Directory]::Delete('C:\dependency-check\dependency-check-current')
New-Item -ItemType SymbolicLink -Path 'dependency-check-current' -Target 'dependency-check-<ver>'
Pop-Location
```

### 8. Verify in a NEW shell

```powershell
dependency-check --version
Get-Item C:\dependency-check\dependency-check-current | Select-Object Target
```

## Gotchas

**`Copy-Item "src\*" dst -Recurse -Force` flattens directories when `dst` already exists.**
It fails with `Container cannot be copied onto existing leaf item`, but only *after* partially
copying — it dumped `cache\`'s contents (`CENTRAL.data`, `CENTRAL.key`, `NODEAUDIT.*`, `POM.*`)
as loose files directly into `data\`. Recovery is `Remove-Item "$dst\*" -Recurse -Force` then
`robocopy /E`. Just use `robocopy` from the start.

**Deleting a directory symlink.** Use `[System.IO.Directory]::Delete($link)` — it removes the
link only and can never recurse into the target. `Remove-Item` is usually safe in PowerShell 7
but the explicit call removes all doubt.

**Elevation.** `New-Item -ItemType SymbolicLink` requires an elevated shell unless Windows
Developer Mode is enabled.

**Stale PATH resolution.** Open a new shell before verifying; the old resolution is cached
in the current session.

**H2 schema on major bumps.** Across a major version (12.x → 13.x) `odc.mv.db` is likely
rejected on a schema-version check and rebuilt from the NVD. `cache\` and `oss_cache\` still
carry over, so the copy remains worthwhile. Have the NVD API key configured so a rebuild
finishes in reasonable time.

**Keep the old version folder** until the new one has completed a successful scan — rollback
is just repointing the symlink back.

## One-shot script (next time)

```powershell
# Run elevated. Set these two lines only.
$new = 'dependency-check-14.0.0'
$old = 'dependency-check-13.0.0'

$root = 'C:\dependency-check'
if (-not (Test-Path "$root\$new\bin\dependency-check.bat")) { throw "Bad layout in $new" }

Remove-Item "$root\$new\data\*" -Recurse -Force -ErrorAction SilentlyContinue
robocopy "$root\$old\data" "$root\$new\data" /E

Push-Location $root
[System.IO.Directory]::Delete("$root\dependency-check-current")
New-Item -ItemType SymbolicLink -Path 'dependency-check-current' -Target $new
Pop-Location

Write-Host "Open a new shell and run: dependency-check --version"
```