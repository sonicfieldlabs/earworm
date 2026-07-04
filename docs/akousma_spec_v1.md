# Akousma — the sonic memory record (spec v1)

> **akousma** (ἄκουσμα, "a thing heard"; plural **akousmata**) — one sound's memory:
> its audio, where it came from, what was heard in it, and how it relates to other sounds.
> The **akousmata** is the shared, cross-app store of all akousma records.

The akousma is the shared unit of sonic memory across the Sonic Field ecosystem —
**oída** (generative ears), **germ** (generative voice), and **algophony** (evaluation &
batch). It is an *envelope* that composes the granular Earworm protocol pieces
(`asset-ref`, `provenance-record`, `analysis-frame`, `earworm-event`, `earworm-session`)
into one queryable record "about a sound."

Canonical schema: [`packages/core/schemas/akousma.schema.json`](../packages/core/schemas/akousma.schema.json)
(`$id: https://earworm.dev/schemas/akousma.schema.json`, JSON Schema draft-07).

## Blocks

| Block | Meaning |
|---|---|
| `akousma_id` | Stable id for this record (`akm_` + 26-char base32, ULID-style). |
| `schema_version` | Semver of this record's shape (`1.0.0`). |
| `created_at` | ISO-8601 UTC. |
| `session_id` | Optional link to the Earworm session this record was reconstructed from. |
| `audio` | The sound: `asset_id`, `uri`, `content_hash`, `duration_seconds`, `sample_rate`, `channels`, `provenance_id`. Mirrors Earworm `asset-ref`. |
| `provenance` | Where it came from: `source_type` (Earworm vocabulary: generated/recorded/imported/cloned/designed/unknown), `origin` (app-level: live-input/system-output/file/generated), `originating_app` (`oida`/`germ`/`algophony`), `device`, `provider`, `model_id`, `seed`, `consent_status`. Mirrors Earworm `provenance-record`. |
| `listening` | What was heard, **namespaced per producer**: `oida.signal`, `akouo.<skill>`, `oida.moss`, … Each value is that producer's result (caption, class, features). Open object. |
| `lineage` | How it relates: `parent_akousma_ids[]` (the genealogy every app must understand), `operation`, `prompt`, `model`, `params`, and `event_ids[]` linking to the Earworm event log. |
| `tags` / `annotations` | Free labels and user notes. |
| `extensions` | **Namespaced per-app** blocks so apps extend without breaking the core: `songid`, `algophony.eval`, `germ.*`, … Open object. |

## Rules

1. **Lineage is the contract.** `parent_akousma_ids` + `event_ids` let any app reconstruct "what's
   behind a sound." oída, germ, and algophony all read and write this block identically.
2. **Listening is additive.** Producers write under their own namespace; nobody reshapes another's block.
3. **Extensions are namespaced.** Never add top-level keys for app-specific data — use `extensions.<app>`.
4. **Audio lives in the store, not the record.** `audio.uri` points into the akousmata store
   (`akousmata://objects/...`) or an absolute path; records stay small and portable.
5. **Provenance carries consent.** Exports for open research strip records whose `consent_status`
   is not `owned`/`licensed`/`public_domain`, and drop personal `listening`/`annotations`.

## How each app uses it

- **oída** (generative ears): writes an akousma on every listen — `provenance.origin` = live-input /
  system-output / file; `listening` from the signal listener + MOSS + AKOÚŌ skills. The three UI
  buttons ("open as sound", "open as prompt", "explore lineage") hand an `akousma_id` to germ.
- **germ** (generative voice): on every transform/generation, writes a new akousma whose
  `lineage.parent_akousma_ids` point at the source(s), with `operation`/`prompt`/`model`/`params`.
  Its lineage explorer walks `parent_akousma_ids`.
- **algophony** (evaluation & batch): queries the akousmata, writes `extensions["algophony.eval"]`,
  and produces sanitized open-research exports.

See [`akousmata-store.md`](./akousmata-store.md) for the shared store, and the Python reference
implementation in [`../packages/py-akousma`](../packages/py-akousma).
