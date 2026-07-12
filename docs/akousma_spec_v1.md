# Akousma — the sonic memory record (spec v1.2)

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

Spec v1.1 (Earworm v0.2) is additive over v1.0: records with `schema_version` `1.0.0`
remain valid. New in v1.1: top-level `summary`, typed `lineage.relations`,
`audio.media`, and provenance `capture_conditions` / `rights_note` /
`pipeline_effects`, plus a recommended envelope for `listening` entries.

Spec v1.2 (Earworm v0.3) is additive over v1.1: records with `schema_version` `1.0.0`
or `1.1.0` remain valid. New in v1.2: top-level `location` (where the sound was heard)
and `capture` (how the listening was triggered — past/future direction, window seconds),
plus the open-record rule: unknown top-level fields are tolerated and preserved, so the
record can keep growing new details without breaking older readers.

## Blocks

| Block | Meaning |
|---|---|
| `akousma_id` | Stable id for this record (`akm_` + 26-char base32, ULID-style). |
| `schema_version` | Semver of this record's shape (`1.1.0`; `1.0.0` records remain valid). |
| `created_at` | ISO-8601 UTC. |
| `session_id` | Optional link to the Earworm session this record was reconstructed from. |
| `summary` | *(v1.1)* One-line human-readable account of the sound for skimming and search. Audio has no skim affordance of its own — the summary is the record's answer to the demand of duration. |
| `audio` | The sound: `asset_id`, `uri`, `content_hash`, `duration_seconds`, `sample_rate`, `channels`, `provenance_id`, and *(v1.1)* `media` (`container`, `codec`, `bit_depth`, `codec_history[]`). Mirrors Earworm `asset-ref`. |
| `provenance` | Where it came from: `source_type` (Earworm vocabulary: generated/recorded/imported/cloned/designed/unknown), `origin` (app-level: live-input/system-output/file/generated/unknown), `originating_app` (`oida`/`germ`/`algophony`), `device`, `provider`, `model_id`, `seed`, `consent_status`, and *(v1.1)* `capture_conditions`, `rights_note`, `pipeline_effects[]` (which of the seven technological effects — capture, telephony, acousmatization, amplification, phonofixation, phonogeneration, reshaping — the sound has passed through). Mirrors Earworm `provenance-record`. |
| `listening` | What was heard, **namespaced per producer**: `oida.signal`, `akouo.<skill>`, `oida.moss`, … Open object. *(v1.1 recommended envelope per entry:)* `{contract?, created_at, summary?, payload}` — `contract` pins the producer's contract (e.g. `akouo/v0.6`) so consumers know which claim discipline shaped the payload. |
| `lineage` | How it relates: `parent_akousma_ids[]` (the causal genealogy every app must understand), `operation`, `prompt`, `model`, `params`, `event_ids[]` linking to the Earworm event log, and *(v1.1)* `relations[]` — typed curatorial links (`variant_of`, `response_to`, `same_source_as`, `recurrence_of`, `series_with`, `compares_with`, `replaces`, `other`) with `target_akousma_id` and optional `note`. |
| `tags` / `annotations` | Free labels and user notes. |
| `extensions` | **Namespaced per-app** blocks so apps extend without breaking the core: `songid`, `algophony.eval`, `germ.*`, … Open object. |
| `location` | *(v1.2)* Where the sound was heard: `lat` / `lon` (required inside the block), `accuracy_m`, `altitude_m`, `label` (human place name), `source` (gps / network / manual / config / inferred), `captured_at`. Optional and consent-scoped — producers attach it only when the listener granted it; navigators may add or correct it afterwards. The listening map reads this block. |
| `capture` | *(v1.2)* How the listening was triggered: `direction` (`past` = the seconds already in the ring buffer when the trigger fired; `future` = the seconds recorded after it; `live` = an open-ended or manual session), `seconds` (window length), `trigger` (hotkey / remote-ear / mcp / dashboard / watcher / …), `armed_at`, `triggered_at`. Device and format detail stay in `provenance` / `audio`. |

## Rules

1. **Lineage is the contract.** `parent_akousma_ids` + `event_ids` let any app reconstruct "what's
   behind a sound." oída, germ, and algophony all read and write this block identically.
2. **Listening is additive.** Producers write under their own namespace; nobody reshapes another's block.
   Prefer the v1.1 envelope (`contract`/`created_at`/`summary`/`payload`) so entries stay comparable.
3. **Extensions are namespaced; the record is open.** App-specific data goes in `extensions.<app>`,
   never in new top-level keys. *(v1.2)* Unknown top-level fields MUST be preserved — stores
   round-trip them verbatim — and MAY be ignored by consumers: a field a reader doesn't
   recognize is future vocabulary, not an error. Shared top-level vocabulary (like `summary`,
   `location`, `capture`) enters through this spec.
4. **Audio lives in the store, not the record.** `audio.uri` points into the akousmata store
   (`akousmata://objects/...`) or an absolute path; records stay small and portable.
5. **Provenance carries consent.** Exports for open research strip records whose `consent_status`
   is not `owned`/`licensed`/`public_domain`, and drop personal `listening`/`annotations`.
   `capture_conditions` and `rights_note` travel with the record: the conditions of capture follow
   the sound into every later context. *(v1.2)* `location` is dropped from open-research exports
   by default — where someone listens is as sensitive as what they heard.
6. **Parents are causal, relations are kinship.** `parent_akousma_ids` means "this sound was made
   from those"; `relations` means "this sound belongs with those" (variants, responses, recurrences,
   series). Never encode kinship as parenthood — it corrupts ancestry walks. The akousmata is not a
   pile of records but the network these two link kinds weave.
7. **Absence is information.** A dangling parent, a missing object, or an unreadable record is
   reported (store `verify()`), never silently dropped: a dead record is still lineage.

## How each app uses it

- **oída** (generative ears): writes an akousma on every listen — `provenance.origin` = live-input /
  system-output / file; `listening` from the signal listener + MOSS + AKOÚŌ skills. The three UI
  buttons ("open as sound", "open as prompt", "explore lineage") hand an `akousma_id` to germ.
  *(v1.2)* oída fills `capture` on every triggered listen (direction past/future + seconds) and
  `location` when the capturing device grants it — the remote ear sends the phone's GPS fix.
- **germ** (generative voice): on every transform/generation, writes a new akousma whose
  `lineage.parent_akousma_ids` point at the source(s), with `operation`/`prompt`/`model`/`params`.
  Its lineage explorer walks `parent_akousma_ids`.
- **algophony** (evaluation & batch): queries the akousmata, writes `extensions["algophony.eval"]`,
  and produces sanitized open-research exports.

See [`akousmata-store.md`](./akousmata-store.md) for the shared store, and the Python reference
implementation in [`../packages/py-akousma`](../packages/py-akousma).
