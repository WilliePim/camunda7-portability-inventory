# Field report: two open-source Camunda 7 codebases held against process-engine-api — what maps, what doesn't

**Type:** discussion / documentation input, not a bug
**Goal:** give maintainers (and anyone planning a C7 exit) a concrete, counted list of C7 usage patterns that have no expression in the API, so the "portable vs. not portable" line can be documented and effort estimated.

## Method

Static inventory (grep of call sites, main sources only, tests excluded) on two public C7 codebases, held against `process-engine-api` `api` module (HEAD, September 2026):

| Codebase | Main `.java` files | Why |
|---|---|---|
| `camunda/camunda-bpm-examples` | 124 | Official samples, broad coverage of platform integration |
| `camunda-consulting/code` (C7 snippets only) | 1,297 | Real-world consulting patterns, closest public thing to enterprise code |

Counts are **call sites**, not distinct features, and the consulting repo over-represents identity/authorization and platform-plugin snippets. Treat numbers as "how often this shape shows up", not as a benchmark. No customer code is included; banking patterns in the last section are from personal experience, anonymised.

API surface used as reference: `DeploymentApi`, `EvaluateDecisionApi`, `StartProcessApi`, `CorrelationApi`, `SignalApi`, `TaskSubscriptionApi`, `ServiceTaskCompletionApi`, `UserTaskCompletionApi`, `UserTaskModificationApi`, `UserTaskSupport`, `CommonRestrictions`.

## 1. What maps cleanly

| C7 pattern | Sites | API |
|---|---|---|
| `runtimeService.startProcessInstanceByKey / ById` | 19 + 27 chained | `StartProcessByDefinitionCmd` |
| `runtimeService.startProcessInstanceByMessage` | 2 | `StartProcessByMessageCmd` |
| `runtimeService.correlateMessage / createMessageCorrelation` | 7 + 7 chained | `CorrelateMessageCmd` |
| `runtimeService.signalEventReceived` | 1 | `SendSignalCmd` |
| `externalTaskService.complete` | 24 | `ServiceTaskCompletionApi.completeTask` |
| `externalTaskService.handleFailure` | 9 | `FailTaskCmd` (retries + backoff) |
| `ExternalTaskHandler` implementations | 6 | `TaskSubscriptionApi` + `TaskHandler` |
| `taskService.complete` | 3 + 12 chained | `UserTaskCompletionApi.completeTask` |
| `taskService.claim / setAssignee` | 11 | `ChangeAssignmentModifyTaskCmd` |
| `throw new BpmnError` from a *task* | 11 | `CompleteTaskByErrorCmd` |
| `repositoryService.createDeployment` | 9 | `DeployBundleCommand` |
| DMN `decisionService` / `DmnEngine.evaluate` | 7 | `EvaluateDecisionApi` |

The external-task style of C7 (`ExternalTaskHandler`, `complete`, `handleFailure`) is already the API's model. Code written that way ports almost mechanically.

## 2. What does not map — by pattern

### A. Business logic inside the engine transaction (`JavaDelegate`, `ExecutionListener`, `TaskListener`)

- **231 delegate/listener classes** (185 `JavaDelegate`, 25 `ExecutionListener`, 22 `TaskListener`) in the consulting repo, 24 + 2 in the examples.
- The API has no in-transaction hook: work is done by a subscriber *outside* the engine transaction and completed via a future.
- **47 of the 231 delegate files call engine services from inside the delegate** via `execution.getProcessEngineServices()` (72 sites total): `startProcessInstanceByKey` (4), `correlateMessage` (2), `taskService.complete` (5), `taskService.createTaskQuery` (4), `historyService.create*Query` (13), `repositoryService.*` (9), `identityService.*` (17), `caseService.*` (4).
- Some of these calls exist in the API (start, correlate) but the **semantics change**: in C7 they run in the same transaction as the calling delegate (atomic, rolled back together); in the API they are independent async commands. This is the pattern that decides the effort of a migration, and it is invisible to BPMN-level analysers.

Migration implication: every delegate becomes a worker; every engine call from inside a delegate becomes a separate command with its own failure mode. Not an API gap by design, but it deserves a documented statement ("delegates are out of scope; here is the rewrite shape").

### B. Query APIs (pull) vs. subscription (push)

