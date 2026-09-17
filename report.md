# Field report: two open-source Camunda 7 codebases held against process-engine-api — what maps, what doesn't

**Type:** discussion / documentation input, not a bug
**Goal:** give maintainers (and anyone planning a C7 exit) a concrete, counted list of C7 usage patterns that have no expression in the API, so the "portable vs. not portable" line can be documented and effort estimated.

## Method

Static inventory (grep of call sites, main sources only, tests excluded) on two public C7 codebases, held against `process-engine-api` `api` module (HEAD, September 2026):

| Codebase | Main `.java` files | Why |
|---|---|---|
| `camunda/camunda-bpm-examples` | 122 | Official samples, broad coverage of platform integration |
| `camunda-consulting/code` (C7 snippets only) | 1,298 | Real-world consulting patterns, closest public thing to enterprise code |

Counts are **call sites**, not distinct features, and the consulting repo over-represents identity/authorization and platform-plugin snippets. Treat numbers as "how often this shape shows up", not as a benchmark. No customer code is included; banking patterns in the last section are from personal experience, anonymised.

API surface used as reference: `DeploymentApi`, `EvaluateDecisionApi`, `StartProcessApi`, `CorrelationApi`, `SignalApi`, `TaskSubscriptionApi`, `ServiceTaskCompletionApi`, `UserTaskCompletionApi`, `UserTaskModificationApi`, `UserTaskSupport`, `CommonRestrictions`.

## 1. What maps cleanly

| C7 pattern | Sites | API |
|---|---|---|
| `runtimeService.startProcessInstanceByKey / ById` | 18 + 51 chained | `StartProcessByDefinitionCmd` |
| `runtimeService.startProcessInstanceByMessage` | 2 | `StartProcessByMessageCmd` |
| `runtimeService.correlateMessage / createMessageCorrelation` | 9 + 4 chained | `CorrelateMessageCmd` |
| `runtimeService.signalEventReceived` | 1 | `SendSignalCmd` |
| `externalTaskService.complete` | 22 | `ServiceTaskCompletionApi.completeTask` |
| `externalTaskService.handleFailure` | 9 | `FailTaskCmd` (retries + backoff) |
| `ExternalTaskHandler` implementations | 7 | `TaskSubscriptionApi` + `TaskHandler` |
| `taskService.complete` | 3 + 12 chained | `UserTaskCompletionApi.completeTask` |
| `taskService.claim / setAssignee` | 6 | `ChangeAssignmentModifyTaskCmd` |
| `throw new BpmnError` from a *task* | 13 | `CompleteTaskByErrorCmd` |
| `repositoryService.createDeployment` | 6 | `DeployBundleCommand` |
| DMN `decisionService` / `DmnEngine.evaluate` | 2 | `EvaluateDecisionApi` |

The external-task style of C7 (`ExternalTaskHandler`, `complete`, `handleFailure`) is already the API's model. Code written that way ports almost mechanically.

## 2. What does not map — by pattern

### A. Business logic inside the engine transaction (`JavaDelegate`, `ExecutionListener`, `TaskListener`)

- **231 delegate/listener classes** (184 `JavaDelegate`, 25 `ExecutionListener`, 22 `TaskListener`) in the consulting repo, 24 + 2 in the examples.
- The API has no in-transaction hook: work is done by a subscriber *outside* the engine transaction and completed via a future.
- **44 of the 231 delegate files call engine services from inside the delegate** via `execution.getProcessEngineServices()` (59 sites total): `startProcessInstanceByKey` (3), `correlateMessage` (2), `taskService.complete` (4), `taskService.createTaskQuery` (3), `historyService.create*Query` (9), `repositoryService.*` (10), `identityService.*` (6), `caseService.*` (13).
- Some of these calls exist in the API (start, correlate) but the **semantics change**: in C7 they run in the same transaction as the calling delegate (atomic, rolled back together); in the API they are independent async commands. This is the pattern that decides the effort of a migration, and it is invisible to BPMN-level analysers.

Migration implication: every delegate becomes a worker; every engine call from inside a delegate becomes a separate command with its own failure mode. Not an API gap by design, but it deserves a documented statement ("delegates are out of scope; here is the rewrite shape").

### B. Query APIs (pull) vs. subscription (push)

| C7 | Sites |
|---|---|
| `taskService.createTaskQuery` | 39 + 20 chained |
| `historyService.createHistoric*Query` (process, activity, task, decision, variable, native) | 35 |
| `runtimeService.createProcessInstanceQuery / createExecutionQuery` | 13 |
| `repositoryService.createProcessDefinitionQuery / createDeploymentQuery / createDecisionDefinitionQuery` | 25 |
| `managementService.createJobQuery` | 3 |

