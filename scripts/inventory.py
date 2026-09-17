"""Reproduce every count in report.md (method table, sections 1, 2 and 3).

    python scripts/inventory.py                   # markdown table on stdout
    python scripts/inventory.py --json out/inventory.json
    python scripts/inventory.py --explain 1.start.chained   # list counted and rejected sites
    python scripts/inventory.py --explain 2G.imports        # impl.* imports ranked by package

Each row is a spec below. Call-site specs count `method_invocation` nodes whose
receiver type resolves (see javaindex.py) to one of the listed Camunda types:
  direct  = receiver is a variable, parameter or field (`runtimeService.x()`)
  chained = receiver is a call (`processEngine.getRuntimeService().x()`)
"unresolved" = sites with a matching method name whose receiver text looks like
the service (e.g. contains `runtimeService`) but whose type could not be
resolved; they are NOT included in "measured".
Class specs count named, non-interface class declarations whose own
extends/implements clause names one of the listed types (resolved by import).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from delegate_scopes import DelegateScopes, analyse, summarise
from javaindex import (
    CLIENT_EXTERNAL_TASK_HANDLER, CLIENT_EXTERNAL_TASK_SERVICE, CONTEXT, DELEGATE_EXECUTION, DELEGATE_TASK,
    JAVA_DELEGATE, SERVICES, CorpusIndex, load_indexes, text, walk,
)
from repos import CORPORA

E = "org.camunda.bpm.engine."
RS, TS, REPO, HS = SERVICES["RuntimeService"], SERVICES["TaskService"], SERVICES["RepositoryService"], SERVICES["HistoryService"]
IS, AS, FS, CS = SERVICES["IdentityService"], SERVICES["AuthorizationService"], SERVICES["FilterService"], SERVICES["CaseService"]
MS, FORM, DS = SERVICES["ManagementService"], SERVICES["FormService"], SERVICES["DecisionService"]
ETS = {SERVICES["ExternalTaskService"], CLIENT_EXTERNAL_TASK_SERVICE}
DMN_ENGINE = "org.camunda.bpm.dmn.engine.DmnEngine"
ANY_ENGINE = "any org.camunda.bpm.engine.* type"
IN_DELEGATE = "delegate"


@dataclass
class Calls:
    receivers: set[str] | str
    methods: str  # regex, full match
    shape: str = "any"  # any | direct | chained
    where: str = "anywhere"  # anywhere | delegate (inside a JavaDelegate/ExecutionListener/TaskListener scope)
    hint: str | None = None  # receiver-text regex for the "unresolved" column

    def describe(self) -> str:
        r = self.receivers if isinstance(self.receivers, str) else ", ".join(sorted(x.rsplit(".", 1)[-1] for x in self.receivers))
        parts = [f"calls `{self.methods}` on {r}"]
        if self.shape != "any":
            parts.append(f"{self.shape} receiver")
        if self.where == IN_DELEGATE:
            parts.append("inside delegate/listener scope")
        return "; ".join(parts)


@dataclass
class Classes:
    supertypes: set[str]  # FQNs; an entry ending in "." matches a package prefix

    def describe(self) -> str:
        return "named classes extending/implementing " + ", ".join(sorted(s.rsplit(".", 1)[-1] or s for s in self.supertypes))


@dataclass
class Throws:
    exception: str
    where: str  # interface FQN whose scope the throw must be in

    def describe(self) -> str:
        return f"`throw new {self.exception.rsplit('.', 1)[-1]}` inside {self.where.rsplit('.', 1)[-1]} scope"


@dataclass
class Imports:
    prefix: str
    measure: str  # declarations | files | package:<segment>

    def describe(self) -> str:
        return f"import declarations of `{self.prefix}*` ({self.measure})"


@dataclass
class Delegates:
    key: str  # key in delegate_scopes.summarise()

    def describe(self) -> str:
        return f"delegate_scopes `{self.key}`"


@dataclass
class Files:
    rule: str  # main | draft

    def describe(self) -> str:
        return "`src/main/` .java files, C8 folders excluded" if self.rule == "main" else "draft rule: .java paths without `/test/`"


@dataclass
class Sum:
    ids: list[str]

    def describe(self) -> str:
        return "sum of " + ", ".join(self.ids)


@dataclass
class Spec:
    id: str
    section: str
    label: str
    reported: str
    how: object
    scope: str = "both"  # both | examples | consulting
    measured: dict[str, int] = field(default_factory=dict)
    unresolved: int | None = None


def hint(name: str) -> str:
    return rf"(?i)\b(get)?{name}\b"


SPECS: list[Spec] = [
    # ---------------------------------------------------------------- method
    Spec("m.files.examples", "Method", "camunda-bpm-examples main .java files", "122", Files("main"), "examples"),
    Spec("m.files.consulting", "Method", "camunda-consulting/code main .java files (C7 only)", "1,298", Files("main"), "consulting"),
    # ------------------------------------------------------------ section 1
    Spec("1.start.direct", "1", "runtimeService.startProcessInstanceByKey / ById", "18",
         Calls({RS}, "startProcessInstanceBy(Key|Id)", "direct", hint=hint("runtimeService"))),
    Spec("1.start.chained", "1", "… chained", "51", Calls({RS}, "startProcessInstanceBy(Key|Id)", "chained", hint=hint("runtimeService"))),
    Spec("1.startByMessage", "1", "runtimeService.startProcessInstanceByMessage", "2",
         Calls({RS}, "startProcessInstanceByMessage", hint=hint("runtimeService"))),
    Spec("1.correlate.direct", "1", "runtimeService.correlateMessage / createMessageCorrelation", "9",
         Calls({RS}, "correlateMessage|createMessageCorrelation", "direct", hint=hint("runtimeService"))),
    Spec("1.correlate.chained", "1", "… chained", "4",
         Calls({RS}, "correlateMessage|createMessageCorrelation", "chained", hint=hint("runtimeService"))),
    Spec("1.signalEvent", "1", "runtimeService.signalEventReceived", "1", Calls({RS}, "signalEventReceived", hint=hint("runtimeService"))),
    Spec("1.ext.complete", "1", "externalTaskService.complete (engine + client)", "22", Calls(ETS, "complete", hint=hint("externalTaskService"))),
    Spec("1.ext.handleFailure", "1", "externalTaskService.handleFailure (engine + client)", "9",
         Calls(ETS, "handleFailure", hint=hint("externalTaskService"))),
    Spec("1.ext.handler", "1", "ExternalTaskHandler implementations", "7", Classes({CLIENT_EXTERNAL_TASK_HANDLER})),
    Spec("1.task.complete.direct", "1", "taskService.complete", "3", Calls({TS}, "complete", "direct", hint=hint("taskService"))),
    Spec("1.task.complete.chained", "1", "… chained", "12", Calls({TS}, "complete", "chained", hint=hint("taskService"))),
    Spec("1.task.claim", "1", "taskService.claim / setAssignee", "6", Calls({TS}, "claim|setAssignee", hint=hint("taskService"))),
    Spec("1.bpmnError", "1", "throw new BpmnError from a task (JavaDelegate)", "13", Throws(E + "delegate.BpmnError", JAVA_DELEGATE)),
    Spec("1.deploy", "1", "repositoryService.createDeployment", "6", Calls({REPO}, "createDeployment", hint=hint("repositoryService"))),
    Spec("1.dmn", "1", "decisionService / DmnEngine evaluate*", "2", Calls({DS, DMN_ENGINE}, "evaluate\\w*", hint=r"(?i)decisionService|dmnEngine")),
    # --------------------------------------------------------------- 2A
    Spec("2A.classes", "2A", "delegate/listener classes (consulting)", "231", Delegates("classes"), "consulting"),
    Spec("2A.javaDelegate", "2A", "… JavaDelegate (consulting)", "184", Delegates("JavaDelegate"), "consulting"),
    Spec("2A.executionListener", "2A", "… ExecutionListener (consulting)", "25", Delegates("ExecutionListener"), "consulting"),
    Spec("2A.taskListener", "2A", "… TaskListener (consulting)", "22", Delegates("TaskListener"), "consulting"),
    Spec("2A.examples.javaDelegate", "2A", "JavaDelegate classes (examples)", "24", Delegates("JavaDelegate"), "examples"),
    Spec("2A.examples.el", "2A", "ExecutionListener classes (examples)", "—", Delegates("ExecutionListener"), "examples"),
    Spec("2A.examples.tl", "2A", "TaskListener classes (examples)", "—", Delegates("TaskListener"), "examples"),
    Spec("2A.examples.listeners", "2A", "listener classes (examples)", "2", Sum(["2A.examples.el", "2A.examples.tl"]), "examples"),
    Spec("2A.callingFiles", "2A", "delegate files calling engine services (consulting)", "44", Delegates("files_calling"), "consulting"),
    Spec("2A.entrySites", "2A", "entry-point sites (consulting)", "59", Delegates("entry_sites"), "consulting"),
    Spec("2A.via.start", "2A", "… startProcessInstanceByKey via entry point", "3", Delegates("method:RuntimeService.startProcessInstanceByKey:entry"), "consulting"),
    Spec("2A.via.correlate", "2A", "… correlateMessage via entry point", "2", Delegates("method:RuntimeService.correlateMessage:entry"), "consulting"),
    Spec("2A.via.taskComplete", "2A", "… taskService.complete via entry point", "4", Delegates("method:TaskService.complete:entry"), "consulting"),
    Spec("2A.via.taskQuery", "2A", "… taskService.createTaskQuery via entry point", "3", Delegates("method:TaskService.createTaskQuery:entry"), "consulting"),
    Spec("2A.via.history", "2A", "… historyService.create*Query via entry point", "9", Delegates("method:HistoryService.create*Query:entry"), "consulting"),
    Spec("2A.via.repository", "2A", "… repositoryService.* via entry point", "10", Delegates("method:RepositoryService.*:entry"), "consulting"),
    Spec("2A.via.identity", "2A", "… identityService.* via entry point", "6", Delegates("method:IdentityService.*:entry"), "consulting"),
    Spec("2A.via.case", "2A", "… caseService.* via entry point", "13", Delegates("method:CaseService.*:entry"), "consulting"),
    # --------------------------------------------------------------- 2B
    Spec("2B.taskQuery.direct", "2B", "taskService.createTaskQuery", "39", Calls({TS}, "createTaskQuery", "direct", hint=hint("taskService"))),
    Spec("2B.taskQuery.chained", "2B", "… chained", "20", Calls({TS}, "createTaskQuery", "chained", hint=hint("taskService"))),
    Spec("2B.historyQuery", "2B", "historyService.createHistoric*Query (incl. native)", "35",
         Calls({HS}, "create(Native)?Historic\\w*Query", hint=hint("historyService"))),
    Spec("2B.runtimeQuery", "2B", "runtimeService.createProcessInstanceQuery / createExecutionQuery", "13",
         Calls({RS}, "createProcessInstanceQuery|createExecutionQuery", hint=hint("runtimeService"))),
    Spec("2B.repositoryQuery", "2B", "repositoryService.createProcessDefinitionQuery / createDeploymentQuery / createDecisionDefinitionQuery", "25",
         Calls({REPO}, "createProcessDefinitionQuery|createDeploymentQuery|createDecisionDefinitionQuery", hint=hint("repositoryService"))),
    Spec("2B.jobQuery", "2B", "managementService.createJobQuery", "3", Calls({MS}, "createJobQuery", hint=hint("managementService"))),
    # --------------------------------------------------------------- 2C
    Spec("2C.historyQueries", "2C", "history query sites", "35", Sum(["2B.historyQuery"])),
    Spec("2C.historyEventHandler", "2C", "HistoryEventHandler implementations", "4", Classes({E + "impl.history.handler.HistoryEventHandler"})),
    Spec("2C.dbHistoryEventHandler", "2C", "DbHistoryEventHandler subclasses", "2", Classes({E + "impl.history.handler.DbHistoryEventHandler"})),
    Spec("2C.historyLevel", "2C", "custom HistoryLevel", "2", Classes({E + "impl.history.HistoryLevel"})),
    Spec("2C.historyEventProducer", "2C", "HistoryEventProducer implementations / subclasses", "2",
         Classes({E + "impl.history.producer.HistoryEventProducer", E + "impl.history.producer.DefaultHistoryEventProducer",
                  E + "impl.history.producer.CacheAwareHistoryEventProducer", E + "impl.history.producer.DefaultCmmnHistoryEventProducer",
                  E + "impl.history.producer.CacheAwareCmmnHistoryEventProducer"})),
    Spec("2C.dynamicRemovalTime", "2C", "DynamicRemovalTimeCalculationStrategy (snippet-local interface)", "2",
         Classes({"com.camunda.bpm.demo.engine_plugin_variable_depending_history_ttl.strategy.DynamicRemovalTimeCalculationStrategy"})),
    Spec("2C.historyRemovalTimeProvider", "2C", "HistoryRemovalTimeProvider implementations (the C7 type behind it)", "—",
         Classes({E + "impl.history.HistoryRemovalTimeProvider", E + "impl.history.DefaultHistoryRemovalTimeProvider"})),
    # --------------------------------------------------------------- 2D
    Spec("2D.identity", "2D", "identityService.*", "≈ 120", Calls({IS}, "\\w+", hint=hint("identityService"))),
    Spec("2D.authorization", "2D", "authorizationService.*", "≈ 115", Calls({AS}, "\\w+", hint=hint("authorizationService"))),
    Spec("2D.filter", "2D", "filterService.*", "≈ 43", Calls({FS}, "\\w+", hint=hint("filterService"))),
    # --------------------------------------------------------------- 2E
    Spec("2E.variables", "2E", "runtimeService.setVariable / getVariable / getVariables", "12",
         Calls({RS}, "setVariable|getVariable|getVariables", hint=hint("runtimeService"))),
    Spec("2E.signal", "2E", "runtimeService.signal(executionId)", "5", Calls({RS}, "signal", hint=hint("runtimeService"))),
    Spec("2E.messageEventReceived", "2E", "runtimeService.messageEventReceived", "7", Calls({RS}, "messageEventReceived", hint=hint("runtimeService"))),
    Spec("2E.deleteProcessInstance", "2E", "deleteProcessInstance", "1", Calls({RS}, "deleteProcessInstance", hint=hint("runtimeService"))),
    Spec("2E.suspendActivate", "2E", "suspend/activateProcessInstanceByProcessDefinitionKey", "4",
         Calls({RS}, "(suspend|activate)ProcessInstanceByProcessDefinitionKey", hint=hint("runtimeService"))),
    Spec("2E.modification", "2E", "createProcessInstanceModification", "1", Calls({RS}, "createProcessInstanceModification", hint=hint("runtimeService"))),
    Spec("2E.activeActivityIds", "2E", "getActiveActivityIds", "2", Calls({RS}, "getActiveActivityIds", hint=hint("runtimeService"))),
    # --------------------------------------------------------------- 2F
    Spec("2F.jobOps", "2F", "managementService setJobRetries / executeJob / activateJobById / recalculateJobDuedate / getJobExceptionStacktrace", "6",
         Calls({MS}, "setJobRetries|executeJob|activateJobById|recalculateJobDuedate|getJobExceptionStacktrace", hint=hint("managementService"))),
    Spec("2F.incidents", "2F", "createIncident / resolveIncident", "9", Calls(ANY_ENGINE, "createIncident|resolveIncident", hint=r"(?i)runtimeService|execution")),
    Spec("2F.jobRetryCmd", "2F", "JobRetryCmd / FoxJobRetryCmd / DefaultJobRetryCmd subclasses", "4",
         Classes({E + "impl.cmd.JobRetryCmd", E + "impl.cmd.FoxJobRetryCmd", E + "impl.cmd.DefaultJobRetryCmd"})),
    Spec("2F.incidentHandler", "2F", "custom IncidentHandler", "2", Classes({E + "impl.incident.IncidentHandler", E + "impl.incident.DefaultIncidentHandler"})),
    Spec("2F.timerEventJobHandler", "2F", "TimerEventJobHandler", "1", Classes({E + "impl.jobexecutor.TimerEventJobHandler"})),
    # --------------------------------------------------------------- 2G
    Spec("2G.imports", "2G", "impl.* imports (consulting)", "615", Imports(E + "impl.", "declarations"), "consulting"),
    Spec("2G.importFiles", "2G", "files with impl.* imports (consulting)", "176", Imports(E + "impl.", "files"), "consulting"),
    Spec("2G.imports.examples", "2G", "impl.* imports (examples)", "~60", Imports(E + "impl.", "declarations"), "examples"),
    *[
        Spec(f"2G.pkg.{p}", "2G", f"impl.{p} imports (consulting)", r, Imports(E + "impl.", f"package:{p}"), "consulting")
        for p, r in [("cfg", "121"), ("persistence", "65"), ("bpmn", "63"), ("pvm", "62"), ("history", "50"),
                     ("interceptor", "46"), ("util", "—"), ("context", "28"), ("jobexecutor", "21")]
    ],
    Spec("2G.plugin", "2G", "ProcessEnginePlugin / AbstractProcessEnginePlugin", "42",
         Classes({E + "impl.cfg.ProcessEnginePlugin", E + "impl.cfg.AbstractProcessEnginePlugin"})),
    Spec("2G.parseListener", "2G", "BpmnParseListener / AbstractBpmnParseListener", "22",
         Classes({E + "impl.bpmn.parser.BpmnParseListener", E + "impl.bpmn.parser.AbstractBpmnParseListener"})),
    Spec("2G.activityBehavior", "2G", "custom ActivityBehavior", "3",
         Classes({E + "impl.pvm.delegate.ActivityBehavior", E + "impl.pvm.delegate.SignallableActivityBehavior", E + "impl.bpmn.behavior."})),
    Spec("2G.commandInterceptor", "2G", "CommandInterceptor", "3", Classes({E + "impl.interceptor.CommandInterceptor"})),
    Spec("2G.command", "2G", "Command<T>", "3", Classes({E + "impl.interceptor.Command"})),
    Spec("2G.sessionFactory", "2G", "SessionFactory", "2", Classes({E + "impl.interceptor.SessionFactory"})),
    Spec("2G.tenantIdProvider", "2G", "TenantIdProvider", "4", Classes({E + "impl.cfg.multitenancy.TenantIdProvider"})),
    Spec("2G.contextCalls", "2G", "Context.getCommandContext() / getProcessEngineConfiguration()", "4",
         Calls({CONTEXT}, "getCommandContext|getProcessEngineConfiguration", hint=r"^Context$")),
    # --------------------------------------------------------------- 2H
    Spec("2H.caseService", "2H", "caseService.*", "≈ 45", Calls({CS}, "\\w+", hint=hint("caseService"))),
    Spec("2H.caseExecutionListener", "2H", "CaseExecutionListener", "10", Classes({E + "delegate.CaseExecutionListener"})),
    # --------------------------------------------------------------- 2I
    *[
        Spec(f"2I.{m}", "2I", f"{m} on DelegateExecution/DelegateTask inside delegates", r,
             Calls({DELEGATE_EXECUTION, DELEGATE_TASK}, m, where=IN_DELEGATE))
        for m, r in [("getVariable", "202"), ("setVariable", "125"), ("getId", "93"), ("getProcessInstanceId", "81"),
                     ("getCurrentActivityId", "79"), ("getCurrentActivityName", "73"), ("getProcessBusinessKey", "71"),
                     ("getProcessDefinitionId", "70"), ("getBpmnModelElementInstance", "6"), ("getTenantId", "3")]
    ],
    # --------------------------------------------------------------- 2J
    *[
        Spec(f"2J.{m}", "2J", m, r, Calls(ANY_ENGINE, m))
        for m, r in [("setVariableLocal", "3"), ("getVariableLocal", "3"), ("removeVariable", "5"), ("hasVariable", "5")]
    ],
    # --------------------------------------------------------------- 2L
    Spec("2L.deleteDeployment", "2L", "deleteDeployment", "4", Calls({REPO}, "deleteDeployment", hint=hint("repositoryService"))),
    Spec("2L.diagram", "2L", "getProcessDiagram / getProcessDiagramLayout", "7",
         Calls({REPO}, "getProcessDiagram|getProcessDiagramLayout", hint=hint("repositoryService"))),
    Spec("2L.model", "2L", "getBpmnModelInstance / getProcessModel", "4",
         Calls({REPO}, "getBpmnModelInstance|getProcessModel", hint=hint("repositoryService"))),
    Spec("2L.processDefinition", "2L", "getProcessDefinition", "3", Calls({REPO}, "getProcessDefinition", hint=hint("repositoryService"))),
    # --------------------------------------------------------------- 2M
    Spec("2M.forms", "2M", "formService.getTaskFormData / getStartFormKey", "3",
         Calls({FORM}, "getTaskFormData|getStartFormKey", hint=hint("formService"))),
    # ------------------------------------------------------------ section 3
    Spec("3.startCorrelate", "3", "Start / correlate / signal", "~90",
         Sum(["1.start.direct", "1.start.chained", "1.startByMessage", "1.correlate.direct", "1.correlate.chained", "1.signalEvent"])),
    Spec("3.externalTask", "3", "External-task worker style", "~40", Sum(["1.ext.complete", "1.ext.handleFailure", "1.ext.handler"])),
    Spec("3.userTask", "3", "User task complete / assign / by-error", "~35",
         Sum(["1.task.complete.direct", "1.task.complete.chained", "1.task.claim", "1.bpmnError"])),
    Spec("3.deployDmn", "3", "Deployment, DMN evaluate", "~10", Sum(["1.deploy", "1.dmn"])),
    Spec("3.delegateClasses", "3", "Delegates & listeners: classes (both repos)", "231", Delegates("classes")),
    Spec("3.delegateCalls", "3", "Delegates & listeners: nested engine calls, entry-point sites (both repos)", "59", Delegates("entry_sites")),
    Spec("3.queries", "3", "Queries", "~135",
         Sum(["2B.taskQuery.direct", "2B.taskQuery.chained", "2B.historyQuery", "2B.runtimeQuery", "2B.repositoryQuery", "2B.jobQuery"])),
    Spec("3.historyInfra", "3", "History infrastructure (classes)", "~12",
         Sum(["2C.historyEventHandler", "2C.dbHistoryEventHandler", "2C.historyLevel", "2C.historyEventProducer", "2C.dynamicRemovalTime"])),
    Spec("3.identity", "3", "Identity / authorization / filters", "~280", Sum(["2D.identity", "2D.authorization", "2D.filter"])),
    Spec("3.lifecycle", "3", "Instance lifecycle, instance variables", "~30",
         Sum(["2E.variables", "2E.signal", "2E.messageEventReceived", "2E.deleteProcessInstance", "2E.suspendActivate",
              "2E.modification", "2E.activeActivityIds"])),
    Spec("3.jobs", "3", "Jobs / incidents / retries", "~20",
         Sum(["2F.jobOps", "2F.incidents", "2F.jobRetryCmd", "2F.incidentHandler", "2F.timerEventJobHandler"])),
    Spec("3.implImports", "3", "Engine internals: impl.* imports (both repos)", "615", Imports(E + "impl.", "declarations")),
    Spec("3.implFiles", "3", "Engine internals: files (both repos)", "176", Imports(E + "impl.", "files")),
    Spec("3.cmmn", "3", "CMMN", "~55", Sum(["2H.caseService", "2H.caseExecutionListener"])),
    Spec("3.contextReads", "3", "Delegate context reads", "~700", Sum([f"2I.{m}" for m in (
        "getVariable", "setVariable", "getId", "getProcessInstanceId", "getCurrentActivityId", "getCurrentActivityName",
        "getProcessBusinessKey", "getProcessDefinitionId", "getBpmnModelElementInstance", "getTenantId")])),
    Spec("3.variableScope", "3", "Variable scope / typed values", "~20",
         Sum(["2J.setVariableLocal", "2J.getVariableLocal", "2J.removeVariable", "2J.hasVariable"])),
]


def matches_supertype(sup: str, wanted: set[str]) -> bool:
    return sup in wanted or any(w.endswith(".") and sup.startswith(w) for w in wanted)


def measure(spec: Spec, ix: CorpusIndex, scopes: DelegateScopes, delegate_summary: dict[str, int],
            call_cache: list, log: list[str] | None = None) -> tuple[int, int | None]:
    """Value for one corpus, and the unresolved-site count for call specs.

    With `log`, appends one line per counted site ("+") and per rejected
    same-name site ("-", with the resolved receiver type).
    """
    how = spec.how
    emit = log.append if log is not None else (lambda _line: None)
    if isinstance(how, Files):
        return len(ix.corpus.main_java() if how.rule == "main" else ix.corpus.draft_rule_java()), None
    if isinstance(how, Delegates):
        key = how.key
        if "*" in key:  # wildcard over method names: method:Service.prefix*:entry
            _, label, col = key.split(":")
            pat = re.compile(re.escape(label).replace(r"\*", r"\w*") + "$")
            return sum(v for k, v in delegate_summary.items()
                       if k.startswith("method:") and k.endswith(":" + col) and pat.match(k.split(":")[1])), None
        return delegate_summary.get(key, 0), None
    if isinstance(how, Classes):
        n = 0
        for td in ix.type_decls():
            if td.kind != "interface_declaration" and any(matches_supertype(s, how.supertypes) for s in td.supers):
                n += 1
                emit(f"+ {td.file.path}:{td.node.start_point[0] + 1} {td.fqn} {td.supers}")
        return n, None
    if isinstance(how, Imports):
        n = 0
        files = 0
        per_package: Counter = Counter()
        for f in ix.files:
            hits = [i for i in f.import_fqns if i.startswith(how.prefix)]
            for i in hits:
                rest = i[len(how.prefix):].split(".")
                per_package[rest[0] if len(rest) >= 2 else "(types directly in the package)"] += 1
            if how.measure.startswith("package:"):
                seg = how.measure.split(":", 1)[1]
                hits = [i for i in hits if len(i[len(how.prefix):].split(".")) >= 2 and i[len(how.prefix):].split(".")[0] == seg]
            n += len(hits)
            files += bool(hits)
        if how.measure == "declarations":
            # ranked, zero-padded so the sorted explain output keeps the ranking
            for rank, (pkg, count) in enumerate(per_package.most_common(), 1):
                emit(f"{rank:03d}. {pkg}: {count}")
        return (files if how.measure == "files" else n), None
    if isinstance(how, Throws):
        n = 0
        for f in ix.files:
            for node in walk(f.tree.root_node):
                if node.type != "throw_statement" or not node.named_children:
                    continue
                expr = node.named_children[0]
                if expr.type == "object_creation_expression" and f.resolve_type_node(expr.child_by_field_name("type")) == how.exception:
                    unit = scopes.unit_of(f, node)
                    where = f"{f.path}:{node.start_point[0] + 1}"
                    if unit is not None and how.where in unit.interfaces:
                        n += 1
                        emit(f"+ {where} in {unit.kind} {unit.name}")
                    else:
                        emit(f"- {where} in {unit.kind + ' ' + unit.name if unit else 'no delegate scope'}")
        return n, None
    if isinstance(how, Calls):
        method = re.compile(how.methods)
        hint_re = re.compile(how.hint) if how.hint else None
        n = 0
        unresolved = 0
        for cs in call_cache:
            if not method.fullmatch(cs.name) or cs.receiver_type == "":
                continue
            obj = cs.node.child_by_field_name("object")
            where = f"{cs.file.path}:{cs.node.start_point[0] + 1} {' '.join(text(cs.node).split())[:100]}"
            if how.shape == "direct" and cs.chained or how.shape == "chained" and not cs.chained:
                continue
            if how.where == IN_DELEGATE and scopes.unit_of(cs.file, cs.node) is None:
                emit(f"- {where} [outside delegate scope, receiver {cs.receiver_type}]")
                continue
            rt = cs.receiver_type
            if rt is None:
                if hint_re is not None:
                    recv = text(obj.child_by_field_name("name")) if obj.type == "method_invocation" else text(obj)
                    if hint_re.search(recv):
                        unresolved += 1
                        emit(f"? {where} [unresolved receiver]")
                continue
            if how.receivers == ANY_ENGINE:
                ok = ix.is_camunda_lib(rt) and rt.startswith(E)
            else:
                ok = rt in how.receivers
            n += ok
            if ok:
                emit(f"+ {where}")
            elif rt.startswith("org.camunda.") or (hint_re is not None and hint_re.search(text(obj))):
                emit(f"- {where} [receiver {rt}]")
        return n, (unresolved if hint_re is not None else None)
    raise TypeError(how)


def number(s: str) -> int | None:
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, help="also write results as JSON")
    ap.add_argument("--explain", metavar="ID", help="list the sites behind one spec instead of the table")
    args = ap.parse_args()

    indexes = load_indexes()
    delegate_results = {name: analyse(ix) for name, ix in indexes.items()}
    delegate_summary = summarise(delegate_results)
    calls = {name: list(ix.call_sites()) for name, ix in indexes.items()}

    if args.explain:
        spec = next((x for x in SPECS if x.id == args.explain), None)
        if spec is None:
            raise SystemExit(f"unknown spec id {args.explain}")
        if isinstance(spec.how, Sum):
            raise SystemExit(f"{spec.id} is {spec.how.describe()}; explain those ids instead")
        print(f"{spec.id}: {spec.label} — {spec.how.describe()} (scope {spec.scope})")
        for c in CORPORA:
            if spec.scope not in ("both", c.name):
                continue
            log: list[str] = []
            value, _ = measure(spec, indexes[c.name], delegate_results[c.name]["scopes"], delegate_summary[c.name], calls[c.name], log)
            print(f"\n## {c.name}: {value}")
            listable = isinstance(spec.how, (Calls, Classes, Throws)) or getattr(spec.how, "measure", "") == "declarations"
            print("\n".join(sorted(log)) if log else "(no sites)" if listable else "(no per-site listing for this spec kind)")
        return

    by_id: dict[str, Spec] = {}
    for spec in SPECS:
        by_id[spec.id] = spec
        if isinstance(spec.how, Sum):
            for c in CORPORA:
                spec.measured[c.name] = sum(by_id[i].measured[c.name] for i in spec.how.ids)
            continue
        unresolved_total = None
        for c in CORPORA:
            ix = indexes[c.name]
            value, unresolved = measure(spec, ix, delegate_results[c.name]["scopes"], delegate_summary[c.name], calls[c.name])
            spec.measured[c.name] = value
            if unresolved is not None and (spec.scope in ("both", c.name)):
                unresolved_total = (unresolved_total or 0) + unresolved
        spec.unresolved = unresolved_total

    print("| ID | § | Pattern | Reported | Measured | Δ | examples | consulting | unresolved, not counted | Method |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    rows = []
    for spec in SPECS:
        total = sum(spec.measured.values()) if spec.scope == "both" else spec.measured[spec.scope]
        rep = number(spec.reported)
        delta = "" if rep is None else f"{total - rep:+d}"
        unresolved = "" if spec.unresolved is None else str(spec.unresolved)
        print(f"| `{spec.id}` | {spec.section} | {spec.label} | {spec.reported} | {total} | {delta} | "
              f"{spec.measured['examples']} | {spec.measured['consulting']} | {unresolved} | {spec.how.describe()} |")
        rows.append({"id": spec.id, "section": spec.section, "label": spec.label, "reported": spec.reported,
                     "scope": spec.scope, "measured": total, "per_corpus": spec.measured, "unresolved": spec.unresolved,
                     "method": spec.how.describe()})
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
