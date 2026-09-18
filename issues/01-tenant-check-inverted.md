# Embedded SignalApiImpl rejects tenantId or withoutTenantId when used alone

In `c7-embedded-core`, `SignalApiImpl.applyRestrictions` checks the tenant restrictions the wrong way round. Each `require` expects the other key to be present instead of absent ([SignalApiImpl.kt#L47-L59](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImpl.kt#L47-L59)). Because of this, a signal can't be sent with only `tenantId` or only `withoutTenantId`, so tenant-scoped signals don't work with the embedded adapter.

### Steps to reproduce

* Library version: `process-engine-adapter-camunda-platform-c7-embedded-core` 2026.09.1 (latest release), process-engine-api 1.7, Camunda 7.24.0. The line links point to commit `d2be36e` on `develop`; every linked file is identical in 2026.09.1.
* JDK version: Eclipse Temurin 21.0.12.1+1 (build 21.0.12.1+1-LTS), a Java version Camunda 7.24 lists as supported ([Supported Environments, Java](https://docs.camunda.org/manual/7.24/introduction/supported-environments/#java)); the reproducer compiles for Java 21
* Operating system: Windows 10 Pro, build 10.0.19045.6466
* Complete executable reproducer: [reproducer/](https://github.com/WilliePim/camunda7-portability-inventory/tree/main/reproducer), a Maven project with an embedded engine on in-memory H2. In that folder, with `JAVA_HOME` pointing to a JDK 21, run `./mvnw test -Dtest=Bug01SignalTenantRestrictionTest`.
* Steps: send a signal with a single tenant restriction through the embedded adapter:

```kotlin
signalApi.sendSignal(
  SendSignalCmd(
    signalName = "mySignal",
    payloadSupplier = { emptyMap() },
    restrictions = mapOf(CommonRestrictions.TENANT_ID to "tenant-a"),
  )
).get()
```

The reproducer shows the same with `mapOf(CommonRestrictions.WITHOUT_TENANT_ID to "true")`.

### Expected behaviour

`tenantId` alone sends the signal for that tenant, `withoutTenantId` alone sends it without a tenant, and only a combination of both keys is rejected.

The embedded message correlation already works this way ([MessageCorrelationBuilderExtensions.kt#L16-L23](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/MessageCorrelationBuilderExtensions.kt#L16-L23)), and so does the remote `SignalApiImpl` ([SignalApiImpl.kt#L51-L63](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImpl.kt#L51-L63)). The remote test sends a signal with `tenantId` alone ([SignalApiImplTest.kt#L42-L55](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/correlation/SignalApiImplTest.kt#L42-L55)).

### Actual behaviour

In the reproducer, `get()` throws an `ExecutionException` caused by `IllegalArgumentException: Illegal restriction combination. ...`. The check runs inside `EngineCommandExecutor.execute`, which uses `CompletableFuture.supplyAsync` ([EngineCommandExecutor.kt#L30](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/shared/EngineCommandExecutor.kt#L30)), so the future completes exceptionally. Stack trace, as Surefire records it for `tenantIdAloneSendsTheSignalToThatTenant`:

```
java.util.concurrent.ExecutionException: java.lang.IllegalArgumentException: Illegal restriction combination. withoutTenantId and withoutTenantId can't be provided in the same time because they are mutually exclusive.
	at java.base/java.util.concurrent.CompletableFuture.reportGet(CompletableFuture.java:396)
	at java.base/java.util.concurrent.CompletableFuture.get(CompletableFuture.java:2073)
	at reproducer.Bug01SignalTenantRestrictionTest.tenantIdAloneSendsTheSignalToThatTenant(Bug01SignalTenantRestrictionTest.java:47)
	at java.base/java.lang.reflect.Method.invoke(Method.java:580)
	at java.base/java.util.ArrayList.forEach(ArrayList.java:1596)
	at java.base/java.util.ArrayList.forEach(ArrayList.java:1596)
Caused by: java.lang.IllegalArgumentException: Illegal restriction combination. withoutTenantId and withoutTenantId can't be provided in the same time because they are mutually exclusive.
	at dev.bpmcrafters.processengineapi.adapter.c7.embedded.correlation.SignalApiImpl.applyRestrictions(SignalApiImpl.kt:48)
	at dev.bpmcrafters.processengineapi.adapter.c7.embedded.correlation.SignalApiImpl.sendSignal$lambda$1(SignalApiImpl.kt:30)
	at dev.bpmcrafters.processengineapi.adapter.c7.embedded.shared.EngineCommandExecutor.execute$lambda$0(EngineCommandExecutor.kt:30)
	at java.base/java.util.concurrent.CompletableFuture$AsyncSupply.run(CompletableFuture.java:1768)
	at java.base/java.util.concurrent.CompletableFuture$AsyncSupply.exec(CompletableFuture.java:1760)
	at java.base/java.util.concurrent.ForkJoinTask.doExec(ForkJoinTask.java:387)
	at java.base/java.util.concurrent.ForkJoinPool$WorkQueue.topLevelExec(ForkJoinPool.java:1312)
	at java.base/java.util.concurrent.ForkJoinPool.scan(ForkJoinPool.java:1843)
	at java.base/java.util.concurrent.ForkJoinPool.runWorker(ForkJoinPool.java:1808)
	at java.base/java.util.concurrent.ForkJoinWorkerThread.run(ForkJoinWorkerThread.java:188)
```

The check fails before the signal reaches the engine. A recording wrapper around `RuntimeService` shows that the adapter creates the builder with `createSignalEvent("mySignal")`, calls `tenantId("tenant-a")` on it, and then the `require` throws: `send()` is never called, and neither waiting instance receives the signal.

Passing both keys gets past the check. The adapter then calls `tenantId("tenant-a")`, `withoutTenantId()` and `send()` on the builder, no error is raised, and the signal reaches only the instance deployed for tenant-a, not the instance deployed without a tenant. The order of the two keys makes no difference.

The error message names `withoutTenantId` twice (lines 49-50 and 56-57). The embedded `SignalApiImplTest` has no test with tenant restrictions ([SignalApiImplTest.kt#L33-L49](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/test/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/correlation/SignalApiImplTest.kt#L33-L49)).
