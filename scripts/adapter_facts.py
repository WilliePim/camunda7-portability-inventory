"""Task 3: what the Camunda 7 adapter writes into meta, does with payloads, and
does with CommonRestrictions.EXECUTION_ID, pinned to file:line.

    python scripts/adapter_facts.py
    python scripts/adapter_facts.py --check-report   # also check the citations in report.md

Every citation carries the text expected on the cited line. The script checks it
against the clones in external/ and fails (exit 1) when a line no longer matches,
printing where the text moved to. The facts were read from the adapter source at
the commit pinned in scripts/repos.py; the script does not infer them.

Citation paths are relative to
  E: engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/
  R: engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/
  API: api/src/main/kotlin/dev/bpmcrafters/processengineapi/ (process-engine-api repo)
  DOCS: docs/ (adapter repo)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

from repos import REPOS, ROOT

BASES = {
    "E": (REPOS["adapter"], "engine-adapter/c7-embedded-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/embedded/"),
    "R": (REPOS["adapter"], "engine-adapter/c7-remote-core/src/main/kotlin/dev/bpmcrafters/processengineapi/adapter/c7/remote/"),
    "API": (REPOS["api"], "api/src/main/kotlin/dev/bpmcrafters/processengineapi/"),
    "DOCS": (REPOS["adapter"], "docs/"),
    "POM": (REPOS["adapter"], "engine-adapter/"),
}

G, C = "guaranteed", "conditional"


@dataclass(frozen=True)
class Cite:
    base: str
    path: str
    line: int
    needle: str

    def __str__(self) -> str:
        return f"{self.base}:{self.path}:{self.line}"


def cite(ref: str, needle: str) -> Cite:
    base, path, line = ref.split(":")
    return Cite(base, path, int(line), needle)


# ------------------------------------------------------------------ meta keys
E_TI = "task/delivery/TaskInformationExtensions.kt"
R_TI = "task/delivery/TaskInformationExtensions.kt"
R_SUB = "task/delivery/subscribe/ExternalTaskExtensions.kt"

# (key, status, citation) per flavour; status "conditional" = omitted when the value is null
USER_META = {
    "embedded": [
        ("processDefinitionKey", C, cite(f"E:{E_TI}:15", "PROCESS_DEFINITION_KEY to processDefinitionKey")),
        ("processDefinitionId", C, cite(f"E:{E_TI}:16", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
        ("activityId", C, cite(f"E:{E_TI}:17", "ACTIVITY_ID to this.taskDefinitionKey")),
        ("tenantId", C, cite(f"E:{E_TI}:18", "TENANT_ID to this.tenantId")),
        ("processInstanceId", C, cite(f"E:{E_TI}:19", "PROCESS_INSTANCE_ID to this.processInstanceId")),
        ("taskName", C, cite(f"E:{E_TI}:20", '"taskName" to this.name')),
        ("taskDescription", C, cite(f"E:{E_TI}:21", '"taskDescription" to this.description')),
        ("assignee", C, cite(f"E:{E_TI}:22", '"assignee" to this.assignee')),
        ("creationDate", C, cite(f"E:{E_TI}:23", '"creationDate" to this.createTime')),
        ("followUpDate", C, cite(f"E:{E_TI}:24", '"followUpDate" to this.followUpDate')),
        ("dueDate", C, cite(f"E:{E_TI}:25", '"dueDate" to this.dueDate')),
        ("formKey", C, cite(f"E:{E_TI}:26", '"formKey" to this.formKey')),
        ("candidateUsers", G, cite(f"E:{E_TI}:27", '"candidateUsers" to candidates.toUsersString()')),
        ("candidateGroups", G, cite(f"E:{E_TI}:28", '"candidateGroups" to candidates.toGroupsString()')),
        ("lastUpdatedDate", C, cite(f"E:{E_TI}:29", '"lastUpdatedDate" to this.lastUpdated')),
        ("reason", G, cite("E:task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:85", "withReason(TaskInformation.CREATE)")),
    ],
    "remote": [
        ("activityId", C, cite(f"R:{R_TI}:34", "ACTIVITY_ID to this.taskDefinitionKey")),
        ("tenantId", C, cite(f"R:{R_TI}:35", "TENANT_ID to this.tenantId")),
        ("processDefinitionId", C, cite(f"R:{R_TI}:36", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
        ("processInstanceId", C, cite(f"R:{R_TI}:37", "PROCESS_INSTANCE_ID to this.processInstanceId")),
        ("businessKey (from a task variable named businessKey)", C, cite(f"R:{R_TI}:38", "BUSINESS_KEY to this.variables?.get(CommonRestrictions.BUSINESS_KEY)")),
        ("taskName", C, cite(f"R:{R_TI}:39", '"taskName" to this.name')),
        ("taskDescription", C, cite(f"R:{R_TI}:40", '"taskDescription" to this.description')),
        ("assignee", C, cite(f"R:{R_TI}:41", '"assignee" to this.assignee')),
        ("creationDate", C, cite(f"R:{R_TI}:42", '"creationDate" to this.created')),
        ("followUpDate", C, cite(f"R:{R_TI}:43", '"followUpDate" to this.followUp')),
        ("dueDate", C, cite(f"R:{R_TI}:44", '"dueDate" to this.due')),
        ("formKey", C, cite(f"R:{R_TI}:45", '"formKey" to this.formKey')),
        ("candidateUsers", G, cite(f"R:{R_TI}:46", '"candidateUsers" to candidates.toUsersString()')),
        ("candidateGroups", G, cite(f"R:{R_TI}:47", '"candidateGroups" to candidates.toGroupsString()')),
        ("lastUpdatedDate", C, cite(f"R:{R_TI}:48", '"lastUpdatedDate" to this.lastUpdated')),
        ("processDefinitionKey (resolver)", C, cite(f"R:{R_TI}:55", "if (processDefinitionKey != null)")),
        ("processDefinitionVersionTag (resolver)", C, cite(f"R:{R_TI}:62", "if (processDefinitionVersionTag != null)")),
        ("reason", G, cite("R:task/delivery/pull/PullUserTaskDelivery.kt:89", "withReason(TaskInformation.CREATE)")),
    ],
}

EXTERNAL_META = {
    "embedded (pull)": [
        ("activityId", C, cite(f"E:{E_TI}:58", "ACTIVITY_ID to this.activityId")),
        ("processDefinitionId", C, cite(f"E:{E_TI}:59", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
        ("processDefinitionKey", C, cite(f"E:{E_TI}:60", "PROCESS_DEFINITION_KEY to this.processDefinitionKey")),
        ("processInstanceId", C, cite(f"E:{E_TI}:61", "PROCESS_INSTANCE_ID to this.processInstanceId")),
        ("tenantId", C, cite(f"E:{E_TI}:62", "TENANT_ID to this.tenantId")),
        ("businessKey", C, cite(f"E:{E_TI}:63", "BUSINESS_KEY to this.businessKey")),
        ("topicName", C, cite(f"E:{E_TI}:64", '"topicName" to this.topicName')),
        ("creationDate", C, cite(f"E:{E_TI}:65", '"creationDate" to this.createTime')),
        ("retries", C, cite(f"E:{E_TI}:66", "RETRIES to this.retries?.toString()")),
        ("reason", G, cite("E:task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:120", "withReason(CREATE)")),
    ],
    "remote (pull)": [
        ("activityId", C, cite(f"R:{R_TI}:18", "ACTIVITY_ID to this.activityId")),
        ("processDefinitionId", C, cite(f"R:{R_TI}:19", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
        ("processDefinitionKey", C, cite(f"R:{R_TI}:20", "PROCESS_DEFINITION_KEY to this.processDefinitionKey")),
        ("processInstanceId", C, cite(f"R:{R_TI}:21", "PROCESS_INSTANCE_ID to this.processInstanceId")),
        ("tenantId", C, cite(f"R:{R_TI}:22", "TENANT_ID to this.tenantId")),
        ("businessKey", C, cite(f"R:{R_TI}:23", "BUSINESS_KEY to this.businessKey")),
        ("topicName", C, cite(f"R:{R_TI}:24", '"topicName" to this.topicName')),
        ("creationDate", C, cite(f"R:{R_TI}:25", '"creationDate" to this.createTime')),
        ("retries", C, cite(f"R:{R_TI}:26", "RETRIES to this.retries?.toString()")),
        ("processDefinitionVersionTag (resolver)", C, cite(f"R:{R_TI}:27", "enrichWithProcessDefinitionMetadata")),
        ("reason", G, cite("R:task/delivery/pull/PullServiceTaskDelivery.kt:131", "withReason(CREATE)")),
    ],
    "remote (subscribed)": [
        ("activityId", C, cite(f"R:{R_SUB}:12", "ACTIVITY_ID to this.activityId")),
        ("processDefinitionKey", C, cite(f"R:{R_SUB}:13", "PROCESS_DEFINITION_KEY to this.processDefinitionKey")),
        ("processInstanceId", C, cite(f"R:{R_SUB}:14", "PROCESS_INSTANCE_ID to this.processInstanceId")),
        ("processDefinitionId", C, cite(f"R:{R_SUB}:15", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
        ("processDefinitionVersionTag", C, cite(f"R:{R_SUB}:16", "PROCESS_DEFINITION_VERSION_TAG to this.processDefinitionVersionTag")),
        ("tenantId", C, cite(f"R:{R_SUB}:17", "TENANT_ID to this.tenantId")),
        ("topicName", C, cite(f"R:{R_SUB}:18", '"topicName" to this.topicName')),
        ("creationDate", C, cite(f"R:{R_SUB}:19", '"creationDate" to this.createTime')),
        ("retries", C, cite(f"R:{R_SUB}:20", "RETRIES to this.retries?.toString()")),
        ("reason", G, cite("R:task/delivery/subscribe/SubscribingServiceTaskDelivery.kt:52", "withReason(TaskInformation.CREATE)")),
    ],
}

PROCESS_META = {
    "embedded": [
        ("processDefinitionKey (value is the process definition id)", C, cite("E:process/StartProcessApiImpl.kt:126", "PROCESS_DEFINITION_KEY to this.processDefinitionId")),
        ("businessKey", C, cite("E:process/StartProcessApiImpl.kt:127", "BUSINESS_KEY to this.businessKey")),
        ("tenantId", C, cite("E:process/StartProcessApiImpl.kt:128", "TENANT_ID to this.tenantId")),
        ("rootProcessInstanceId", C, cite("E:process/StartProcessApiImpl.kt:129", '"rootProcessInstanceId" to this.rootProcessInstanceId')),
        ("processDefinitionId", C, cite("E:process/StartProcessApiImpl.kt:130", "PROCESS_DEFINITION_ID to this.processDefinitionId")),
    ],
    "remote": [
        ("processDefinitionKey", C, cite("R:process/StartProcessApiImpl.kt:149", "PROCESS_DEFINITION_KEY to this.definitionKey")),
        ("businessKey", C, cite("R:process/StartProcessApiImpl.kt:150", "BUSINESS_KEY to this.businessKey")),
        ("tenantId", C, cite("R:process/StartProcessApiImpl.kt:151", "TENANT_ID to this.tenantId")),
        ("processDefinitionId", C, cite("R:process/StartProcessApiImpl.kt:152", "PROCESS_DEFINITION_ID to this.definitionId")),
    ],
}

META_RULES = [
    ("`metaOf` drops every pair whose value is null (both adapters): all engine-sourced keys are conditional.",
     [cite(f"E:{E_TI}:92", ".filter { it.second != null }"), cite(f"R:{R_TI}:96", ".filter { it.second != null }")]),
    ("candidateUsers/candidateGroups are `joinToString(\",\")` results, never null: always present, empty string when none.",
     [cite(f"E:{E_TI}:83", 'joinToString(",")'), cite(f"R:{R_TI}:87", 'joinToString(",")')]),
    ("`reason` is added by `withReason` on every delivery (create/assign/update) and termination (delete/complete).",
     [cite("API:task/TaskInformation.kt:36", "meta + (REASON to reason)")]),
    ("Termination and completion notifications carry `emptyMap()` meta plus `reason` only.",
     [cite("E:task/completion/C7UserTaskCompletionApiImpl.kt:36", "TaskInformation(cmd.taskId, emptyMap()).withReason(TaskInformation.COMPLETE)"),
      cite("E:task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:158", "TaskInformation(taskId = taskId,")]),
    ("No flavour writes `executionId` into task meta; no flavour writes an activity name for external tasks.",
     [cite(f"E:{E_TI}:54", "fun LockedExternalTask.toTaskInformation()"), cite(f"R:{R_SUB}:9", "fun ExternalTask.toTaskInformation()")]),
    ("Remote user-task `processDefinitionKey`/version tag come from a resolver and are added only when it returns non-null.",
     [cite(f"R:{R_TI}:52", "fun Map<String, String>.enrichWithProcessDefinitionMetadata")]),
    ("The adapter docs already publish meta-key tables for user and service tasks (no guaranteed/conditional marking; "
     "processInstanceId, businessKey, formKey, retries, version tag not listed).",
     [cite("DOCS:reference-c7-embedded.md:175", "task information meta block"), cite("DOCS:reference-c7-remote.md:210", "task information meta block")]),
]

# ------------------------------------------------------------- payload mapping
PAYLOAD = [
    ("start by definition", "variables on the new instance (global); business key read from payload key `businessKey`, which also stays a variable",
     [cite("E:process/StartProcessApiImpl.kt:51", "runtimeService.startProcessInstanceByKey("), cite("E:process/StartProcessApiImpl.kt:53", "payload[CommonRestrictions.BUSINESS_KEY]?.toString()"),
      cite("R:process/StartProcessApiImpl.kt:44", "this.variables = valueMapper.mapValues(payload)")]),
    ("start by message", "`setVariables` / `processVariables` (global)",
     [cite("E:process/StartProcessApiImpl.kt:70", ".setVariables(payload)"), cite("R:process/StartProcessApiImpl.kt:59", ".processVariables(valueMapper.mapValues(")]),
    ("correlate message", "`setVariables` / `processVariables`, not the `*Local` variants",
     [cite("E:correlation/CorrelationApiImpl.kt:45", ".setVariables(cmd.payloadSupplier.get())"), cite("R:correlation/CorrelationApiImpl.kt:43", ".processVariables(valueMapper.mapValues(payload))")]),
    ("send signal", "`setVariables` / `variables`",
     [cite("E:correlation/SignalApiImpl.kt:31", ".setVariables(cmd.payloadSupplier.get())"), cite("R:correlation/SignalApiImpl.kt:29", ".variables(valueMapper.mapValues(cmd.payloadSupplier.get()))")]),
    ("complete external task", "`variables` only; local variables never set (official client passes `mapOf()`)",
     [cite("E:task/completion/C7ServiceTaskCompletionApiImpl.kt:32", "cmd.get()"), cite("R:task/completion/FeignServiceTaskCompletionApiImpl.kt:34", "this.variables = valueMapper.mapValues(cmd.get())"),
      cite("R:task/completion/OfficialClientServiceTaskCompletionApiImpl.kt:30", "mapOf()")]),
    ("complete user task", "`taskService.complete(taskId, variables)` / `CompleteTaskDto.variables`",
     [cite("E:task/completion/C7UserTaskCompletionApiImpl.kt:30", "taskService.complete("), cite("R:task/completion/UserTaskCompletionApiImpl.kt:33", "this.variables = valueMapper.mapValues(cmd.get())")]),
    ("complete user task by error", "embedded passes error code only (message and payload dropped); remote passes message and variables",
     [cite("E:task/completion/C7UserTaskCompletionApiImpl.kt:47", "taskService.handleBpmnError("), cite("R:task/completion/UserTaskCompletionApiImpl.kt:52", "this.variables = valueMapper.mapValues(cmd.get())")]),
    ("modify user task payload", "task-local only: set / remove / remove all local variables",
     [cite("E:task/modification/C7UserTaskModificationApiImpl.kt:65", "taskService.setVariablesLocal(cmd.taskId, cmd.get())"),
      cite("E:task/modification/C7UserTaskModificationApiImpl.kt:66", "taskService.removeVariablesLocal(cmd.taskId, cmd.get())"),
      cite("R:task/modification/UserTaskModificationApiImpl.kt:61", "taskApiClient.modifyTaskLocalVariables(")]),
    ("read variables for a user task", "all visible variables (`getVariables`, not local), filtered in memory by payloadDescription",
     [cite("E:task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:92", "taskService.getVariables(task.id).filterBySubscription(activeSubscription)"),
      cite("R:task/delivery/pull/PullUserTaskDelivery.kt:96", "taskApiClient.getTaskVariables(task.id, deserializeOnServer)")]),
    ("read variables for an external task", "fetch-and-lock without a variable list (all variables), filtered in memory; remote subscribed restricts on the engine side",
     [cite("E:task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:219", ".enableCustomObjectDeserialization()"),
      cite("E:task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:122", "lockedTask.variables.filterBySubscription(activeSubscription)"),
      cite("R:task/delivery/pull/PullServiceTaskDelivery.kt:129", "valueMapper.mapDtos(lockedTask.variables!!).filterBySubscription(activeSubscription)"),
      cite("R:task/delivery/subscribe/SubscribingServiceTaskDelivery.kt:128", "this.variables(*subscription.payloadDescription!!.toTypedArray())")]),
    ("serialization, embedded", "no conversion: the raw map goes to the C7 Java API, so the engine's configured serializers apply "
     "(docs: Spin JSON needs Jackson 2; Java serialization otherwise)",
     [cite("DOCS:reference-c7-embedded.md:32", "## Jackson and Spin compatibility")]),
    ("serialization, remote", "`ValueMapper.mapValues` from io.holunda.c7 `c7-rest-client-variables`; rules live outside this repository",
     [cite("POM:c7-remote-core/pom.xml:55", "<artifactId>c7-rest-client-variables</artifactId>"),
      cite("DOCS:reference-c7-remote.md:50", "engine itself uses Spin for JSON variables")]),
]

# ------------------------------------------------------------------ restrictions
RESTRICTIONS = [
    ("unsupported restriction keys throw IllegalArgumentException (`require`)",
     [cite("API:RestrictionAware.kt:28", "require(areSupported(restrictions))")]),
    ("message correlation, embedded: supports tenantId, withoutTenantId, useGlobalCorrelationKey — executionId NOT honoured (rejected)",
     [cite("E:correlation/CorrelationApiImpl.kt:59", "override fun getSupportedRestrictions(): Set<String> = setOf("),
      cite("E:correlation/CorrelationApiImpl.kt:46", ".applyTenantRestrictions(ensureSupported(cmd.restrictions))")]),
    ("message correlation, remote: same three keys — executionId NOT honoured (rejected)",
     [cite("R:correlation/CorrelationApiImpl.kt:63", "override fun getSupportedRestrictions(): Set<String> = setOf("),
      cite("R:correlation/CorrelationApiImpl.kt:46", "ensureSupported(cmd.restrictions)")]),
    ("signal, embedded: executionId honoured",
     [cite("E:correlation/SignalApiImpl.kt:38", "CommonRestrictions.EXECUTION_ID,"), cite("E:correlation/SignalApiImpl.kt:61", "CommonRestrictions.EXECUTION_ID -> this.executionId(value)")]),
    ("signal, embedded: tenantId alone / withoutTenantId alone fail the `require` (condition not negated)",
     [cite("E:correlation/SignalApiImpl.kt:48", "require(restrictions.containsKey(CommonRestrictions.WITHOUT_TENANT_ID))")]),
    ("signal, remote: executionId honoured",
     [cite("R:correlation/SignalApiImpl.kt:37", "CommonRestrictions.EXECUTION_ID,"), cite("R:correlation/SignalApiImpl.kt:65", "CommonRestrictions.EXECUTION_ID -> this.executionId(value)")]),
    ("task subscriptions: executionId honoured when matching tasks (all four deliveries)",
     [cite("E:task/delivery/pull/EmbeddedPullUserTaskDelivery.kt:206", "CommonRestrictions.EXECUTION_ID -> it.value == task.executionId"),
      cite("E:task/delivery/pull/EmbeddedPullServiceTaskDelivery.kt:239", "CommonRestrictions.EXECUTION_ID -> it.value == task.executionId"),
      cite("R:task/delivery/pull/PullUserTaskDelivery.kt:219", "CommonRestrictions.EXECUTION_ID -> it.value == task.executionId"),
      cite("R:task/delivery/pull/PullServiceTaskDelivery.kt:282", "CommonRestrictions.EXECUTION_ID -> it.value == task.executionId")]),
    ("docs list the correlation restrictions (tenantId, withoutTenantId, useGlobalCorrelationKey)",
     [cite("DOCS:reference-c7-embedded.md:162", "## Message Correlation"), cite("DOCS:reference-c7-remote.md:197", "## Message Correlation")]),
]

# ---------------------------------------------------------------------- other
OTHER = [
    ("CommonRestrictions constants run from ACTIVITY_ID to WORKER_LOCK_DURATION_IN_MILLISECONDS",
     [cite("API:CommonRestrictions.kt:12", 'const val ACTIVITY_ID = "activityId"'),
      cite("API:CommonRestrictions.kt:37", 'const val PROCESS_DEFINITION_ID = "processDefinitionId"'),
      cite("API:CommonRestrictions.kt:64", 'const val WORKER_LOCK_DURATION_IN_MILLISECONDS')]),
    ("send signal, embedded: `createSignalEvent(name)` with restrictions applied, then `send()`",
     [cite("E:correlation/SignalApiImpl.kt:29", ".createSignalEvent(cmd.signalName)")]),
    ("start at element, embedded: a start, then a separate modification using the definition id stored under processDefinitionKey",
     [cite("E:process/StartProcessApiImpl.kt:83", "val instance = this.startProcess(startProcessCommand).get()"),
      cite("E:process/StartProcessApiImpl.kt:84", "instance.meta[CommonRestrictions.PROCESS_DEFINITION_KEY] as String"),
      cite("E:process/StartProcessApiImpl.kt:87", ".startBeforeActivity(cmd.elementId)")]),
    ("start at element, remote: start instructions sent with the start request",
     [cite("R:process/StartProcessApiImpl.kt:95", "startProcessInstanceDto.startInstructions(listOf(startInstructionDto))")]),
    ("AdapterDataConverter is used for decision results",
     [cite("E:decision/DelegatingDmnDecisionEvaluationOutput.kt:11", "private val dataConverter: AdapterDataConverter")]),
]

REPORT_PREFIX = {"emb": "E", "rem": "R", "api": "API", "docs": "DOCS"}
REPORT_TOKEN = re.compile(r"(?:(emb|rem|api|docs): )?`((?:[\w\-]+/)*[\w\-]+\.(?:kt|md|xml))?:(\d+)(?:-(\d+))?`")


def all_cites() -> list[Cite]:
    rows = [c for table in (USER_META, EXTERNAL_META, PROCESS_META) for flavour in table.values() for _, _, c in flavour]
    rows += [c for _, cs in META_RULES + RESTRICTIONS + OTHER for c in cs]
    rows += [c for _, _, cs in PAYLOAD for c in cs]
    return rows


def report_citations(text: str) -> list[tuple[str, str, int, int]]:
    """(base, path, first, last) for each adapter/API citation in report.md.

    A citation without a prefix inherits the last prefix in the same paragraph;
    a bare `:NN-MM` inherits the last path.
    """
    out = []
    for para in re.split(r"\n\s*\n", text):
        prefix = path = None
        for m in REPORT_TOKEN.finditer(para):
            prefix = REPORT_PREFIX[m.group(1)] if m.group(1) else prefix
            path = m.group(2) or path
            if path is None or prefix is None and not path.startswith("engine-adapter/"):
                continue
            first = int(m.group(3))
            last = int(m.group(4) or first)
            if path.startswith("engine-adapter/"):
                out.append(("POM", path[len("engine-adapter/"):], first, last))
            else:
                out.append((prefix, path, first, last))
    return out


def check(c: Cite) -> str:
    repo, base = BASES[c.base]
    lines = (repo.dir / base / c.path).read_text(encoding="utf-8").splitlines()
    if 0 < c.line <= len(lines) and c.needle in lines[c.line - 1]:
        return "ok"
    found = [i + 1 for i, line in enumerate(lines) if c.needle in line]
    return f"MOVED to {found}" if found else "MISSING"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-report", action="store_true",
                    help="also require every adapter/API citation in report.md to fall on a verified fact")
    args = ap.parse_args()
    failures: list[str] = []

    def ref(c: Cite) -> str:
        status = check(c)
        if status != "ok":
            failures.append(f"{c}: {status} (expected `{c.needle}`)")
            return f"`{c}` **{status}**"
        return f"`{c}`"

    print(f"Adapter commit {REPOS['adapter'].commit}, API commit {REPOS['api'].commit}\n")
    for title, table in (("TaskInformation.meta — USER tasks", USER_META),
                         ("TaskInformation.meta — EXTERNAL tasks", EXTERNAL_META),
                         ("ProcessInformation.meta (start process)", PROCESS_META)):
        print(f"## {title}\n")
        print("| Flavour | Key | Status | Citation |\n|---|---|---|---|")
        for flavour, rows in table.items():
            for key, status, c in rows:
                print(f"| {flavour} | `{key}` | {status} | {ref(c)} |")
        print()
    print("## Meta rules\n")
    for text, cites in META_RULES:
        print(f"- {text} " + ", ".join(ref(c) for c in cites))
    print("\n## Payload → C7 variables\n")
    print("| Operation | Behaviour | Citations |\n|---|---|---|")
    for op, text, cites in PAYLOAD:
        print(f"| {op} | {text} | " + "<br>".join(ref(c) for c in cites) + " |")
    print("\n## Restrictions and EXECUTION_ID\n")
    for text, cites in RESTRICTIONS:
        print(f"- {text}: " + ", ".join(ref(c) for c in cites))
    print("\n## Other\n")
    for text, cites in OTHER:
        print(f"- {text}: " + ", ".join(ref(c) for c in cites))

    if args.check_report:
        facts = all_cites()
        cited = report_citations((ROOT / "report.md").read_text(encoding="utf-8"))
        print(f"\n## report.md citations\n\n{len(cited)} adapter/API citations found in report.md.")
        for base, path, first, last in cited:
            if not any(f.base == base and f.path == path and first <= f.line <= last for f in facts):
                failures.append(f"report.md cites {base}:{path}:{first}-{last}, not covered by a verified fact above")
    if failures:
        print("\n## Citation check FAILED\n")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)
    print("\nAll citations verified.")


if __name__ == "__main__":
    main()
