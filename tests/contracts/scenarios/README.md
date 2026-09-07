# Shared listening scenario matrix

The portable bundle is
`@earworm/core/fixtures/scenarios/matrix.json`. It is generated from existing
local examples by `node scripts/generate-listening-scenarios.mjs`; `--check`
rejects stale output during `pnpm validate`. Source records are never edited by
the generator. The bundle includes resolved source scopes and 13 negative cases.

| Scenario | Retained distinction | Legacy 1.6 schema |
| --- | --- | --- |
| agent_only | Agent, structured report, qualified access; no human hearing | accepts envelope |
| human_agent | Separate human/agent accounts and apparatus subjects; no influence | accepts envelope |
| influenced_ensemble | Explicit pass-to-listening map and matching attributed effect | accepts envelope |
| second_report | Record input, resolved source pointer and separate receiving report | rejects 1.7 / v3 |
| beyond_band | 96 kHz representation, 16 kHz effective model input, unsupported 20–30 kHz request | accepts envelope |
| generation_lineage | Generated source, subsequent account, decision and chronology | rejects 1.7 / v3 |

Acceptance of a legacy envelope is not negotiation of its opaque companions.
The new validators independently check access, context and adapters. The beyond
scenario stores an undetermined account, not a measurement of the unsupported
band; absent physical capture evidence stays unknown. Human and agent subjects
in the plural fixture have their own access declarations. The fixture records
synthetic attributed influence, not a demonstrated model-to-human effect.

`scripts/test-listening-scenarios.mjs` and
`packages/py-akousma/tests/test_listening_scenarios.py` exercise the same six
records and mutations through existing SDK validators. The Python suite also
stores each record and its source scope, reopens, reindexes and checks exact
preservation. `check.mjs` accepts an injected SDK and legacy-schema validator so
the identical suite can run against an isolated packed consumer.

AKOÚŌ provides an optional cross-package runner:

```sh
python -I /path/to/akouo/scripts/validate-earworm-scenarios.py \
  /path/to/earworm/packages/core/fixtures/scenarios/matrix.json
```

Install the local Python `akousma` and `akouo-contract` packages first. This runs
the actual access gate, second-report planner and output validator, including
rejection of borrowed receiving identities, ungrounded inherited claims,
unsupported hearing and unsupported spectral measurements. MASA observation,
graph and recipe integration have separate suites and remain distinct evidence.

No schema/package release numbers change. No DSP, model, device, physical capture,
human evaluation, external command or public delivery runs in these fixtures.
