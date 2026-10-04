# SQLite Sidecar Deletion Race Correction

The final release regression encountered `UnsafePathError` while a reader validated `events.sqlite3-shm` concurrently with SQLite connection shutdown. A clean pre-fix diagnostic reproduced the cause in 4,000 real `Store.events()` calls across two independent Stores: one actual no-follow stat returned `nlink=0`, `regular=True`, `uid=1000` (the current user), and `mode=0600`, followed by one `UnsafePathError`. No attributes, permissions, links or SQLite internals were modified by the diagnostic.

SQLite normally removes the WAL and its shared-memory file when the last connection closes. The zero-link sample is consistent with pathname lookup retaining the old inode while SQLite unlinks it. [SQLite WAL lifecycle documentation](https://sqlite.org/wal.html#avoiding_excessively_large_wal_files) describes that cleanup; [Linux stat documentation](https://man7.org/linux/man-pages/man2/stat.2.html) describes concurrent metadata sampling.

`check_private_file()` now makes at most three no-follow stat attempts when an **optional, exact known SQLite sidecar name** has a zero link count and otherwise passes every security check. Validation succeeds only when the optional path is missing or a fully valid singly linked replacement is observed. Persistent zero-link samples fail closed. The primary database, required files and unrelated optional names never receive this retry. Non-regular files, symlinks, hardlinks, foreign owners and nonprivate modes fail immediately, including on replacement samples. Other filesystem errors propagate.

Changes are confined to `src/agentcanary/filesystem.py`, `tests/test_store_sidecars.py` and this note. Store APIs and connection behavior remain unchanged.

Verification:

- 26 new deterministic race/replacement/security cases and real multi-Store concurrency coverage. The real stress test checks all 400 writes, unique event IDs and contiguous durable sequences while readers open and close independent connections; an additional 1,600 read-only operations exercise sidecar turnover.
- Focused store/state/policy/integration suite: **66 passed in 14.55s**, including the previously failing policy test.
- Full Python 3.12 regression: **220 passed in 65.19s**, with no skips or failures.
- Full lint passed; formatting passed for 87 files; strict typing passed for 17 source files.
