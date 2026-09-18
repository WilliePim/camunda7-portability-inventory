package reproducer;

import dev.bpmcrafters.processengineapi.adapter.c7.embedded.shared.EngineCommandExecutor;
import java.util.UUID;
import java.util.concurrent.ForkJoinPool;
import org.camunda.bpm.engine.ProcessEngine;
import org.camunda.bpm.engine.ProcessEngineConfiguration;
import org.camunda.bpm.engine.RepositoryService;
import org.camunda.bpm.engine.RuntimeService;
import org.camunda.bpm.engine.TaskService;
import org.camunda.bpm.engine.impl.cfg.StandaloneInMemProcessEngineConfiguration;
import org.camunda.bpm.engine.repository.DeploymentBuilder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

/** A fresh embedded Camunda 7 engine on an in-memory H2 database for every test. */
abstract class EngineTestSupport {

  protected ProcessEngine engine;
  protected RuntimeService runtimeService;
  protected TaskService taskService;
  protected RepositoryService repositoryService;
  /** The adapter's executor, as the embedded starter creates it by default. */
  protected final EngineCommandExecutor commandExecutor = new EngineCommandExecutor(ForkJoinPool.commonPool());

  @BeforeEach
  void startEngine() {
    String name = "reproducer-" + UUID.randomUUID();
    engine = new StandaloneInMemProcessEngineConfiguration()
        .setProcessEngineName(name)
        .setJdbcUrl("jdbc:h2:mem:" + name + ";DB_CLOSE_DELAY=-1")
        .setDatabaseSchemaUpdate(ProcessEngineConfiguration.DB_SCHEMA_UPDATE_CREATE_DROP)
        .setJobExecutorActivate(false)
        .setHistory(ProcessEngineConfiguration.HISTORY_FULL)
        .buildProcessEngine();
    runtimeService = engine.getRuntimeService();
    taskService = engine.getTaskService();
    repositoryService = engine.getRepositoryService();
  }

  @AfterEach
  void stopEngine() {
    engine.close();
  }

  /** Deploys a classpath resource, for the given tenant or without tenant when {@code tenantId} is null. */
  protected void deploy(String resource, String tenantId) {
    DeploymentBuilder deployment = repositoryService.createDeployment().addClasspathResource(resource);
    if (tenantId != null) {
      deployment.tenantId(tenantId);
    }
    deployment.deploy();
  }
}
