# Verification of report.md

Reproduction of every count in `report.md` (method table, sections 1–3), the headline claim, and the Camunda 7 adapter behaviour that sections E, I and J depend on. `report.md` has been corrected in place from these results.

| Input | Commit |
|---|---|
| `camunda/camunda-bpm-examples` | `6c7f4c4adb4beb9a2f5d4c5e49fc1ddfc6dab3fc` |
| `camunda-consulting/code` | `c9ef30b62a47a7063c077397cb3340b28fb4cc3c` |
| `bpm-crafters/process-engine-api` | `b02569855596de4fb423dc181489e72595235503` |
| `bpm-crafters/process-engine-adapters-camunda-7` | `d2be36eca2edf24d1e1a43540cee77d9e9dffd21` |

Clone date 2026-09-17. Commands are in [README.md](README.md).

**Corpus rule.** Main sources are `.java` files under `src/main/`. `snippets/reverse-adapter/` in `camunda-consulting/code` is excluded: it is a Zeebe job-worker bridge that imports `io.camunda.zeebe`. No other folder in either repository imports `io.camunda.*` or declares a Zeebe dependency. Four BPMN files carry only an `xmlns:zeebe` declaration, and those folders stay in. Neither repository contains Kotlin sources.

**Counting rule.** Counts come from a tree-sitter parse, not text grep, so comments are ignored. A call is counted only when its receiver's static type resolves to the Camunda type named in the row. The type is resolved from:
- the variable, parameter or field declaration, plus imports;
- a known getter chain, e.g. `processEngine.getRuntimeService()` or `execution.getProcessEngineServices().getRuntimeService()`;
- the target type of a lambda (`JavaDelegate`, external-task `handler`).

Engine implementation classes (`TaskServiceImpl`, …) count as their service interface. Unresolved receivers are not counted. For call rows with a receiver-name hint, the script reports unresolved sites in a separate column: every such row reported 0. Class rows count named, non-interface classes whose own `extends` / `implements` clause names the type. `python scripts/inventory.py --explain <ID>` lists every counted site and every rejected same-name site for a row.

## 1. Counts

Δ = measured − reported. For "≈ n" and "~n", Δ is computed against n. Scope is the repository set the report's sentence refers to: `both` = sum of the two repositories. Method: `inventory.py <ID>`, where `<ID>` is the spec in `scripts/inventory.py`. Rows whose method starts with `delegate_scopes` are computed by the delegate analysis shared with `delegates.py`.

