import assert from "node:assert/strict";
import { modelEcologyErrors } from "../packages/sdk-js/src/index.js";
const space={model:"test",revision:"a".repeat(40),preprocessing_sha256:"b".repeat(64),dimensions:3,pooling:"mean",metric:"cosine"};
assert.deepEqual(modelEcologyErrors("embedding-space",space), []);
for (const change of [{revision:"main"},{dimensions:NaN},{dimensions:0},{metric:"euclidean"},{extra:true}]) assert.ok(modelEcologyErrors("embedding-space",{...space,...change}).length);
assert.ok(modelEcologyErrors("model-deployment",{enabled:true}).length);
assert.ok(modelEcologyErrors("analysis-evidence",{result:{confidence:Infinity}}).length);
console.log("Model ecology: pinned embedding space, strict deployment and finite evidence gates passed");
