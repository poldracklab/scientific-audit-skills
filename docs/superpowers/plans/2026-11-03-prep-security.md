# Audit prep security fixes

Approved scope: security review findings 1 (scan output links), 2 (unsafe retrieval),
and 5 (existing run destinations). Download/extraction resource limits and deliberate
run tampering are excluded.

- [x] Commit failing pytest regressions before implementation.
- [x] Reject scan input/output symlinks before reading or writing; preserve ordinary rescans.
- [x] Use one shared HTTP(S) transport with public-address checks at connection time,
  pinned resolved addresses, redirect checks, and no implicit proxies. Route Crossref
  through it too. Keep TLS verification and hostname checks.
- [x] Restrict remote Git cloning to HTTPS GitHub, pin its public address, disable
  redirects, implicit URL rewrites/proxies and recursive submodule fetching. Keep tests
  offline by substituting the transport, not by allowing production local-path fetching.
- [x] Atomically reserve each run destination, copy into it, and clean up only owned
  partial contents. Reject existing files, directories and dangling links unchanged.
- [x] Run the full suite and fresh code review; record compatibility changes in the skill.

Keep the existing CLI and dependencies. The network policy belongs in a small shared
module, rather than duplicate checks in every repository fetcher.

Validation: failing tests committed in f928d3a; focused suite 62 passed, full suite
404 passed (5 existing PyMuPDF/SWIG deprecation warnings). Fresh review found no
actionable in-scope issues. Live public HTTPS retrieval and a temporary GitHub
Hello-World clone succeeded with the restricted transports. Resource limits and
deliberate run tampering remain outside scope.

Follow-up: user additionally requested extraction of downloaded data archives.
Use the existing local extractor, preserve originals, record results and review
failures, and retain the existing policy of listing nested archives rather than
recursively expanding them. Write/commit regressions first.
