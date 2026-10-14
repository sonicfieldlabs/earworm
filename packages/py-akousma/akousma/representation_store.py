"""Opt-in representation custody in the canonical shared SQLite store.

The owner supplies current material permissions and binding verification.
Exact bytes and immutable metadata are committed with the record in one
transaction. Default legacy put() retains its explicit 1.9 refusal.
"""

from copy import deepcopy
from hashlib import sha256
import json
import secrets
import time

from .representations import (
    REPRESENTATION_CONTRACTS,
    admit_representation_record,
    record_19_errors,
)

MAX_ARTIFACT_BYTES = 1_048_576
QUERY_SCAN_LIMIT = 512
CURSOR_LIFETIME_SECONDS = 900


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


class RepresentationStore:
    def __init__(self, store, *, authorize, query_scope=None):
        if not callable(authorize):
            raise ValueError("Current owner material authorization is required")
        self.store = store
        self.authorize = authorize
        self.query_scope = query_scope or getattr(getattr(authorize, "__self__", None), "actor_ref", "owner")
        self.conn = store.conn
        if self.conn.in_transaction:
            raise ValueError(
                "Representation admission requires a clean transaction boundary"
            )
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS representation_objects (
                sha256 TEXT PRIMARY KEY, bytes BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS representation_artifacts (
                representation_ref TEXT PRIMARY KEY, metadata TEXT NOT NULL, sha256 TEXT
            );
            CREATE TABLE IF NOT EXISTS representation_members (
                record_id TEXT NOT NULL, representation_ref TEXT NOT NULL,
                PRIMARY KEY(record_id, representation_ref)
            );
            CREATE TABLE IF NOT EXISTS representation_operations (
                operation_ref TEXT PRIMARY KEY, record_id TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS representation_identity_history (
                representation_ref TEXT PRIMARY KEY, metadata_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS representation_operation_history (
                operation_ref TEXT PRIMARY KEY, record_id TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_representation_order
                ON akousmata(created_at DESC, akousma_id DESC)
                WHERE json_extract(record, '$.record_kind')='representation_record';
            CREATE TABLE IF NOT EXISTS representation_query_cursors (
                token TEXT PRIMARY KEY, query TEXT NOT NULL, created_at TEXT NOT NULL,
                record_id TEXT NOT NULL, expires_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_representation_cursor_expiry
                ON representation_query_cursors(expires_at);
        """)

    def _permit(self, action, rep, *, resolve_representation=None):
        if (
            self.authorize(
                action,
                deepcopy(rep),
                resolve_representation=resolve_representation or self._representation,
            )
            is not True
        ):
            raise PermissionError("Material terms do not authorize " + action)

    def _representation(self, identity):
        row = self.conn.execute(
            """SELECT r.metadata FROM representation_artifacts r
            WHERE r.representation_ref=? AND EXISTS(
                SELECT 1 FROM representation_members m JOIN akousmata a ON a.akousma_id=m.record_id
                WHERE m.representation_ref=r.representation_ref)""",
            (identity,),
        ).fetchone()
        if row is None:
            raise KeyError(identity)
        return json.loads(row["metadata"])

    def representation(self, identity, *, action="read"):
        rep = self._representation(identity)
        self._permit(action, rep)
        return rep

    def read_bytes(self, identity, *, action="read") -> bytes:
        rep = self.representation(identity, action=action)
        digest = rep["artifact"].get("sha256")
        row = self.conn.execute(
            "SELECT bytes FROM representation_objects WHERE sha256=?", (digest,)
        ).fetchone()
        if row is None:
            raise ValueError("Representation artifact is not retained")
        data = bytes(row["bytes"])
        if (
            len(data) != rep["artifact"].get("byte_count")
            or sha256(data).hexdigest() != digest
        ):
            raise ValueError("Retained representation artifact changed")
        return data

    def get(self, record_id):
        record = self.store.get(record_id)
        if record is None or record.get("record_kind") != "representation_record":
            return None
        for rep in record["extensions"]["earworm_representation"]["representations"]:
            self._permit("read_metadata", rep)
        return record

    def operation(self, operation_ref):
        row = self.conn.execute(
            "SELECT record_id FROM representation_operations WHERE operation_ref=?",
            (operation_ref,),
        ).fetchone()
        record = self.get(row["record_id"]) if row else None
        if record is None:
            return None
        block = record["extensions"]["earworm_representation"]
        primary = next(
            (
                a["representation_ref"]
                for a in block["accesses"]
                if a["role"] in {"subject", "score", "work"}
                and a["status"] == "available"
            ),
            None,
        )
        return dict(
            operation_ref=operation_ref,
            primary_representation_ref=primary,
            output_representation_refs=[
                o["representation_ref"] for o in block["outputs"]
            ],
            account_representation_refs=[
                o["representation_ref"]
                for o in block["outputs"]
                if o["kind"] == "account"
            ],
        )

    def producers(self, representation_refs):
        parents = set()
        for identity in representation_refs:
            rows = self.conn.execute(
                """SELECT a.akousma_id FROM akousmata a,
                json_each(a.record,'$.extensions.earworm_representation.outputs') o
                WHERE json_extract(o.value,'$.representation_ref')=?""",
                (identity,),
            ).fetchall()
            parents.update(r["akousma_id"] for r in rows)
        return sorted(parents)

    def put(
        self,
        record: dict,
        *,
        supported_contracts,
        resolve_artifact=None,
        validate_binding=None,
    ) -> str:
        if self.conn.in_transaction:
            raise ValueError(
                "Representation admission requires a clean transaction boundary"
            )
        if not set(REPRESENTATION_CONTRACTS) <= set(supported_contracts):
            raise ValueError(
                "Required representation contracts have not been negotiated"
            )
        errors = record_19_errors(record)
        if errors or record.get("record_kind") != "representation_record":
            raise ValueError(
                "Invalid opt-in representation record: " + "; ".join(errors)
            )
        block = deepcopy(record["extensions"]["earworm_representation"])
        indexed = {r["representation_id"]: r for r in block["representations"]}

        def resolve_rep(identity):
            return indexed.get(identity) or self._representation(identity)

        if block["record_ref"] != record["akousma_id"]:
            raise ValueError("Memory and representation record identities must agree")
        material = {}
        for rep in block["representations"]:
            self._permit("retain_metadata", rep, resolve_representation=resolve_rep)
            artifact = rep["artifact"]
            if artifact["state"] == "retained":
                self._permit("retain", rep, resolve_representation=resolve_rep)
                data = artifact.get("inline_text")
                data = (
                    data.encode("utf-8")
                    if isinstance(data, str)
                    else resolve_artifact(deepcopy(rep))
                    if callable(resolve_artifact)
                    else None
                )
                if (
                    not isinstance(data, bytes)
                    or len(data) > MAX_ARTIFACT_BYTES
                    or len(data) != artifact["byte_count"]
                    or sha256(data).hexdigest() != artifact["sha256"]
                ):
                    raise ValueError(
                        "Exact retained artifact bytes are unavailable or mismatched"
                    )
                material[rep["representation_id"]] = data
        admit_representation_record(
            block,
            supported_contracts=supported_contracts,
            resolve_artifact=lambda rep: material.get(rep["representation_id"]),
            validate_binding=validate_binding,
            resolve_operation=self.operation,
        )
        retained = deepcopy(record)
        for rep in retained["extensions"]["earworm_representation"]["representations"]:
            rep["artifact"].pop("inline_text", None)
        rid = retained["akousma_id"]
        if self.store.forgotten(rid):
            raise ValueError("A forgotten representation record cannot be resurrected")
        existing = self.store.get(rid)
        if existing is not None:
            if canonical(existing) != canonical(retained):
                raise ValueError(
                    "Representation records are immutable; use a new identity"
                )
            return rid
        parents = retained["lineage"]["parent_akousma_ids"]
        if rid in parents or any(self.store.get(p) is None for p in parents):
            raise ValueError("Memory lineage requires existing distinct parents")
        previous = block.get("return", {}).get("previous_operation_ref")
        if previous:
            row = self.conn.execute(
                "SELECT record_id FROM representation_operations WHERE operation_ref=?",
                (previous,),
            ).fetchone()
            if row is None or row["record_id"] not in parents:
                raise ValueError(
                    "A retained return must keep its previous memory parent"
                )
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            for rep in block["representations"]:
                self._permit("retain_metadata", rep, resolve_representation=resolve_rep)
                if rep["artifact"]["state"] == "retained":
                    self._permit("retain", rep, resolve_representation=resolve_rep)
            if any(self.store.get(p) is None for p in parents):
                raise ValueError("A memory parent disappeared before commit")
            if self.conn.execute(
                "SELECT 1 FROM representation_operation_history WHERE operation_ref=?",
                (block["operation_ref"],),
            ).fetchone():
                raise ValueError("An operation identity cannot be reused")
            for rep in retained["extensions"]["earworm_representation"][
                "representations"
            ]:
                key = rep["representation_id"]
                encoded = canonical(rep)
                old = self.conn.execute(
                    "SELECT metadata FROM representation_artifacts WHERE representation_ref=?",
                    (key,),
                ).fetchone()
                history = self.conn.execute(
                    "SELECT metadata_sha256 FROM representation_identity_history WHERE representation_ref=?",
                    (key,),
                ).fetchone()
                fingerprint = sha256(encoded.encode()).hexdigest()
                live = self.conn.execute(
                    "SELECT 1 FROM representation_members m JOIN akousmata a ON a.akousma_id=m.record_id WHERE m.representation_ref=?",
                    (key,),
                ).fetchone()
                if history and (history["metadata_sha256"] != fingerprint or not live):
                    raise ValueError(
                        "A representation identity cannot change or be silently resurrected"
                    )
                if old and old["metadata"] != encoded:
                    raise ValueError(
                        "A representation identity cannot change metadata or bytes"
                    )
                digest = rep["artifact"].get("sha256")
                if key in material:
                    old_object = self.conn.execute(
                        "SELECT bytes FROM representation_objects WHERE sha256=?",
                        (digest,),
                    ).fetchone()
                    if old_object and bytes(old_object["bytes"]) != material[key]:
                        raise ValueError(
                            "Content-addressed artifact collision or corruption"
                        )
                    self.conn.execute(
                        "INSERT OR IGNORE INTO representation_objects VALUES (?,?)",
                        (digest, material[key]),
                    )
                self.conn.execute(
                    "INSERT OR IGNORE INTO representation_artifacts VALUES (?,?,?)",
                    (key, encoded, digest),
                )
                self.conn.execute(
                    "INSERT OR IGNORE INTO representation_identity_history VALUES (?,?)",
                    (key, fingerprint),
                )
                self.conn.execute(
                    "INSERT INTO representation_members VALUES (?,?)", (rid, key)
                )
            self.conn.execute(
                "INSERT INTO representation_operations VALUES (?,?)",
                (block["operation_ref"], rid),
            )
            self.conn.execute(
                "INSERT INTO representation_operation_history VALUES (?,?)",
                (block["operation_ref"], rid),
            )
            self.conn.execute(
                """INSERT INTO akousmata(akousma_id,created_at,originating_app,source_type,origin,
                session_id,record_class,record) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    rid,
                    retained["created_at"],
                    retained["provenance"].get("originating_app"),
                    retained["provenance"].get("source_type"),
                    retained["provenance"].get("origin"),
                    retained.get("session_id"),
                    "legacy",
                    canonical(retained),
                ),
            )
            for parent in parents:
                self.conn.execute(
                    "INSERT INTO lineage_edges VALUES (?,?)", (rid, parent)
                )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return rid

    def page(self, *, limit=50, form=None, output_kind=None, query=None,
             cursor=None, include_record=None, audience="owner"):
        """Bounded keyset traversal with opaque, query-bound navigation state.

        An empty page can have a continuation. Neither the token nor this
        response reveals withheld identities or counts. Every request resolves
        current permissions, including an optional audience-specific check.
        """
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Representation query limit must be 1..200")
        if any(value is not None and (not isinstance(value, str) or len(value) > 200)
               for value in (form, output_kind, query)):
            raise ValueError("Representation filters must be bounded text")
        binding = canonical(dict(scope=self.query_scope, audience=audience,
                                 form=form or None, output_kind=output_kind or None,
                                 query=query or None))
        now = time.time()
        position = None
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) != 43:
                raise ValueError("Invalid or expired representation continuation")
            row = self.conn.execute(
                "SELECT * FROM representation_query_cursors WHERE token=?", (cursor,)
            ).fetchone()
            if row is None or row["query"] != binding or row["expires_at"] <= now:
                raise ValueError("Invalid or expired representation continuation")
            position = (row["created_at"], row["record_id"])
        params = []
        after = ""
        if position:
            after = " AND (a.created_at,a.akousma_id)<(?,?)"
            params.extend(position)
        params.append(QUERY_SCAN_LIMIT + 1)
        rows = self.conn.execute("""SELECT a.akousma_id,a.created_at FROM akousmata a
            WHERE json_extract(a.record,'$.record_kind')='representation_record'
            AND EXISTS(SELECT 1 FROM representation_operations o WHERE o.record_id=a.akousma_id)"""
            + after + " ORDER BY a.created_at DESC,a.akousma_id DESC LIMIT ?", params).fetchall()
        records = []
        processed = 0
        for row in rows[:QUERY_SCAN_LIMIT]:
            processed += 1
            position = (row["created_at"], row["akousma_id"])
            try:
                record = self.get(row["akousma_id"])
                if record is not None and include_record and include_record(record) is not True:
                    continue
            except PermissionError:
                continue
            if record is None:
                continue
            block = record["extensions"]["earworm_representation"]
            if form and not any(r["form"] == form for r in block["representations"]):
                continue
            if output_kind and not any(
                o["kind"] == output_kind for o in block["outputs"]
            ):
                continue
            if query and query.casefold() not in canonical(record).casefold():
                continue
            records.append(record)
            if len(records) == limit:
                break
        next_cursor = None
        with self.conn:
            self.conn.execute("""DELETE FROM representation_query_cursors WHERE token IN (
                SELECT token FROM representation_query_cursors WHERE expires_at<=? LIMIT 128)""", (now,))
            if processed < len(rows):
                next_cursor = secrets.token_urlsafe(32)
                self.conn.execute("INSERT INTO representation_query_cursors VALUES (?,?,?,?,?)",
                                  (next_cursor, binding, *position, now + CURSOR_LIFETIME_SECONDS))
        return dict(records=records, next_cursor=next_cursor)

    def list(self, *, limit=50, form=None, output_kind=None):
        """Compatibility first page; use page() to traverse older material."""
        return self.page(limit=limit, form=form, output_kind=output_kind)["records"]

    def forget(self, record_id, *, actor, reason):
        record = self.store.get(record_id)
        if record is None:
            return None
        for rep in record["extensions"]["earworm_representation"]["representations"]:
            self._permit("forget", rep)
        receipt = self.store.forget_with_receipt(record_id, actor=actor, reason=reason)
        # Availability also joins the canonical table, so even an interrupted
        # cleanup cannot serve an artifact from a forgotten sole record.
        with self.conn:
            self.conn.execute(
                "DELETE FROM representation_members WHERE record_id=?", (record_id,)
            )
            self.conn.execute(
                "DELETE FROM representation_operations WHERE record_id=?", (record_id,)
            )
            self.conn.execute(
                "DELETE FROM representation_artifacts WHERE NOT EXISTS(SELECT 1 FROM representation_members m WHERE m.representation_ref=representation_artifacts.representation_ref)"
            )
            self.conn.execute(
                "DELETE FROM representation_objects WHERE NOT EXISTS(SELECT 1 FROM representation_artifacts a WHERE a.sha256=representation_objects.sha256)"
            )
        return dict(
            receipt,
            representation_cleanup="unshared logical artifacts removed; physical SQLite erasure is not established",
        )


def retained_representation_record(
    block, *, created_at, parents=(), originating_app="oida"
) -> dict:
    return dict(
        akousma_id=block["record_ref"],
        schema_version="1.9.0",
        record_kind="representation_record",
        created_at=created_at,
        subject="Textual listening or sounding",
        provenance=dict(
            source_type="designed",
            origin="file",
            originating_app=originating_app,
            consent_status="unknown",
        ),
        lineage=dict(parent_akousma_ids=list(parents)),
        extensions=dict(earworm_representation=deepcopy(block)),
    )
