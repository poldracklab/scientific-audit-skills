# Audit prep security fixes

Approved scope: security review findings 1 (scan output links), 2 (unsafe retrieval),
and 5 (existing run destinations). Download/extraction resource limits and deliberate
run tampering are excluded.

- [ ] Commit failing pytest regressions before implementation.
- [ ] Reject scan input/output symlinks before reading or writing; preserve ordinary rescans.
- [ ] Use one shared HTTP(S) transport with public-address checks at connection time,
  pinned resolved addresses, redirect checks, and no implicit proxies. Route Crossref
  through it too. Keep TLS verification and hostname checks.
- [ ] Restrict remote Git cloning to HTTPS GitHub, pin its public address, disable
  redirects, implicit URL rewrites/proxies and recursive submodule fetching. Keep tests
  offline by substituting the transport, not by allowing production local-path fetching.
- [ ] Atomically reserve each run destination, copy into it, and clean up only owned
  partial contents. Reject existing files, directories and dangling links unchanged.
- [ ] Run the full suite and fresh code review; record compatibility changes in the skill.

Keep the existing CLI and dependencies. The network policy belongs in a small shared
module, rather than duplicate checks in every repository fetcher.
