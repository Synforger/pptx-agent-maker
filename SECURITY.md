# Security Policy

## Reporting a vulnerability

Use **GitHub Security Advisories private vulnerability reporting** to
disclose security issues responsibly:

1. Open https://github.com/Synforger/pptx-agent-maker/security/advisories/new
2. Fill in the affected version + reproduction + impact estimate
3. Maintainer will acknowledge within 7 days

Do not file public Issues or PRs for security-relevant findings. Public
discussion only after a fix has shipped and end users have had time to
update.

If GitHub access is unavailable, reach `Synforger` via the
contact channel listed in the repo's README.

## Supported versions

| version | supported |
|---|---|
| main (= rolling release) | ✅ active |
| tagged releases (= v0.x) | ⚠️ best effort (= no formal LTS) |
| forks / mirrors | ❌ out of scope |

This is a personal project; there is no enterprise LTS. Security fixes
land on `main` and the next tagged release. Pin to a specific tag if
your environment requires reproducibility.

## Threat model

A local command-line toolkit and library. It reads a deck project that
lives outside this repository (`.toml` manifests, `.py` page declarations,
`.pptx` specimens) and writes `.pptx` files; the bundled preview serves the
rendered pages over a loopback HTTP server.

Threats that follow from that shape:

- a hostile project folder — a page declaration is imported and executed, and
  a manifest names paths the toolkit opens
- a hostile `.pptx` — parsed by `python-pptx` and converted by LibreOffice
- the preview's HTTP surface — it binds loopback only, but a reverse proxy can
  put it on a network, so path handling has to stay inside the served tree
- supply chain — `python-pptx`, and LibreOffice / poppler which are invoked
  rather than bundled

## In scope

- Authentication / authorization flaws (= when applicable)
- Sensitive data leakage (= secrets in logs / errors / responses)
- Path traversal / SSRF / SQLi / XSS / RCE in code paths the
  template's own scripts execute
- Dependency vulnerabilities surfaced by `task audit`

## Out of scope

- Issues in upstream dependencies that are already disclosed
  (= report those upstream; this repo will pick up the fix on next bump)
- Best-practice nudges with no concrete exploit path
- Vulnerabilities only reproducible with privileged local access
  (= `sudo` / root) — those imply the threat model has already failed
- Cosmetic / DoS-via-resource-exhaustion in dev-mode tools

## Audit log

The maintainer runs `task audit` (= `pip-audit` + `npm audit` +
`cargo audit` + `gitleaks` + `anon-scan` aggregated) at least every
6 months. Findings + resolutions are tracked here:

| date | findings | resolution |
|---|---|---|
| 2026-09-23 | none | first run of `task audit` after adopting the template core |

## Upstream redirect

When a vulnerability originates in a transitive dependency, the
disclosure goes to the upstream maintainer first. This repo only
contains the integration layer; the offending logic lives elsewhere
and should be patched there.
