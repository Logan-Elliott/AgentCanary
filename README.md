# AgentCanary

AgentCanary plants synthetic sensitive-looking artifacts in AI-agent workspaces and records when their issued markers are observed in reads, copies, tool inputs, model requests, or attempted HTTP transmission. It runs locally and requires no external collector or real credentials.

Inspired by Thinkst Canary's use of canaries for detection, adapted to agent workspaces and explicit tool/model integrations.

```text
CREATE → READ → COPY / TOOL_USE / MODEL_REQUEST → EXFILTRATION
```

Each event carries a canary ID, timestamp, observation source, provenance, and process/run/destination information where available. `EXFILTRATION` means an observed attempt, not confirmed delivery. See [coverage and limitations](docs/limitations.md).

## Install

Supported baseline: Linux, Python 3.11 or newer, and a mounted `/proc` filesystem. No root access, auditd, eBPF, containers, or runtime Python dependencies are required.

From this repository checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
agentcanary --help
```

For development, use `uv sync --locked` and run commands with `uv run`. The committed lockfile pins development dependencies; isolated builds use the Hatchling version range declared in `pyproject.toml`. Package publication is not required for installation.

## Seed and monitor a workspace

```bash
agentcanary seed ./workspace --profile realistic
agentcanary monitor ./workspace
```

After the monitor prints its JSON readiness line, read an artifact in another terminal from the same working directory:

```bash
cat ./workspace/.aws/credentials > /dev/null
agentcanary report
agentcanary report --format jsonl
```

Stop monitoring with Ctrl-C. The default state directory is `./.agentcanary`. To select another private directory, put `--state-dir PATH` before the command. Existing files are never overwritten by seeding.

Readiness means initialization completed; check `watch_count` and `MONITOR_HEALTH` records for coverage. Linux file notifications do not identify the reader's PID. SDK observations provide explicit caller attribution.

## Create individual artifacts

```bash
agentcanary create aws-key
agentcanary create kubeconfig --root ./sandbox --output .kube/config
agentcanary types
```

Built-in types: `aws-key`, `openai-key`, `anthropic-key`, `kubeconfig`, `ssh-key`, `env`, `database`, and `payroll`. Profiles are `minimal` and `realistic`. Individual creation chooses a unique default filename unless `--output` is provided.

All built-in credentials are labeled synthetic and use nonfunctional values. SSH artifacts are not real keys; service destinations use `.invalid` names. Artifact formats resemble common configuration files, while credential values remain visibly invalid.

Custom templates are inert text:

```bash
agentcanary create custom --template examples/custom-template.txt --output custom-note.txt
```

Templates support `$token`, `$canary_id`, `$label`, and `$$` for a literal dollar sign. The issued token must appear in the output; synthetic labeling is mandatory. Never put real secrets in custom templates.

## Attribute SDK observations

```python
from agentcanary import Observer, Store

observer = Observer(Store(".agentcanary"), run_id="agent-evaluation")
payload = observer.read("workspace/.aws/credentials")
observer.observe_tool(payload, tool="summarizer")
observer.observe_model(payload, destination="https://mock-model.invalid/v1/responses")
```

These methods inspect input and record marker sightings. They do not send a model request. `Observer.copy()` records successful exclusive copies; `Observer.run_tool()` observes input and invokes an argument array with `shell=False`. Caller PID and tool-input provenance do not prove that a child consumed the input. See [the SDK example](examples/observe_workspace.py) and [architecture](docs/architecture.md).

## Inspect HTTP attempts locally

```bash
agentcanary proxy --port 8080
```

The endpoint binds to loopback and always blocks; it never forwards traffic or resolves a supplied upstream hostname. Configure an HTTP client to use it as an explicit proxy, or send a mock API request directly to its address. Recognized model routes generate `MODEL_REQUEST` evidence as well as marker-bearing transmission attempts.

HTTP client PID is unknown. HTTPS `CONNECT` tunnels cannot expose encrypted payloads and are rejected. Use the SDK before TLS for cooperating HTTPS/model integrations. Requests that bypass these integrations are outside coverage.

Matching supports issued markers in plaintext and bounded URL, JSON-escape, and common base64 representations; HTTP gzip decoding is bounded. Limits and unsupported framing produce diagnostics. Arbitrary encryption, hashing, splitting and transformation are not covered.

## Policy and reports

```bash
agentcanary --config examples/policy.toml proxy --port 8080
agentcanary report --format json
agentcanary report --action MODEL_REQUEST --run-id agent-evaluation
agentcanary report --hide-policy
```

Policy annotations retain the audit record. Exact-origin allowlists and ignore rules do not permit forwarding or remove creation/health evidence. `--hide-policy` hides ignored/allowlisted observations in the report only. Configuration is explicit and rejects unknown settings.

JSON reports contain `events` and `count`; JSONL is one event per line. Events are ordered by durable ingestion sequence, not assumed cross-process causality. Default reports omit artifact contents and redact synthetic token values.

## Local end-to-end demonstration

```bash
agentcanary demo --directory ./demo-run
agentcanary --state-dir ./demo-run/state report --format jsonl
# Or choose a new unique output directory automatically:
agentcanary demo --json
```

The demo seeds one synthetic canary, starts a passive Linux monitor and the blocking HTTP endpoint, then runs a real Python child using the installed package. The child reads and copies the artifact, passes its bytes to a local subprocess tool, observes mock model input, and makes two HTTP requests that must return 403. All connections stay on loopback; `.invalid` destinations are request labels only.

The directory must be new and its parent must exist; existing directories and symlinks are refused. Each run retains `workspace/`, private `state/`, token-free `events.jsonl`, `report.txt` and `summary.json`. `--state-dir` does not change the demo's isolated state location; `--config` is rejected. `--timeout` bounds child execution and evidence collection (default 15 seconds), with separate bounded worker shutdown. Failure returns nonzero and retains available evidence without claiming completion.

All six lifecycle actions must be present. SDK events identify the child caller PID; passive and HTTP events keep unknown actor PIDs. Tool input and mock model input do not imply semantic use or provider delivery. The controlled tool receipt confirms receipt of the fixture bytes separately. Run correlation does not establish causality between independently scheduled sensors.

## Development and verification

```bash
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
uv run python scripts/verify_install.py
```

Tests exercise real Linux notifications, subprocesses, concurrent writers, loopback requests, malformed/oversized inputs, policy behavior, and failure cleanup. No provider API key is needed. The installation verifier checks wheel/source contents and installs each into a separate temporary environment, then runs the CLI and complete demo outside the checkout. Source installation may download build dependencies; application checks require no external service.

## Documentation

- [Architecture and extension interfaces](docs/architecture.md)
- [SDK, HTTP and policy integration](docs/integrations.md)
- [Threat model](docs/threat-model.md)
- [Monitoring limitations](docs/limitations.md)
- [Contributing](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Release notes](CHANGELOG.md)

Licensed under [MIT](LICENSE).