| § | Count | Scope | Reported | Measured | Δ | examples | consulting | Method |
|---|---|---|---:|---:|---:|---:|---:|---|
| Method | camunda-bpm-examples main .java files | examples | 122 | 124 | +2 | 124 |  | `inventory.py m.files.examples` |
| Method | camunda-consulting/code main .java files (C7 only) | consulting | 1,298 | 1297 | -1 |  | 1297 | `inventory.py m.files.consulting` |
| 1 | runtimeService.startProcessInstanceByKey / ById | both | 18 | 19 | +1 | 6 | 13 | `inventory.py 1.start.direct` |
| 1 | … chained | both | 51 | 27 | -24 | 6 | 21 | `inventory.py 1.start.chained` |
| 1 | runtimeService.startProcessInstanceByMessage | both | 2 | 2 | +0 | 1 | 1 | `inventory.py 1.startByMessage` |
| 1 | runtimeService.correlateMessage / createMessageCorrelation | both | 9 | 7 | -2 | 0 | 7 | `inventory.py 1.correlate.direct` |
| 1 | … chained | both | 4 | 7 | +3 | 0 | 7 | `inventory.py 1.correlate.chained` |
| 1 | runtimeService.signalEventReceived | both | 1 | 1 | +0 | 0 | 1 | `inventory.py 1.signalEvent` |
| 1 | externalTaskService.complete (engine + client) | both | 22 | 24 | +2 | 6 | 18 | `inventory.py 1.ext.complete` |
| 1 | externalTaskService.handleFailure (engine + client) | both | 9 | 9 | +0 | 0 | 9 | `inventory.py 1.ext.handleFailure` |
| 1 | ExternalTaskHandler implementations | both | 7 | 6 | -1 | 0 | 6 | `inventory.py 1.ext.handler` |
| 1 | taskService.complete | both | 3 | 3 | +0 | 1 | 2 | `inventory.py 1.task.complete.direct` |
| 1 | … chained | both | 12 | 12 | +0 | 0 | 12 | `inventory.py 1.task.complete.chained` |
| 1 | taskService.claim / setAssignee | both | 6 | 11 | +5 | 0 | 11 | `inventory.py 1.task.claim` |
| 1 | throw new BpmnError from a task (JavaDelegate) | both | 13 | 11 | -2 | 2 | 9 | `inventory.py 1.bpmnError` |
| 1 | repositoryService.createDeployment | both | 6 | 9 | +3 | 3 | 6 | `inventory.py 1.deploy` |
| 1 | decisionService / DmnEngine evaluate* | both | 2 | 7 | +5 | 2 | 5 | `inventory.py 1.dmn` |
| 2A | delegate/listener classes (consulting) | consulting | 231 | 231 | +0 |  | 231 | `inventory.py 2A.classes` (delegate_scopes) |
| 2A | … JavaDelegate (consulting) | consulting | 184 | 185 | +1 |  | 185 | `inventory.py 2A.javaDelegate` (delegate_scopes) |
| 2A | … ExecutionListener (consulting) | consulting | 25 | 25 | +0 |  | 25 | `inventory.py 2A.executionListener` (delegate_scopes) |
| 2A | … TaskListener (consulting) | consulting | 22 | 22 | +0 |  | 22 | `inventory.py 2A.taskListener` (delegate_scopes) |
| 2A | JavaDelegate classes (examples) | examples | 24 | 24 | +0 | 24 |  | `inventory.py 2A.examples.javaDelegate` (delegate_scopes) |
| 2A | ExecutionListener classes (examples) | examples | — | 1 |  | 1 |  | `inventory.py 2A.examples.el` (delegate_scopes) |
| 2A | TaskListener classes (examples) | examples | — | 1 |  | 1 |  | `inventory.py 2A.examples.tl` (delegate_scopes) |
| 2A | listener classes (examples) | examples | 2 | 2 | +0 | 2 |  | `inventory.py 2A.examples.listeners` = sum of 2A.examples.el, 2A.examples.tl |
| 2A | delegate files calling engine services (consulting) | consulting | 44 | 47 | +3 |  | 47 | `inventory.py 2A.callingFiles` (delegate_scopes) |
| 2A | entry-point sites (consulting) | consulting | 59 | 72 | +13 |  | 72 | `inventory.py 2A.entrySites` (delegate_scopes) |
| 2A | … startProcessInstanceByKey via entry point | consulting | 3 | 4 | +1 |  | 4 | `inventory.py 2A.via.start` (delegate_scopes) |
| 2A | … correlateMessage via entry point | consulting | 2 | 2 | +0 |  | 2 | `inventory.py 2A.via.correlate` (delegate_scopes) |
| 2A | … taskService.complete via entry point | consulting | 4 | 5 | +1 |  | 5 | `inventory.py 2A.via.taskComplete` (delegate_scopes) |
| 2A | … taskService.createTaskQuery via entry point | consulting | 3 | 4 | +1 |  | 4 | `inventory.py 2A.via.taskQuery` (delegate_scopes) |
| 2A | … historyService.create*Query via entry point | consulting | 9 | 13 | +4 |  | 13 | `inventory.py 2A.via.history` (delegate_scopes) |
| 2A | … repositoryService.* via entry point | consulting | 10 | 9 | -1 |  | 9 | `inventory.py 2A.via.repository` (delegate_scopes) |
| 2A | … identityService.* via entry point | consulting | 6 | 17 | +11 |  | 17 | `inventory.py 2A.via.identity` (delegate_scopes) |
| 2A | … caseService.* via entry point | consulting | 13 | 4 | -9 |  | 4 | `inventory.py 2A.via.case` (delegate_scopes) |
| 2B | taskService.createTaskQuery | both | 39 | 39 | +0 | 1 | 38 | `inventory.py 2B.taskQuery.direct` |
| 2B | … chained | both | 20 | 25 | +5 | 0 | 25 | `inventory.py 2B.taskQuery.chained` |
| 2B | historyService.createHistoric*Query (incl. native) | both | 35 | 38 | +3 | 2 | 36 | `inventory.py 2B.historyQuery` |
| 2B | runtimeService.createProcessInstanceQuery / createExecutionQuery | both | 13 | 20 | +7 | 1 | 19 | `inventory.py 2B.runtimeQuery` |
| 2B | repositoryService.createProcessDefinitionQuery / createDeploymentQuery / createDecisionDefinitionQuery | both | 25 | 33 | +8 | 5 | 28 | `inventory.py 2B.repositoryQuery` |
| 2B | managementService.createJobQuery | both | 3 | 5 | +2 | 0 | 5 | `inventory.py 2B.jobQuery` |
| 2C | history query sites | both | 35 | 38 | +3 | 2 | 36 | `inventory.py 2C.historyQueries` = sum of 2B.historyQuery |
| 2C | HistoryEventHandler implementations | both | 4 | 4 | +0 | 0 | 4 | `inventory.py 2C.historyEventHandler` |
| 2C | DbHistoryEventHandler subclasses | both | 2 | 2 | +0 | 0 | 2 | `inventory.py 2C.dbHistoryEventHandler` |
| 2C | custom HistoryLevel | both | 2 | 4 | +2 | 2 | 2 | `inventory.py 2C.historyLevel` |
| 2C | HistoryEventProducer implementations / subclasses | both | 2 | 2 | +0 | 0 | 2 | `inventory.py 2C.historyEventProducer` |
| 2C | DynamicRemovalTimeCalculationStrategy (snippet-local interface) | both | 2 | 2 | +0 | 0 | 2 | `inventory.py 2C.dynamicRemovalTime` |
| 2C | HistoryRemovalTimeProvider implementations (the C7 type behind it) | both | — | 1 |  | 0 | 1 | `inventory.py 2C.historyRemovalTimeProvider` |
| 2D | identityService.* | both | ≈ 120 | 151 | +31 | 2 | 149 | `inventory.py 2D.identity` |
| 2D | authorizationService.* | both | ≈ 115 | 121 | +6 | 0 | 121 | `inventory.py 2D.authorization` |
| 2D | filterService.* | both | ≈ 43 | 45 | +2 | 0 | 45 | `inventory.py 2D.filter` |
| 2E | runtimeService.setVariable / getVariable / getVariables | both | 12 | 15 | +3 | 1 | 14 | `inventory.py 2E.variables` |
| 2E | runtimeService.signal(executionId) | both | 5 | 4 | -1 | 1 | 3 | `inventory.py 2E.signal` |
| 2E | runtimeService.messageEventReceived | both | 7 | 6 | -1 | 0 | 6 | `inventory.py 2E.messageEventReceived` |
| 2E | deleteProcessInstance | both | 1 | 1 | +0 | 0 | 1 | `inventory.py 2E.deleteProcessInstance` |
| 2E | suspend/activateProcessInstanceByProcessDefinitionKey | both | 4 | 4 | +0 | 0 | 4 | `inventory.py 2E.suspendActivate` |
| 2E | createProcessInstanceModification | both | 1 | 2 | +1 | 0 | 2 | `inventory.py 2E.modification` |
| 2E | getActiveActivityIds | both | 2 | 2 | +0 | 0 | 2 | `inventory.py 2E.activeActivityIds` |
| 2F | managementService setJobRetries / executeJob / activateJobById / recalculateJobDuedate / getJobExceptionStacktrace | both | 6 | 6 | +0 | 0 | 6 | `inventory.py 2F.jobOps` |
| 2F | createIncident / resolveIncident | both | 9 | 0 | -9 | 0 | 0 | `inventory.py 2F.incidents` |
| 2F | JobRetryCmd / FoxJobRetryCmd / DefaultJobRetryCmd subclasses | both | 4 | 6 | +2 | 0 | 6 | `inventory.py 2F.jobRetryCmd` |
| 2F | custom IncidentHandler | both | 2 | 3 | +1 | 0 | 3 | `inventory.py 2F.incidentHandler` |
| 2F | TimerEventJobHandler | both | 1 | 1 | +0 | 0 | 1 | `inventory.py 2F.timerEventJobHandler` |
| 2G | impl.* imports (consulting) | consulting | 615 | 617 | +2 |  | 617 | `inventory.py 2G.imports` |
| 2G | files with impl.* imports (consulting) | consulting | 176 | 176 | +0 |  | 176 | `inventory.py 2G.importFiles` |
| 2G | impl.* imports (examples) | examples | ~60 | 81 | +21 | 81 |  | `inventory.py 2G.imports.examples` |
| 2G | impl.cfg imports (consulting) | consulting | 121 | 122 | +1 |  | 122 | `inventory.py 2G.pkg.cfg` |
| 2G | impl.persistence imports (consulting) | consulting | 65 | 66 | +1 |  | 66 | `inventory.py 2G.pkg.persistence` |
| 2G | impl.bpmn imports (consulting) | consulting | 63 | 65 | +2 |  | 65 | `inventory.py 2G.pkg.bpmn` |
| 2G | impl.pvm imports (consulting) | consulting | 62 | 63 | +1 |  | 63 | `inventory.py 2G.pkg.pvm` |
| 2G | impl.history imports (consulting) | consulting | 50 | 51 | +1 |  | 51 | `inventory.py 2G.pkg.history` |
| 2G | impl.interceptor imports (consulting) | consulting | 46 | 46 | +0 |  | 46 | `inventory.py 2G.pkg.interceptor` |
| 2G | impl.context imports (consulting) | consulting | 28 | 28 | +0 |  | 28 | `inventory.py 2G.pkg.context` |
| 2G | impl.jobexecutor imports (consulting) | consulting | 21 | 21 | +0 |  | 21 | `inventory.py 2G.pkg.jobexecutor` |
| 2G | ProcessEnginePlugin / AbstractProcessEnginePlugin | both | 42 | 49 | +7 | 6 | 43 | `inventory.py 2G.plugin` |
| 2G | BpmnParseListener / AbstractBpmnParseListener | both | 22 | 18 | -4 | 2 | 16 | `inventory.py 2G.parseListener` |
| 2G | custom ActivityBehavior | both | 3 | 5 | +2 | 1 | 4 | `inventory.py 2G.activityBehavior` |
| 2G | CommandInterceptor | both | 3 | 4 | +1 | 1 | 3 | `inventory.py 2G.commandInterceptor` |
| 2G | Command<T> | both | 3 | 3 | +0 | 2 | 1 | `inventory.py 2G.command` |
| 2G | SessionFactory | both | 2 | 2 | +0 | 1 | 1 | `inventory.py 2G.sessionFactory` |
| 2G | TenantIdProvider | both | 4 | 4 | +0 | 1 | 3 | `inventory.py 2G.tenantIdProvider` |
| 2G | Context.getCommandContext() / getProcessEngineConfiguration() | both | 4 | 44 | +40 | 6 | 38 | `inventory.py 2G.contextCalls` |
| 2H | caseService.* | both | ≈ 45 | 31 | -14 | 0 | 31 | `inventory.py 2H.caseService` |
| 2H | CaseExecutionListener | both | 10 | 10 | +0 | 0 | 10 | `inventory.py 2H.caseExecutionListener` |
| 2I | getVariable on DelegateExecution/DelegateTask inside delegates | both | 202 | 205 | +3 | 7 | 198 | `inventory.py 2I.getVariable` |
| 2I | setVariable on DelegateExecution/DelegateTask inside delegates | both | 125 | 134 | +9 | 7 | 127 | `inventory.py 2I.setVariable` |
| 2I | getId on DelegateExecution/DelegateTask inside delegates | both | 93 | 91 | -2 | 1 | 90 | `inventory.py 2I.getId` |
| 2I | getProcessInstanceId on DelegateExecution/DelegateTask inside delegates | both | 81 | 80 | -1 | 0 | 80 | `inventory.py 2I.getProcessInstanceId` |
| 2I | getCurrentActivityId on DelegateExecution/DelegateTask inside delegates | both | 79 | 74 | -5 | 0 | 74 | `inventory.py 2I.getCurrentActivityId` |
| 2I | getCurrentActivityName on DelegateExecution/DelegateTask inside delegates | both | 73 | 71 | -2 | 0 | 71 | `inventory.py 2I.getCurrentActivityName` |
| 2I | getProcessBusinessKey on DelegateExecution/DelegateTask inside delegates | both | 71 | 72 | +1 | 0 | 72 | `inventory.py 2I.getProcessBusinessKey` |
| 2I | getProcessDefinitionId on DelegateExecution/DelegateTask inside delegates | both | 70 | 71 | +1 | 0 | 71 | `inventory.py 2I.getProcessDefinitionId` |
| 2I | getBpmnModelElementInstance on DelegateExecution/DelegateTask inside delegates | both | 6 | 7 | +1 | 1 | 6 | `inventory.py 2I.getBpmnModelElementInstance` |
| 2I | getTenantId on DelegateExecution/DelegateTask inside delegates | both | 3 | 2 | -1 | 2 | 0 | `inventory.py 2I.getTenantId` |
| 2J | setVariableLocal | both | 3 | 7 | +4 | 0 | 7 | `inventory.py 2J.setVariableLocal` |
| 2J | getVariableLocal | both | 3 | 4 | +1 | 0 | 4 | `inventory.py 2J.getVariableLocal` |
| 2J | removeVariable | both | 5 | 6 | +1 | 0 | 6 | `inventory.py 2J.removeVariable` |
| 2J | hasVariable | both | 5 | 4 | -1 | 0 | 4 | `inventory.py 2J.hasVariable` |
| 2L | deleteDeployment | both | 4 | 2 | -2 | 0 | 2 | `inventory.py 2L.deleteDeployment` |
| 2L | getProcessDiagram / getProcessDiagramLayout | both | 7 | 7 | +0 | 0 | 7 | `inventory.py 2L.diagram` |
| 2L | getBpmnModelInstance / getProcessModel | both | 4 | 2 | -2 | 0 | 2 | `inventory.py 2L.model` |
| 2L | getProcessDefinition | both | 3 | 3 | +0 | 0 | 3 | `inventory.py 2L.processDefinition` |
| 2M | formService.getTaskFormData / getStartFormKey | both | 3 | 3 | +0 | 0 | 3 | `inventory.py 2M.forms` |
| 3 | Start / correlate / signal | both | ~90 | 63 | -27 | 13 | 50 | `inventory.py 3.startCorrelate` = sum of 1.start.direct, 1.start.chained, 1.startByMessage, 1.correlate.direct, 1.correlate.chained, 1.signalEvent |
| 3 | External-task worker style | both | ~40 | 39 | -1 | 6 | 33 | `inventory.py 3.externalTask` = sum of 1.ext.complete, 1.ext.handleFailure, 1.ext.handler |
| 3 | User task complete / assign / by-error | both | ~35 | 37 | +2 | 3 | 34 | `inventory.py 3.userTask` = sum of 1.task.complete.direct, 1.task.complete.chained, 1.task.claim, 1.bpmnError |
| 3 | Deployment, DMN evaluate | both | ~10 | 16 | +6 | 5 | 11 | `inventory.py 3.deployDmn` = sum of 1.deploy, 1.dmn |
| 3 | Delegates & listeners: classes (both repos) | both | 231 | 257 | +26 | 26 | 231 | `inventory.py 3.delegateClasses` (delegate_scopes) |
| 3 | Delegates & listeners: nested engine calls, entry-point sites (both repos) | both | 59 | 73 | +14 | 1 | 72 | `inventory.py 3.delegateCalls` (delegate_scopes) |
| 3 | Queries | both | ~135 | 160 | +25 | 9 | 151 | `inventory.py 3.queries` = sum of 2B.taskQuery.direct, 2B.taskQuery.chained, 2B.historyQuery, 2B.runtimeQuery, 2B.repositoryQuery, 2B.jobQuery |
| 3 | History infrastructure (classes) | both | ~12 | 14 | +2 | 2 | 12 | `inventory.py 3.historyInfra` = sum of 2C.historyEventHandler, 2C.dbHistoryEventHandler, 2C.historyLevel, 2C.historyEventProducer, 2C.dynamicRemovalTime |
| 3 | Identity / authorization / filters | both | ~280 | 317 | +37 | 2 | 315 | `inventory.py 3.identity` = sum of 2D.identity, 2D.authorization, 2D.filter |
| 3 | Instance lifecycle, instance variables | both | ~30 | 34 | +4 | 2 | 32 | `inventory.py 3.lifecycle` = sum of 2E.variables, 2E.signal, 2E.messageEventReceived, 2E.deleteProcessInstance, 2E.suspendActivate, 2E.modification, 2E.activeActivityIds |
| 3 | Jobs / incidents / retries | both | ~20 | 16 | -4 | 0 | 16 | `inventory.py 3.jobs` = sum of 2F.jobOps, 2F.incidents, 2F.jobRetryCmd, 2F.incidentHandler, 2F.timerEventJobHandler |
| 3 | Engine internals: impl.* imports (both repos) | both | 615 | 698 | +83 | 81 | 617 | `inventory.py 3.implImports` |
| 3 | Engine internals: files (both repos) | both | 176 | 201 | +25 | 25 | 176 | `inventory.py 3.implFiles` |
| 3 | CMMN | both | ~55 | 41 | -14 | 0 | 41 | `inventory.py 3.cmmn` = sum of 2H.caseService, 2H.caseExecutionListener |
| 3 | Delegate context reads | both | ~700 | 807 | +107 | 18 | 789 | `inventory.py 3.contextReads` = sum of 2I.getVariable, 2I.setVariable, 2I.getId, 2I.getProcessInstanceId, 2I.getCurrentActivityId, 2I.getCurrentActivityName, 2I.getProcessBusinessKey, 2I.getProcessDefinitionId, 2I.getBpmnModelElementInstance, 2I.getTenantId |
| 3 | Variable scope / typed values | both | ~20 | 21 | +1 | 0 | 21 | `inventory.py 3.variableScope` = sum of 2J.setVariableLocal, 2J.getVariableLocal, 2J.removeVariable, 2J.hasVariable |

