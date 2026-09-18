# Embedded completeTaskByError for user tasks ignores errorMessage and payload

In `c7-embedded-core`, `C7UserTaskCompletionApiImpl.completeTaskByError` passes only the task id and the error code to the engine ([C7UserTaskCompletionApiImpl.kt#L47-L50](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7UserTaskCompletionApiImpl.kt#L47-L50)). The `errorMessage` and the payload of `CompleteTaskByErrorCmd` are never used. A user task handler that completes a task with a BPMN error therefore loses its error message and variables with the embedded adapter. The remote implementation passes both to the engine (see Expected behaviour).

### Steps to reproduce

* Library version: `process-engine-adapter-camunda-platform-c7-embedded-core` 2026.09.1 (latest release), process-engine-api 1.7, Camunda 7.24.0. The line links point to commit `d2be36e` on `develop` for the adapter and `b025698` for process-engine-api; every linked file is identical in 2026.09.1 and 1.7.
* JDK version: Eclipse Temurin 21.0.12.1+1 (build 21.0.12.1+1-LTS), a Java version Camunda 7.24 lists as supported ([Supported Environments, Java](https://docs.camunda.org/manual/7.24/introduction/supported-environments/#java)); the reproducer compiles for Java 21
* Operating system: Windows 10 Pro, build 10.0.19045.6466
* Complete executable reproducer: `reproducer/`, a Maven project with an embedded engine on in-memory H2 (link to follow when published). Run `./mvnw test -Dtest=Bug02UserTaskCompleteByErrorTest`.
* Steps: use a process with a user task that has an error boundary event for the error code `REJECTED`, followed by a second user task. The error event definition stores the error message in a process variable (`camunda:errorMessageVariable="errorMessage"`), which is how the lost message is observed. The model is `reproducer/src/test/resources/user-task-error.bpmn`.

```kotlin
userTaskCompletionApi.completeTaskByError(
  CompleteTaskByErrorCmd(
    taskId = taskId,
    errorCode = "REJECTED",
    errorMessage = "Document incomplete",
    payloadSupplier = { mapOf("rejectionReason" to "missing signature") },
  )
).get()

val next = taskService.createTaskQuery().processInstanceId(processInstanceId).singleResult()
taskService.getVariables(next.id) // rejectionReason was not set by the call above
```

### Expected behaviour

The error message and the payload are passed to the engine together with the error code, as in the embedded external task implementation ([C7ServiceTaskCompletionApiImpl.kt#L47-L53](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7ServiceTaskCompletionApiImpl.kt#L47-L53)) and the remote user task implementation ([UserTaskCompletionApiImpl.kt#L47-L54](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/task/completion/UserTaskCompletionApiImpl.kt#L47-L54)).

The engine method for this is `TaskService.handleBpmnError(taskId, errorCode, errorMessage, variables)`. Called directly with the same arguments on the same process model, it sets `errorMessage` to `Document incomplete` and `rejectionReason` to `missing signature` on the next task (reproducer test `observed_engineHandleBpmnErrorWithMessageAndVariables`).

### Actual behaviour

In the reproducer, the error code reaches the engine: the boundary event is taken, and the next task sees `errorCode` = `REJECTED`. The error message and the payload do not reach it. The test `completeTaskByErrorPassesErrorMessageAndPayload` fails with:

```
org.opentest4j.AssertionFailedError: errorMessage variable ==> expected: <Document incomplete> but was: <null>
org.opentest4j.AssertionFailedError: payload variable rejectionReason ==> expected: <missing signature> but was: <null>
org.opentest4j.AssertionFailedError: payload supplier called ==> expected: <true> but was: <false>
```

The adapter calls `taskService.handleBpmnError(cmd.taskId, cmd.errorCode)`. It never reads `cmd.errorMessage` and never calls the payload supplier (`cmd.get()`).

`CompleteTaskByErrorCmd` defines both fields ([CompleteTaskByErrorCmd.kt#L10-L27](https://github.com/bpm-crafters/process-engine-api/blob/b02569855596de4fb423dc181489e72595235503/api/src/main/kotlin/dev/bpmcrafters/processengineapi/task/CompleteTaskByErrorCmd.kt#L10-L27)). No test in the adapter repository calls `completeTaskByError`.
