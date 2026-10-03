# Observation research

Linux inotify delivers per-inode access notifications without process identity. Identical queued events may coalesce; queue overflow and file invalidation must be explicit health conditions. IN_ACCESS is evidence of access, not a count of reads or a byte range. mmap and alternate execution patterns are blind spots. See https://man7.org/linux/man-pages/man7/inotify.7.html .

An explicit Python SDK is a truthful attribution layer with no claims of hostile-agent enforcement. Python audit hooks are not a sandbox (https://docs.python.org/3/library/sys.html#sys.addaudithook). Prefer explicit read/copy/tool methods with successful-operation events; tool input events distinguish invocation attempts when necessary. Keep content ephemeral and retain only registered-token match evidence.

Use readiness events and bounded waits in real-process tests. Test replacement and deletion rather than asserting only happy-path read events. Sink failures must be surfaced to caller/monitor owner rather than leaving a live-but-silent monitor.
