# Draft issue 02

**Proposed title:** Embedded `C7UserTaskCompletionApiImpl.completeTaskByError` ignores error message and payload

**Repository:** `bpm-crafters/process-engine-adapters-camunda-7`
**Verified against:** commit `d2be36eca2edf24d1e1a43540cee77d9e9dffd21` (upstream `HEAD` on 2026-09-17)
**Affected module:** `engine-adapter/c7-embedded-core`
**Affected class:** `dev.bpmcrafters.processengineapi.adapter.c7.embedded.task.completion.C7UserTaskCompletionApiImpl`, method `completeTaskByError`
- `engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7UserTaskCompletionApiImpl.kt:44-59`

## Expected behaviour

`CompleteTaskByErrorCmd` carries an optional `errorMessage` and a payload supplier (`process-engine-api`, `api/src/main/kotlin/dev/bpmcrafters/processengineapi/task/CompleteTaskByErrorCmd.kt:10-27`). When a user task is completed by BPMN error, both should reach the engine together with the error code.

Two other places in the adapter pass all three:
- the embedded external-task implementation: `externalTaskService.handleBpmnError(cmd.taskId, workerId, cmd.errorCode, cmd.errorMessage, cmd.get())` (`engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/task/completion/C7ServiceTaskCompletionApiImpl.kt:47-53`);
- the remote user-task implementation, which sets `errorCode`, `errorMessage` and `variables` on `TaskBpmnErrorDto` (`engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/task/completion/UserTaskCompletionApiImpl.kt:47-54`).

## Actual behaviour

Only the task id and error code are passed:

```kotlin
taskService.handleBpmnError(
  cmd.taskId,
  cmd.errorCode
)                                   // C7UserTaskCompletionApiImpl.kt:47-50
```

`cmd.errorMessage` is not read, and the payload supplier (`cmd.get()`) is never called, so none of the payload variables are set by this call. No test in the adapter repository calls `completeTaskByError`.

## Reproduction sketch

Spring Boot application with the Camunda 7 embedded adapter:
- `userTaskCompletionApi` is the injected `dev.bpmcrafters.processengineapi.task.UserTaskCompletionApi`;
- `taskService` is `org.camunda.bpm.engine.TaskService` of the same engine.

The process has a user task with an error boundary event for code `REJECTED`, followed by a second user task.

```kotlin
import dev.bpmcrafters.processengineapi.task.CompleteTaskByErrorCmd

userTaskCompletionApi.completeTaskByError(
  CompleteTaskByErrorCmd(
    taskId = taskId,
    errorCode = "REJECTED",
    errorMessage = "Document incomplete",
    payloadSupplier = { mapOf("rejectionReason" to "missing signature") },
  )
).get()

val next = taskService.createTaskQuery().processInstanceId(processInstanceId).singleResult()
taskService.getVariables(next.id)
// expected: contains "rejectionReason" -> "missing signature"
// actual:   "rejectionReason" was not set by the error call
```

The same call through the remote adapter sends `errorMessage` and the variables.

## Impact

User-task handlers that complete a task by BPMN error lose the error message and all payload variables with the embedded adapter, while the same call keeps them with the remote adapter and for external tasks.
