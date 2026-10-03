# Security

AgentCanary is an observation framework, not a sandbox or a system-wide egress control. Read [the threat model](docs/threat-model.md) and [limitations](docs/limitations.md) before relying on its evidence.

Report vulnerabilities privately to the maintainer at dev.loganelliott@gmail.com. Include the affected version, environment, expected/actual behavior and a minimal local example using synthetic data. Do not include real credentials, private request bodies or access to third-party systems. Coordinate disclosure before publishing details that could put users at risk.

The initial supported line is 0.1.x. No response-time or remediation SLA is promised. Dependency updates and security fixes are verified with the same local test, type, lint and packaging checks as other changes.
