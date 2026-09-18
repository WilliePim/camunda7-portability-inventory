package reproducer;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import org.camunda.bpm.engine.RuntimeService;
import org.camunda.bpm.engine.runtime.SignalEventReceivedBuilder;

/**
 * Wraps a RuntimeService so that every call the adapter makes on the signal builder is recorded,
 * including {@code send()}, the call that hands the signal to the engine.
 */
final class RecordingRuntimeService {

  private RecordingRuntimeService() {
  }

  static RuntimeService wrap(RuntimeService target, List<String> calls) {
    return (RuntimeService) Proxy.newProxyInstance(
        RecordingRuntimeService.class.getClassLoader(),
        new Class<?>[] {RuntimeService.class},
        (proxy, method, args) -> {
          Object result = invoke(method, target, args);
          if (method.getName().equals("createSignalEvent")) {
            calls.add("createSignalEvent(" + args[0] + ")");
            return wrapBuilder((SignalEventReceivedBuilder) result, calls);
          }
          return result;
        });
  }

  private static SignalEventReceivedBuilder wrapBuilder(SignalEventReceivedBuilder target, List<String> calls) {
    return (SignalEventReceivedBuilder) Proxy.newProxyInstance(
        RecordingRuntimeService.class.getClassLoader(),
        new Class<?>[] {SignalEventReceivedBuilder.class},
        (proxy, method, args) -> {
          String arguments = args == null ? "" : Arrays.stream(args).map(String::valueOf).collect(Collectors.joining(", "));
          calls.add(method.getName() + "(" + arguments + ")");
          Object result = invoke(method, target, args);
          return result == target ? proxy : result;
        });
  }

  private static Object invoke(Method method, Object target, Object[] args) throws Throwable {
    try {
      return method.invoke(target, args);
    } catch (InvocationTargetException e) {
      throw e.getCause();
    }
  }
}
