# Git Investigation — Watermill Dependency/Path Metadata (ION-14997)

**Date:** 2026-07-27
**Context:** After a `git pull` on `develop`, a remote branch update appeared for
`ION-14997-Watermill-bl-inbound-consumer`. This note records *what changed*, *whether
`develop` already has it*, and *the exact git commands used to find out* — so the same
investigation can be reproduced later.

---

## 1. What exactly changed

A single commit on the feature branch:

- **Commit:** `47e979ca` — *"ION-14997 Add Dependency and Path json"*
- **Author:** Nishith N `<nishith.n@e2open.com>`
- **Date:** 2026-07-23
- **Branch:** `origin/ION-14997-Watermill-bl-inbound-consumer` (advanced `d4cd1a6d..47e979ca`)
- **Files:** `app_dependency.json` (+26/-2), `app_path.json` (+10/-1) — build metadata only, **no Java/source logic**.

### `app_dependency.json`
Registered the **watermill side-bus modules** as dependents of the core libraries so the
dependency-aware CI build picks them up:

- Added to the dependents of `shared` and `gen2-parser`/canonical:
  - `watermill-publisher`
  - `watermill/booking-inbound-consumer`
  - `watermill/billoflading/ebl-inbound-consumers`
  - `watermill/billoflading/registration-inbound-consumers`
  - `watermill/cargoscreen-consumer`
  - `watermill/itv-gps-consumer`
  - `watermill/visibility-inbound-consumer`
- Added a new **`consumer-commons`** dependency block mapping to the same six watermill consumers.

### `app_path.json`
Added path mappings for the watermill directories:

- `watermill-publisher/`
- `watermill/booking-inbound-consumer/`
- `watermill/billoflading/ebl-inbound-consumers/`
- `watermill/billoflading/registration-inbound-consumers/`
- `watermill/consumer-commons/`
- `watermill/cargoscreen-consumer/`
- `watermill/itv-gps-consumer/`
- `watermill/visibility-inbound-consumer/`

**Net effect:** these two CI/build-metadata files now know the watermill modules exist and
how they depend on the core modules, so watermill modules are included in the
dependency-triggered build. No runtime behavior changed.

---

## 2. Merge status (as of 2026-07-27)

- The commit `47e979ca` is **NOT** in `develop`.
- The feature branch `ION-14997-Watermill-bl-inbound-consumer` is **NOT** merged into `develop`.
- `develop` and the feature branch have **diverged**: ahead/behind count = **`2  2`**
  (`develop` has 2 commits the feature lacks; the feature has 2 the `develop` lacks).
- Local `develop` therefore does **not** contain these changes yet.

---

## 3. Commands used (reproducible investigation)

### 3.1 Which branch am I on + what are the new commits + which files changed
```bash
git --no-pager branch --show-current
git --no-pager log --oneline -5 d4cd1a6d..47e979ca
git --no-pager diff --stat d4cd1a6d..47e979ca
```
- `branch --show-current` → prints the checked-out branch (`develop`).
- `log --oneline A..B` → lists commits reachable from `B` (new tip) but **not** from `A`
  (old tip) — i.e. exactly what the pull brought in. `--no-pager` prints inline without opening a pager.
- `diff --stat A..B` → summarizes the files changed between the two commits with insert/delete counts.

### 3.2 Is the commit in develop, and is the feature branch merged
```bash
git branch --contains 47e979ca            # lists branches that include this commit; empty => not in develop
git branch --merged develop -a            # lists all branches already merged into develop
git --no-pager rev-list --left-right --count develop...origin/ION-14997-Watermill-bl-inbound-consumer
```
- `branch --contains <sha>` → every branch whose history includes that commit. Empty/absent
  `develop` means `develop` does not have it.
- `branch --merged develop -a` → branches (incl. remotes with `-a`) fully merged into
  `develop`. Absence of the feature branch means it's unmerged.
- `rev-list --left-right --count A...B` → the **three-dot** form. Prints two numbers:
  commits unique to the left (`develop`) and unique to the right (feature). `2  2` = diverged.

### 3.3 The actual content of the change
```bash
git --no-pager show 47e979ca --stat                              # commit metadata + file stat
git --no-pager diff d4cd1a6d..47e979ca -- app_dependency.json app_path.json   # line-level diff of the two files
```
- `show <sha> --stat` → author/date/message plus per-file change summary.
- `diff A..B -- <paths>` → the exact line-level additions/removals, scoped to the listed files.

### Quick reference — the `..` vs `...` distinction
| Form | Meaning |
|---|---|
| `A..B` | Commits reachable from `B` but not `A` (used with `log`/`diff` for "what's new in B"). |
| `A...B` | Symmetric difference; with `rev-list --left-right --count` gives ahead/behind counts. |

---

## 4. Takeaways

- The watermill build metadata (ION-14997) is committed on its feature branch only; it must
  be merged (or the feature branch rebased onto `develop`, given the 2/2 divergence) before
  `develop` builds treat the watermill modules as first-class dependency-tracked modules.
- To obtain the changes locally now: `git checkout ION-14997-Watermill-bl-inbound-consumer`
  (the remote-tracking ref was updated by the pull), or cherry-pick `47e979ca`.
