# Provenance and Policy

Earworm treats governance as part of the core protocol.

Every generated or imported asset should be able to answer:

- What is the source type?
- Which provider, model, voice, seed, request hash, and asset hash produced it?
- What is the consent status?
- What usage constraints apply?
- Which events transformed it?
- Which agent or system actor proposed or applied changes?
- Can automated actions be reversed?

## Retention

`RetentionPolicy` currently captures:

- retention mode
- optional expiration
- local-only behavior
- sensitive fields
- fields omitted from `agent_safe` context bundles

When `mode` is `expires_at`, context query and manifest export reject expired sessions. Applications remain responsible for physically deleting expired local files, but the core protocol will not hand expired memory to agents or manifests.

`redaction.sensitive_fields` is enforced for all context bundles. `redaction.agent_safe_omissions` is additionally enforced when a selector requests `summarization: "agent_safe"`.

## Export Gates

Manifest export can require complete provenance for selected assets. This gives applications a protocol-level place to block exports when source or rights metadata is incomplete.