All numeric corrections in `report.md` use the Measured column. Where the report wrote "≈" or "~", the corrected value is an exact count and the sign was dropped. No count was unreproducible: every row has a definition in `scripts/inventory.py` and a measured value.

## 2. Headline claim: delegates and listeners

`python scripts/delegates.py` (definitions in `scripts/delegate_scopes.py`):
- **Delegate/listener class:** a named, non-abstract class implementing `org.camunda.bpm.engine.delegate.{JavaDelegate, ExecutionListener, TaskListener}`, directly or through a supertype in the same project.
- **Entry point:** one of the four calls below, made inside such a class (or inside an abstract, anonymous or lambda implementation):
  - `DelegateExecution.getProcessEngineServices()`
  - `DelegateTask.getProcessEngineServices()`
  - `Context.getProcessEngineConfiguration()`
  - `Context.getCommandContext()`
- **Engine method:** a call inside such a scope on an engine service, `ProcessEngineConfigurationImpl` or `CommandContext` (getters excluded).
- **"via entry point":** the receiver expression, or the initializer of the local variable used as receiver, contains an entry-point call.

### Delegate and listener implementations

| | examples | consulting | total |
|---|---:|---:|---:|
| named non-abstract classes (headline) | 26 | 231 | 257 |
| … implementing JavaDelegate | 24 | 185 | 209 |
| … implementing ExecutionListener | 1 | 25 | 26 |
| … implementing TaskListener | 1 | 22 | 23 |
| … of which implement an interface directly | 26 | 231 | 257 |
| abstract classes implementing one (not in headline) | 0 | 1 | 1 |
| anonymous classes (not in headline) | 0 | 0 | 0 |
| lambdas (not in headline) | 0 | 0 | 0 |

