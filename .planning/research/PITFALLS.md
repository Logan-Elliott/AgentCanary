# Pitfalls research

Inotify has no originating PID and can coalesce events or overflow. IN_ACCESS is evidence of access rather than byte-level provenance. File replacement and watch loss need explicit diagnostics. Do not recursively scan and then report the monitor's own reads as agent activity. SDK instrumentation is cooperative and bypassable; Python audit hooks are not a sandbox. HTTP CONNECT cannot reveal TLS bodies; block and report the blind spot. Limit request size, connection count, read duration, compression expansion and decoder depth. Preserve unknown attribution rather than guessing from /proc. Guard seed paths against symlinks, traversal, preexisting files and crash/concurrency failures. Keep event metadata bounded and redacted, including URL userinfo/query/fragment. Event policy must not erase CREATE history.

Sources: https://man7.org/linux/man-pages/man7/inotify.7.html ; https://docs.python.org/3/library/sys.html#sys.addaudithook
