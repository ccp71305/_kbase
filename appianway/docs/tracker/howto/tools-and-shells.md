# Tools and shells at a glance

← [How-to index](README.md) · [Tracker home](../README.md)


| Tool | What it is | Used for |
|---|---|---|
| `git` | Git client | local config, hooks, branches |
| `gh` | GitHub CLI, already logged in as `ArijitKunduWTG` (`gh auth status`) | `gh api …` calls the GitHub REST API with your login, so no token handling |
| `--jq '<expr>'` | Option of `gh api`: filters the JSON reply with a [jq](https://jqlang.org/manual/) expression (built into `gh`, no separate install) | showing only the fields that matter |
| `curl` | HTTP client | reading files from the Maven repository over HTTPS |
| `grep`, `sed`, `cut`, `head`, `wc` | Text tools in **Git Bash** | searching and slicing the Jenkins log |
| `Select-String`, `Get-Content`, `Invoke-RestMethod` | The **PowerShell** equivalents | same jobs in PowerShell ([cheat sheet](../howto/bash-powershell-cheatsheet.md)) |
| `javap` | JDK class-file disassembler (`C:\Program Files\Eclipse Adoptium\jdk-17.0.17.10-hotspot\bin\javap.exe`) | proving a method exists in a published jar |

The checks were run in Git Bash. Each one also has a tested PowerShell version.

A variable for the repository path saves typing:

```bash
R=repos/wtg-e2open/INTTRA.appianway          # Git Bash: no spaces around =
```

```powershell
$R = 'repos/wtg-e2open/INTTRA.appianway'     # PowerShell
```

`gh api $R/...` (Bash) or `gh api "$R/..."` (PowerShell) then expands to `gh api repos/wtg-e2open/INTTRA.appianway/...`. `gh api` sends a **GET** unless you add `-X POST` or `-f`/`-F` fields, so these calls cannot change anything.
