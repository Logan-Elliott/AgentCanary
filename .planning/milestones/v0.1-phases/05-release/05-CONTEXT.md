# Phase 5: Release hardening — Context

Routine decisions and local completion are delegated. Publishing, pushing, deployment and remote PRs remain outside authorization.

- Release 0.1.0 as a Linux/Python >=3.11 package with no runtime dependencies. Verify the minimum Python version and another current interpreter, plus the development interpreter. Use temporary isolated environments inside the VM.
- Include license metadata, typing marker, complete source distribution contents, reproducible development dependencies, concise release notes, practical README/docs/examples and CI definitions. CI is authored locally; do not claim a hosted run occurred.
- Clean wheel and source-distribution installations must work outside the checkout, without PYTHONPATH or editable dependencies. Run the installed CLI and the complete demo, and inspect artifact contents/metadata for missing files or accidental local artifacts.
- Final review explicitly covers architectural weaknesses, false positives/negatives, attribution, races, synthetic-secret handling, network blind spots, portability, missing tests and usability. Review findings require correction and relevant regression checks; documented capability boundaries must remain honest.
- Close all 15 requirements through measured verification. Preserve final GSD audit, review and phase evidence, then archive the milestone locally. Do not start another milestone or perform remote ship actions.

Phase 1–3 independent reviews are available. Phase 3 corrections preserve origin identity for policy and reject duplicate JSON names. Phase 4 supplies the installed demo. Documentation preparation can proceed while Phase 4 finishes, but release acceptance and archival require its successful verification.