| C7 | Sites |
|---|---|
| `taskService.createTaskQuery` | 39 + 25 chained |
| `historyService.createHistoric*Query` (process, activity, task, decision, variable, native) | 38 |
| `runtimeService.createProcessInstanceQuery / createExecutionQuery` | 20 |
| `repositoryService.createProcessDefinitionQuery / createDeploymentQuery / createDecisionDefinitionQuery` | 33 |
| `managementService.createJobQuery` | 5 |

The API is push-only (`subscribeForTask`); `UserTaskSupport` gives a local in-memory list of *subscribed* tasks, which is not a query. Every custom tasklist, dashboard, "where is my instance", or reconciliation batch in a C7 app is built on queries. This is the largest surface with no counterpart.

Ask: either a minimal read-only `TaskQueryApi` / `ProcessInstanceQueryApi` (by business key, definition key, tenant, activity — the keys already in `CommonRestrictions`), or an explicit "queries are out of scope, use engine-native or projections" note in the docs.

### C. History and audit

- 38 history query sites (above) plus **custom history infrastructure**: `HistoryEventHandler` (4), `DbHistoryEventHandler` subclasses (2), custom `HistoryLevel` (4), `HistoryEventProducer` (2), `DynamicRemovalTimeCalculationStrategy` (2).
- Nothing in the API touches history. In regulated environments (banking) history is a compliance artefact, not a nice-to-have; C8's history model is also different.

Ask: document that history is engine-native and that audit requirements must be met by the application (event sourcing / outbox from workers), not by the API.

### D. Identity, authorization, filters

- `identityService.*` 151 sites, `authorizationService.*` 121, `filterService.*` 45, plus `ReadOnlyIdentityProvider`, LDAP/Keycloak identity plugins, `AuthenticationExtractor`, `ProcessEngineAuthenticationFilter`.
- Zero counterpart. Clearly by design, but it is the second-largest block of code in the consulting repo and is common in enterprise C7 apps (provisioning users/groups/tenants at startup, candidate group logic).

### E. Process instance lifecycle and variables outside tasks

| C7 | Sites | Note |
|---|---|---|
| `runtimeService.setVariable / getVariable / getVariables` | 15 | variables on a running instance, not on a task |
| `runtimeService.signal(executionId)` | 4 | *execution* signal (wait state), not a BPMN signal event — different from `SendSignalCmd` |
| `runtimeService.messageEventReceived(name, executionId)` | 6 | maps partially to correlation, but targets an execution id |
| `deleteProcessInstance` | 1 | |
| `suspend/activateProcessInstanceByProcessDefinitionKey` | 4 | |
| `createProcessInstanceModification` | 2 | |
| `getActiveActivityIds` | 2 | |

Adapter citations in §E, §I and §J refer to `bpm-crafters/process-engine-adapters-camunda-7` at `d2be36e`: `emb:` = `engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/`, `rem:` = `engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/`, `docs:` = `docs/`; `api:` = `bpm-crafters/process-engine-api` at `b025698`, `api/src/main/kotlin/dev/bpmcrafters/processengineapi/`.

`CommonRestrictions.EXECUTION_ID` exists, but the C7 adapter does not honour it for message correlation. Both `CorrelationApiImpl` classes accept only `tenantId`, `withoutTenantId` and `useGlobalCorrelationKey` (emb: `correlation/CorrelationApiImpl.kt:59-63`, rem: `correlation/CorrelationApiImpl.kt:63-67`); any other key fails `ensureSupported` with `IllegalArgumentException` (api: `RestrictionAware.kt:27-28`). `messageEventReceived(name, executionId)` (6) has no path through `CorrelationApi`.

The adapter honours `EXECUTION_ID` for `SendSignalCmd` (emb: `correlation/SignalApiImpl.kt:61`, rem: `correlation/SignalApiImpl.kt:65`). That call is `createSignalEvent(name).executionId(id)` (emb: `correlation/SignalApiImpl.kt:28-32`): it delivers a signal event to one execution's signal subscription, not the wait-state trigger of `runtimeService.signal(executionId)` (4). The adapter also honours `EXECUTION_ID` when matching task subscriptions (emb: `task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:206`, `task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:239`; rem: `task/delivery/pull/PullUserTaskDelivery.kt:219`, `task/delivery/pull/PullServiceTaskDelivery.kt:282`).

Already covered by the adapter: the docs list the supported correlation restrictions, and `executionId` is not among them (docs: `reference-c7-embedded.md:162-170`, `reference-c7-remote.md:197-205`). Not covered: the docs have no restriction table for signals.

