import {readFile, writeFile} from 'node:fs/promises';
const root = new URL('../packages/core/schemas/', import.meta.url);
const schema = JSON.parse(await readFile(new URL('akousma-1.7.schema.json',root),'utf8'));
const spectral = JSON.parse(await readFile(new URL('spectral-bundle.schema.json',root),'utf8'));
delete spectral.$id; delete spectral.$schema;
schema.$id='https://earworm.dev/schemas/akousma-1.8.schema.json';
schema.description='Opt-in spec 1.8: native evidence and spectral derivatives; explicit consumer admission required.';
schema.properties.schema_version={const:'1.8.0'};
schema.$defs.spectralBundle=spectral;
schema.properties.extensions.properties['oida.spectral']={$ref:'#/$defs/spectralBundle'};
schema.properties.extensions.properties['akouo.agent-native']={type:'object',required:['contract'],properties:{contract:{const:'akouo/agent-native-evidence/v1'}},description:'Full offline and reference validation supplied by the host. Unavailable validator means unvalidated evidence.'};
const text=JSON.stringify(schema,null,2)+'\n', path=new URL('akousma-1.8.schema.json',root);
if(process.argv.includes('--check')) {if(await readFile(path,'utf8')!==text)throw Error('Spec 1.8 schema is stale');}
else await writeFile(path,text);
