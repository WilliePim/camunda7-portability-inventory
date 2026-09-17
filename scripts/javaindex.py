"""Import-aware index of Java main sources, built on tree-sitter.

The index resolves the static type of a method-call receiver without a
classpath, using only what is visible in the source:

* variables, parameters and fields are looked up by lexical scope (innermost
  first), including fields inherited from superclasses in the same project;
* a simple type name resolves to a fully qualified name (FQN) through the
  file's single-type imports, wildcard imports, its own package, or types
  declared in the same project;
* well-known Camunda 7 getters (`getRuntimeService()`, `getProcessEngineServices()`,
  `ProcessEngines.getDefaultProcessEngine()`, `Context.getCommandContext()`, ...)
  return their engine type when their own receiver resolves to a Camunda type,
  or when they are called unqualified inside a class whose supertype is a
  Camunda type;
* untyped lambda parameters are typed only for functional interfaces whose
  target type is visible: a lambda returned from / assigned to a `JavaDelegate`,
  `ExecutionListener` or `TaskListener`, and a lambda passed to the external task
  client's `subscribe(..)...handler(..)`.

Anything else stays unresolved and is not counted (the scripts prefer
under-counting). Unresolved sites are reported separately.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Iterator

import tree_sitter_java
from tree_sitter import Language, Node, Parser

from repos import CORPORA, Corpus

JAVA = Language(tree_sitter_java.language())
PARSER = Parser(JAVA)

E = "org.camunda.bpm.engine."
DELEGATE_EXECUTION = E + "delegate.DelegateExecution"
DELEGATE_TASK = E + "delegate.DelegateTask"
JAVA_DELEGATE = E + "delegate.JavaDelegate"
EXECUTION_LISTENER = E + "delegate.ExecutionListener"
TASK_LISTENER = E + "delegate.TaskListener"
CLIENT_EXTERNAL_TASK = "org.camunda.bpm.client.task.ExternalTask"
CLIENT_EXTERNAL_TASK_SERVICE = "org.camunda.bpm.client.task.ExternalTaskService"
CLIENT_EXTERNAL_TASK_HANDLER = "org.camunda.bpm.client.task.ExternalTaskHandler"
CLIENT_TOPIC_SUBSCRIPTION_BUILDER = "org.camunda.bpm.client.topic.TopicSubscriptionBuilder"
CONTEXT = E + "impl.context.Context"
PROCESS_ENGINE_CONFIGURATION_IMPL = E + "impl.cfg.ProcessEngineConfigurationImpl"
COMMAND_CONTEXT = E + "impl.interceptor.CommandContext"

SERVICES = {
    s: E + s
    for s in (
        "RuntimeService", "TaskService", "RepositoryService", "HistoryService", "IdentityService",
        "AuthorizationService", "FilterService", "CaseService", "ManagementService", "FormService",
        "ExternalTaskService", "DecisionService",
    )
}

# Getter name -> returned type. Applied only on Camunda-typed receivers.
GETTER_RETURNS = {f"get{s}": fqn for s, fqn in SERVICES.items()}
GETTER_RETURNS.update({
    "getProcessEngineServices": E + "ProcessEngineServices",
    "getProcessEngine": E + "ProcessEngine",
    "getDefaultProcessEngine": E + "ProcessEngine",
    "buildProcessEngine": E + "ProcessEngine",
    "getProcessEngineConfiguration": PROCESS_ENGINE_CONFIGURATION_IMPL,
    "getCommandContext": COMMAND_CONTEXT,
    "getDmnEngine": "org.camunda.bpm.dmn.engine.DmnEngine",
    "getProcessEngineService": "org.camunda.bpm.ProcessEngineService",
    "getExecution": E + "delegate.DelegateExecution",
})

# Lambda target type -> parameter types, in order.
LAMBDA_PARAMS = {
    JAVA_DELEGATE: [DELEGATE_EXECUTION],
    EXECUTION_LISTENER: [DELEGATE_EXECUTION],
    TASK_LISTENER: [DELEGATE_TASK],
    CLIENT_EXTERNAL_TASK_HANDLER: [CLIENT_EXTERNAL_TASK, CLIENT_EXTERNAL_TASK_SERVICE],
}

TYPE_DECLS = ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration")
SCOPE_STOP = "program"
UNTYPED = "<untyped>"


def text(n: Node | None) -> str:
    return n.text.decode("utf-8", "replace") if n is not None else ""


def walk(n: Node) -> Iterator[Node]:
    stack = [n]
    while stack:
        cur = stack.pop()
        yield cur
        stack.extend(reversed(cur.children))


def base_type_name(t: Node | None) -> str | None:
    """`List<Foo>` -> `List`, `a.b.Foo` -> `a.b.Foo`, primitives/arrays -> None."""
    if t is None:
        return None
    if t.type == "generic_type":
        return base_type_name(t.named_children[0])
    if t.type in ("type_identifier", "scoped_type_identifier"):
        return text(t)
    return None


@dataclass
class TypeDecl:
    file: "JavaFile"
    node: Node
    fqn: str
    super_names: list[Node]  # type nodes of extends/implements
    abstract: bool
    kind: str

    @cached_property
    def supers(self) -> list[str]:
        out = []
        for t in self.super_names:
            name = base_type_name(t)
            if name:
                out.append(self.file.resolve_type_name(name) or f"?{name}")
        return out


class JavaFile:
    def __init__(self, index: "CorpusIndex", path: str):
        self.index = index
        self.path = path
        self.src = (index.corpus.repo.dir / path).read_bytes()
        self.tree = PARSER.parse(self.src)
        root = self.tree.root_node
        self.project = path.split("/src/main/")[0]
        self.package = ""
        self.imports: dict[str, str] = {}
        self.wildcards: set[str] = set()
        self.import_fqns: list[str] = []
        for n in root.named_children:
            if n.type == "package_declaration":
                self.package = text(n.named_children[-1]) if n.named_children else ""
            elif n.type == "import_declaration":
                is_static = any(c.type == "static" for c in n.children)
                name_node = next((c for c in n.named_children if c.type in ("scoped_identifier", "identifier")), None)
                name = text(name_node)
                wildcard = any(c.type == "asterisk" for c in n.children)
                self.import_fqns.append(name + (".*" if wildcard else ""))
                if wildcard and not is_static:
                    self.wildcards.add(name)
                elif not is_static:
                    self.imports[name.rsplit(".", 1)[-1]] = name
        self.types: list[TypeDecl] = []
        self._collect_types(root, self.package)

    def _collect_types(self, node: Node, prefix: str) -> None:
        for n in node.named_children:
            if n.type in TYPE_DECLS:
                name = text(n.child_by_field_name("name"))
                fqn = f"{prefix}.{name}" if prefix else name
                supers: list[Node] = []
                sc = n.child_by_field_name("superclass")
                if sc is not None:
                    supers += [c for c in sc.named_children]
                for c in n.named_children:
                    if c.type in ("super_interfaces", "extends_interfaces"):
                        for tl in c.named_children:
                            supers += tl.named_children if tl.type == "type_list" else [tl]
                mods = next((c for c in n.children if c.type == "modifiers"), None)
                abstract = n.type == "interface_declaration" or (mods is not None and "abstract" in text(mods).split())
                self.types.append(TypeDecl(self, n, fqn, supers, abstract, n.type))
                body = n.child_by_field_name("body")
                if body is not None:
                    self._collect_types(body, fqn)
            elif n.type not in ("method_declaration", "constructor_declaration"):
                # nested types can also sit inside enum_body_declarations etc.
                if n.type in ("class_body", "interface_body", "enum_body", "enum_body_declarations"):
                    self._collect_types(n, prefix)

    @cached_property
    def local_type_names(self) -> dict[str, str]:
        return {t.fqn.rsplit(".", 1)[-1]: t.fqn for t in self.types}

    @cached_property
    def imports_camunda(self) -> bool:
        return any(i.startswith("org.camunda.bpm.") for i in self.import_fqns)

    # ---------------------------------------------------------------- types
    def resolve_type_name(self, name: str) -> str | None:
        if "." in name:
            head, rest = name.split(".", 1)
            if head[:1].islower():
                return name  # written fully qualified
            h = self.resolve_type_name(head)
            return f"{h}.{rest}" if h else None
        if name in self.local_type_names:
            return self.local_type_names[name]
        if name in self.imports:
            return self.imports[name]
        for fqn in self.index.catalog.get(name, ()):
            pkg = fqn.rsplit(".", 1)[0]
            if pkg in self.wildcards or pkg == self.package:
                return fqn
        for fqn in self.index.project_types(self.project).get(name, ()):
            if fqn.rsplit(".", 1)[0] == self.package:
                return fqn
        return None

    def resolve_type_node(self, t: Node | None) -> str | None:
        name = base_type_name(t)
        return self.resolve_type_name(name) if name else None

    # ------------------------------------------------------------ variables
    def declared_type(self, at: Node, name: str) -> tuple[str | None, Node | None] | None:
        """Innermost declaration of `name` visible at `at`: (type FQN or UNTYPED, initializer)."""
        prev = at
        cur = at.parent
        while cur is not None and cur.type != SCOPE_STOP:
            hit = self._declared_in(cur, prev, name)
            if hit is not None:
                return hit
            prev, cur = cur, cur.parent
        return None

    def _declared_in(self, cur: Node, prev: Node, name: str):
        t = cur.type
        if t in ("block", "constructor_body", "switch_block_statement_group", "switch_rule"):
            for c in cur.named_children:
                if c.start_byte >= prev.start_byte:
                    break
                if c.type == "local_variable_declaration":
                    r = self._from_declarators(c, name)
                    if r:
                        return r
        elif t in ("method_declaration", "constructor_declaration"):
            params = cur.child_by_field_name("parameters")
            for p in params.named_children if params is not None else ():
                if p.type == "formal_parameter" and text(p.child_by_field_name("name")) == name:
                    return self._typed(p.child_by_field_name("type"), None)
                if p.type == "spread_parameter":
                    decl = next((c for c in p.named_children if c.type == "variable_declarator"), None)
                    if decl is not None and text(decl.child_by_field_name("name")) == name:
                        return (None, None)
        elif t == "lambda_expression":
            return self._lambda_param(cur, name)
        elif t == "catch_clause":
            p = next((c for c in cur.named_children if c.type == "catch_formal_parameter"), None)
            if p is not None and text(p.child_by_field_name("name")) == name:
                return (None, None)
        elif t == "enhanced_for_statement":
            if text(cur.child_by_field_name("name")) == name:
                return self._typed(cur.child_by_field_name("type"), None)
        elif t == "for_statement":
            for c in cur.children_by_field_name("init"):
                if c.type == "local_variable_declaration":
                    r = self._from_declarators(c, name)
                    if r:
                        return r
        elif t == "try_with_resources_statement":
            spec = cur.child_by_field_name("resources")
            for r in spec.named_children if spec is not None else ():
                if r.type == "resource" and text(r.child_by_field_name("name")) == name:
                    return self._typed(r.child_by_field_name("type"), r.child_by_field_name("value"))
        elif t in ("class_body", "interface_body", "enum_body"):
            return self._field(cur.parent, name, depth=0)
        elif t == "record_declaration":
            params = cur.child_by_field_name("parameters")
            for p in params.named_children if params is not None else ():
                if text(p.child_by_field_name("name")) == name:
                    return self._typed(p.child_by_field_name("type"), None)
        return None

    def _typed(self, type_node: Node | None, init: Node | None):
        if type_node is not None and text(type_node) == "var":
            return (self.index.expr_type(self, init) if init is not None else None, init)
        return (self.resolve_type_node(type_node), init)

    def _from_declarators(self, decl: Node, name: str):
        for d in decl.children_by_field_name("declarator"):
            if text(d.child_by_field_name("name")) == name:
                return self._typed(decl.child_by_field_name("type"), d.child_by_field_name("value"))
        return None

    def _field(self, type_decl: Node | None, name: str, depth: int):
        """Field `name` in a type declaration body, then in project superclasses."""
        if type_decl is None or depth > 6:
            return None
        body = type_decl.child_by_field_name("body") if type_decl.type in TYPE_DECLS else next(
            (c for c in type_decl.named_children if c.type == "class_body"), None)
        containers = [body] if body is not None else []
        if body is not None:
            containers += [c for c in body.named_children if c.type == "enum_body_declarations"]
        for container in containers:
            for c in container.named_children:
                if c.type in ("field_declaration", "constant_declaration"):
                    r = self._from_declarators(c, name)
                    if r:
                        return r
        if type_decl.type in TYPE_DECLS:
            td = self.index.decl_for_node(self, type_decl)
            for sup in td.supers if td else ():
                sup_decl = self.index.find_type(self.project, sup)
                if sup_decl is not None:
                    r = sup_decl.file._field(sup_decl.node, name, depth + 1)
                    if r:
                        return r
        return None

    def _lambda_param(self, lam: Node, name: str):
        params = lam.child_by_field_name("parameters")
        if params is None:
            return None
        names: list[str] = []
        if params.type == "identifier":
            names = [text(params)]
        elif params.type == "inferred_parameters":
            names = [text(c) for c in params.named_children]
        elif params.type == "formal_parameters":
            for i, p in enumerate(params.named_children):
                if p.type == "formal_parameter" and text(p.child_by_field_name("name")) == name:
                    return self._typed(p.child_by_field_name("type"), None)
            return None
        if name not in names:
            return None
        target = self.index.lambda_target(self, lam)
        types = LAMBDA_PARAMS.get(target or "")
        i = names.index(name)
        if types and i < len(types) and len(names) == len(types):
            return (types[i], None)
        return (UNTYPED, None)


@dataclass
class CallSite:
    file: JavaFile
    node: Node
    name: str
    receiver_type: str | None  # None = unresolved, "" = unqualified call
    chained: bool


class CorpusIndex:
    def __init__(self, corpus: Corpus, catalog: dict[str, set[str]] | None = None):
        self.corpus = corpus
        self.catalog: dict[str, set[str]] = catalog if catalog is not None else {}
        self.files = [JavaFile(self, p) for p in corpus.main_java()]
        self._types_by_project: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self._decl_by_fqn: dict[tuple[str, str], TypeDecl] = {}
        self._decl_by_node: dict[tuple[str, int], TypeDecl] = {}
        for f in self.files:
            for t in f.types:
                self._types_by_project[f.project][t.fqn.rsplit(".", 1)[-1]].append(t.fqn)
                self._decl_by_fqn.setdefault((f.project, t.fqn), t)
                self._decl_by_node[(f.path, t.node.id)] = t
        self._expr_cache: dict[tuple[str, int], str | None] = {}
        self.declared_fqns = {q for (_, q) in self._decl_by_fqn}

    def is_camunda_lib(self, fqn: str) -> bool:
        """A Camunda library type, not a class the snippets declare under org.camunda.*."""
        return fqn.startswith("org.camunda.") and fqn not in self.declared_fqns

    # ----------------------------------------------------------- type index
    def project_types(self, project: str) -> dict[str, list[str]]:
        return self._types_by_project.get(project, {})

    def find_type(self, project: str, fqn: str) -> TypeDecl | None:
        if (project, fqn) in self._decl_by_fqn:
            return self._decl_by_fqn[(project, fqn)]
        # sibling module of a multi-module snippet: same top two path segments
        top = "/".join(project.split("/")[:2])
        for (p, q), d in self._decl_by_fqn.items():
            if q == fqn and p.startswith(top):
                return d
        return None

    def decl_for_node(self, f: JavaFile, n: Node) -> TypeDecl | None:
        return self._decl_by_node.get((f.path, n.id))

    def all_supertypes(self, td: TypeDecl, depth: int = 0) -> set[str]:
        """Resolved supertypes, following types declared in the same project."""
        out: set[str] = set()
        if depth > 8:
            return out
        for s in td.supers:
            out.add(s)
            sup = self.find_type(td.file.project, s)
            if sup is not None and sup is not td:
                out |= self.all_supertypes(sup, depth + 1)
        return out

    # ----------------------------------------------------------- expression
    def enclosing_type_decl(self, f: JavaFile, n: Node) -> TypeDecl | None:
        cur = n.parent
        while cur is not None:
            if cur.type in TYPE_DECLS:
                return self.decl_for_node(f, cur)
            cur = cur.parent
        return None

    def lambda_target(self, f: JavaFile, lam: Node) -> str | None:
        parent = lam.parent
        while parent is not None and parent.type in ("parenthesized_expression",):
            parent = parent.parent
        if parent is None:
            return None
        if parent.type == "return_statement":
            m = parent.parent
            while m is not None and m.type not in ("method_declaration", "lambda_expression"):
                m = m.parent
            if m is not None and m.type == "method_declaration":
                return f.resolve_type_node(m.child_by_field_name("type"))
        if parent.type == "variable_declarator":
            decl = parent.parent
            return f.resolve_type_node(decl.child_by_field_name("type")) if decl is not None else None
        if parent.type == "cast_expression":
            return f.resolve_type_node(parent.child_by_field_name("type"))
        if parent.type == "argument_list":
            call = parent.parent
            if call is not None and call.type == "method_invocation" and text(call.child_by_field_name("name")) == "handler":
                obj = call.child_by_field_name("object")
                if self.expr_type(f, obj) == CLIENT_TOPIC_SUBSCRIPTION_BUILDER:
                    return CLIENT_EXTERNAL_TASK_HANDLER
                chain = {text(x.child_by_field_name("name")) for x in walk(obj) if x.type == "method_invocation"} if obj else set()
                if "subscribe" in chain and any(i.startswith("org.camunda.bpm.client.") for i in f.import_fqns):
                    return CLIENT_EXTERNAL_TASK_HANDLER
        return None

    def expr_type(self, f: JavaFile, n: Node | None) -> str | None:
        if n is None:
            return None
        key = (f.path, n.id)
        if key in self._expr_cache:
            return self._expr_cache[key]
        self._expr_cache[key] = None  # recursion guard
        r = self._expr_type(f, n)
        # engine implementation classes stand for their service interface
        if r is not None and r.startswith(E + "impl.") and r.endswith("ServiceImpl"):
            iface = E + r.rsplit(".", 1)[-1][: -len("Impl")]
            if iface in SERVICES.values():
                r = iface
        self._expr_cache[key] = r
        return r

    def _expr_type(self, f: JavaFile, n: Node) -> str | None:
        t = n.type
        if t == "parenthesized_expression":
            return self.expr_type(f, n.named_children[0]) if n.named_children else None
        if t == "cast_expression":
            return f.resolve_type_node(n.child_by_field_name("type"))
        if t == "object_creation_expression":
            return f.resolve_type_node(n.child_by_field_name("type"))
        if t == "this":
            td = self.enclosing_type_decl(f, n)
            return td.fqn if td else None
        if t == "identifier":
            name = text(n)
            d = f.declared_type(n, name)
            if d is not None:
                return None if d[0] == UNTYPED else d[0]
            if name[:1].isupper():
                return f.resolve_type_name(name)  # static receiver: a class name
            return None
        if t == "field_access":
            obj = n.child_by_field_name("object")
            if obj is not None and obj.type == "this":
                td = self.enclosing_type_decl(f, n)
                r = f._field(td.node, text(n.child_by_field_name("field")), 0) if td else None
                return None if r is None or r[0] == UNTYPED else r[0]
            return None
        if t == "method_invocation":
            name = text(n.child_by_field_name("name"))
            obj = n.child_by_field_name("object")
            if obj is None:
                td = self.enclosing_type_decl(f, n)
                ret = self._method_return(td, name)
                if ret is not None:
                    return ret
                if name in GETTER_RETURNS and td is not None and any(
                    self.is_camunda_lib(s) for s in self.all_supertypes(td)
                ):
                    return GETTER_RETURNS[name]
                return None
            ot = self.expr_type(f, obj)
            if ot is None:
                return None
            if self.is_camunda_lib(ot) and name in GETTER_RETURNS:
                return GETTER_RETURNS[name]
            decl = self.find_type(f.project, ot)
            if decl is not None:
                return self._method_return(decl, name)
            return None
        return None

    def _method_return(self, td: TypeDecl | None, name: str, depth: int = 0) -> str | None:
        if td is None or depth > 6:
            return None
        body = td.node.child_by_field_name("body")
        for c in body.named_children if body is not None else ():
            if c.type == "method_declaration" and text(c.child_by_field_name("name")) == name:
                return td.file.resolve_type_node(c.child_by_field_name("type"))
        for s in td.supers:
            sup = self.find_type(td.file.project, s)
            if sup is not None:
                r = self._method_return(sup, name, depth + 1)
                if r is not None:
                    return r
        return None

    # ---------------------------------------------------------------- sites
    def call_sites(self) -> Iterator[CallSite]:
        for f in self.files:
            for n in walk(f.tree.root_node):
                if n.type != "method_invocation":
                    continue
                obj = n.child_by_field_name("object")
                name = text(n.child_by_field_name("name"))
                if obj is None:
                    yield CallSite(f, n, name, "", False)
                    continue
                if obj.type == "super":
                    continue
                yield CallSite(f, n, name, self.expr_type(f, obj), obj.type == "method_invocation")

    def type_decls(self) -> Iterator[TypeDecl]:
        for f in self.files:
            yield from f.types

    def anonymous_classes(self) -> Iterator[tuple[JavaFile, Node, str | None]]:
        for f in self.files:
            for n in walk(f.tree.root_node):
                if n.type == "object_creation_expression" and any(c.type == "class_body" for c in n.named_children):
                    yield f, n, f.resolve_type_node(n.child_by_field_name("type"))

    def lambdas(self) -> Iterator[tuple[JavaFile, Node, str | None]]:
        for f in self.files:
            for n in walk(f.tree.root_node):
                if n.type == "lambda_expression":
                    yield f, n, self.lambda_target(f, n)


def build_catalog(corpora: list[Corpus]) -> dict[str, set[str]]:
    """Simple name -> Camunda FQNs seen in explicit imports (for wildcard imports)."""
    catalog: dict[str, set[str]] = defaultdict(set)
    for c in corpora:
        for p in c.main_java():
            for line in (c.repo.dir / p).read_bytes().decode("utf-8", "replace").splitlines():
                s = line.strip()
                if s.startswith("import ") and not s.startswith("import static") and ".camunda." in s and "*" not in s:
                    fqn = s[len("import "):].rstrip(";").strip()
                    catalog[fqn.rsplit(".", 1)[-1]].add(fqn)
    for fqn in list(SERVICES.values()) + list(GETTER_RETURNS.values()) + [
        DELEGATE_EXECUTION, DELEGATE_TASK, JAVA_DELEGATE, EXECUTION_LISTENER, TASK_LISTENER, CONTEXT,
    ]:
        catalog[fqn.rsplit(".", 1)[-1]].add(fqn)
    return catalog


def load_indexes() -> dict[str, CorpusIndex]:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    missing = [c.repo.dir for c in CORPORA if not c.repo.dir.exists()]
    if missing:
        sys.exit(f"missing clones: {missing}; run `python scripts/clone.py` first")
    catalog = build_catalog(CORPORA)
    return {c.name: CorpusIndex(c, catalog) for c in CORPORA}


def line_of(n: Node) -> int:
    return n.start_point[0] + 1
