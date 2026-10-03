# Stack research

Python >=3.11, argparse, dataclasses, sqlite3, string.Template and standard-library HTTP primitives keep runtime dependencies small. Use inotify-simple as a small Linux adapter if useful; imports must be lazy for portable core/SDK/report operations. Use pytest, coverage, Ruff, mypy and build for development, uv.lock for reproducibility. SQLite WAL and separate short-lived connections support simultaneous writers; busy timeout, schema version and restrictive state permissions are required.

Sources: https://docs.python.org/3/library/sqlite3.html ; https://packaging.python.org/en/latest/tutorials/packaging-projects/
