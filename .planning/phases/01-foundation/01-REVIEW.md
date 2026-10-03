---
phase: 01-foundation
reviewed: 2026-10-03T22:01:23Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - src/agentcanary/models.py
  - src/agentcanary/store.py
  - src/agentcanary/filesystem.py
  - src/agentcanary/generator.py
  - src/agentcanary/templates.py
  - src/agentcanary/report.py
  - src/agentcanary/cli.py
  - src/agentcanary/protocols.py
  - src/agentcanary/__init__.py
  - src/agentcanary/__main__.py
  - pyproject.toml
  - tests/test_store.py
  - tests/test_generator.py
  - tests/test_cli.py
  - tests/test_concurrency.py
  - tests/test_report.py
  - tests/test_seed_rollback.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
historical_findings:
  critical: 3
  warning: 1
  info: 0
  total: 4
status: clean
resolution_status: resolved
fixes_verified: 2026-10-03T22:07:55Z
fix_commits:
  - 96096f55bcf1e39cc4612f2bdcf67dcdadb129af
  - 729af227c526d0a51b100e244081fc82721aa000
  - 37e58088a4d199ecf6e68f308555b397d04cb0e7
reviewed_implementation: 7ea2b61f0fd0bac6fddf026e45e7178474203cdc
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-03T22:01:23Z  
**Depth:** deep  
**Files reviewed:** 17 (16 original scope files and one focused regression file)  
**Status:** resolved — no outstanding findings; canonical workflow status `clean`  
**Fixes verified:** 2026-10-03T22:07:55Z

## Summary

Four concrete findings were identified in the completed foundation implementation: existing directory permissions were changed by store construction; ordinary seed failures could leave unregistered files; path containment used a different identity from filesystem traversal; and rejected SQLite databases were modified before validation. The original severities remain three BLOCKER findings and one WARNING. All four are now resolved by the parent agent's commits listed above. Frontmatter `findings` counts only outstanding issues; `historical_findings` and the narrative retain the original classifications and evidence.

Scope is the completed Phase 1 implementation at `7ea2b61`, plus its directly imported public contracts. Review of CLI code covers only the completed create, seed, types and report paths. Unfinished Phase 2 SDK, matching and monitor additions are excluded. No structural pre-pass or external reviewer evidence was supplied. Source and tests were not modified by this reviewer, and no commits were made.

## Narrative Findings (AI reviewer)

### CR-01: Opening an existing state directory changes unrelated user permissions

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/filesystem.py:36-42` at the reviewed implementation; caller `/home/gsd/projects/agent-canary/src/agentcanary/store.py:31`  
**Disposition:** Resolved by parent commit `96096f5`; replacement validation was inspected.

**Issue:** `open_directory(private=True)` called `fchmod(fd, 0700)` regardless of whether this operation created the directory. Every `Store` construction, including the reporting path, therefore changed permissions on a user-selected existing directory. A selected project directory could unexpectedly stop being accessible to collaborators or services. This side effect occurred before database validation and could accompany an otherwise rejected operation.

**Evidence:** A benign existing directory explicitly set to mode `0755` became `0700` after `Store(existing_directory)`. This used only a disposable local directory.

**Fix:** Create new state directories privately; validate ownership and private permissions on existing directories and fail without modifying them. Recheck the private-directory contract when opening subsequent connections. The parent implemented this and reported 14 focused passing cases across directory, store and concurrency tests, with scoped lint, format and type checks.

### CR-02: Ordinary rollback can stop early or miss a newly created artifact

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/generator.py:137-146` and `163-178` at the reviewed implementation  
**Disposition:** Resolved by parent commit `37e5808`; corrected ownership ordering and cleanup were inspected, and both targeted regressions passed independently.

**Issue:** There are two independent failure points in the promised ordinary-failure rollback. First, `os.dup(parent_fd)` is evaluated while creating the rollback entry, after `os.open(... O_CREAT | O_EXCL ...)` has already created the file. If the descriptor allocation fails, the new file is absent from `created` and survives rollback. Second, rollback suppresses only `FileNotFoundError`; a persistent `fsync` failure after one deletion aborts the loop, skips earlier files, skips directory cleanup, and prevents the remaining descriptor cleanup from running. These failures require neither a process crash nor a hostile actor.

**Evidence:** Two small local checks were performed against the reviewed implementation:

- A two-artifact seed with a simulated persistent `EIO` beginning at the second file's `fsync` left the first artifact present, while the registry contained zero canaries. Cleanup deleted the second artifact and then aborted at its own failing `fsync`.
- A valid 80-artifact batch in a review subprocess with a temporary soft descriptor limit of 64 raised `EMFILE` and left one zero-byte artifact, while the registry contained zero canaries. The process limit was restored before fixture cleanup.

The existing test at `/home/gsd/projects/agent-canary/tests/test_generator.py:160-169` injects a one-time `fsync` failure; it does not exercise the persistent cleanup failure. This is coverage context, not a separate test-quality finding.

**Fix:** Acquire the resources needed to record ownership before creating a destination, or immediately remove the just-created file if bookkeeping fails. Ensure all acquired descriptors are closed under an outer cleanup `finally`. Attempt cleanup for every owned file and directory even when an earlier cleanup operation fails; retain the original failure and report any cleanup failures without stopping subsequent cleanup. Keep device/inode checks so cleanup remains limited to files this operation created. Add both focused failure cases and assert that subsequent seeding succeeds after the error condition is removed.

