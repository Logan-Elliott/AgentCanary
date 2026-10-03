# Project Research Summary

## Key Findings
Use small, independent Python modules and provenance-rich events. A reliable unprivileged baseline combines Linux access notifications, explicit attributed SDK calls and a local HTTP blocking endpoint. No single layer can guarantee universal tracking of an uncooperative agent.

## Implications for Roadmap
Build safe creation and storage first, then observation contracts, network parsing and matching, a real subprocess demo, and finally release/audit hardening. Include negative and race tests from the beginning.

## Sources
- https://man7.org/linux/man-pages/man7/inotify.7.html
- https://docs.python.org/3/library/sys.html#sys.addaudithook
- https://docs.python.org/3/library/sqlite3.html

## Assumptions
The operator controls the workspace and selects observation boundaries. Generated credentials are visibly invalid, and destinations use reserved .invalid names. Test traffic remains on loopback. A compromised same-user process can bypass or tamper with local monitoring. These constraints are part of the product contract.
