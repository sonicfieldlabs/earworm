# Earworm in the Oída gateway

Oída's `oida/gateway/v0.5` interface is a host adapter over the existing
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
- an `akouo/listening-context/v2` declaration plus listening-pass,
  listening-provenance, and route-decision references;
- explicit remember/forget actions and the effective raw-audio policy.

Each request returns a route decision before any content. A refusal at input or
capture is complete: OÍDA may persist an akousma v1.5 decision-only record with
no audio asset and no fabricated listening. Each accepted report emits an attributable `listening.report.created` event.
Plural routes may add `listening.disagreement.recorded`; action proposals and
decisions use the listening action event family. When remembered, OÍDA writes
the corresponding references into akousma v1.5's `earworm/auditum/v2` block. The block
indexes the hearing; AKOÚŌ's namespaced producer report remains the semantic
source of its six claim categories.

The model's narrative is an `analysis.frame` input. It is not `measured`
evidence unless its source is a real DSP/measurement result or metadata. This
keeps context portable across Hermes, Codex, Claude, MOSS-Audio, and future
hosts without pretending that their listening apparatuses are equivalent.
Likewise, an available host tool is a capability, not action authority: the
gateway defaults to observation or recommendation until a scoped grant is
present and records refusal as an outcome rather than a missing event.
