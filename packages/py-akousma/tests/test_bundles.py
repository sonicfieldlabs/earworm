import json
from copy import deepcopy
from pathlib import Path
from akousma.bundles import bundle_manifest_errors


def test_manifest_and_negative_cases():
    manifest=json.loads((Path(__file__).resolve().parents[3]/"tests/contracts/bundles/manifest.json").read_text())
    assert bundle_manifest_errors(manifest)==[]
    assert json.loads(json.dumps(manifest))==manifest
    for key,value in [("sha256","bad"),("path","../escape")]:
        changed=deepcopy(manifest);changed["entries"][0][key]=value
        assert bundle_manifest_errors(changed)
    for key,value in [("disclosure","public-projection"),("contract","earworm/agent-sounds/v1")]:
        changed=deepcopy(manifest);changed[key]=value
        assert bundle_manifest_errors(changed)
    changed=deepcopy(manifest);changed["entries"].append(deepcopy(changed["entries"][0]))
    assert bundle_manifest_errors(changed)
