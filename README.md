# Camunda 7 → process-engine-api portability inventory

This repository verifies and hosts a static inventory of how open-source Camunda 7 code uses the engine, compared against the [process-engine-api](https://github.com/bpm-crafters/process-engine-api). It also contains a reproducer for three bugs in the embedded Camunda 7 adapter (`c7-embedded-core` in [process-engine-adapters-camunda-7](https://github.com/bpm-crafters/process-engine-adapters-camunda-7)): the bug reports are in [issues/](issues/), the failing tests in [reproducer/](reproducer/).

| File | Content |
|---|---|
| [report.md](report.md) | Standalone field report: Camunda 7 engine usage counted in two open-source codebases and held against process-engine-api, with what maps, what does not, a summary table, and documentation asks for the maintainers of the API and its Camunda 7 adapter (section 5). It files no bugs; those are in `issues/`. |
| [verification.md](verification.md) | Every count in `report.md`: reported vs measured, delta, method. Also: claims corrected, gaps the Camunda 7 adapter already covers, open questions. |
| [issues/](issues/) | Drafts of three bug reports for [process-engine-adapters-camunda-7](https://github.com/bpm-crafters/process-engine-adapters-camunda-7), all in `c7-embedded-core`, written to that repository's bug template with the reproducer's results. |
| [reproducer/](reproducer/) | Maven project that runs the embedded adapter on an in-memory Camunda 7 engine, with one failing test per bug in `issues/` ([reproducer/README.md](reproducer/README.md)). |
| `scripts/` | Everything used to produce the numbers and citations. Runnable from the repository root. |
| `external/` | Clones of the analysed repositories (git-ignored, created by `scripts/clone.py`). |

## Running the reproducer

The three bugs in `issues/` are reproduced by the Maven project in `reproducer/`. You need git, a JDK 21 and network access to Maven Central. Maven itself is not needed: the wrapper downloads Maven 3.9.12 on the first run.

```sh
git clone https://github.com/WilliePim/camunda7-portability-inventory.git camunda7-portability-inventory
cd camunda7-portability-inventory/reproducer
export JAVA_HOME=/path/to/jdk-21   # replace with the folder of your JDK 21
./mvnw test
```

Maven runs on the JDK in `JAVA_HOME` and falls back to the first `java` on the `PATH` only when `JAVA_HOME` is unset, which can be a different JDK; set it explicitly. To find the path of your JDK 21, the folder that contains `bin/java`: on macOS `/usr/libexec/java_home -v 21` prints it, on Linux JDKs are usually folders under `/usr/lib/jvm/`, and in PowerShell `Get-ChildItem 'C:\Program Files\Eclipse Adoptium', 'C:\Program Files\Java' -Directory -ErrorAction SilentlyContinue` lists the usual install folders. In PowerShell, set it with `$env:JAVA_HOME = 'C:\path\to\jdk-21'` and run `.\mvnw.cmd test`.

Expected result: `Tests run: 9, Failures: 3, Errors: 2` and `BUILD FAILURE`. The build fails on purpose. The five bug tests assert the behaviour the API describes, so they fail while the bugs exist; the four `observed_*` tests record what the adapter and the engine do, and pass. Full output, with stack traces, is in `target/surefire-reports/`; the result of each test is in [reproducer/README.md](reproducer/README.md).

| Component | Version |
|---|---|
| `process-engine-adapter-camunda-platform-c7-embedded-core` | 2026.09.1, the latest release |
| `process-engine-api`, `process-engine-api-impl` | 1.7 |
| `camunda-engine` | 7.24.0, on H2 2.3.232 in memory |
| JDK | Java 21, which Camunda 7.24 [lists as supported](https://docs.camunda.org/manual/7.24/introduction/supported-environments/#java); recorded run on Eclipse Temurin 21.0.12.1+1 |

## Running from a clean checkout

You need git, Python 3 (tested with 3.13) and network access to github.com. The commands are for a POSIX shell; Git Bash works on Windows. PowerShell differences are noted below the block.

```sh
# 1. Get this repository
git clone https://github.com/WilliePim/camunda7-portability-inventory.git camunda7-portability-inventory
cd camunda7-portability-inventory

# 2. Python environment with the parser packages (tree-sitter, tree-sitter-java)
python -m venv .venv
source .venv/bin/activate        # Git Bash on Windows: source .venv/Scripts/activate
python -m pip install -r scripts/requirements.txt

# 3. Fetch the four analysed repositories at the pinned commits
python scripts/clone.py

# 4. Produce the results
mkdir -p out
python scripts/inventory.py --json out/inventory.json > out/inventory.md
python scripts/delegates.py --sites > out/delegates.md
python scripts/adapter_facts.py --check-report > out/adapter_facts.md
```

In PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`, and create the folder with `mkdir out`. Windows PowerShell 5.1 writes UTF-16 files with `>`, so either pipe to `Out-File -Encoding utf8 out/inventory.md` or run step 4 in Git Bash.

All scripts are run from the repository root. They print Markdown to standard output. The redirects above only keep a copy in `out/`, which is git-ignored.

### What each step produces

| Step | Files written | Printed |
|---|---|---|
| `pip install` | `.venv/` (git-ignored) | pip's install log |
| `clone.py` | `external/<owner>__<name>/` for the four repositories: shallow, detached at the commit pinned in `scripts/repos.py`, with `core.longpaths=true` | One line per repository with the checked-out commit. On a second run it prints `(already present)` and fetches nothing. |
| `inventory.py` | With `--json PATH`: the same rows as JSON (the folder is created if needed) | One table row per count in `report.md` (126 rows): id, section, pattern, reported value, measured value, delta, value per repository, unresolved sites not counted, and the counting rule |
| `delegates.py` | none | Three tables: delegate/listener implementations, engine access from inside delegates (entry points), distinct engine methods called from inside delegates. `--sites` adds the 73 entry-point call sites with file:line. |
| `adapter_facts.py` | none | The Camunda 7 adapter's meta keys, payload handling and restriction handling, each with a file:line citation checked against the source. With `--check-report` it also checks the 64 adapter/API citations in `report.md`. |

### Checking the result

- No line printed by `clone.py` contains `differs from pinned commit`.
- `adapter_facts.py` ends with `All citations verified.` and exits with status 0. If a cited line no longer contains the expected text, it lists the citation under `Citation check FAILED` and exits with status 1.
- The Measured column of `out/inventory.md` is the column of the same name in `verification.md` section 1, which is where the numbers in `report.md` come from.
- The three tables in `out/delegates.md` are the tables in `verification.md` section 2.
- Headline values to spot-check: 231 delegate/listener classes in the consulting repository (257 in both), 47 of them calling the engine through 72 entry-point call sites (48 and 73 in both).

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

The limits below apply to the inventory: the scripts in `scripts/`, `report.md` and `verification.md`. They do not apply to the three adapter bugs in `issues/`, which the reproducer observes at runtime against the released adapter instead of inferring them from source.

- **Static analysis only.** The inventory scripts parse the analysed sources; nothing in them is compiled or executed.
  - Call receivers are typed from declarations, imports and known Camunda getter chains, without a classpath.
  - A receiver the index cannot resolve is not counted, so counts err low.
  - The adapter behaviour described in the report's sections is read from source, not observed at runtime. The three bugs are the exception: each one is shown by a failing test in `reproducer/`.
- **Java only.** Not analysed: BPMN/DMN/CMMN XML (e.g. `camunda:delegateExpression` bindings), scripts embedded in models, and non-Java sources. Neither corpus contains Kotlin.
- **Snippet repositories, not applications.**
  - Both corpora are samples and consulting snippets: many small projects, some near-duplicates, some generated code (e.g. an OpenAPI client).
  - Counts describe how often a shape appears in these repositories, not in production systems.
- **No customer code.** Only the four public repositories above are analysed.
- **Remote adapter serialization** depends on `io.holunda.c7:c7-rest-client-variables`, which is not cloned. Its rules are not verified here.
- **Windows.** Some snippet paths exceed 260 characters. `clone.py` sets `core.longpaths=true` in each clone for git, and Python needs Windows long-path support enabled (the `LongPathsEnabled` registry setting) to read those files.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