The API is push-only (`subscribeForTask`); `UserTaskSupport` gives a local in-memory list of *subscribed* tasks, which is not a query. Every custom tasklist, dashboard, "where is my instance", or reconciliation batch in a C7 app is built on queries. This is the largest surface with no counterpart.

Ask: either a minimal read-only `TaskQueryApi` / `ProcessInstanceQueryApi` (by business key, definition key, tenant, activity — the keys already in `CommonRestrictions`), or an explicit "queries are out of scope, use engine-native or projections" note in the docs.

### C. History and audit

- 35 history query sites (above) plus **custom history infrastructure**: `HistoryEventHandler` (4), `DbHistoryEventHandler` subclasses (2), custom `HistoryLevel` (2), `HistoryEventProducer` (2), `DynamicRemovalTimeCalculationStrategy` (2).
- Nothing in the API touches history. In regulated environments (banking) history is a compliance artefact, not a nice-to-have; C8's history model is also different.

Ask: document that history is engine-native and that audit requirements must be met by the application (event sourcing / outbox from workers), not by the API.

### D. Identity, authorization, filters

- `identityService.*` ≈ 120 sites, `authorizationService.*` ≈ 115, `filterService.*` ≈ 43, plus `ReadOnlyIdentityProvider`, LDAP/Keycloak identity plugins, `AuthenticationExtractor`, `ProcessEngineAuthenticationFilter`.
- Zero counterpart. Clearly by design, but it is the second-largest block of code in the consulting repo and is common in enterprise C7 apps (provisioning users/groups/tenants at startup, candidate group logic).

### E. Process instance lifecycle and variables outside tasks

| C7 | Sites | Note |
|---|---|---|
| `runtimeService.setVariable / getVariable / getVariables` | 12 | variables on a running instance, not on a task |
| `runtimeService.signal(executionId)` | 5 | *execution* signal (wait state), not a BPMN signal event — different from `SendSignalCmd` |
| `runtimeService.messageEventReceived(name, executionId)` | 7 | maps partially to correlation, but targets an execution id |
| `deleteProcessInstance` | 1 | |
| `suspend/activateProcessInstanceByProcessDefinitionKey` | 4 | |
| `createProcessInstanceModification` | 1 | |
| `getActiveActivityIds` | 2 | |

`CommonRestrictions.EXECUTION_ID` exists, so execution-targeted correlation may be expressible; the docs should say so. Instance-level variable access and cancellation have no path.

### F. Jobs, incidents, retries

- `managementService`: `setJobRetries`, `executeJob`, `activateJobById`, `recalculateJobDuedate`, `getJobExceptionStacktrace` (6 sites); `createIncident / resolveIncident` (9); custom `JobRetryCmd / FoxJobRetryCmd / DefaultJobRetryCmd` subclasses (4); custom `IncidentHandler` (2); `TimerEventJobHandler` (1).
- `FailTaskCmd` covers retries for the task at hand. Operations-side job/incident handling (retry storms, bulk re-run) has no counterpart.

### G. Engine internals (`org.camunda.bpm.engine.impl.*`)

- **615 imports across 176 files** (consulting) + ~60 (examples). Top packages: `impl.cfg` 121, `impl.persistence` 65, `impl.bpmn` 63, `impl.pvm` 62, `impl.history` 50, `impl.interceptor` 46, `impl.context` 28, `impl.jobexecutor` 21.
- Concrete shapes: `ProcessEnginePlugin` / `AbstractProcessEnginePlugin` (42), `BpmnParseListener` / `AbstractBpmnParseListener` (22), custom `ActivityBehavior` (3), `CommandInterceptor` (3), `Command<T>` (3), `SessionFactory` (2), `TenantIdProvider` (4), `Context.getCommandContext()` / `Context.getProcessEngineConfiguration()` (4).
- Unportable by definition. Not an API concern, but a C7-exit assessment must count them: each one is a design decision, not a rewrite.

### H. CMMN

- `caseService.*` ≈ 45 sites, `CaseExecutionListener` (10). Dead end on every target engine; worth a one-line "not supported, no plan" in the feature matrix.

### I. Delegate context reads → `TaskInformation.meta`

Most-used reads inside delegates: `getVariable` 202, `setVariable` 125, `getId` 93, `getProcessInstanceId` 81, `getCurrentActivityId` 79, `getCurrentActivityName` 73, `getProcessBusinessKey` 71, `getProcessDefinitionId` 70, `getBpmnModelElementInstance` 6, `getTenantId` 3.

