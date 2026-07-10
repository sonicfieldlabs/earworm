# Earworm in the Oída gateway

Oída's `oida/gateway/v0.2` interface is a host adapter over the existing
Earworm protocol, not a new memory protocol. It produces the same signal,
analysis, action, provenance, retention, and context-bundle structures whether
perception came from Oída's configured local engine or from an audio-capable
host model.

Host-supplied sessions should record:

- the host id, session id, provider, and model id;
- the declared acoustic apparatus and its blind spots;
- whether Oída could access the raw audio or received derived observations only;
- time anchors, confidence, basis, and source for each observation;
- AKOÚŌ routing and claim-permission results;
- explicit remember/forget actions and the effective raw-audio policy.

The model's narrative is an `analysis.frame` input. It is not `measured`
evidence unless its source is a real DSP/measurement result or metadata. This
keeps context portable across Hermes, Codex, Claude, MOSS-Audio, and future
hosts without pretending that their listening apparatuses are equivalent.
