# Contributing

Earworm welcomes issues, discussions, forks, and pull requests.

By submitting a contribution, you agree that your contribution is provided under the Mozilla Public License 2.0 (`MPL-2.0`), the same license as the project code.

## Development

```sh
pnpm install
pnpm check
```

Before opening a pull request:

- Add or update fixtures when protocol behavior changes.
- Add tests for event-store, selector, manifest, or SDK behavior.
- Run `pnpm check`.
- Keep schema changes and fixture changes together.
- Do not include secrets, provider API keys, private voice data, or proprietary PhonoStack/AUM implementation code.

## Pull Request Expectations

Good PRs should state:

- What changed.
- Which protocol objects or APIs are affected.
- Whether schemas or fixtures changed.
- Which checks were run.

## Certificate of Origin

By contributing, you certify that you have the right to submit the work and license it under `MPL-2.0`.