Starting at an element is expressible (`StartProcessByDefinitionAtElementCmd`, `StartProcessByMessageAtElementCmd`). The embedded adapter implements it as a start followed by a separate `createModification(...).startBeforeActivity(...)` (emb: `process/StartProcessApiImpl.kt:75-107`); the remote adapter sends `startInstructions` with the start request (rem: `process/StartProcessApiImpl.kt:88-97`). Modification of a running instance, as in the 2 `createProcessInstanceModification` sites, has no path. Instance-level variable access and cancellation have no path.

### F. Jobs, incidents, retries

- `managementService`: `setJobRetries`, `executeJob`, `activateJobById`, `recalculateJobDuedate`, `getJobExceptionStacktrace` (6 sites); `createIncident / resolveIncident` (0); custom `JobRetryCmd / FoxJobRetryCmd / DefaultJobRetryCmd` subclasses (6); custom `IncidentHandler` (3); `TimerEventJobHandler` (1).
- `FailTaskCmd` covers retries for the task at hand. Operations-side job/incident handling (retry storms, bulk re-run) has no counterpart.

### G. Engine internals (`org.camunda.bpm.engine.impl.*`)

- **617 imports across 176 files** (consulting) + 81 (examples). Top packages: `impl.cfg` 122, `impl.persistence` 66, `impl.bpmn` 65, `impl.pvm` 63, `impl.history` 51, `impl.interceptor` 46, `impl.context` 28, `impl.jobexecutor` 21.
- Concrete shapes: `ProcessEnginePlugin` / `AbstractProcessEnginePlugin` (49), `BpmnParseListener` / `AbstractBpmnParseListener` (18), custom `ActivityBehavior` (5), `CommandInterceptor` (4), `Command<T>` (3), `SessionFactory` (2), `TenantIdProvider` (4), `Context.getCommandContext()` / `Context.getProcessEngineConfiguration()` (44).
- Unportable by definition. Not an API concern, but a C7-exit assessment must count them: each one is a design decision, not a rewrite.

### H. CMMN

- `caseService.*` 31 sites, `CaseExecutionListener` (10). Dead end on every target engine; worth a one-line "not supported, no plan" in the feature matrix.

### I. Delegate context reads → `TaskInformation.meta`

Most-used reads inside delegates: `getVariable` 205, `setVariable` 134, `getId` 91, `getProcessInstanceId` 80, `getCurrentActivityId` 74, `getProcessBusinessKey` 72, `getCurrentActivityName` 71, `getProcessDefinitionId` 71, `getBpmnModelElementInstance` 7, `getTenantId` 2.

`TaskInformation` is `taskId + Map<String,String> meta`. `CommonRestrictions` names `activityId`, `businessKey`, `correlationKey`, `processDefinitionKey`, `processInstanceId`, `processDefinitionId`, `processDefinitionVersionTag`, `tenantId`, `withoutTenantId`, `messageId`, `messageTTL`, `executionId` and `workerLockDurationInMilliseconds` (api: `CommonRestrictions.kt:12-64`). The API module has no **list of meta keys each adapter fills** for a subscribed task.

The C7 adapter fills the keys below. `metaOf` drops every key whose value is null (emb: `task/delivery/TaskInformationExtensions.kt:90-96`, rem: `task/delivery/TaskInformationExtensions.kt:94-100`), so every key read from the engine is conditional. Guaranteed keys:
- `reason`, on every task (api: `task/TaskInformation.kt:35-37`);
- `candidateUsers` / `candidateGroups`, on user tasks: comma-joined, empty string when there are none (emb: `task/delivery/TaskInformationExtensions.kt:78-83`, rem: `task/delivery/TaskInformationExtensions.kt:82-87`).

| Key | USER emb. | USER rem. | EXTERNAL emb. pull | EXTERNAL rem. pull | EXTERNAL rem. subscribed |
|---|---|---|---|---|---|
| `reason` | G | G | G | G | G |
| `candidateUsers`, `candidateGroups` | G | G | — | — | — |
| `activityId` | C | C | C | C | C |
| `processDefinitionId` | C | C | C | C | C |
| `processDefinitionKey` | C | C | C | C | C |
| `processInstanceId` | C | C | C | C | C |
| `tenantId` | C | C | C | C | C |
| `businessKey` | — | C (task variable named `businessKey`) | C | C | — |
| `processDefinitionVersionTag` | — | C | — | C | C |
| `taskName`, `taskDescription`, `assignee`, `formKey` | C | C | — | — | — |
| `creationDate` | C | C | C | C | C |
| `followUpDate`, `dueDate`, `lastUpdatedDate` | C | C | — | — | — |
| `topicName`, `retries` | — | — | C | C | C |
| `executionId` | — | — | — | — | — |

