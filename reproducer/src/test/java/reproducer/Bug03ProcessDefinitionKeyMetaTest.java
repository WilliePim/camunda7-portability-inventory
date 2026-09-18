package reproducer;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import dev.bpmcrafters.processengineapi.CommonRestrictions;
import dev.bpmcrafters.processengineapi.adapter.c7.embedded.process.StartProcessApiImpl;
import dev.bpmcrafters.processengineapi.process.ProcessInformation;
import dev.bpmcrafters.processengineapi.process.StartProcessByDefinitionCmd;
import dev.bpmcrafters.processengineapi.process.StartProcessByMessageCmd;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Issue 03: the embedded StartProcessApiImpl returns the process definition id as processDefinitionKey.
 *
 * <p>approval.bpmn: process key approval_process, with a none start event and a message start event
 * for the message approval_requested.
 */
class Bug03ProcessDefinitionKeyMetaTest extends EngineTestSupport {

  private StartProcessApiImpl startProcessApi;
  private String definitionId;

  @BeforeEach
  void setUp() {
    deploy("approval.bpmn", null);
    definitionId = repositoryService.createProcessDefinitionQuery()
        .processDefinitionKey("approval_process").singleResult().getId();
    startProcessApi = new StartProcessApiImpl(runtimeService, repositoryService, commandExecutor);
  }

  /** Fails against 2026.09.1: meta[processDefinitionKey] holds the definition id. */
  @Test
  void startByDefinitionReturnsTheDefinitionKey() throws Exception {
    ProcessInformation info = startProcessApi.startProcess(new StartProcessByDefinitionCmd("approval_process")).get();

    assertKeyAndId(info);
  }

  /** Fails against 2026.09.1 in the same way: both start paths build the meta with toProcessInformation(). */
  @Test
  void startByMessageReturnsTheDefinitionKey() throws Exception {
    ProcessInformation info = startProcessApi.startProcess(new StartProcessByMessageCmd("approval_requested")).get();

    assertKeyAndId(info);
  }

  private void assertKeyAndId(ProcessInformation info) {
    String key = info.getMeta().get(CommonRestrictions.PROCESS_DEFINITION_KEY);
    assertAll(
        () -> assertEquals("approval_process", key, "meta[processDefinitionKey] is the key"),
        () -> assertNotEquals(definitionId, key, "meta[processDefinitionKey] is not the definition id " + definitionId),
        () -> assertEquals(definitionId, info.getMeta().get(CommonRestrictions.PROCESS_DEFINITION_ID),
            "meta[processDefinitionId] is the definition id"));
  }
}
