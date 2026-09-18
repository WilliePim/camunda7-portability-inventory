# Review notes on report.md

These notes come from a read-only pass over `report.md`, made after the fixes to §2D, §5 (asks 1 and 4) and §M. Each item below is a sentence that a maintainer could contradict using this repository's own numbers or sources. Nothing listed here has been changed in `report.md`.

Line numbers refer to `report.md` at the commit that adds this file. Script rows are from `python scripts/inventory.py`, unless stated otherwise.

1. Method, line 8 ("Static inventory (grep of call sites, ...)") and Caveats, line 256 ("Static grep, no runtime").

   The counts in the report come from a tree-sitter parse with receiver types resolved through imports, not from grep (`scripts/javaindex.py`; `verification.md`, "Counting rule" and section 3, item 2).

   Running grep reproduces the old numbers, not the corrected ones. For example, across both repositories 35 of the 56 grep hits for chained `startProcessInstanceBy(Key|Id)` calls are commented-out lines, while the report shows 27 (`1.start.chained`).

2. Method table, line 13 ("`camunda-consulting/code` (C7 snippets only) | 1,297").

   The 1,297 files are not all snippets: 1,052 are under `snippets/` and 245 under `one-time-examples/`. These counts come from `Corpus.main_java()` in `scripts/repos.py`, grouped by top-level folder.

3. Method, line 15 ("Counts are **call sites**, not distinct features").

   Several counts are not call sites:
   - classes: 231 and 257 delegate/listener classes, 6 `ExternalTaskHandler` implementations, the §2C and §2F subclasses, and the §2G plugin and listener shapes;
   - import declarations: 617 and 698;
   - files: 1,297 and 176.

4. §2A, line 42 ("231 delegate/listener classes (185 `JavaDelegate`, 25 `ExecutionListener`, 22 `TaskListener`)").

   The three per-interface counts add up to 232, not 231. One class, `DelegationCodeTestProxy`, implements both `JavaDelegate` and `ExecutionListener` (`verification.md` section 3, item 8). The report does not say this.

5. §2C, line 65, and the §3 row "History infrastructure | 14 classes", line 226.

   `DynamicRemovalTimeCalculationStrategy` (2) is listed as custom Camunda history infrastructure. It is an interface declared inside one snippet, not a Camunda type (`2C.dynamicRemovalTime`; `verification.md` section 3, item 12).

   The Camunda extension point behind it, `HistoryRemovalTimeProvider`, has 1 implementation (`2C.historyRemovalTimeProvider`). The 14 classes in §3 include the 2 snippet-local implementations.

6. §2E table, line 81 ("`runtimeService.messageEventReceived(name, executionId)` | 6 | maps partially to correlation").

   The text of the same section says `messageEventReceived(name, executionId)` "has no path through `CorrelationApi`" (line 89). The adapter rejects `executionId` for correlation (adapter `correlation/CorrelationApiImpl.kt:59-63` embedded, `:63-67` remote).

7. §3 row "External-task worker style | 39", line 221; "Jobs / incidents / retries (ops) | 16", line 229; "CMMN | 41", line 231.

   The column is headed "Sites", but these three rows add classes to call sites:
   - External-task worker style: 33 call sites + 6 `ExternalTaskHandler` classes (`1.ext.complete`, `1.ext.handleFailure`, `1.ext.handler`);
   - Jobs / incidents / retries: 6 call sites + 10 classes (`2F.jobOps`, `2F.jobRetryCmd`, `2F.incidentHandler`, `2F.timerEventJobHandler`);
   - CMMN: 31 call sites + 10 `CaseExecutionListener` classes (`2H.caseService`, `2H.caseExecutionListener`).

8. §3 row "User task complete / assign / by-error | 37", line 222.

   The 37 includes the 11 `throw new BpmnError` sites from §1. Those are counted inside `JavaDelegate` scopes (`1.bpmnError`), so they are service-task errors, not user-task errors. The user-task sites in the row are 26: `taskService.complete` 3 + 12 chained, and claim / setAssignee 11.

9. §3 row "Delegates & listeners in shared transaction | 257 classes, 73 nested engine calls", line 224.

   73 is the number of entry-point call sites, not engine calls. `python scripts/delegates.py` counts 85 engine-method calls reached through those entry points, and 117 engine-method calls inside delegate scopes in total (both repositories).

10. §3 row "Instance lifecycle, instance variables | 34 | partial", line 228.

    None of the 34 counted sites has a path in the API:
    - §E states "no path" for rows covering 28 of them: instance variables 15, `signal(executionId)` 4, `messageEventReceived` 6, `deleteProcessInstance` 1 and running-instance modification 2 (lines 80-81 and 89-95).
    - The other 6 (suspend/activate 4, `getActiveActivityIds` 2) have no matching command in the API surface listed in the Method section.

    The only related coverage in §E is starting a new instance at an element, and none of the 34 sites does that.

11. §3 row "Variable scope / typed values | 21", line 233.

    The 21 are only `setVariableLocal` 7, `getVariableLocal` 4, `removeVariable` 6 and `hasVariable` 4 (`2J.*` rows). Typed values (`ObjectValue`, `TypedValue`, `Variables.objectValue(...)`) are not counted anywhere.

12. §5 ask 3, line 250 ("Adapter behaviour for variables (§J): scope, serialization, removal").

    §J says the embedded adapter's serialization behaviour is already documented (adapter `docs/reference-c7-embedded.md:32-52`), and narrows its own ask to the remote `ValueMapper` rules. Ask 3 still asks for serialization in general.

    The scope and removal parts still hold: the adapter implements them, and none of the adapter docs mentions removal or variable scope.

Not listed: statements of judgement that no count in this repository measures, and that no count contradicts. These are "ports almost mechanically" (§1), "the pattern that decides the effort of a migration" (§2A), "common in enterprise C7 apps" (§D), "frequently pinned per variable" (§J) and "Dead end on every target engine" (§H).
