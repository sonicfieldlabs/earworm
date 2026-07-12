# The akousmata store

The **akousmata** is the shared, cross-app memory layer — one store that oída, germ, and
algophony all read and write, so a sound listened by oída can be transformed in germ and
evaluated in algophony while carrying one continuous lineage.

## Location

- Default: `~/workspace/akousmata/` — which is also the home of the
  **akousmata navigator app** (`github.com/sonicfieldlabs/akousmata`): the
  code is public, the data files (`index.sqlite`, `objects/`, `wiki/`,
  `settings.json`) are gitignored there and never tracked.
- Override: `AKOUSMATA_PATH` environment variable to separate code and data.

The data is personal listening memory and is never pushed. Open-research
publication is **export-only** and sanitized (see the spec's consent rule).

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
  lat             REAL,           -- v0.3: hoisted from record["location"] (nullable)
  lon             REAL,           -- v0.3: hoisted from record["location"] (nullable)
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
CREATE INDEX idx_akousmata_created ON akousmata(created_at);   -- v0.3
CREATE INDEX idx_akousmata_location ON akousmata(lat, lon);    -- v0.3
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
- v0.2.1 library operations for navigators: `tags()` (distinct tags with
  counts), `changed_since(iso)` (watchers/realtime feeds), and
  `forget(id, delete_audio=False)` — the memory operation: removes the record
  and its outgoing edges, keeps inbound edges as reportable absence, and only
  deletes the audio object when no other record shares its content hash.

### The covenant surface (v0.4, spec v1.3)

- Records' `covenant.id` is hoisted into an indexed `covenant_id` column on
  `put()` (in-place migration, like lat/lon); `query(covenant_id=…)` makes
  "everything listened under this covenant" one indexed call, and
  `reindex()` re-hoists. The block itself carries the covenant's identity
  and honest absence — what was withheld, counted and attributed, never
  described — so filtering and auditing by ethics never exposes withheld
  content.

### The location surface (v0.3, spec v1.2)

- Records' `location.lat` / `location.lon` are hoisted into indexed `lat`/`lon`
  columns on `put()`; existing stores migrate in place on open (`ALTER TABLE`,
  nullable, no data rewrite). `reindex()` re-hoists after bulk edits.
- `locations()` returns every located record newest-first — the listening
  map's feed. `near(lat, lon, radius_km=…)` answers "what did I hear around
  here": bounding-box prefilter on the indexed columns, exact haversine
  distance in Python, nearest first. `query(has_location=…)` filters either way.
- Performance housekeeping shipped with it: `created_at` is now indexed
  (every list/timeline/cursor query sorts on it), and `tags()` uses SQLite's
  JSON1 `json_each` instead of parsing every record blob in Python, with the
  old scan kept as a fallback for JSON1-less builds.

## Access

All three apps use the reference implementation rather than talking to SQLite directly:

- Python: [`earworm/packages/py-akousma`](../packages/py-akousma) — `AkousmataStore` (put/get/query,
  lineage walks, content-addressed audio) + schema validation. Consumed by oída, germ backend,
  algophony pipelines.
- JavaScript/TypeScript: `@earworm/core` + `@earworm/sdk-js` for germ UI / algophony dashboard.

Concurrency: SQLite WAL mode; a small local service can front the store later if multi-writer
contention appears. For now, single-machine, library-level access with WAL is sufficient.
