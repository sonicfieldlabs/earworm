import { readFileSync } from 'node:fs';
import * as sdk from '../packages/sdk-js/src/index.js';
import { compileContractSchema } from '../packages/sdk-js/src/listening-contracts.js';
import { checkListeningScenarios } from '../tests/contracts/scenarios/check.mjs';
import schema from '../packages/core/schemas/akousma.schema.json' with {type:'json'};

const matrix=JSON.parse(readFileSync(new URL('../packages/core/fixtures/scenarios/matrix.json',import.meta.url),'utf8'));
const result=checkListeningScenarios(sdk,compileContractSchema(schema),matrix);
console.log(JSON.stringify(result));
