# Embedded SignalApiImpl rejects tenantId or withoutTenantId when used alone

### Describe the bug

In `c7-embedded-core`, `SignalApiImpl.applyRestrictions` checks the tenant restrictions the wrong way round. Each `require` expects the other key to be present instead of absent ([SignalApiImpl.kt#L47-L59](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImpl.kt#L47-L59)). Because of this, a signal can't be sent with only `tenantId` or only `withoutTenantId`, so tenant-scoped signals don't work with the embedded adapter.

### To Reproduce

Send a signal with a single tenant restriction through the embedded adapter:

```kotlin
signalApi.sendSignal(
  SendSignalCmd(
    signalName = "mySignal",
    payloadSupplier = { emptyMap() },
    restrictions = mapOf(CommonRestrictions.TENANT_ID to "tenant-a"),
  )
).get()
```

The same happens with `mapOf(CommonRestrictions.WITHOUT_TENANT_ID to "true")`.

### Expected behavior

`tenantId` alone sends the signal for that tenant, `withoutTenantId` alone sends it without a tenant, and only a combination of both keys is rejected.

The embedded message correlation already works this way ([MessageCorrelationBuilderExtensions.kt#L16-L23](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/MessageCorrelationBuilderExtensions.kt#L16-L23)), and so does the remote `SignalApiImpl` ([SignalApiImpl.kt#L51-L63](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImpl.kt#L51-L63)). The remote test sends a signal with `tenantId` alone ([SignalApiImplTest.kt#L42-L55](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImplTest.kt#L42-L55)).

### Actual behavior

`get()` throws an `ExecutionException` caused by `IllegalArgumentException: Illegal restriction combination. ...`. The check runs inside `EngineCommandExecutor.execute`, which uses `CompletableFuture.supplyAsync` ([EngineCommandExecutor.kt#L30](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/shared/EngineCommandExecutor.kt#L30)), so the future completes exceptionally.

Passing both keys gets past the check, and both `tenantId(...)` and `withoutTenantId()` are called on the builder.

### Environment

- process-engine-adapters-camunda-7: commit `d2be36e`, the latest on `develop` as of 2026-09-17
- Module: `c7-embedded-core`
- process-engine-api: 1.7 (the version set in the adapter's `pom.xml`)

### Additional context

The error message names `withoutTenantId` twice (lines 49-50 and 56-57). The embedded `SignalApiImplTest` has no test with tenant restrictions ([SignalApiImplTest.kt#L33-L49](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImplTest.kt#L33-L49)).
