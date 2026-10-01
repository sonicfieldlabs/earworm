import copy
import json
from pathlib import Path
import pytest
from akousma import validation_errors
from akousma.spectral import admit_record, spectral_bundle_errors

ROOT=Path(__file__).resolve().parents[3]

def record():
    v=json.loads((ROOT/'tests/contracts/evolution/research.json').read_text())
    return v

def test_version_admission_is_lossless_and_fail_closed():
    v=record();assert validation_errors(v)==[]
    v['extensions']['unknown.example']={'retain':[1,2,3]}
    assert admit_record(v,supported_versions=['1.7.0'])==v
    v['schema_version']='1.8.0'
    assert validation_errors(v)==[]
    before=copy.deepcopy(v)
    with pytest.raises(ValueError):admit_record(v,supported_versions=['1.7.0'])
    assert before==v
    assert admit_record(v,supported_versions=['1.8.0'])==v
    v['schema_version']='99.0.0';assert validation_errors(v)

def test_native_validator_is_mandatory():
    v=record();v['schema_version']='1.8.0';v['extensions']['akouo.agent-native']={'contract':'akouo/agent-native-evidence/v1'}
    assert validation_errors(v)
    assert validation_errors(v,validate_native=lambda x:['unresolved host evidence'])
    assert validation_errors(v,validate_native=lambda x:[])==[]

def test_store_requires_version_and_representation_admission(tmp_path):
    from akousma import AkousmataStore
    v=record();v['schema_version']='1.8.0'
    store=AkousmataStore(tmp_path)
    with pytest.raises(ValueError):store.put(v)
    bundle=json.loads((ROOT/'tests/contracts/spectral/bundle.json').read_text())
    bundle['record_ref']=v['akousma_id'];v['extensions']['oida.spectral']=bundle
    with pytest.raises(ValueError):store.put(v,supported_versions=['1.8.0'],resolve_object=lambda r:bundle['views'][0])
    store.put(v,supported_versions=['1.8.0'],resolve_object=lambda r:bundle['views'][0],resolve_representation=lambda r:bundle)
    assert store.get(v['akousma_id'])==v

def test_spectral_retention_hash_and_axes():
    v=json.loads((ROOT/'tests/contracts/spectral/bundle.json').read_text())
    assert spectral_bundle_errors(v)==[]
    for key,value in [('sha256','b'*64),('expanded_bytes',99),('axis_order',[]),('for','human')]:
        bad=copy.deepcopy(v);bad['views'][0][key]=value
        if key=='for':bad['views'][0]['kind']='projection_png'
        assert spectral_bundle_errors(bad)
    bad=copy.deepcopy(v);bad['views'][0]['state']='ephemeral';bad['views'][0]['reason']='not retained'
    assert spectral_bundle_errors(bad)
    del bad['views'][0]['object_ref'];del bad['views'][0]['sha256'];assert spectral_bundle_errors(bad)==[]
    assert spectral_bundle_errors(v,resolve_object=lambda r:None)

def test_version_and_extension_scenario_matrix():
    scenarios=json.loads((ROOT/'tests/contracts/spectral/scenarios.json').read_text())
    for scenario in scenarios:
        v=record();v['schema_version']=scenario['schema_version']
        if scenario['extension']=='agent_native':
            v['extensions']['akouo.agent-native']={'contract':'akouo/agent-native-evidence/v1'}
        if scenario['extension']=='spectral':
            bundle=json.loads((ROOT/'tests/contracts/spectral/bundle.json').read_text())
            bundle['record_ref']=v['akousma_id'];v['extensions']['oida.spectral']=bundle
        before=copy.deepcopy(v)
        if scenario['expected']=='accepted':
            assert admit_record(v,supported_versions=scenario['supported_versions'])==v
        elif scenario['expected']=='refused':
            with pytest.raises(ValueError):admit_record(v,supported_versions=scenario['supported_versions'])
        elif scenario['expected']=='host_validation_required':
            with pytest.raises(ValueError):admit_record(v,supported_versions=scenario['supported_versions'])
            assert admit_record(v,supported_versions=scenario['supported_versions'],validate_native=lambda value:[])==v
        elif scenario['expected']=='host_resolution_required':
            with pytest.raises(ValueError):admit_record(v,supported_versions=scenario['supported_versions'])
            bundle=v['extensions']['oida.spectral']
            assert admit_record(v,supported_versions=scenario['supported_versions'],
                resolve_object=lambda ref:bundle['views'][0],resolve_representation=lambda ref:bundle)==v
        else:
            pytest.fail(f"Unknown scenario expectation: {scenario['expected']}")
        assert v==before, scenario['name']
