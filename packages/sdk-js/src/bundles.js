/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import schema from '@earworm/core/schemas/bundle-manifest.schema.json' with { type: 'json' };
import { compileContractSchema, schemaErrors } from './listening-contracts.js';
const validate = compileContractSchema(schema);
const finite = v => typeof v === "number" ? Number.isFinite(v) : v && typeof v === "object" ? Object.values(v).every(finite) : true;
export function bundleManifestErrors(manifest) {
  if (!finite(manifest)) return ["Manifest must be finite JSON"];
  const errors = schemaErrors(validate, manifest);
  if (errors.length) return errors;
  const entries = manifest.entries;
  if (new Set(entries.map(e => e.path)).size !== entries.length || new Set(entries.map(e => e.id)).size !== entries.length) errors.push('Bundle paths and IDs must be unique');
  if (manifest.disclosure === 'public-projection' && entries.some(e => e.kind !== 'metadata-projection')) errors.push('Public bundles contain only metadata projections');
  if (manifest.contract === 'earworm/agent-sounds/v1' && !entries.some(e => e.kind === 'audio' && e.recipient_requirements.length)) errors.push('Agent sounds require audio and declared recipient capabilities');
  return errors;
}