G = guaranteed, C = conditional (omitted when null), — = not written. Sources:

| Flavour | Source |
|---|---|
| USER emb. | emb: `task/delivery/TaskInformationExtensions.kt:11-31` |
| USER rem. | rem: `task/delivery/TaskInformationExtensions.kt:30-67` |
| EXTERNAL emb. pull | emb: `task/delivery/TaskInformationExtensions.kt:54-68` |
| EXTERNAL rem. pull | rem: `task/delivery/TaskInformationExtensions.kt:14-28` |
| EXTERNAL rem. subscribed | rem: `task/delivery/subscribe/ExternalTaskExtensions.kt:9-22` |

Termination notifications (delete, complete) carry only `reason` (emb: `task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:158`, `task/completion/C7UserTaskCompletionApiImpl.kt:36`).

`ProcessInformation.meta` returned by `startProcess` (all conditional):
- emb.: `processDefinitionKey`, `businessKey`, `tenantId`, `rootProcessInstanceId`, `processDefinitionId` (emb: `process/StartProcessApiImpl.kt:123-132`). The `processDefinitionKey` entry holds the process definition id (emb: `process/StartProcessApiImpl.kt:126`).
- rem.: `processDefinitionKey`, `businessKey`, `tenantId`, `processDefinitionId` (rem: `process/StartProcessApiImpl.kt:146-164`).

Delegate reads above against these keys:

| Delegate read | Meta key |
|---|---|
| `getCurrentActivityId` | `activityId` |
| `getProcessInstanceId` | `processInstanceId` |
| `getProcessDefinitionId` | `processDefinitionId`, in every flavour |
| `getTenantId` | `tenantId` |
| `getProcessBusinessKey` | `businessKey` on external tasks except remote subscribed; none on user tasks |
| `getVariable` / `setVariable` | payload (§J) |
| `getId` (execution id) | none: `executionId` is not written |
| `getCurrentActivityName` | `taskName` on user tasks; none on external tasks |
| `getBpmnModelElementInstance` | none |

Already covered by the adapter:
- A per-adapter table of meta keys exists in the adapter docs (docs: `reference-c7-embedded.md:175-208`, `reference-c7-remote.md:210-243`).
- The process definition *id* (versioned) is named (`CommonRestrictions.PROCESS_DEFINITION_ID`) and filled.

Ask: extend the existing docs tables with the guaranteed / conditional / absent marking above, and add the keys they omit (`processInstanceId`, `businessKey`, `formKey`, `retries`, `processDefinitionVersionTag`, `reason`). This single table would answer most "can my delegate be ported" questions.

### J. Variable semantics

- C7 code uses typed values (`ObjectValue`, `TypedValue`, `VariableMap`, `Variables.objectValue(...).serializationDataFormat(...)`, Spin JSON/XML), local vs. process scope (`setVariableLocal` 7, `getVariableLocal` 4), `removeVariable` (6), `hasVariable` (4).
- The API payload is `Map<String, Any?>`. Start, correlate, signal and complete commands have no scope, removal or serialization-format parameter. In C7 apps the serialization format is frequently pinned per variable for Cockpit readability or for cross-version compatibility.

What the C7 adapter does with a payload map:
- **Scope on write.** Start, correlate, signal and complete pass the map to the non-local variable APIs:
  - start: `startProcessInstanceByKey(key, businessKey, payload)` (emb: `process/StartProcessApiImpl.kt:51-55`), `variables` (rem: `process/StartProcessApiImpl.kt:44`);
  - correlate: `setVariables` / `processVariables` (emb: `correlation/CorrelationApiImpl.kt:45`, rem: `correlation/CorrelationApiImpl.kt:43`);
  - signal: `setVariables` / `variables` (emb: `correlation/SignalApiImpl.kt:31`, rem: `correlation/SignalApiImpl.kt:29`);
  - user task completion: `taskService.complete(taskId, payload)` (emb: `task/completion/C7UserTaskCompletionApiImpl.kt:30-33`, rem: `task/completion/UserTaskCompletionApiImpl.kt:30-35`);
  - external task completion sets no local variables (emb: `task/completion/C7ServiceTaskCompletionApiImpl.kt:29-33`, rem: `task/completion/FeignServiceTaskCompletionApiImpl.kt:32-36`). The remote official-client variant passes an empty local map (rem: `task/completion/OfficialClientServiceTaskCompletionApiImpl.kt:26-31`).
  - On start, the payload entry `businessKey` becomes the business key and also stays a variable (emb: `process/StartProcessApiImpl.kt:51-55`, rem: `process/StartProcessApiImpl.kt:41-44`).
