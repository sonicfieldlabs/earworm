# ADR 0001: JSON Schema Is the Canonical Protocol Contract

Status: accepted

Date: May 25, 2026

## Context

Earworm needs to work across applications, SDKs, provider adapters, batch tools, and future real-time systems. TypeScript is the first implementation target, but the protocol cannot depend on TypeScript-specific types.

## Decision

JSON Schema is the canonical contract for Earworm protocol objects.

TypeScript, Python, and other SDK types should be generated from, checked against, or manually kept conformant with the JSON Schemas.

## Consequences

- Fixtures become executable protocol examples.
- Conformance tests can run outside one SDK.
- Application integrations can validate manifests without importing the full SDK.
- The repository needs schema review discipline before breaking changes.
- Type helpers are implementation conveniences, not the source of truth.
