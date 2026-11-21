# Step 2 — email-sender (`WI01124532-aws-sdk-upgrade-email-sender`)

← [Tracker home](../README.md) · [All steps](README.md)

Cut 2026-11-19 from `ff281fa1` (after PR #5). Merged as [PR #6](https://github.com/wtg-e2open/INTTRA.appianway/pull/6) (`feca5faf`, 2026-11-19 14:03 UTC; head `838104b6`, 15 commits `6e7b6335` … `838104b6`). This page was written when the tracker was split (the old progress doc had no step log for email-sender); the commit-by-commit detail is in the PR description file.

- **PR description, review guide, walkthrough, command log:** `docs/redesign/pr-details/2026-11-19-apway-pr-2-email-sender-description.md`
- **Design page:** `docs/redesign/2026-10-30-apway-WI01124532-email-sender.md`
- **Tests:** email-sender 13 → 25 (1 skipped); shared 1831 → 1837 (email role, `withEmail()`).
- **Build:** full reactor green, 10:00 min.
- **shared additions:** `ClientSettings.email()` (v1 SES: 10 s / 50 s, no execution timeout, 50 connections, 0 retries), `ClientProfile.email(..)`, `CloudClients.email(..)`, `CloudServicesModule.withEmail()` / `withEmailSettings(..)`.
- **Golden test:** the SESv2 request and the CLOSE events equal v1 (`wire/sent-and-dropped.expected.txt`).
- **Pre-review:** 10 points, 3 fixed (`withEmailSettings` alone binds email, an exact comment, a bounded health-check HTTP call).
- **Copilot:** no inline comments; "Needs a closer look" answered with a PR comment (snapshot in CI, IAM, retries and timeouts, INT shutdown check).
- **Known defect:** [F16](../findings.md#f16), failure events (disabled test `EmailSenderKnownDefectsTest`). [F17](../findings.md#f17) was found here too.
