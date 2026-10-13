"""Current owner-declared material uses in the canonical shared store.

These declarations are operational permissions, not verification of a license
or another party's acceptance. Derived representations inherit every input's
current restrictions. No grant is created by parsing a source or model output.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json

from . import new_id

MATERIAL_ACTIONS = frozenset(
    {
        "read",
        "read_metadata",
        "execute",
        "retain",
        "retain_metadata",
        "disclose_local",
        "disclose_external",
        "export",
        "export_public",
        "forget",
    }
)


class MaterialTerms:
    def __init__(self, store, *, actor_ref, clock=None):
        self.store, self.conn, self.actor_ref = store, store.conn, actor_ref
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.conn.execute("""CREATE TABLE IF NOT EXISTS representation_terms (
            terms_ref TEXT PRIMARY KEY, declaration TEXT NOT NULL, active INTEGER NOT NULL
        )""")
        self.conn.commit()

    def set(
        self,
        terms_ref,
        *,
        actions,
        basis,
        expected_revision=None,
        active=True,
        expires_at=None,
    ):
        if (
            not isinstance(terms_ref, str)
            or not terms_ref
            or not isinstance(actions, list)
            or any(not isinstance(a, str) for a in actions)
            or not set(actions) <= MATERIAL_ACTIONS
            or not isinstance(basis, str)
            or not basis
            or type(active) is not bool
        ):
            raise ValueError(
                "Explicit terms, supported actions and owner basis are required"
            )
        if self.conn.in_transaction:
            raise ValueError("Terms mutation needs a clean transaction boundary")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            old = self.get(terms_ref)
            if (old["revision"] if old else None) != expected_revision:
                raise ValueError("Terms declaration changed")
            value = dict(
                contract="earworm/material-terms/v1",
                terms_ref=terms_ref,
                revision=new_id("terms"),
                actions=list(dict.fromkeys(actions)),
                actor_ref=self.actor_ref,
                basis=basis,
                at=self.clock(),
                active=active,
                attestation="owner_declared",
            )
            if expires_at is not None:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                issued = datetime.fromisoformat(value["at"].replace("Z", "+00:00"))
                if (
                    expiry.tzinfo is None
                    or expiry.utcoffset().total_seconds() != 0
                    or expiry <= issued
                ):
                    raise ValueError(
                        "Terms expiry must be a future explicit UTC boundary"
                    )
                value["expires_at"] = expires_at
            self.conn.execute(
                "INSERT OR REPLACE INTO representation_terms VALUES(?,?,?)",
                (terms_ref, json.dumps(value), int(active)),
            )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return value

    def get(self, terms_ref):
        row = self.conn.execute(
            "SELECT declaration FROM representation_terms WHERE terms_ref=?",
            (terms_ref,),
        ).fetchone()
        return json.loads(row["declaration"]) if row else None

    def revoke(self, terms_ref, *, expected_revision):
        old = self.get(terms_ref)
        if old is None:
            raise KeyError(terms_ref)
        return self.set(
            terms_ref,
            actions=old["actions"],
            basis="Owner revoked prior material uses",
            expected_revision=expected_revision,
            active=False,
        )

    def allows(self, action, terms_ref):
        """Check a current declaration, including its explicit expiry."""
        grant = self.get(terms_ref)
        if (
            action not in MATERIAL_ACTIONS
            or grant is None
            or not grant["active"]
            or action not in grant["actions"]
        ):
            return False
        if grant.get("expires_at"):
            return datetime.fromisoformat(
                self.clock().replace("Z", "+00:00")
            ) < datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))
        return True

    def permit(self, action, rep, *, resolve_representation=None):
        def visit(value, seen):
            key = value["representation_id"]
            if key in seen:
                return False
            terms = value.get("terms", {})
            if terms.get("status") != "declared":
                return False
            if not self.allows(action, terms["ref"]):
                return False
            if value["origin"]["kind"] in {"generated", "transformed"}:
                for parent in value["origin"]["source_refs"]:
                    try:
                        original = (
                            resolve_representation(parent)
                            if callable(resolve_representation)
                            else None
                        )
                    except (KeyError, ValueError):
                        return False
                    if original is None or not visit(original, seen | {key}):
                        return False
            return True

        try:
            return action in MATERIAL_ACTIONS and visit(deepcopy(rep), set())
        except (KeyError, TypeError):
            return False