`TaskInformation` is `taskId + Map<String,String> meta`. `CommonRestrictions` names `activityId`, `businessKey`, `processDefinitionKey`, `processInstanceId`, `tenantId`, `executionId`, but I could not find, in the API module, a **guaranteed list of meta keys each adapter fills** for a subscribed task. Activity *name*, process definition *id* (versioned), and model-element access are not named anywhere.

Ask: a documented, per-adapter table of meta keys (guaranteed / best-effort / absent). This single table would answer most "can my delegate be ported" questions.

### J. Variable semantics

- C7 code uses typed values (`ObjectValue`, `TypedValue`, `VariableMap`, `Variables.objectValue(...).serializationDataFormat(...)`, Spin JSON/XML), local vs. process scope (`setVariableLocal` 3, `getVariableLocal` 3), `removeVariable` (5), `hasVariable` (5).
- The API payload is `Map<String, Any?>`. Scope (local/global), removal, and serialization format are not expressible. In C7 apps the serialization format is frequently pinned per variable for Cockpit readability or for cross-version compatibility.

Ask: document what the C7 adapter does with a payload map (global scope? JSON? Java serialization?) and that local-scope and removal are unsupported.

### K. Errors from listeners

- `BpmnError` thrown from a task maps (`CompleteTaskByErrorCmd`). `BpmnError` thrown from an `ExecutionListener` (start/end events, sequence flows) has no counterpart because listeners themselves don't exist.

### L. Repository beyond deployment

- `deleteDeployment` (4), `getProcessDiagram / getProcessDiagramLayout` (7), `getBpmnModelInstance / getProcessModel` (4), `getProcessDefinition` (3). Deployment maps; introspection does not.

### M. Forms

- `formService.getTaskFormData / getStartFormKey` (3). Not in the API; form keys may or may not appear in task meta.

## 3. Summary table

| Area | Sites (both repos) | In API | Verdict |
|---|---|---|---|
| Start / correlate / signal | ~90 | yes | ports |
| External-task worker style | ~40 | yes | ports |
| User task complete / assign / by-error | ~35 | yes | ports |
| Deployment, DMN evaluate | ~10 | yes | ports |
| Delegates & listeners in shared transaction | 231 classes, 59 nested engine calls | no | rewrite as workers; semantics change |
| Queries (task, history, runtime, repository, job) | ~135 | no | largest gap; needs a stance |
| History infrastructure | ~12 classes | no | engine-native; document |
| Identity / authorization / filters | ~280 | no | out of scope; document |
| Instance lifecycle, instance variables | ~30 | partial | `EXECUTION_ID` may cover part; document |
| Jobs / incidents / retries (ops) | ~20 | partial | `FailTaskCmd` only |
| Engine internals (`impl.*`) | 615 imports / 176 files | no | design work, not porting |
| CMMN | ~55 | no | dead end; state it |
| Delegate context reads | ~700 | partial | meta keys undocumented |
| Variable scope / typed values | ~20 | partial | document adapter behaviour |

## 4. Patterns from banking codebases (anonymised, from experience — not from the two repos above)

<!-- SIMONE: fill this in. Keep it to shapes, no client names, no code. Suggested prompts: -->
- Delegates that open their own JDBC/JPA transaction on a bank DB *and* rely on the engine transaction for rollback (dual-write with no outbox).
- `TaskListener` on `create` that computes candidate groups from an external entitlements system (identity + shared transaction).
- History queries used as the audit trail for regulators (activity instances + variable history joined by business key).
- `runtimeService.signal(executionId)` used as a wait/resume mechanism for asynchronous host-system callbacks (mainframe batch replies).
- `BpmnParseListener` injecting execution listeners on every service task for logging/metrics.
- Variables pinned to JSON serialization for Cockpit and for cross-version compatibility during blue/green deployments.
<!-- end -->

## 5. Concrete asks to maintainers

1. **Meta-key table per adapter** (§I). Highest value per line of documentation.
2. **Stance on queries** (§B): minimal read-only API, or explicit out-of-scope.
3. **Adapter behaviour for variables** (§J): scope, serialization, removal.
4. **Feature matrix additions**: CMMN (not supported), execution-targeted correlation via `EXECUTION_ID` (supported?), listeners (out of scope).
5. Optional: a short "portability checklist" mapping C7 packages/interfaces → {API / engine-native / rewrite}. The counts above suggest where to start.

## Caveats

Static grep, no runtime; snippet repositories, not production applications; counts include duplicated snippets across similar examples; C8-specific folders excluded. Happy to re-run the inventory against any codebase the maintainers prefer, or to turn the summary table into a docs page.
