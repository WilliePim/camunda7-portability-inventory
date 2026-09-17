"""Task 2: delegates and listeners, and engine calls made from inside them.

    python scripts/delegates.py            # markdown report on stdout
    python scripts/delegates.py --sites    # also list every entry-point call site

Definitions are in delegate_scopes.py.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from delegate_scopes import ENTRY_POINTS, analyse, summarise
from javaindex import load_indexes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", action="store_true", help="list every entry-point call site")
    args = ap.parse_args()
    indexes = load_indexes()
    results = {name: analyse(ix) for name, ix in indexes.items()}
    summary = summarise(results)
    names = list(summary)

    def row(label: str, key: str) -> str:
        vals = [summary[n].get(key, 0) for n in names]
        return f"| {label} | " + " | ".join(str(v) for v in vals) + f" | {sum(vals)} |"

    head = "| | " + " | ".join(names) + " | total |\n|---|" + "---:|" * (len(names) + 1)
    print("## Delegate and listener implementations\n")
    print(head)
    print(row("named non-abstract classes (headline)", "classes"))
    print(row("… implementing JavaDelegate", "JavaDelegate"))
    print(row("… implementing ExecutionListener", "ExecutionListener"))
    print(row("… implementing TaskListener", "TaskListener"))
    print(row("… of which implement an interface directly", "classes_direct"))
    print(row("abstract classes implementing one (not in headline)", "abstract"))
    print(row("anonymous classes (not in headline)", "anonymous"))
    print(row("lambdas (not in headline)", "lambda"))
    print("\n## Engine access from inside delegates\n")
    print(head)
    print(row("entry-point call sites, all delegate scopes", "entry_sites"))
    for kind in ENTRY_POINTS:
        print(row(f"… via `{kind}`", f"entry:{kind}"))
    print(row("entry-point call sites inside named classes", "entry_sites_in_classes"))
    print(row("named classes with ≥1 entry-point call (headline)", "classes_calling"))
    print(row("files containing those classes", "files_calling"))
    print(row("delegate units of any kind with ≥1 entry-point call", "units_calling"))
    print(row("DelegateExecution/DelegateTask.getProcessEngine() sites (not in headline)", "getProcessEngine_sites"))

    print("\n## Distinct engine methods called inside delegate scopes\n")
    total: dict[str, Counter] = defaultdict(Counter)
    for r in results.values():
        for m, c in r["methods"].items():
            total[m].update(c)
    print("| Method | via entry point | via getProcessEngine() | other origin (field, parameter) | total |")
    print("|---|---:|---:|---:|---:|")
    for m, c in sorted(total.items(), key=lambda kv: (-kv[1]["entry"], -sum(kv[1].values()), kv[0])):
        print(f"| `{m}` | {c['entry']} | {c['getProcessEngine']} | {c['other']} | {sum(c.values())} |")
    print(f"| **distinct methods** | {sum(1 for c in total.values() if c['entry'])} | "
          f"{sum(1 for c in total.values() if c['getProcessEngine'])} | {sum(1 for c in total.values() if c['other'])} | {len(total)} |")
    print(f"| **call sites** | {sum(c['entry'] for c in total.values())} | {sum(c['getProcessEngine'] for c in total.values())} | "
          f"{sum(c['other'] for c in total.values())} | {sum(sum(c.values()) for c in total.values())} |")

    if args.sites:
        print("\n## Entry-point call sites\n")
        for name, r in results.items():
            for u, path, line, snippet, kind in sorted(r["entry_sites"], key=lambda s: (s[1], s[2])):
                print(f"- {name} `{path}:{line}` ({u.kind} {u.name.rsplit('.', 1)[-1]}, {kind}) `{snippet}`")


if __name__ == "__main__":
    main()