### Engine access from inside delegates

| | examples | consulting | total |
|---|---:|---:|---:|
| entry-point call sites, all delegate scopes | 1 | 72 | 73 |
| … via `DelegateExecution.getProcessEngineServices()` | 1 | 57 | 58 |
| … via `DelegateTask.getProcessEngineServices()` | 0 | 10 | 10 |
| … via `Context.getProcessEngineConfiguration()` | 0 | 3 | 3 |
| … via `Context.getCommandContext()` | 0 | 2 | 2 |
| entry-point call sites inside named classes | 1 | 72 | 73 |
| named classes with ≥1 entry-point call (headline) | 1 | 47 | 48 |
| files containing those classes | 1 | 47 | 48 |
| delegate units of any kind with ≥1 entry-point call | 1 | 47 | 48 |
| DelegateExecution/DelegateTask.getProcessEngine() sites (not in headline) | 0 | 16 | 16 |

### Distinct engine methods called inside delegate scopes

| Method | via entry point | via getProcessEngine() | other origin (field, parameter) | total |
|---|---:|---:|---:|---:|
| `HistoryService.createHistoricDecisionInstanceQuery` | 7 | 0 | 0 | 7 |
| `TaskService.complete` | 5 | 2 | 0 | 7 |
| `RepositoryService.createProcessDefinitionQuery` | 4 | 5 | 0 | 9 |
| `RuntimeService.startProcessInstanceByKey` | 4 | 2 | 1 | 7 |
| `TaskService.createTaskQuery` | 4 | 2 | 0 | 6 |
| `AuthorizationService.saveAuthorization` | 4 | 0 | 0 | 4 |
| `IdentityService.createUserQuery` | 4 | 0 | 0 | 4 |
| `RuntimeService.createExecutionQuery` | 4 | 0 | 0 | 4 |
| `CaseService.closeCaseInstance` | 3 | 0 | 0 | 3 |
| `HistoryService.createHistoricProcessInstanceQuery` | 3 | 0 | 0 | 3 |
| `RuntimeService.createMessageCorrelation` | 2 | 1 | 0 | 3 |
| `RuntimeService.setVariable` | 2 | 0 | 1 | 3 |
| `IdentityService.createTenantUserMembership` | 2 | 0 | 0 | 2 |
| `IdentityService.getCurrentAuthentication` | 2 | 0 | 0 | 2 |
| `IdentityService.newTenant` | 2 | 0 | 0 | 2 |
| `IdentityService.saveTenant` | 2 | 0 | 0 | 2 |
| `ProcessEngineConfigurationImpl.getExpressionManager` | 2 | 0 | 0 | 2 |
| `RepositoryService.createDecisionDefinitionQuery` | 2 | 0 | 0 | 2 |
| `RepositoryService.deleteDeployment` | 2 | 0 | 0 | 2 |
| `RuntimeService.correlateMessage` | 2 | 0 | 0 | 2 |
| `RuntimeService.getVariable` | 2 | 0 | 0 | 2 |
| `HistoryService.createHistoricActivityInstanceQuery` | 1 | 0 | 1 | 2 |
| `RuntimeService.createProcessInstanceModification` | 1 | 1 | 0 | 2 |
| `CaseService.createCaseInstanceByKey` | 1 | 0 | 0 | 1 |
| `CommandContext.getIncidentManager` | 1 | 0 | 0 | 1 |
| `CommandContext.getJobManager` | 1 | 0 | 0 | 1 |
| `ExternalTaskService.complete` | 1 | 0 | 0 | 1 |
| `HistoryService.createHistoricTaskInstanceQuery` | 1 | 0 | 0 | 1 |
| `HistoryService.createHistoricVariableInstanceQuery` | 1 | 0 | 0 | 1 |
| `IdentityService.clearAuthentication` | 1 | 0 | 0 | 1 |
| `IdentityService.createTenantQuery` | 1 | 0 | 0 | 1 |
| `IdentityService.newUser` | 1 | 0 | 0 | 1 |
| `IdentityService.saveUser` | 1 | 0 | 0 | 1 |
| `IdentityService.setAuthenticatedUserId` | 1 | 0 | 0 | 1 |
| `ManagementService.getJobExceptionStacktrace` | 1 | 0 | 0 | 1 |
| `ProcessEngineConfigurationImpl.getIdGenerator` | 1 | 0 | 0 | 1 |
| `RepositoryService.createDeployment` | 1 | 0 | 0 | 1 |
| `RuntimeService.deleteProcessInstance` | 1 | 0 | 0 | 1 |
| `RuntimeService.signalEventReceived` | 1 | 0 | 0 | 1 |
| `RuntimeService.startProcessInstanceByMessage` | 1 | 0 | 0 | 1 |
| `TaskService.newTask` | 1 | 0 | 0 | 1 |
| `TaskService.saveTask` | 1 | 0 | 0 | 1 |
| `RuntimeService.createProcessInstanceQuery` | 0 | 5 | 0 | 5 |
| `RuntimeService.activateProcessInstanceByProcessDefinitionKey` | 0 | 2 | 0 | 2 |
| `RuntimeService.suspendProcessInstanceByProcessDefinitionKey` | 0 | 2 | 0 | 2 |
| `ManagementService.createBatchStatisticsQuery` | 0 | 1 | 0 | 1 |
| `ManagementService.createJobQuery` | 0 | 0 | 1 | 1 |
| `ManagementService.setJobRetries` | 0 | 0 | 1 | 1 |
| `ProcessEngineConfigurationImpl.getCommandExecutorTxRequiresNew` | 0 | 0 | 1 | 1 |
| `RuntimeService.createMigrationPlan` | 0 | 1 | 0 | 1 |
| `RuntimeService.createProcessInstanceByKey` | 0 | 1 | 0 | 1 |
| `RuntimeService.newMigration` | 0 | 1 | 0 | 1 |
| **distinct methods** | 42 | 13 | 6 | 52 |
| **call sites** | 85 | 26 | 6 | 117 |

