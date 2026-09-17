# Embedded StartProcessApiImpl returns the process definition id as processDefinitionKey

### Describe the bug

In `c7-embedded-core`, `ProcessInstance.toProcessInformation()` stores `processDefinitionId` under the `processDefinitionKey` meta key ([StartProcessApiImpl.kt#L126](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/process/StartProcessApiImpl.kt#L126)). The `ProcessInformation` returned by `startProcess` therefore has the definition id under both `processDefinitionKey` and `processDefinitionId`, while the remote adapter returns the definition key. Code that reads `processDefinitionKey` gets a different value depending on which adapter is used.

### To Reproduce

Deploy a process with the key `approval_process`, then start it:

```kotlin
val info = startProcessApi.startProcess(
  StartProcessByDefinitionCmd(
    definitionKey = "approval_process",
    payloadSupplier = { emptyMap() },
  )
).get()

info.meta[CommonRestrictions.PROCESS_DEFINITION_KEY] // returns the definition id, not "approval_process"
```

Starting by message with `StartProcessByMessageCmd` gives the same result, because both paths use `toProcessInformation` (lines 49, 55 and 72).

### Expected behavior

`processDefinitionKey` holds the BPMN process id (`approval_process`), and `processDefinitionId` holds the id of the deployed definition (for example `approval_process:912834729348`). Three sources agree on this:

- the constants in `CommonRestrictions` ([CommonRestrictions.kt#L24-L37](https://github.com/bpm-crafters/process-engine-api/blob/b02569855596de4fb423dc181489e72595235503/api/src/main/kotlin/dev/bpmcrafters/processengineapi/CommonRestrictions.kt#L24-L37));
- the examples in the adapter docs ([reference-c7-embedded.md#L186-L187](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/docs/reference-c7-embedded.md?plain=1#L186-L187));
- the remote adapter ([StartProcessApiImpl.kt#L149](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImpl.kt#L149)), whose test checks this ([StartProcessApiImplByMessageTest.kt#L88](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImplByMessageTest.kt#L88)).

### Actual behavior

Both keys contain the definition id:

```kotlin
CommonRestrictions.PROCESS_DEFINITION_KEY to this.processDefinitionId,   // line 126
...
CommonRestrictions.PROCESS_DEFINITION_ID to this.processDefinitionId,    // line 130
```

### Environment

- process-engine-adapters-camunda-7: commit `d2be36e`, the latest on `develop` as of 2026-09-17
- Module: `c7-embedded-core`
- process-engine-api: 1.7 (the version set in the adapter's `pom.xml`)

### Additional context

The start-at-element paths read the definition id back from the `processDefinitionKey` entry and pass it to `runtimeService.createModification(...)` (lines 84-85 and 101-102). A fix on line 126 also needs to change those lines to use `PROCESS_DEFINITION_ID`. No embedded test checks the meta of a started process instance.
