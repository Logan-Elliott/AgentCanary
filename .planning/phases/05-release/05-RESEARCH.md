# Release verification research

Packaging uses Hatchling and standardized project metadata. Use an SPDX `license` expression and `license-files`; include docs/examples/tests in the source archive and verify the archive itself. The wheel must include `py.typed` and the CLI/module entry points. Runtime dependencies remain empty.

Clean installation tests must run from a temporary working directory with Python path overrides removed. A successful import from the checkout does not demonstrate installation. Install both distribution formats in separate virtual environments and execute the public CLI/demo against temporary synthetic fixtures.

CI configuration can pin official action commits and a uv version, run a Python matrix with at most two concurrent jobs, and reuse the same local verification commands. Only the local equivalent is executed in this milestone.

Primary references checked during release preparation:
- https://hatch.pypa.io/latest/config/metadata/
- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/actions/setup-python/releases/tag/v7.0.0

Actual source and tests remain the authority for product behavior. Public prose must not imply transparent TLS decryption, authenticated client attribution, tamper resistance or successful exfiltration.