## 3. Claims in report.md that were wrong or unsupported

Each item states the problem, the evidence, and the correction applied. "Not amended" marks prose outside the numbers and sections E, I and J, which the task left untouched.

### Method and corpus

1. **Method table file counts (122 / 1,298).** They match the rule "any `.java` path without `/test/`", applied to the whole consulting repository. That rule:
   - kept the C8 snippet `snippets/reverse-adapter` (2 files) and a Maven wrapper helper (`snippets/quarkus-with-rest-api/.mvn/wrapper/MavenWrapperDownloader.java`);
   - dropped main-source files in packages named `test`: 2 in `snippets/data-in-processes/src/main/java/org/camunda/consulting/patterns/data/test/` and 2 in `testing/assert/job-announcement-publication-process/src/main/java/org/camunda/bpm/engine/test/assertions/examples/jobannouncement/`.

   **Correction:** 124 / 1,297.
2. **"Static inventory (grep of call sites …)".** Line grep counts commented-out code and misses chained calls split across lines.
   - Across both repositories, 35 of the 56 grep hits for `getRuntimeService().startProcessInstanceBy(Key|Id)` are on commented-out lines. Most sit in the generated `CamundaBpmProcessApplication` template.
   - 2 of the 9 hits for `runtimeService.correlateMessage / createMessageCorrelation` are commented out.
   - 3 chained correlations split across lines were not matched.

   **Correction:** all counts replaced by parser-based values (§1 table). The Method sentence itself is not amended.

