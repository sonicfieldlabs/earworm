# Earworm

Earworm is a project-agnostic framework for persistent listening in agentic signal chains.

It pairs signal processing with a parallel context chain: prompts, generation metadata, timing, analysis, user edits, agent actions, modulation, provenance, and render history. The goal is to let downstream agents and processors query what a signal is, how it was produced, what the user intended, and which actions changed it over time.

Status: `0.1.0` planning and protocol implementation.

Canonical repository: `https://github.com/sonicfieldlabs/earworm`.

## License and Trademarks

Earworm code is licensed under the Mozilla Public License 2.0 (`MPL-2.0`). You can use, modify, fork, and integrate it into other open-source or commercial projects. If you distribute modified Earworm source files, those modified files must remain available under `MPL-2.0`.

The `Earworm` and `PhonoStack` names, logos, and related branding are handled separately. See [TRADEMARKS.md](TRADEMARKS.md). In short: you can build with Earworm, but you cannot present a fork or product as the official Earworm project without permission.

## Current Scope

The repository is being built phase by phase from the system master document:

- M-1: repository bootstrap.
- M0: schema lock.
- M1: event store and state reconstruction.
- M2: timing, assets, and analysis ingestion.
- M3: query API and context bundles.
- M4: modulation intent and automation output.
- M5: manifest export and audit.
- M6: open-source package readiness.

## Quick Start

Requirements: Node.js `>=22` and pnpm `>=10`.

```sh
pnpm install
pnpm validate
pnpm test
pnpm check
pnpm examples:smoke
```

The current validation path uses local scripts and JSON fixtures so the protocol can be tested before adding external dependencies.

## Repository Layout

```text
packages/core/        Canonical schemas, fixtures, and event-store primitives.
packages/sdk-js/      Thin JavaScript client wrapper over the core store.
packages/sdk-python/  Read-only Python fixture/session reader for integrations.
docs/                 Concepts, ADRs, governance, and API notes.
examples/             Runnable integration examples.
tests/                Cross-package conformance fixtures and tests.
scripts/              Repository validation and test entry points.
```

## Akousmata Surface

In the Listening Stack, Akousmata names the memory-operations surface over Earworm chains: remember, list, search, similarity, export, and forget. Earworm `0.1.0` provides the persistence protocol underneath that surface: append-only events, queryable context bundles, manifest export, retention/redaction policy, and reversible automation records.

The M3.5 roadmap target is to expose Akousmata as stable helper APIs over the existing event/query primitives while keeping Earworm project-agnostic.

## Contributing

Pull requests are welcome. By contributing, you agree that your contributions are licensed under `MPL-2.0`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Core Thesis

Earworm turns a signal chain into an agentic signal chain by giving every stage access to persistent, time-indexed, queryable memory of intent, provenance, analysis, and previous actions.
