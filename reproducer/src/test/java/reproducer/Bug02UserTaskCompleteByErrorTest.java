package reproducer;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import dev.bpmcrafters.processengineapi.adapter.c7.embedded.task.completion.C7UserTaskCompletionApiImpl;
import dev.bpmcrafters.processengineapi.impl.task.InMemSubscriptionRepository;
import dev.bpmcrafters.processengineapi.task.CompleteTaskByErrorCmd;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;
import org.camunda.bpm.engine.task.Task;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Issue 02: the embedded completeTaskByError for user tasks ignores errorMessage and payload.
 *
 * <p>user-task-error.bpmn: user task "review" with an error boundary event for code REJECTED that stores the
 * error code and message in the variables errorCode and errorMessage, followed by the user task "rework".
 */
class Bug02UserTaskCompleteByErrorTest extends EngineTestSupport {

  private C7UserTaskCompletionApiImpl userTaskCompletionApi;
  private String processInstanceId;
  private String reviewTaskId;

  @BeforeEach
  void setUp() {
    deploy("user-task-error.bpmn", null);
    processInstanceId = runtimeService.startProcessInstanceByKey("review_process").getId();
    reviewTaskId = taskService.createTaskQuery().processInstanceId(processInstanceId).singleResult().getId();
    userTaskCompletionApi = new C7UserTaskCompletionApiImpl(taskService, new InMemSubscriptionRepository(), commandExecutor);
  }

  /** Fails against 2026.09.1: the error code reaches the engine, the message and the payload do not. */
  @Test
  void completeTaskByErrorPassesErrorMessageAndPayload() throws Exception {
    AtomicBoolean payloadSupplierCalled = new AtomicBoolean(false);

    userTaskCompletionApi.completeTaskByError(new CompleteTaskByErrorCmd(
        reviewTaskId,
        "REJECTED",
        "Document incomplete",
        () -> {
          payloadSupplierCalled.set(true);
          return Map.of("rejectionReason", "missing signature");
        })).get();

    Task next = taskService.createTaskQuery().processInstanceId(processInstanceId).singleResult();
    Map<String, Object> variables = taskService.getVariables(next.getId());
    assertAll(
        () -> assertEquals("rework", next.getTaskDefinitionKey(), "error boundary event taken"),
        () -> assertEquals("REJECTED", variables.get("errorCode"), "errorCode variable"),
        () -> assertEquals("Document incomplete", variables.get("errorMessage"), "errorMessage variable"),
        () -> assertEquals("missing signature", variables.get("rejectionReason"), "payload variable rejectionReason"),
        () -> assertTrue(payloadSupplierCalled.get(), "payload supplier called"));
  }

  /**
   * Passes against 2026.09.1: the engine call the fix needs, TaskService.handleBpmnError(taskId, errorCode,
   * errorMessage, variables), delivers the message and the variables through the same process model.
   */
  @Test
  void observed_engineHandleBpmnErrorWithMessageAndVariables() {
    taskService.handleBpmnError(reviewTaskId, "REJECTED", "Document incomplete",
        Map.of("rejectionReason", "missing signature"));

    Task next = taskService.createTaskQuery().processInstanceId(processInstanceId).singleResult();
    Map<String, Object> variables = taskService.getVariables(next.getId());
    assertAll(
        () -> assertEquals("rework", next.getTaskDefinitionKey(), "error boundary event taken"),
        () -> assertEquals("REJECTED", variables.get("errorCode"), "errorCode variable"),
        () -> assertEquals("Document incomplete", variables.get("errorMessage"), "errorMessage variable"),
        () -> assertEquals("missing signature", variables.get("rejectionReason"), "payload variable rejectionReason"));
  }
}
