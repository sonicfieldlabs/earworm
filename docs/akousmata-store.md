# The akousmata store

The **akousmata** is the shared, cross-app memory layer — one store that oída, germ, and
algophony all read and write, so a sound listened by oída can be transformed in germ and
evaluated in algophony while carrying one continuous lineage.

## Location

- Default: `~/workspace/akousmata/` (private; **never** inside a git repo).
- Override: `AKOUSMATA_PATH` environment variable.

It sits outside every repository, like `SFL/docs`. It is personal listening memory and is never
pushed. Open-research publication is **export-only** and sanitized (see the spec's consent rule).

## Layout

```
akousmata/
├── index.sqlite            # queryable index of all akousma records (see schema below)
├── objects/                # content-addressed audio + blobs
│   └── <ab>/<sha256>.<ext> # sharded by first 2 hex chars of the content hash
└── README.md
```

Audio referenced by an akousma's `audio.uri` uses `akousmata://objects/<sha256>.<ext>`, resolved
against `objects/`. Records are stored whole (as JSON) in `index.sqlite` for portability; the DB is
an index/cache that can be rebuilt from the JSON blobs.

## `index.sqlite` schema

```sql
CREATE TABLE akousmata (
  akousma_id      TEXT PRIMARY KEY,
  created_at      TEXT NOT NULL,
  originating_app TEXT,            -- oida | germ | algophony
  source_type     TEXT,           -- generated | recorded | imported | ...
  origin          TEXT,           -- live-input | system-output | file | generated
  content_hash    TEXT,
  session_id      TEXT,
  record          TEXT NOT NULL   -- the full akousma JSON
);
CREATE TABLE lineage_edges (
  child_id  TEXT NOT NULL,        -- akousma_id
  parent_id TEXT NOT NULL,        -- akousma_id
  PRIMARY KEY (child_id, parent_id)
);
CREATE INDEX idx_lineage_parent ON lineage_edges(parent_id);
CREATE TABLE relation_edges (    -- v0.2: typed kinship links (lineage.relations)
  from_id  TEXT NOT NULL,        -- akousma_id
  rel_type TEXT NOT NULL,        -- variant_of | response_to | same_source_as | recurrence_of | series_with | compares_with | replaces | other
  to_id    TEXT NOT NULL,        -- akousma_id
  PRIMARY KEY (from_id, rel_type, to_id)
);
CREATE INDEX idx_relation_to ON relation_edges(to_id);
CREATE INDEX idx_akousmata_hash ON akousmata(content_hash);
```

`lineage_edges` is denormalized from each record's `lineage.parent_akousma_ids` so the lineage
explorer (germ) and batch queries (algophony) can walk ancestry/descendants without scanning.
`relation_edges` (v0.2) is denormalized from `lineage.relations` so kinship — variants, responses,
recurrences, series — is walkable in both directions without confusing it with causal parenthood.

### Store maintenance (v0.2)

- `reindex()` rebuilds both edge tables from the stored records (run once after upgrading a
  pre-relations store).
- `verify()` returns an integrity report — dangling parents, dangling relation targets, missing
  audio objects, invalid records — reported rather than dropped: absence is information.
- Richer queries: `query(tag=…, text=…, since=…, until=…, session_id=…, content_hash=…)` and
  `find_by_hash()` for dedupe/recurrence lookups.

## Access

All three apps use the reference implementation rather than talking to SQLite directly:

- Python: [`earworm/packages/py-akousma`](../packages/py-akousma) — `AkousmataStore` (put/get/query,
  lineage walks, content-addressed audio) + schema validation. Consumed by oída, germ backend,
  algophony pipelines.
- JavaScript/TypeScript: `@earworm/core` + `@earworm/sdk-js` for germ UI / algophony dashboard.

Concurrency: SQLite WAL mode; a small local service can front the store later if multi-writer
contention appears. For now, single-machine, library-level access with WAL is sufficient.
