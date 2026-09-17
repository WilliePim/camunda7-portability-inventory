# Draft issue 01

**Proposed title:** Embedded `SignalApiImpl` rejects `tenantId` or `withoutTenantId` used alone

**Repository:** `bpm-crafters/process-engine-adapters-camunda-7`
**Verified against:** commit `d2be36eca2edf24d1e1a43540cee77d9e9dffd21` (upstream `HEAD` on 2026-09-17)
**Affected module:** `engine-adapter/c7-embedded-core`
**Affected class:** `dev.bpmcrafters.processengineapi.adapter.c7.embedded.correlation.SignalApiImpl`, method `applyRestrictions`
- `engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImpl.kt:47-59`

## Expected behaviour

Both keys are listed as supported restrictions (`SignalApiImpl.kt:37-41`), and they are mutually exclusive:
- `tenantId` alone sends the signal with `SignalEventReceivedBuilder.tenantId(value)`;
- `withoutTenantId` alone sends it with `withoutTenantId()`;
- the command is rejected only when both keys are present.

Two other places in the adapter already behave this way:
- the embedded message-correlation code checks for the *absence* of the other key (`engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/MessageCorrelationBuilderExtensions.kt:16-23`);
- the remote `SignalApiImpl` does the same (`engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImpl.kt:51-63`), and its test sends a signal with `tenantId` alone (`engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImplTest.kt:42-55`).

## Actual behaviour

The `require` conditions are not negated:

```kotlin
CommonRestrictions.TENANT_ID -> this.tenantId(value).apply {
  require(restrictions.containsKey(CommonRestrictions.WITHOUT_TENANT_ID)) { ... }   // line 48
}
CommonRestrictions.WITHOUT_TENANT_ID -> this.withoutTenantId().apply {
  require(restrictions.containsKey(CommonRestrictions.TENANT_ID)) { ... }           // line 55
}
```

As a result:
- `tenantId` alone fails with `IllegalArgumentException`.
- `withoutTenantId` alone fails with `IllegalArgumentException`.
- Both keys together pass both checks, and the builder receives both `tenantId(value)` and `withoutTenantId()`.

The check runs inside `EngineCommandExecutor.execute`, which uses `CompletableFuture.supplyAsync` (`engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/shared/EngineCommandExecutor.kt:30`). The returned future therefore completes exceptionally, and `get()` throws `ExecutionException`.

The error message also names the same key twice: it interpolates `WITHOUT_TENANT_ID` in both places (`SignalApiImpl.kt:49-50`, `:56-57`).

The embedded `SignalApiImplTest` has no case with tenant restrictions (`engine-adapter/c7-embedded-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImplTest.kt:33-49`).

## Reproduction sketch

Spring Boot application with the Camunda 7 embedded adapter. `signalApi` is the injected `dev.bpmcrafters.processengineapi.correlation.SignalApi`.

```kotlin
import dev.bpmcrafters.processengineapi.CommonRestrictions
import dev.bpmcrafters.processengineapi.correlation.SendSignalCmd

// 1. tenantId alone: expected to send, actually throws
signalApi.sendSignal(
  SendSignalCmd(
    signalName = "mySignal",
    payloadSupplier = { emptyMap() },
    restrictions = mapOf(CommonRestrictions.TENANT_ID to "tenant-a"),
  )
).get() // ExecutionException, cause IllegalArgumentException("Illegal restriction combination. ...")

// 2. withoutTenantId alone: expected to send, actually throws
signalApi.sendSignal(
  SendSignalCmd(
    signalName = "mySignal",
    payloadSupplier = { emptyMap() },
    restrictions = mapOf(CommonRestrictions.WITHOUT_TENANT_ID to "true"),
  )
).get() // ExecutionException, cause IllegalArgumentException

// 3. both keys: expected to be rejected, actually passes the adapter's checks
signalApi.sendSignal(
  SendSignalCmd(
    signalName = "mySignal",
    payloadSupplier = { emptyMap() },
    restrictions = mapOf(
      CommonRestrictions.TENANT_ID to "tenant-a",
      CommonRestrictions.WITHOUT_TENANT_ID to "true",
    ),
  )
).get()
```

## Impact

With the embedded adapter, a signal cannot be scoped by tenant: `tenantId` or `withoutTenantId` alone always fails, and the only combination the adapter accepts contains both mutually exclusive keys.
