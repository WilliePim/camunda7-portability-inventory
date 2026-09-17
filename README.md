# Camunda 7 → process-engine-api portability inventory

This repository verifies and hosts a static inventory of how open-source Camunda 7 code uses the engine, compared against the [process-engine-api](https://github.com/bpm-crafters/process-engine-api).

| File | Content |
|---|---|
| [report.md](report.md) | The inventory, written as an issue for the process-engine-api maintainers. Counts corrected and sections E, I, J amended from the verification. |
| [verification.md](verification.md) | Every count in `report.md`: reported vs measured, delta, method. Also: claims corrected, gaps the Camunda 7 adapter already covers, open questions. |
| `scripts/` | Everything used to produce the numbers and citations. Runnable from the repository root. |
| `external/` | Clones of the analysed repositories (git-ignored, created by `scripts/clone.py`). |

## Re-running

Requirements: git and Python (tested with 3.13).

```sh
python -m pip install -r scripts/requirements.txt   # tree-sitter, tree-sitter-java

python scripts/clone.py                          # shallow clones at the pinned commits into external/
python scripts/inventory.py                      # Task 1: every count in report.md, reported vs measured
python scripts/delegates.py                      # Task 2: delegate/listener classes and engine calls made from inside them
python scripts/adapter_facts.py --check-report   # Task 3: adapter meta keys, payload mapping, EXECUTION_ID; checks report.md citations
```

Options:

| Command | Effect |
|---|---|
| `python scripts/inventory.py --explain 1.start.chained` | Lists every counted site and every rejected same-name site for one row. Row ids are in `scripts/inventory.py` and in the Method column of `verification.md`. |
| `python scripts/inventory.py --json out/inventory.json` | Also writes the table as JSON. `out/` is git-ignored. |
| `python scripts/delegates.py --sites` | Lists every entry-point call site. |
| `python scripts/clone.py --latest` | Fetches default-branch HEAD instead of the pinned commits and prints the new hashes. To analyse them, update the commits in `scripts/repos.py`. |

`scripts/repos.py` (repositories, pinned commits, main-source rule), `scripts/javaindex.py` (import-aware Java index) and `scripts/delegate_scopes.py` (delegate scopes and entry points) are modules used by the scripts above.

`adapter_facts.py` exits with status 1 when a cited adapter line no longer contains the expected source text.

## Analysed repositories

Cloned on 2026-09-17 with `--depth 1`.

| Repository | Commit | Use |
|---|---|---|
| [camunda/camunda-bpm-examples](https://github.com/camunda/camunda-bpm-examples) | `6c7f4c4adb4beb9a2f5d4c5e49fc1ddfc6dab3fc` | Camunda 7 corpus (124 main `.java` files) |
| [camunda-consulting/code](https://github.com/camunda-consulting/code) | `c9ef30b62a47a7063c077397cb3340b28fb4cc3c` | Camunda 7 corpus (1,297 main `.java` files); `snippets/reverse-adapter/` excluded as Camunda 8 / Zeebe |
| [bpm-crafters/process-engine-api](https://github.com/bpm-crafters/process-engine-api) | `b02569855596de4fb423dc181489e72595235503` | API reference (`api` module, version `1.8-SNAPSHOT`) |
| [bpm-crafters/process-engine-adapters-camunda-7](https://github.com/bpm-crafters/process-engine-adapters-camunda-7) | `d2be36eca2edf24d1e1a43540cee77d9e9dffd21` | Adapter behaviour for sections E, I, J (the build pins `process-engine-api` 1.7) |

Main sources are `.java` files under `src/main/`. Test sources and build helpers such as `.mvn/wrapper` are excluded.

## Known limitations

- **Static analysis only.** Nothing is compiled or executed.
  - Call receivers are typed from declarations, imports and known Camunda getter chains, without a classpath.
  - A receiver the index cannot resolve is not counted, so counts err low.
  - Adapter behaviour is read from source, not observed at runtime.
- **Java only.** Not analysed: BPMN/DMN/CMMN XML (e.g. `camunda:delegateExpression` bindings), scripts embedded in models, and non-Java sources. Neither corpus contains Kotlin.
- **Snippet repositories, not applications.**
  - Both corpora are samples and consulting snippets: many small projects, some near-duplicates, some generated code (e.g. an OpenAPI client).
  - Counts describe how often a shape appears in these repositories, not in production systems.
- **No customer code.** Only the four public repositories above are analysed.
- **Remote adapter serialization** depends on `io.holunda.c7:c7-rest-client-variables`, which is not cloned. Its rules are not verified here.
- **Windows.** `clone.py` sets `core.longpaths=true` in each clone because some snippet paths exceed 260 characters.
