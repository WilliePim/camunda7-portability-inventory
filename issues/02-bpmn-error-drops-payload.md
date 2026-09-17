# Embedded completeTaskByError for user tasks ignores errorMessage and payload

### Describe the bug

In `c7-embedded-core`, `C7UserTaskCompletionApiImpl.completeTaskByError` passes only the task id and the error code to the engine ([C7UserTaskCompletionApiImpl.kt#L47-L50](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7UserTaskCompletionApiImpl.kt#L47-L50)). The `errorMessage` and the payload of `CompleteTaskByErrorCmd` are never used. A user task handler that completes a task with a BPMN error therefore loses its error message and variables with the embedded adapter, but keeps them with the remote adapter.

### To Reproduce

Use a process with a user task that has an error boundary event for the error code `REJECTED`, followed by a second user task.

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

### Expected behavior

The error message and the payload are passed to the engine together with the error code, as in the embedded external task implementation ([C7ServiceTaskCompletionApiImpl.kt#L47-L53](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7ServiceTaskCompletionApiImpl.kt#L47-L53)) and the remote user task implementation ([UserTaskCompletionApiImpl.kt#L47-L54](https://github.com/bpm-crafters/process-engine-adapters-camunda-7/blob/d2be36eca2edf24d1e1a43540cee77d9e9dffd21/engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/task/completion/UserTaskCompletionApiImpl.kt#L47-L54)).

### Actual behavior

The adapter calls `taskService.handleBpmnError(cmd.taskId, cmd.errorCode)`. It never reads `cmd.errorMessage` and never calls the payload supplier (`cmd.get()`).

### Environment

- process-engine-adapters-camunda-7: commit `d2be36e`, the latest on `develop` as of 2026-09-17
- Module: `c7-embedded-core`
- process-engine-api: 1.7 (the version set in the adapter's `pom.xml`)

### Additional context

`CompleteTaskByErrorCmd` defines both fields ([CompleteTaskByErrorCmd.kt#L10-L27](https://github.com/bpm-crafters/process-engine-api/blob/b02569855596de4fb423dc181489e72595235503/api/src/main/kotlin/dev/bpmcrafters/processengineapi/task/CompleteTaskByErrorCmd.kt#L10-L27)). No test in the adapter repository calls `completeTaskByError`.
