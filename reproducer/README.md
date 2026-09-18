# Reproducer: three bugs in c7-embedded-core

Runs the embedded Camunda 7 adapter of [process-engine-adapters-camunda-7](https://github.com/bpm-crafters/process-engine-adapters-camunda-7) against an in-memory engine and shows the three bugs described in [`../issues/`](../issues/).

| Component | Version |
|---|---|
| `process-engine-adapter-camunda-platform-c7-embedded-core` | 2026.09.1 (latest release) |
| `process-engine-api`, `process-engine-api-impl` | 1.7 |
| `camunda-engine` | 7.24.0, on H2 2.3.232 in memory |
| JUnit | 5.11.4 |

Compiled for Java 21, which Camunda 7.24 lists as supported ([Supported Environments, Java](https://docs.camunda.org/manual/7.24/introduction/supported-environments/#java)). It needs a JDK 21; the wrapper uses the one in `JAVA_HOME`. Last run with Eclipse Temurin 21.0.12.1+1 on Windows 10 Pro (10.0.19045) and Maven 3.9.12 through the wrapper.

## Run

```sh
./mvnw test        # Windows: mvnw.cmd test
```

One test class per bug: `./mvnw test -Dtest=Bug01SignalTenantRestrictionTest`.

The build fails on purpose. Each bug test asserts the behaviour the API describes, so it fails while the bug exists. The tests named `observed_*` pass: they record what the adapter and the engine do and are not bug tests. Full output, with stack traces, is written to `target/surefire-reports/`.

Every test starts a new engine (`EngineTestSupport`) and calls the adapter classes directly, without Spring: `SignalApiImpl`, `C7UserTaskCompletionApiImpl` and `StartProcessApiImpl`, each with the adapter's `EngineCommandExecutor`.

## Testing a fix

`-Dadapter.version` runs the tests against another published adapter release, for example `./mvnw test -Dadapter.version=2026.07.1`. For an unreleased fix, install the adapter from a clone of process-engine-adapters-camunda-7 and pass the version of that clone's root `pom.xml`:

```sh
./mvnw install -DskipTests -pl engine-adapter/c7-embedded-core -am   # in the adapter clone
./mvnw test -Dadapter.version=2026.09.2-SNAPSHOT                     # here, with that version
```

With the three bugs fixed, the five bug tests pass and the three `observed_*` tests of issue 01 fail, because they record the behaviour of 2026.09.1.

## Tests and results on 2026.09.1

| Test | Issue | Result | What it shows |
|---|---|---|---|
| `Bug01SignalTenantRestrictionTest.tenantIdAloneSendsTheSignalToThatTenant` | 01 | error | `get()` throws `ExecutionException` caused by `IllegalArgumentException: Illegal restriction combination. withoutTenantId and withoutTenantId can't be provided in the same time because they are mutually exclusive.` |
| `Bug01SignalTenantRestrictionTest.withoutTenantIdAloneSendsTheSignalWithoutTenant` | 01 | error | the same exception for `withoutTenantId` alone |
| `Bug01SignalTenantRestrictionTest.observed_tenantIdAlone_failsBeforeSend` | 01 | passes | the adapter calls `createSignalEvent(mySignal)` and `tenantId(tenant-a)` on the builder, then the check throws; `send()` is never called and no instance receives the signal |
| `Bug01SignalTenantRestrictionTest.observed_bothKeys_tenantIdFirst_deliversToTenantOnly` | 01 | passes | with both keys the check passes, `tenantId(tenant-a)`, `withoutTenantId()` and `send()` are called, and only the tenant-a instance receives the signal |
| `Bug01SignalTenantRestrictionTest.observed_bothKeys_withoutTenantIdFirst_deliversToTenantOnly` | 01 | passes | the same with the keys in the other order |
| `Bug02UserTaskCompleteByErrorTest.completeTaskByErrorPassesErrorMessageAndPayload` | 02 | failure | the boundary event is taken and `errorCode` is `REJECTED`, but `errorMessage` and the payload variable `rejectionReason` are `null`, and the payload supplier is never called |
| `Bug02UserTaskCompleteByErrorTest.observed_engineHandleBpmnErrorWithMessageAndVariables` | 02 | passes | `TaskService.handleBpmnError(taskId, errorCode, errorMessage, variables)` on the same model sets `errorMessage` and `rejectionReason` |
| `Bug03ProcessDefinitionKeyMetaTest.startByDefinitionReturnsTheDefinitionKey` | 03 | failure | `meta[processDefinitionKey]` is `approval_process:1:3`, the definition id, instead of `approval_process` |
| `Bug03ProcessDefinitionKeyMetaTest.startByMessageReturnsTheDefinitionKey` | 03 | failure | the same when the process is started by message |

The signal tests wrap `RuntimeService` in `RecordingRuntimeService`, which records every call the adapter makes on the signal builder. The process models are in `src/test/resources/`: `signal-wait.bpmn`, deployed once for tenant-a and once without tenant; `user-task-error.bpmn`, whose error boundary event stores the error code and message in the variables `errorCode` and `errorMessage`; and `approval.bpmn`, with a none start event and a message start event.
