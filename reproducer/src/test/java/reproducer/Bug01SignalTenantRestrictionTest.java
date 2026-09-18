package reproducer;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import dev.bpmcrafters.processengineapi.CommonRestrictions;
import dev.bpmcrafters.processengineapi.adapter.c7.embedded.correlation.SignalApiImpl;
import dev.bpmcrafters.processengineapi.correlation.SendSignalCmd;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Issue 01: the embedded SignalApiImpl rejects tenantId or withoutTenantId when used alone.
 *
 * <p>The same process waits for the signal twice: one instance deployed for tenant-a, one deployed without tenant.
 */
class Bug01SignalTenantRestrictionTest extends EngineTestSupport {

  private final List<String> builderCalls = new ArrayList<>();
  private SignalApiImpl signalApi;
  private String tenantInstance;
  private String noTenantInstance;

  @BeforeEach
  void setUp() {
    deploy("signal-wait.bpmn", "tenant-a");
    deploy("signal-wait.bpmn", null);
    tenantInstance = runtimeService.createProcessInstanceByKey("signal_wait")
        .processDefinitionTenantId("tenant-a").execute().getId();
    noTenantInstance = runtimeService.createProcessInstanceByKey("signal_wait")
        .processDefinitionWithoutTenantId().execute().getId();
    signalApi = new SignalApiImpl(RecordingRuntimeService.wrap(runtimeService, builderCalls), commandExecutor);
  }

  /** Fails against 2026.09.1: get() throws, see the stack trace in the test report. */
  @Test
  void tenantIdAloneSendsTheSignalToThatTenant() throws Exception {
    signalApi.sendSignal(new SendSignalCmd("mySignal", Map.of(CommonRestrictions.TENANT_ID, "tenant-a"))).get();

    assertAll(
        () -> assertEquals(true, receivedSignal(tenantInstance), "tenant-a instance received the signal"),
        () -> assertEquals(false, receivedSignal(noTenantInstance), "instance without tenant received the signal"));
  }

  /** Fails against 2026.09.1 in the same way. */
  @Test
  void withoutTenantIdAloneSendsTheSignalWithoutTenant() throws Exception {
    signalApi.sendSignal(new SendSignalCmd("mySignal", Map.of(CommonRestrictions.WITHOUT_TENANT_ID, "true"))).get();

    assertAll(
        () -> assertEquals(false, receivedSignal(tenantInstance), "tenant-a instance received the signal"),
        () -> assertEquals(true, receivedSignal(noTenantInstance), "instance without tenant received the signal"));
  }

  // The tests below pass against 2026.09.1. They record what the adapter does, they are not bug tests.

  /** The check fails after tenantId(...) on the builder and before send(): nothing reaches the engine. */
  @Test
  void observed_tenantIdAlone_failsBeforeSend() {
    ExecutionException e = assertThrows(ExecutionException.class, () ->
        signalApi.sendSignal(new SendSignalCmd("mySignal", Map.of(CommonRestrictions.TENANT_ID, "tenant-a"))).get());

    assertAll(
        () -> assertInstanceOf(IllegalArgumentException.class, e.getCause()),
        () -> assertEquals(List.of("createSignalEvent(mySignal)", "tenantId(tenant-a)"), builderCalls),
        () -> assertFalse(receivedSignal(tenantInstance)),
        () -> assertFalse(receivedSignal(noTenantInstance)));
  }

  /** Both keys pass the check; the engine then delivers to the tenant only. */
  @Test
  void observed_bothKeys_tenantIdFirst_deliversToTenantOnly() throws Exception {
    signalApi.sendSignal(new SendSignalCmd("mySignal",
        ordered(CommonRestrictions.TENANT_ID, "tenant-a", CommonRestrictions.WITHOUT_TENANT_ID, "true"))).get();

    assertAll(
        () -> assertEquals(List.of("createSignalEvent(mySignal)", "tenantId(tenant-a)", "withoutTenantId()",
            "setVariables({})", "send()"), builderCalls),
        () -> assertTrue(receivedSignal(tenantInstance)),
        () -> assertFalse(receivedSignal(noTenantInstance)));
  }

  /** Same result with the keys in the other order. */
  @Test
  void observed_bothKeys_withoutTenantIdFirst_deliversToTenantOnly() throws Exception {
    signalApi.sendSignal(new SendSignalCmd("mySignal",
        ordered(CommonRestrictions.WITHOUT_TENANT_ID, "true", CommonRestrictions.TENANT_ID, "tenant-a"))).get();

    assertAll(
        () -> assertEquals(List.of("createSignalEvent(mySignal)", "withoutTenantId()", "tenantId(tenant-a)",
            "setVariables({})", "send()"), builderCalls),
        () -> assertTrue(receivedSignal(tenantInstance)),
        () -> assertFalse(receivedSignal(noTenantInstance)));
  }

  private boolean receivedSignal(String processInstanceId) {
    return taskService.createTaskQuery().processInstanceId(processInstanceId)
        .taskDefinitionKey("after_signal").count() == 1;
  }

  private static Map<String, String> ordered(String... keysAndValues) {
    Map<String, String> map = new LinkedHashMap<>();
    for (int i = 0; i < keysAndValues.length; i += 2) {
      map.put(keysAndValues[i], keysAndValues[i + 1]);
    }
    return map;
  }
}
