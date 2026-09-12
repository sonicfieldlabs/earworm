"""Owner-selected offline MASA runtime adapters, shared by record hosts."""

import hashlib
import json
from pathlib import Path
import subprocess


def masa_validator(module):
    path = Path(module).resolve()
    if not path.is_file():
        raise ValueError("Select an installed local MASA validator module")
    cache = {}

    def validate(record):
        raw = json.dumps(record, allow_nan=False)
        if len(raw.encode()) > 2 * 1024 * 1024:
            return ["MASA record exceeds 2 MiB"]
        key = hashlib.sha256(raw.encode()).hexdigest()
        if key not in cache:
            code = "import{readFileSync}from'node:fs';const v=await import(process.argv[1]);const r=v.validateMatterRecord(JSON.parse(readFileSync(0,'utf8')));process.stdout.write(JSON.stringify({valid:r.valid===true}));"
            try:
                result = subprocess.run(
                    [
                        "node",
                        "--max-old-space-size=128",
                        "--input-type=module",
                        "-e",
                        code,
                        path.as_uri(),
                    ],
                    input=raw,
                    text=True,
                    capture_output=True,
                    timeout=15,
                    check=True,
                )
                cache[key] = (
                    []
                    if json.loads(result.stdout).get("valid") is True
                    else ["Canonical MASA validation failed"]
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                return ["Canonical MASA validator unavailable or failed"]
            if len(cache) > 128:
                cache.pop(next(iter(cache)))
        return cache[key]

    return validate


def lineage_directions(module):
    path = Path(module).resolve()
    if not path.is_file():
        raise ValueError("Select an installed local MASA core module")
    code = "const{relationRegistry:r}=await import(process.argv[1]);if(r.masaVersion!=='0.2.0')throw Error('version');process.stdout.write(JSON.stringify(Object.fromEntries(r.relations.filter(x=>x.lineageDirection).map(x=>[x.id,x.lineageDirection]))));"
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code, path.as_uri()],
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    return json.loads(result.stdout)
