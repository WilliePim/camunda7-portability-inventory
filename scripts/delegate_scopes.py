"""Delegate/listener scopes and engine calls made from inside them.

Shared by inventory.py (section 2A rows) and delegates.py.

Definitions
* delegate/listener class: a named, non-abstract class that implements
  org.camunda.bpm.engine.delegate.{JavaDelegate, ExecutionListener, TaskListener},
  directly or through a supertype declared in the same project. Abstract classes,
  anonymous classes and lambdas are counted on separate lines.
* delegate scope: the body of such a class, of an abstract class implementing one
  of the interfaces, of an anonymous class of one of the interfaces, or of a
  lambda whose target type is one of them.
* entry point: inside a delegate scope, one of
  DelegateExecution.getProcessEngineServices(), DelegateTask.getProcessEngineServices(),
  Context.getProcessEngineConfiguration(), Context.getCommandContext()
  (Context = org.camunda.bpm.engine.impl.context.Context).
  DelegateExecution/DelegateTask.getProcessEngine() is reported separately.
* engine method: a call inside a delegate scope whose receiver type resolves to a
  Camunda engine service (RuntimeService, TaskService, ...),
  ProcessEngineConfigurationImpl or CommandContext; service getters excluded.
  "via entry point" means the receiver expression, or the initializer of the local
  variable used as receiver, contains an entry-point call.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from javaindex import (
    COMMAND_CONTEXT, CONTEXT, DELEGATE_EXECUTION, DELEGATE_TASK, EXECUTION_LISTENER, GETTER_RETURNS,
    JAVA_DELEGATE, PROCESS_ENGINE_CONFIGURATION_IMPL, SERVICES, TASK_LISTENER, TYPE_DECLS,
    CorpusIndex, JavaFile, line_of, text,
)
from tree_sitter import Node

INTERFACES = {JAVA_DELEGATE: "JavaDelegate", EXECUTION_LISTENER: "ExecutionListener", TASK_LISTENER: "TaskListener"}
ENGINE_RECEIVERS = set(SERVICES.values()) | {PROCESS_ENGINE_CONFIGURATION_IMPL, COMMAND_CONTEXT}
DELEGATE_CONTEXT = {DELEGATE_EXECUTION, DELEGATE_TASK}
ENTRY_POINTS = (
    "DelegateExecution.getProcessEngineServices()",
    "DelegateTask.getProcessEngineServices()",
    "Context.getProcessEngineConfiguration()",
    "Context.getCommandContext()",
)
EXTRA_ENTRY = "getProcessEngine"


@dataclass(frozen=True)
class Unit:
    """A delegate implementation: named class, anonymous class or lambda."""

    path: str
    line: int
    kind: str  # class | abstract | anonymous | lambda
    name: str
    interfaces: frozenset[str]


class DelegateScopes:
    def __init__(self, ix: CorpusIndex):
        self.ix = ix
        self.units: dict[tuple[str, int], Unit] = {}
        self.direct: set[tuple[str, int]] = set()
        for td in ix.type_decls():
            if td.kind == "interface_declaration":
                continue
            found = frozenset(i for i in ix.all_supertypes(td) if i in INTERFACES)
            if found:
                kind = "abstract" if td.abstract else "class"
                self.units[(td.file.path, td.node.id)] = Unit(td.file.path, line_of(td.node), kind, td.fqn, found)
                if any(s in INTERFACES for s in td.supers):
                    self.direct.add((td.file.path, td.node.id))
        for f, n, t in ix.anonymous_classes():
            found = self._implemented(f, t)
            if found:
                self.units[(f.path, n.id)] = Unit(f.path, line_of(n), "anonymous", t or "", found)
        for f, n, t in ix.lambdas():
            if t in INTERFACES:
                self.units[(f.path, n.id)] = Unit(f.path, line_of(n), "lambda", t, frozenset({t}))

    def _implemented(self, f: JavaFile, t: str | None) -> frozenset[str]:
        if t is None:
            return frozenset()
        if t in INTERFACES:
            return frozenset({t})
        decl = self.ix.find_type(f.project, t)
        return frozenset(i for i in self.ix.all_supertypes(decl) if i in INTERFACES) if decl else frozenset()

    def unit_of(self, f: JavaFile, n: Node) -> Unit | None:
        """Innermost delegate unit enclosing `n`."""
        cur = n.parent
        while cur is not None:
            if cur.type in TYPE_DECLS or cur.type in ("object_creation_expression", "lambda_expression"):
                u = self.units.get((f.path, cur.id))
                if u is not None:
                    return u
            cur = cur.parent
        return None

    def named_classes(self) -> list[Unit]:
        return [u for u in self.units.values() if u.kind == "class"]


def entry_kind(ix: CorpusIndex, f: JavaFile, n: Node) -> str | None:
    """One of ENTRY_POINTS, EXTRA_ENTRY for DelegateExecution/DelegateTask.getProcessEngine(), or None."""
    if n.type != "method_invocation":
        return None
    name = text(n.child_by_field_name("name"))
    obj = n.child_by_field_name("object")
    if obj is None:
        return None
    if name in ("getProcessEngineConfiguration", "getCommandContext") and ix.expr_type(f, obj) == CONTEXT:
        return f"Context.{name}()"
    if name in ("getProcessEngineServices", "getProcessEngine"):
        t = ix.expr_type(f, obj)
        if t in DELEGATE_CONTEXT:
            return f"{t.rsplit('.', 1)[-1]}.{name}()" if name == "getProcessEngineServices" else EXTRA_ENTRY
    return None


def origin(ix: CorpusIndex, f: JavaFile, n: Node | None, depth: int = 0) -> str:
    """Where a receiver expression gets its engine object from."""
    if n is None or depth > 8:
        return "other"
    if n.type in ("parenthesized_expression", "cast_expression"):
        inner = n.child_by_field_name("value") if n.type == "cast_expression" else (n.named_children[0] if n.named_children else None)
        return origin(ix, f, inner, depth + 1)
    if n.type == "method_invocation":
        k = entry_kind(ix, f, n)
        if k:
            return "entry" if k in ENTRY_POINTS else EXTRA_ENTRY
        return origin(ix, f, n.child_by_field_name("object"), depth + 1)
    if n.type == "identifier":
        d = f.declared_type(n, text(n))
        if d is not None and d[1] is not None:
            return origin(ix, f, d[1], depth + 1)
        return "other"
    return "other"


def analyse(ix: CorpusIndex) -> dict:
    scopes = DelegateScopes(ix)
    entry_sites: list[tuple[Unit, str, int, str, str]] = []  # unit, path, line, snippet, entry point
    extra_sites: list[tuple[Unit, str, int, str, str]] = []
    methods: dict[str, Counter] = defaultdict(Counter)
    for cs in ix.call_sites():
        unit = None
        k = entry_kind(ix, cs.file, cs.node)
        if k:
            unit = scopes.unit_of(cs.file, cs.node)
            if unit is not None:
                site = (unit, cs.file.path, line_of(cs.node), " ".join(text(cs.node).split())[:110], k)
                (entry_sites if k in ENTRY_POINTS else extra_sites).append(site)
        if cs.receiver_type in ENGINE_RECEIVERS and cs.name not in GETTER_RETURNS:
            unit = unit or scopes.unit_of(cs.file, cs.node)
            if unit is not None:
                label = f"{cs.receiver_type.rsplit('.', 1)[-1]}.{cs.name}"
                methods[label][origin(ix, cs.file, cs.node.child_by_field_name("object"))] += 1
    return {"scopes": scopes, "entry_sites": entry_sites, "extra_sites": extra_sites, "methods": methods}


def summarise(results: dict[str, dict]) -> dict[str, dict[str, int]]:
    """Flat numbers per corpus (used by inventory.py as well)."""
    out: dict[str, dict[str, int]] = {}
    for name, r in results.items():
        s: DelegateScopes = r["scopes"]
        named = s.named_classes()
        entry_units = {u for (u, *_rest) in r["entry_sites"]}
        row = {
            "classes": len(named),
            "classes_direct": sum(1 for k, u in s.units.items() if u.kind == "class" and k in s.direct),
            "abstract": sum(1 for u in s.units.values() if u.kind == "abstract"),
            "anonymous": sum(1 for u in s.units.values() if u.kind == "anonymous"),
            "lambda": sum(1 for u in s.units.values() if u.kind == "lambda"),
            "entry_sites": len(r["entry_sites"]),
            "entry_sites_in_classes": sum(1 for (u, *_x) in r["entry_sites"] if u.kind == "class"),
            "classes_calling": sum(1 for u in entry_units if u.kind == "class"),
            "files_calling": len({u.path for u in entry_units if u.kind == "class"}),
            "units_calling": len(entry_units),
            "getProcessEngine_sites": len(r["extra_sites"]),
        }
        for kind in ENTRY_POINTS:
            row[f"entry:{kind}"] = sum(1 for s in r["entry_sites"] if s[4] == kind)
        for fqn, short in INTERFACES.items():
            row[short] = sum(1 for u in named if fqn in u.interfaces)
        for m, c in r["methods"].items():
            row[f"method:{m}:entry"] = c["entry"]
            row[f"method:{m}:all"] = sum(c.values())
        out[name] = row
    return out