- **Local scope and removal.** User-task payload modification is task-local. `UpdatePayloadTaskCmd` maps to `setVariablesLocal`, `DeletePayloadTaskCmd` to `removeVariablesLocal`, and `ClearPayloadTaskCmd` removes all local variables (emb: `task/modification/C7UserTaskModificationApiImpl.kt:63-70`, rem: `task/modification/UserTaskModificationApiImpl.kt:59-70`). No other command writes local variables or removes variables.
- **Scope on read.** A user-task handler receives all variables visible from the task (`getVariables`, not `getVariablesLocal`), filtered in memory by the subscription's payload description (emb: `task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:92`, rem: `task/delivery/pull/PullUserTaskDelivery.kt:96-100`). External tasks are fetched with all variables and filtered in memory (emb: `task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:122`, `:211-223`; rem: `task/delivery/pull/PullServiceTaskDelivery.kt:129`). The remote subscribed delivery restricts variable names at fetch time (rem: `task/delivery/subscribe/SubscribingServiceTaskDelivery.kt:125-131`).
- **Serialization, embedded.** The adapter does not convert the map; it hands the map to the C7 Java API, so the engine's variable serializers and default serialization format apply. `AdapterDataConverter` (Jackson 2 / 3) is used only for decision results (emb: `decision/DelegatingDmnDecisionEvaluationOutput.kt:11-22`). The docs state two constraints (docs: `reference-c7-embedded.md:32-52`):
  - Spin JSON serialization requires Jackson 2 on the adapter side;
  - Jackson 3 setups work with Java serialization of object variables.
- **Serialization, remote.** Every outbound map goes through `ValueMapper.mapValues` from `io.holunda.c7:c7-rest-client-variables` (`engine-adapter/c7-remote-core/pom.xml:53-58`; rem: `task/completion/UserTaskCompletionApiImpl.kt:33`). Its typing and serialization rules are defined outside the adapter repository and were not read.

Already covered by the adapter:
- task-local writes and variable removal for user tasks (`UpdatePayloadTaskCmd`, `DeletePayloadTaskCmd`, `ClearPayloadTaskCmd`);
- a documented Spin / Jackson serialization stance for the embedded adapter.

Ask: document three points:
- start, correlate, signal and complete write process-scope variables;
- local scope and removal exist only as user-task payload modification;
- the remote `ValueMapper` serialization rules.

### K. Errors from listeners

- `BpmnError` thrown from a task maps (`CompleteTaskByErrorCmd`). `BpmnError` thrown from an `ExecutionListener` (start/end events, sequence flows) has no counterpart because listeners themselves don't exist.

### L. Repository beyond deployment

- `deleteDeployment` (2), `getProcessDiagram / getProcessDiagramLayout` (7), `getBpmnModelInstance / getProcessModel` (2), `getProcessDefinition` (3). Deployment maps; introspection does not.

### M. Forms

- `formService.getTaskFormData / getStartFormKey` (3). Not in the API; form keys may or may not appear in task meta.

## 3. Summary table

| Area | Sites (both repos) | In API | Verdict |
|---|---|---|---|
| Start / correlate / signal | 63 | yes | ports |
| External-task worker style | 39 | yes | ports |
| User task complete / assign / by-error | 37 | yes | ports |
| Deployment, DMN evaluate | 16 | yes | ports |
| Delegates & listeners in shared transaction | 257 classes, 73 nested engine calls | no | rewrite as workers; semantics change |
| Queries (task, history, runtime, repository, job) | 160 | no | largest gap; needs a stance |
| History infrastructure | 14 classes | no | engine-native; document |
| Identity / authorization / filters | 317 | no | out of scope; document |
| Instance lifecycle, instance variables | 34 | partial | `EXECUTION_ID` may cover part; document |
| Jobs / incidents / retries (ops) | 16 | partial | `FailTaskCmd` only |
| Engine internals (`impl.*`) | 698 imports / 201 files | no | design work, not porting |
| CMMN | 41 | no | dead end; state it |
| Delegate context reads | 807 | partial | meta keys undocumented |
| Variable scope / typed values | 21 | partial | document adapter behaviour |

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