### Section 1

3. **Start 18 + 51 chained → 19 + 27; correlate 9 + 4 chained → 7 + 7.** See item 2.
4. **`taskService.claim / setAssignee` 6 → 11, `createDeployment` 6 → 9.** The measured values include chained or line-split forms: `engine.getTaskService().claim(...)` (5 sites) and `processEngine.getRepositoryService().createDeployment()`.
5. **DMN evaluate 2 → 7.** 6 of the 7 sites are `DmnEngine.evaluateDecision` / `evaluateDecisionTable` calls on the standalone DMN engine; 1 is a `DecisionService` call.
6. **`ExternalTaskHandler` implementations 7 → 6; `externalTaskService.complete` 22 → 24.**
   - Each draft value includes one site in the excluded C8 folder `snippets/reverse-adapter` (`MyTaskImplementation`).
   - `complete` gains 3 chained engine calls (`getExternalTaskService().complete(...)`).
7. **`throw new BpmnError` from a task 13 → 11.** Main sources contain 15 grep hits:
   - 11 inside `JavaDelegate` scopes (counted);
   - 3 on commented-out lines;
   - 1 (`one-time-examples/oop2013-cookshow/.../GeoAdapter.java:35`) in a class that implements no delegate interface.

### Section 2A (headline)

8. **"184 `JavaDelegate`" → 185.** The additional class is `DelegationCodeTestProxy` (see item 1). It implements both `JavaDelegate` and `ExecutionListener`, so the per-interface counts (185 + 25 + 22 = 232) exceed the 231 distinct classes.
9. **"44 of the 231 delegate files … via `execution.getProcessEngineServices()` (59 sites total)" → 47 / 72.** The corrected numbers use the Task 2 definition (four entry points). The sentence names only one entry point; the 72 consulting sites split into:
   - 57 `DelegateExecution.getProcessEngineServices()`
   - 10 `DelegateTask.getProcessEngineServices()`
   - 3 `Context.getProcessEngineConfiguration()`
   - 2 `Context.getCommandContext()`

   The wording has since been amended to name all four entry points with their site counts. The draft's 59 is closest to the 57 `DelegateExecution` sites; its exact rule is not reproducible.