**Verified correction:** Rollback descriptors are reserved before file and directory creation and released if creation fails. Cleanup continues after individual filesystem errors while preserving the initiating exception, and tracked descriptors are closed best-effort. The independent regression run confirmed no remaining artifacts after persistent `fsync` errors or real child-process `EMFILE`, an empty registry in both cases, and unchanged descriptor count for the persistent-error case. Cleanup remains best-effort if the filesystem itself refuses removal; complete recovery from an unavailable filesystem is not claimed.

### CR-03: Path containment and directory traversal disagree about root identity

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/filesystem.py:15-19`, `25-27`; containment caller `/home/gsd/projects/agent-canary/src/agentcanary/generator.py:103-105`  
**Disposition:** Resolved by parent commit `37e5808`; canonicalization was inspected and the pure path-equivalence regression passed independently.

**Issue:** `absolute_path()` preserves alternate absolute-root anchors that compare differently as `Path` objects. In contrast, `open_directory()` always starts from the literal root descriptor and traverses only `absolute.parts[1:]`, discarding that anchor distinction. Consequently two paths can have different lexical identities in the state-directory containment check yet select the same directory through this implementation. The explicit guarantee that artifacts cannot be placed inside the selected state directory is therefore not enforced consistently for all accepted absolute paths. Root rejection in `open_directory(private=True)` has the same lexical assumption.

**Evidence:** An in-memory comparison produced unequal results from `absolute_path()` for two root spellings with identical `parts[1:]`. No directory was opened, no artifact was seeded, and no bypass was exercised. The traversal equivalence follows directly from `open_directory()` starting at its literal root and consuming those identical component lists.

**Fix:** Normalize all accepted absolute paths to the same root spelling used by the Linux descriptor traversal, before storing `state_dir`, comparing containment, or checking the filesystem root. Alternatively reject ambiguous root spellings before any operation. Preserve the no-symlink-following behavior; resolving symlinks is not required to fix this. Add pure canonicalization-equivalence tests and root-validation tests.

**Verified correction:** `absolute_path()` now normalizes its anchor to the literal root used by descriptor traversal, without resolving symlinks. Tests verify equivalent root spellings produce equal paths and the root itself normalizes to `Path("/")`.

### WR-01: Store construction changes a foreign SQLite database before rejecting it

**Classification:** WARNING  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/store.py:73-83` at the reviewed implementation  
**Disposition:** Resolved by parent commit `729af22`; corrected ordering was inspected.

**Issue:** `_initialize()` originally executed persistent `PRAGMA journal_mode=WAL` before reading the schema version, application ID and table inventory. Selecting an unrelated database named `events.sqlite3` therefore changed its journal configuration even though initialization subsequently refused it. The rejection was not side-effect free for the preexisting database and could interfere with the configuration expected by its owning application.

**Evidence:** A disposable SQLite database containing one unrelated table began in `delete` mode. `Store` raised `StoreError: refusing to initialize an unrecognized database`, but a subsequent normal SQLite read showed journal mode `wal`. The fixture's row remained intact; no data loss is claimed.

**Fix:** Validate ownership/schema before making persistent configuration changes; initialize recognized new state transactionally, and only then configure WAL. Add a regression asserting that a rejected foreign database retains its contents and journal mode. The parent implemented this and reported 16 focused passing tests, including byte-for-byte preservation of the foreign database and 20 synchronized two-thread initialization rounds.

## Review evidence and boundaries

The final pass was limited to the corrections for these findings. Commit `37e5808` and its regression tests were read; the reviewer independently ran `.venv/bin/python -m pytest -q tests/test_seed_rollback.py`: **3 passed**. The parent reported **35 focused tests passed** plus scoped lint and type checks for the completed correction set. Earlier fixes `96096f5` and `729af22` were inspected during the initial review, with their parent-run evidence recorded under the corresponding findings. No whole-source rereview or full-suite rerun was performed for this final pass.

Cross-file tracing covered `CLI -> generator -> templates/Canary -> descriptor filesystem operations -> Store.register_many -> CREATE/Event`, `Store.record -> Event serialization -> SQLite transaction`, and `CLI report -> Store query -> Event reconstruction -> report redaction`. The public protocols and package exports were checked against these calls. Models' bounds, UUID/action validation, metadata immutability, token redaction, transaction failure paths, destination collision checks and CLI error handling were read in context. No import cycle was found in this completed scope.

Separate from the findings above, 100 synchronized two-thread initializations against fresh local databases completed all 200 `Store` constructions without errors. This supports only the exercised initialization scenario; it is not a general concurrency proof. The full suite was not rerun by this reviewer because the parent and executor already own that verification. All review fixtures were removed.

The following are existing scope limits, not additional defects:

- Filesystem writes and SQLite commits are separate durability boundaries. Abrupt termination can leave unregistered artifacts; this is already disclosed in `seed()` and the phase summary. CR-02 concerns ordinary errors, which have a stronger documented cleanup guarantee.
- A process controlling the monitoring account can tamper with evidence. No same-account hostile race, exploit reproduction, third-party probe or external transmission was attempted.
- The storage implementation depends on Linux directory-descriptor operations and `/proc/self/fd` (`store.py:59`), in addition to Python 3.11+. This is stated in the phase summary. Release documentation and package platform metadata must preserve that requirement; a dependency-free Python wheel does not imply a portable storage backend. Final public documentation is an explicitly deferred phase, so its current absence is not counted as a foundation defect.
- Metadata allowlisting and report redaction are not a general-purpose secret scrubber. Adapter-owned destination and label sanitization is already part of the stated contract and must be checked in the later adapter reviews.

---

_Reviewer: foundation_review_astra (gsd-code-reviewer)_  
_Depth: deep_
