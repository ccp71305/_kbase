# Step 1e — functional testing (`WI01124532-aws-sdk-upgrade-functional-testing`)

← [Tracker home](../README.md) · [All steps](README.md)


Cut 2026-11-17 from the 1d branch at `366d13f7` (stacked on PR #2). Pushed as PR #3 on 2026-11-17, retargeted to the feature branch after #2 merged, and **merged 2026-11-18 as `58aee71b`**. PR description: `docs/redesign/pr-details/2026-11-17-apway-pr-1e-functional-testing-description.md`.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `c0fe1b3a` red: functional-testing uses the same libraries as the services | red | `FunctionalTestingLibraryVersionsTest` (4): dropwizard-testing/-jackson/-lifecycle were 4.0.16 next to core 5.0.2; Mockito 2.8.9, logback 1.5.33, slf4j 2.0.17. Mockito read from the jar manifest (no `pom.properties`) |
| 2 | `135b7b19` green: functional-testing pins follow the reactor | green | DW 5.0.2, Mockito 2.27.0, logback 1.5.38 (+ explicit `logback-core`), slf4j 2.0.18 (explicit). Full reactor green 11:02 min, all service counts unchanged |
| 3 | `24fc7867` red: cloud-sdk fakes behave like cloud-sdk | red | 29 self-tests; fakes generated as stubs (every public method throws) |
| 4 | `23c97e6e` green: cloud-sdk fakes | green | [D33](../decisions.md#d33). `FakeQueue` (also `FakeSQS`), `FakeStorage` (+ `asFakeS3()` view), `FakeNotificationService`, `FakeParameterStore` |
| 5 | `9bf56929` red: JUnit 5 base with the fakes bound like the cloud module | red | `CloudFunctionalTestBaseTest` (4), `IntegrationTestSupportCommandTest` (1) on `PingApplication` (`ping.yaml`, `ping-test.properties`) |
| 6 | `98163ba8` green: JUnit 5 functional-test base | green | `CloudFunctionalTestBase.cloudBindings(topic, parameters...)`, `IntegrationTestExtension` (`DropwizardAppExtension` around `IntegrationTestSupport`), injectable server command |
| 7 | `55f3f049` red: AWS SDK boundary rule | red | [D34](../decisions.md#d34). `AwsSdkBoundaryTest` (6) with compliant / violating fixtures; ArchUnit 1.3.0 core added |
| 8 | `80d93521` green: AWS SDK boundary rule | green | `AwsSdkBoundary.rule()/ruleAllowing()/check()/checkAllowing()`; allowed: DynamoDB annotations (+ `DefaultAttributeConverterProvider`, found by the fixture), `ConditionalCheckFailedException`. **Full reactor green 9:26 min**, functional-testing 0 → 44 |
| 9 | `a410715e` red: functional-testing runs the reactor's JUnit and Surefire | red | PR #3 review R1 (Copilot). `FunctionalTestingLibraryVersionsTest` +2: Jupiter 5.14.4 / Platform 1.14.4 by `Bundle-Version` (5.12.2 found, via Jersey); the pom imports `junit-bom` and declares the root's Surefire version (it declared none) |
| 10 | `b3a96744` green: functional-testing imports the reactor's junit-bom and pins Surefire | green | [D35](../decisions.md#d35). `junit-bom` 5.14.4 import; `junit-jupiter-api` compile, `-engine` test, both without versions; Surefire 3.2.5 |
| 11 | `f082ed16` red: the queue fake leaves a health-probed message in the queue | red | PR #3 review R2 (Copilot). `FakeQueueTest` +2: `InboundMessageQueueHealthCheck` on a populated queue, then the same message is received; a receive that does not wait returns at once on an empty queue |
| 12 | `78b936f8` green: a visibility-0 receive leaves messages in the queue fake | green | [D36](../decisions.md#d36). **Full reactor green 8:49 min** (26 build units); functional-testing 48 (versions 6, fakes 31, base 5, boundary 6); all other counts unchanged |