10. **Per-method breakdown.** Corrected to the "via entry point" counts in the consulting repository:
    - `startProcessInstanceByKey` 3 → 4
    - `taskService.complete` 4 → 5
    - `taskService.createTaskQuery` 3 → 4
    - `historyService.create*Query` 9 → 13
    - `repositoryService.*` 10 → 9
    - `identityService.*` 6 → 17
    - `caseService.*` 13 → 4

    The listed groups account for 58 engine-method calls reached through entry points. One entry point can feed several calls through a local variable, so this number is not a subset of the 72 entry-point sites. §2 lists all methods. 16 further call sites use `DelegateExecution.getProcessEngine()`, which the Task 2 definition does not count.

### Sections 2B–2M

11. **§2B "This is the largest surface with no counterpart" and §3 "largest gap".** Unsupported by the counts. Queries total 160 sites, while identity / authorization / filters total 317 and delegate context reads total 807. Not amended.
12. **§2C `DynamicRemovalTimeCalculationStrategy` (2).** This is not a Camunda type. It is an interface declared in the snippet (`com.camunda.bpm.demo.engine_plugin_variable_depending_history_ttl.strategy`), with 2 implementations. The Camunda extension point behind it is `HistoryRemovalTimeProvider`, implemented once. The count is correct for the local interface; not amended. Also: custom `HistoryLevel` 2 → 4 (2 in the examples repository).
13. **§2D identity items.** The row lists `AuthenticationExtractor`, which resolves to `org.camunda.optimize.plugin.security.authentication.AuthenticationExtractor`: an Optimize plugin interface, not an engine or web-app type. "Second-largest block of code in the consulting repo" has no measure behind it. Not amended. Counts corrected: `identityService.*` 151, `authorizationService.*` 121, `filterService.*` 45.
14. **§2F `createIncident / resolveIncident` (9) → 0.** The grep hits are:
    - method declarations and `super.resolveIncident(...)` calls inside custom `IncidentHandler` classes;
    - a generated OpenAPI REST client (`snippets/camunda-openapi-client`);
    - a hand-written `DelegateExecution` implementation.

    None is a call on `RuntimeService` or `DelegateExecution`.
15. **§2G "Top packages".** The list omits `impl.util`, which has 33 imports in the consulting repository and ranks 7th, ahead of `impl.context` (28) and `impl.jobexecutor` (21). Not amended. `Context.getCommandContext()` / `getProcessEngineConfiguration()` 4 → 44: the draft's 4 is not reproducible (calls inside delegate scopes only: 5).
16. **§2H `caseService.*` ≈ 45 → 31.** Grep for `caseService.` finds 0 sites in the consulting repository; all 31 are `getCaseService().…` chains.
17. **§2I draft sum.** The §2I reads summed to 803, while §3 reported "~700". The measured sum is 807.
18. **§2L.**
    - `deleteDeployment` 4 → 2: the grep hits include 2 commented-out calls (`snippets/upload-and-deploy-processes/.../UndeployProcessDelegate.java:40, :55`).
    - `getBpmnModelInstance / getProcessModel` 4 → 2: the grep hits include 2 commented-out lines, a method declaration with an unqualified call to it, and one call on `ExecutionEntity`. The 2 counted calls are on `RepositoryService`.

### Section 3

19. **"Sites (both repos)" held consulting-only values.** The rows "231 classes, 59 nested engine calls" and "615 imports / 176 files" were consulting-only. Corrected to both-repository values: 257 classes, 73 entry-point sites, 698 imports, 201 files. The consulting-only values remain in §2A and §2G.
20. **Verdicts contradicted by §E and §I, not amended (outside E/I/J):**
    - "`EXECUTION_ID` may cover part": the adapter rejects `EXECUTION_ID` for message correlation and honours it only for signals and task subscriptions.
    - "meta keys undocumented": the adapter docs contain meta-key tables.

### Sections E, I, J (amended)

21. **§E "execution-targeted correlation may be expressible".** Wrong for the C7 adapter: `EXECUTION_ID` is not a supported correlation restriction and is rejected with `IllegalArgumentException`. Corrected in §E.
22. **§I "could not find … a guaranteed list of meta keys" and "process definition id (versioned) … not named anywhere".**
    - The API module has no list, but the adapter docs have per-adapter tables.
    - `CommonRestrictions.PROCESS_DEFINITION_ID` exists, and every adapter flavour writes `processDefinitionId`.
    - The draft's `CommonRestrictions` enumeration omitted 7 constants.

    Corrected in §I.
23. **§J "Scope (local/global), removal, and serialization format are not expressible".** Wrong for user tasks: `UpdatePayloadTaskCmd`, `DeletePayloadTaskCmd` and `ClearPayloadTaskCmd` write and remove task-local variables. Corrected in §J; the statement is narrowed to start, correlate, signal and complete.

### Sections 4–5 and M (not amended)

24. **§5 ask 4 "execution-targeted correlation via `EXECUTION_ID` (supported?)".** Answer: not supported for message correlation, supported for signals (§E). Not amended.
25. **§M "form keys may or may not appear in task meta".** `formKey` is written for user tasks by both adapters, conditional on a non-null value (`emb: task/delivery/TaskInformationExtensions.kt:26`, `rem: task/delivery/TaskInformationExtensions.kt:45`). Not amended.

## 4. Gaps in report.md the adapter already covers

