import assert from 'node:assert/strict';
import fs from 'node:fs';
import { bundleManifestErrors } from '../packages/sdk-js/src/index.js';
const manifest = JSON.parse(fs.readFileSync(new URL('../tests/contracts/bundles/manifest.json', import.meta.url)));
assert.deepEqual(bundleManifestErrors(manifest), []);
for (const mutate of [m => m.entries.push(structuredClone(m.entries[0])), m => m.entries[0].path='../escape', m => m.entries[0].sha256='invalid', m => m.disclosure='public-projection', m => m.contract='earworm/agent-sounds/v1']) {
 const changed=structuredClone(manifest);mutate(changed);assert(bundleManifestErrors(changed).length>0);
}
assert.deepEqual(JSON.parse(JSON.stringify(manifest)),manifest);
console.log('E17 manifest and five negative JS cases passed');
