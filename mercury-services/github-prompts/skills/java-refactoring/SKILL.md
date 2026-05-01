---
name: java-refactoring
description: >
  **WORKFLOW SKILL** — Guide enterprise Java refactoring and library upgrades.
  USE FOR: library version upgrades; API migrations; Maven dependency management;
  module-by-module refactoring with test verification.
  INVOKES: session context tools, git tools, kb tools, jira tools, terminal commands.
---

# Java Refactoring & Library Upgrade Skill

## AWS upgrades

cloud-sdk-api and cloud-sdk-aws are the two main modules in mercury-services-commons repository which needs to be used by all the active modules in this workspace for AWS related operations. 
The following modules have been upgraded to use the cloud-sdk-api and cloud-sdk-aws modules for AWS related operations:
auth, network, registration, booking-bridge, webbl, tx-tracking, self-service-reports, db-migration
Refer to these modules for the AWS related code changes and usage of cloud-sdk-api and cloud-sdk-aws modules.


## Workflow

### 1. Gather Requirements
```
jira_get_issue("<TICKET>")
session_list(project="mercury-services", module="<module being worked on>")
session_create(name="<TICKET> <description>", project="mercury-services", modules="<module being worked on>", tags=["java", "refactoring"])
```

### 1a. If requirements are not clear, gather more information
```
If no Jira ticket exists check available skills for guidance.
kb_grep(pattern="<library-name> upgrade", file_pattern="*.md")
kb_grep(pattern="<library-name> migration", file_pattern="*.md")
```

### 2. Assess Impact
```
kb_grep(pattern="<old-class-or-import>", file_pattern="*.java")
kb_grep(pattern="<artifact-id>", file_pattern="pom.xml")
git_file_history(repo, "pom.xml")
```

### 3. Execute Module by Module
```bash
# For each module in dependency order:
mvn compile -pl <module> -am    # compile
mvn test -pl <module>           # test
mvn verify -pl <module>         # verify (runs integration tests if resources are available) and if all tests pass, then mark the module as complete in the session context
session_add_context(...)        # track
```

### 4. Final Verification
```bash
mvn clean verify
```
### 5. Increase knowledgebase
```
kb_add_entry(title="<library-name> upgrade in <module>", content="Summary of changes,
challenges, and solutions encountered during the upgrade process.")
Add new skills if necessary if it helps future refactoring efforts.
```
## Rules
- Never break public API without deprecation
- Watch for transitive dependency changes
- Verify Jackson serialization compatibility
- Run integration tests after all modules pass
