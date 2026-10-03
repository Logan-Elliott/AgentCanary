# Integration research

The required building blocks are implemented locally and already tested individually. A real subprocess using `sys.executable -m ...` verifies packaging and attribution boundaries better than an in-process imitation. Use `subprocess.run` with an argument array, a finite timeout, and no shell. Fixtures and `.invalid` destination labels must never be interpreted as external connection targets.

Readiness is an API state, not elapsed time. Poll for durable evidence with a bounded monotonic deadline while checking worker errors; avoid demanding a total order between kernel and SDK observations. SQLite ingestion sequence orders commits, not all observed actions across threads/processes.

Grounding: `src/agentcanary/sdk.py`, `network.py`, `monitors/inotify.py`, `store.py`, and the existing real-loopback and subprocess tests. This phase introduces no external library or protocol dependency.
