# Earworm Concept Overview

Earworm separates the audible signal chain from a persistent context chain.

The audible chain carries audio, MIDI, text, control, video, image, or other media. The context chain records what those signals mean: prompt intent, generation requests, provider metadata, alignment, analysis, user edits, agent actions, modulation decisions, provenance, and rendered outputs.

Akousmata names the memory-operations surface planned over this context chain for the Listening Stack: remember, list, search, similarity, export, and forget. Earworm remains the lower-level persistence protocol that makes those operations append-only, auditable, and project-agnostic.

```text
Signal chain:   Source -> Generator -> Processor -> Processor -> Render
Context chain:  Prompt -> Intent -> Parameters -> Analysis -> Events -> Modulation -> Provenance
```

The two chains synchronize through stable references:

- `session_id`
- `event_id`
- `asset_id`
- `segment_id`
- `node_id`
- time ranges
- sample indexes
- character and word ranges
- provenance identifiers

## Core Objects

- `EarwormSession`: top-level container for assets, events, policies, and derived views.
- `EarwormEvent`: immutable record of something that happened.
- `SignalPacket`: signal reference plus context and timing metadata.
- `AnalysisFrame`: time-indexed extracted features.
- `ModulationIntent`: semantic or analytic reason to control a parameter.
- `AutomationLane`: concrete time-indexed parameter stream.
- `ProvenanceRecord`: source, rights, provider, model, and transformation metadata.
- `AgentAction`: reversible operation proposed or applied by an agent.

## MVP Vertical Slice

The first complete proof should:

1. Create a session.
2. Ingest a prompt.
3. Record a generation request.
4. Attach a generated asset with provider metadata.
5. Ingest timing and basic analysis frames.
6. Query context for one segment.
7. Emit a modulation intent.
8. Commit a reversible automation lane.
9. Record a render.
10. Export and validate a manifest.
