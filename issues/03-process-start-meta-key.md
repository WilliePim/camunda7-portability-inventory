# Embedded StartProcessApiImpl returns the process definition id as processDefinitionKey

In `c7-embedded-core`, `ProcessInstance.toProcessInformation()` stores `processDefinitionId` under the `processDefinitionKey` meta key ([StartProcessApiImpl.kt#L126](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/process/StartProcessApiImpl.kt#L126)). The `ProcessInformation` returned by `startProcess` therefore has the definition id under both `processDefinitionKey` and `processDefinitionId`. The remote adapter sets `processDefinitionKey` from the definition key (see Expected behaviour), so code that reads `processDefinitionKey` gets a different value depending on which adapter is used.

### Steps to reproduce

* Library version: `process-engine-adapter-camunda-platform-c7-embedded-core` 2026.09.1 (latest release), process-engine-api 1.7, Camunda 7.24.0. The line links point to commit `d2be36e` on `develop` for the adapter and `b025698` for process-engine-api; every linked file is identical in 2026.09.1 and 1.7.
* JDK version: Eclipse Temurin 21.0.12.1+1 (build 21.0.12.1+1-LTS), a Java version Camunda 7.24 lists as supported ([Supported Environments, Java](https://docs.camunda.org/manual/7.24/introduction/supported-environments/#java)); the reproducer compiles for Java 21
* Operating system: Windows 10 Pro, build 10.0.19045.6466
* Complete executable reproducer: `reproducer/`, a Maven project with an embedded engine on in-memory H2 (link to follow when published). Run `./mvnw test -Dtest=Bug03ProcessDefinitionKeyMetaTest`.
* Steps: deploy a process with the key `approval_process`, then start it:

```kotlin
val info = startProcessApi.startProcess(
  StartProcessByDefinitionCmd(
    definitionKey = "approval_process",
    payloadSupplier = { emptyMap() },
  )
).get()

info.meta[CommonRestrictions.PROCESS_DEFINITION_KEY] // "approval_process:1:3" in the reproducer: the definition id, not "approval_process"
```

The reproducer shows the same result when the process is started by message with `StartProcessByMessageCmd`; both paths use `toProcessInformation` (lines 49, 55 and 72).

### Expected behaviour

`processDefinitionKey` holds the BPMN process id (`approval_process`), and `processDefinitionId` holds the id of the deployed definition (`approval_process:1:3` in the reproducer). Three sources agree on this:

- the constants in `CommonRestrictions` ([CommonRestrictions.kt#L24-L37](https://github.com/bpm-crafters/process-engine-api/blob/b02569855596de4fb423dc181489e72595235503/api/src/main/kotlin/dev/bpmcrafters/processengineapi/CommonRestrictions.kt#L24-L37));
- the examples in the adapter docs ([reference-c7-embedded.md#L186-L187](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/docs/reference-c7-embedded.md?plain=1#L186-L187));
- the remote adapter ([StartProcessApiImpl.kt#L149](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImpl.kt#L149)), whose test checks this ([StartProcessApiImplByMessageTest.kt#L88](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/process/StartProcessApiImplByMessageTest.kt#L88)).

### Actual behaviour

In the reproducer, both keys contain the definition id, for a start by definition key and for a start by message. Both tests fail with:

```
org.opentest4j.AssertionFailedError: meta[processDefinitionKey] is the key ==> expected: <approval_process> but was: <approval_process:1:3>
org.opentest4j.AssertionFailedError: meta[processDefinitionKey] is not the definition id approval_process:1:3 ==> expected: not equal but was: <approval_process:1:3>
```

`meta[processDefinitionId]` is `approval_process:1:3` as well. The source sets both keys from the same property:

```kotlin
CommonRestrictions.PROCESS_DEFINITION_KEY to this.processDefinitionId,   // line 126
...
CommonRestrictions.PROCESS_DEFINITION_ID to this.processDefinitionId,    // line 130
```

The start-at-element paths read the definition id back from the `processDefinitionKey` entry and pass it to `runtimeService.createModification(...)` (lines 84-85 and 101-102). A fix on line 126 also needs to change those lines to use `PROCESS_DEFINITION_ID`. The fix changes the value that existing callers of the embedded adapter receive under `processDefinitionKey`, from the definition id to the definition key. No embedded test checks the meta of a started process instance.
