# Changelog

All notable changes to `okf-cli` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-28

### Added

- Provenance-aware concept creation with `--resource` and `--sources-file`.
- Safe `concept update` support for metadata, body, resource, and source changes.
- YAML and JSON source-file parsing with validation for IDs, usage metadata,
  dates, usage windows, and extension fields.
- Validation of concept `resource` and `sources` metadata, including warnings
  for missing relative source paths.
- Bounded, streaming Pi conversation ZIP extraction through
  `scripts/extract_pi_archive.py` for privacy-conscious knowledge synthesis.
- Regression and end-to-end coverage for provenance creation, non-destructive
  updates, source validation, archive bounds, no-op behavior, and CLI contracts.
- Design and implementation plans for the Hermes Fitness OKF population.

### Changed

- Existing concepts can now be patched without replacing unspecified
  frontmatter fields, provenance, or body content.
- Meaningful updates atomically write the concept, rebuild indexes, and append
  one `Update` log entry; no-op updates write nothing and create no log entry.
- The package version and default `generated.by` actor now derive from the same
  version source.
- Agent guidance now requires explicit paths, JSON dry-runs before mutation,
  provenance-backed synthesis, safe updates, and post-change validation.

### Fixed

- Bumped the provenance-capable release to `0.2.0`, allowing global uv installs
  to be distinguished from the older `0.1.0` executable that lacked
  `concept update` and provenance options.

### Security

- Archive records are read with a configurable maximum size instead of being
  loaded without bounds.
- The documented archive workflow excludes raw transcripts, credentials,
  personal health records, and user-specific meal or workout data from curated
  concepts.

## [0.1.0] - 2026-07-28

### Added

- Initial portable, noninteractive OKF v0.2 CLI.
- Catalog and bundle initialization and registration.
- Concept creation, deterministic index rebuilding, log appends, validation,
  JSON output envelopes, dry-runs, configuration discovery, and stable exit
  codes.
