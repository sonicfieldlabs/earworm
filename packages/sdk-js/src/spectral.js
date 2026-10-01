import schema from '@earworm/core/schemas/spectral-bundle.schema.json' with {type:'json'};
import recordSchema from '@earworm/core/schemas/akousma-1.8.schema.json' with {type:'json'};
import {compileContractSchema, schemaErrors} from './listening-contracts.js';
import {nextRecordErrors} from './record-evolution.js';
const validate=compileContractSchema(schema), validateRecord=compileContractSchema(recordSchema);
const finite=v=>typeof v==='number'?Number.isFinite(v):v&&typeof v==='object'?Object.values(v).every(finite):true;

export function spectralBundleErrors(bundle,{resolveObject}={}) {
  if(!finite(bundle))return ['Nonfinite spectral value'];
  const errors=schemaErrors(validate,bundle); if(errors.length)return errors;
  if(bundle.source_interval_samples[0]>=bundle.source_interval_samples[1])errors.push('Invalid source interval');
  if(new Set(bundle.views.map(v=>v.view_id)).size!==bundle.views.length)errors.push('Duplicate view identity');
  for(const v of bundle.views){
    const s=v.settings;
    if(!(0<=s.f_min&&s.f_min<s.f_max&&s.f_max<=bundle.effective_rate_hz/2))errors.push('Invalid frequency bounds');
    if(v.kind.startsWith('projection_')&&(v.for!=='human'||!v.losses.length))errors.push('Projection must declare human target and losses');
    if(v.state!=='retained')continue;
    if(v.sha256!==v.object_ref.split('/').at(-1).split('.')[0])errors.push('Object hash mismatch');
    if(v.shape.reduce((a,b)=>a*b,1)*({float32:4,float64:8,complex64:8,complex128:16,uint8:1}[v.dtype])!==v.expanded_bytes)errors.push('Shape/dtype/expanded-byte mismatch');
    if(v.shape.length!==v.axis_order.length||v.shape.length!==v.axis_units.length)errors.push('Axis dimensions mismatch');
    if(resolveObject){const actual=resolveObject(v.object_ref);if(!actual||['sha256','dtype','shape','byte_count','expanded_bytes'].some(k=>JSON.stringify(actual[k])!==JSON.stringify(v[k])))errors.push('Object metadata unavailable or mismatched');}
  }
  return errors;
}

export function record18Errors(record,{validateNative,resolveObject}={}) {
  if(!finite(record))return ['Nonfinite record value'];
  const errors=schemaErrors(validateRecord,record);if(errors.length)return errors;
  const base=structuredClone(record);base.schema_version='1.7.0';errors.push(...nextRecordErrors(base));
  const ext=record.extensions??{};
  if(ext['oida.spectral'])errors.push(...spectralBundleErrors(ext['oida.spectral'],{resolveObject}));
  if(ext['akouo.agent-native']){
    if(typeof validateNative!=='function')errors.push('Native evidence unvalidated: host validator unavailable');
    else {const result=validateNative(ext['akouo.agent-native']);if(!Array.isArray(result)||result.some(e=>typeof e!=='string'))throw TypeError('Host validator must return error strings');errors.push(...result);}
  }
  return errors;
}

export function admitRecord18(record,{supportedVersions,validateNative,resolveObject,resolveRepresentation}={}) {
  if(record.schema_version!=='1.8.0'||!supportedVersions?.includes('1.8.0'))throw Error('Consumer has not admitted 1.8; no downgrade');
  const errors=record18Errors(record,{validateNative,resolveObject});
  if(record.extensions?.['oida.spectral']&&!resolveObject)errors.push('Retained object host validation unavailable');
  const bundle=record.extensions?.['oida.spectral'];
  if(bundle){const actual=resolveRepresentation?.(bundle.sampled_representation);if(!actual||['subject_ref','excerpt_sha256','record_ref','source_interval_samples','effective_rate_hz','channel_layout'].some(k=>JSON.stringify(actual[k])!==JSON.stringify(bundle[k])))errors.push('Sampled representation identity/scope unvalidated');if(bundle.record_ref!==record.akousma_id)errors.push('Bundle belongs to another record');}
  if(errors.length)throw Error(errors.join('; '));return structuredClone(record);
}