| # | Report section | Gap as drafted | What the adapter already provides | Evidence |
|---|---|---|---|---|
| 1 | §I, §5 ask 1 | No per-adapter table of meta keys | Adapter docs publish meta-key tables for user and service tasks. Missing: guaranteed/conditional marking and the keys `processInstanceId`, `businessKey`, `formKey`, `retries`, `processDefinitionVersionTag`, `reason`. | `docs/reference-c7-embedded.md:175-208`, `docs/reference-c7-remote.md:210-243` |
| 2 | §I | Process definition *id* (versioned) not named | `CommonRestrictions.PROCESS_DEFINITION_ID`, written as `processDefinitionId` by every flavour | `api: CommonRestrictions.kt:37`; `emb: task/delivery/TaskInformationExtensions.kt:16,59`; `rem: task/delivery/TaskInformationExtensions.kt:19,36`; `rem: task/delivery/subscribe/ExternalTaskExtensions.kt:15` |
| 3 | §J, §5 ask 3 | Removal and local scope not expressible | `UpdatePayloadTaskCmd` → `setVariablesLocal`; `DeletePayloadTaskCmd` → `removeVariablesLocal`; `ClearPayloadTaskCmd` → remove all local variables (user tasks) | `emb: task/modification/C7UserTaskModificationApiImpl.kt:63-70`; `rem: task/modification/UserTaskModificationApiImpl.kt:59-70` |
| 4 | §J, §5 ask 3 | Serialization behaviour undocumented | Embedded docs state the supported Spin / Jackson 2 / Jackson 3 combinations for object variables; remote docs place Spin JSON with the remote engine runtime. Scope and the remote `ValueMapper` rules remain undocumented. | `docs/reference-c7-embedded.md:32-52`; `docs/reference-c7-remote.md:40-50` |
| 5 | §E, §5 ask 4 | Docs should say whether `EXECUTION_ID` works for correlation | The docs list the supported correlation restrictions (`tenantId`, `withoutTenantId`, `useGlobalCorrelationKey`), and `executionId` is not among them. Signal restrictions are not documented. | `docs/reference-c7-embedded.md:162-170`, `docs/reference-c7-remote.md:197-205` |
| 6 | §M | Form keys "may or may not" be in task meta | `formKey` is written for user tasks (conditional) | `emb: task/delivery/TaskInformationExtensions.kt:26`, `rem: task/delivery/TaskInformationExtensions.kt:45` |
| 7 | §E (`createProcessInstanceModification`) | No modification path | Starting a new instance at an element is supported. Modifying a running instance (both counted sites do this) is not. | `emb: process/StartProcessApiImpl.kt:75-107`; `rem: process/StartProcessApiImpl.kt:88-97` |

`python scripts/adapter_facts.py --check-report` checks every adapter citation in `report.md` against the source text at the pinned commit.

## 5. Other adapter findings (not added to report.md)

These findings came up while reading the adapter. Their report sections were outside the amendment scope.

- **Embedded user-task `CompleteTaskByErrorCmd`** calls `taskService.handleBpmnError(taskId, errorCode)`: the error message and payload are not passed (`emb: task/completion/C7UserTaskCompletionApiImpl.kt:47-50`). The remote adapter passes both (`rem: task/completion/UserTaskCompletionApiImpl.kt:47-54`). Relevant to §1 and §K.
- **Embedded `SendSignalCmd` tenant checks** require the opposite key to be present: `require(restrictions.containsKey(WITHOUT_TENANT_ID))` for `tenantId` (`emb: correlation/SignalApiImpl.kt:47-59`). So `tenantId` alone or `withoutTenantId` alone fails. The remote adapter negates the check (`rem: correlation/SignalApiImpl.kt:51-63`).
- **Embedded `ProcessInformation.meta`** stores the process definition id under `processDefinitionKey` (`emb: process/StartProcessApiImpl.kt:126`). Start-at-element reads it back as a definition id (`:84`). This is in §I.
- **Adapter/API versions.** The adapter build pins `process-engine-api` 1.7 (`pom.xml:24`); the analysed API checkout is `1.8-SNAPSHOT`. Differences between the two were not checked.

## 6. Open questions

1. **Remote serialization.** Typing and serialization rules of `ValueMapper` (`io.holunda.c7:c7-rest-client-variables`) are not settled. Its source is not in the analysed repositories.
2. **Typed values through the embedded adapter.** Does a `TypedValue` placed in the payload map (e.g. `Variables.objectValue(x).serializationDataFormat("application/json").create()`) keep its format? Not settled: the adapter passes the map through unchanged, but no engine was run.
3. **Remote user-task `businessKey`.** It is read from a task variable named `businessKey` in the task DTO (`rem: task/delivery/TaskInformationExtensions.kt:38`). The task query sets no variable-related options, and whether the REST response fills `variables` was not determined.
4. **Section 1 scope.** §1 does not say which repositories its "Sites" cover. Two draft values equal two-repository grep totals (`externalTaskService.complete` 22 = 6 + 16, `taskService.complete` 3 = 1 + 2), so both repositories were measured.
5. **The draft's §2A rule.** The rule behind 44 files / 59 sites and the per-method breakdown (sums to 50) could not be identified. The closest measured value is 57 `DelegateExecution.getProcessEngineServices()` sites.
6. **Coverage limits of static analysis:**
   - Delegates bound in BPMN via `camunda:expression` or `camunda:delegateExpression` to beans that do not implement the interfaces are not counted: BPMN XML was not analysed.
   - Scripts embedded in BPMN (Groovy, JavaScript) were not analysed.
   - A receiver is resolved only through declarations visible in the same project. A field inherited from a class outside the project, or a receiver variable named unlike its service (e.g. `rs`), stays unresolved and uncounted. The "unresolved" column only covers conventionally named receivers.
7. **Generated code.** `snippets/camunda-openapi-client` is generated code and is part of the file count. It declares no engine-typed calls, so it does not affect call-site counts.
