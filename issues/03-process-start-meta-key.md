# Draft issue 03

**Proposed title:** Embedded `StartProcessApiImpl` writes the process definition id under the `processDefinitionKey` meta key

**Repository:** `bpm-crafters/process-engine-adapters-camunda-7`
**Verified against:** commit `d2be36eca2edf24d1e1a43540cee77d9e9dffd21` (upstream `HEAD` on 2026-09-17)
**Affected module:** `engine-adapter/c7-embedded-core`
**Affected class:** `dev.bpmcrafters.processengineapi.adapter.c7.embedded.process.StartProcessApiImpl` (file-level function `ProcessInstance.toProcessInformation`)
- `engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/process/StartProcessApiImpl.kt:123-132`, key at line 126

## Expected behaviour

In the `ProcessInformation.meta` returned by `startProcess`, `processDefinitionKey` holds the process definition key (the BPMN process id), and `processDefinitionId` holds the id of the deployed definition. `process-engine-api` defines the two keys this way:
- `PROCESS_DEFINITION_KEY`: "Definition attribute of a BPMN process from XML holding the id of the element." (`api/src/main/kotlin/dev/bpmcrafters/processengineapi/CommonRestrictions.kt:24-27`);
- `PROCESS_DEFINITION_ID`: "Id provided by the runtime to identify a deployed process definition." (`CommonRestrictions.kt:34-37`).

The adapter docs describe `processDefinitionKey` with the example `approval_process`, and `processDefinitionId` with `approval_process:912834729348` (`docs/reference-c7-embedded.md:186-187`).

The remote adapter follows this:
- it writes `definitionKey` under `PROCESS_DEFINITION_KEY` (`engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImpl.kt:149`, `:159`);
- its test asserts the result (`engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImplByMessageTest.kt:88`).

## Actual behaviour

The embedded adapter writes `processDefinitionId` under both keys:

```kotlin
fun ProcessInstance.toProcessInformation() = ProcessInformation(
  instanceId = this.id,
  meta = metaOf(
    CommonRestrictions.PROCESS_DEFINITION_KEY to this.processDefinitionId,   // line 126
    ...
    CommonRestrictions.PROCESS_DEFINITION_ID to this.processDefinitionId,    // line 130
  )
)
```

The start-at-element paths rely on this. They read the id back from the `processDefinitionKey` entry and pass it to `runtimeService.createModification(...)` (`StartProcessApiImpl.kt:84-85` and `:101-102`). A fix at line 126 therefore also needs to change those lines to read `PROCESS_DEFINITION_ID`.

No embedded test asserts the `ProcessInformation.meta` of a started instance.

## Reproduction sketch

Spring Boot application with the Camunda 7 embedded adapter. `startProcessApi` is the injected `dev.bpmcrafters.processengineapi.process.StartProcessApi`, and a process with key `approval_process` is deployed.

```kotlin
import dev.bpmcrafters.processengineapi.CommonRestrictions
import dev.bpmcrafters.processengineapi.process.StartProcessByDefinitionCmd

val info = startProcessApi.startProcess(
  StartProcessByDefinitionCmd(
    definitionKey = "approval_process",
    payloadSupplier = { emptyMap() },
  )
).get()

info.meta[CommonRestrictions.PROCESS_DEFINITION_KEY]
// expected: "approval_process"
// actual:   the process definition id, equal to info.meta[CommonRestrictions.PROCESS_DEFINITION_ID]
```

`StartProcessByMessageCmd` returns the same meta, because both start paths use `toProcessInformation` (`StartProcessApiImpl.kt:49`, `:55`, `:72`).

## Impact

Code that reads `processDefinitionKey` from `ProcessInformation.meta` receives the definition id with the embedded adapter and the definition key with the remote adapter.
