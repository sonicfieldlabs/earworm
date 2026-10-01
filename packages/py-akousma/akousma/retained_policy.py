"""Conservative policy projection for retained, untyped listening prose.

Restrictions are cumulative across producer representations. Moving a covenant
to a different location never grants permission to the old text.
"""

from copy import deepcopy


def retained_covenant(record):
    candidates = [record.get("covenant"), (record.get("auditum") or {}).get("covenant"),
                  ((record.get("extensions") or {}).get("oida.native-policy") or {}).get("covenant")]
    for entry in (record.get("listening") or {}).values():
        payload = entry.get("payload") or {}
        candidates.append((payload.get("listening_context") or {}).get("covenant"))
    merged = {}
    for value in candidates:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if isinstance(item, list):
                target = merged.setdefault(key, [])
                if not isinstance(target, list):
                    target = merged[key] = []
                target.extend(deepcopy(part) for part in item if part not in target)
            elif key not in merged:
                merged[key] = deepcopy(item)
    if (record.get("provenance") or {}).get("consent_status") == "restricted":
        merged.setdefault("rules_applied", []).append("do_not_reveal:restricted_consent")
    return merged


def blocks_untyped_prose(covenant):
    if not isinstance(covenant, dict):
        return False
    return any(isinstance(item, dict) for item in covenant.get("withheld", []) or []) or any(
        str(rule).startswith(("do_not_reveal:", "ignore:", "coarsen:", "do_not_retain:memory"))
        for rule in covenant.get("rules_applied", []) or []
    )
