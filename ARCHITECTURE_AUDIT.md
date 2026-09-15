# WrappedNow Architecture Audit

This audit describes the application after the first local-first persistence
pass. It is a diagnosis and prioritization document; most findings are not yet
implemented.

## Resolved in the synchronization milestone

- Replaced the nonexistent `/api/build` flow with `POST /api/sync` and durable
  `GET /api/sync/status` reporting.
- Playlist selection no longer starts Spotify network work.
- Selected/hidden IDs moved from the size-limited session cookie to SQLite.
- Sync status and terminal errors are persisted; abandoned running jobs are
  marked interrupted at startup.
- Unchanged owned playlists are skipped using Spotify snapshot IDs.
- Persisted artist enrichment is loaded before new Spotify artist requests.
- Spotipy now uses an in-memory token handler instead of its implicit shared
  `.cache` file.

The findings below remain useful as the original audit record. Items listed
above should be read as historical context where they overlap.

## Current behavior

1. `/` now redirects to `/dashboard`, which redirects unauthenticated requests
   to Spotify login. The old public landing page is no longer served.
2. Spotify Authorization Code OAuth stores the token dictionary and UI
   selection in a signed browser session cookie.
3. `/api/playlists` downloads playlist metadata and adds Liked Songs as a
   synthetic playlist.
4. Selecting playlists posts their IDs to `/api/selection`. Missing datasets
   start a daemon thread which fetches playlists sequentially.
5. Each page of tracks is normalized; every previously unseen artist is then
   fetched individually to obtain genres and artwork.
6. A completed playlist is kept in a process-local cache and persisted both as
   normalized relational rows and as a complete JSON document in SQLite.
7. The workspace requests one endpoint per metric. Each endpoint loops over the
   selected in-memory datasets and calculates its own response from scratch.
8. The browser caches metric responses for the lifetime of the page and renders
   them with separate metric-specific JavaScript modules.

## P0: correctness and reliability

### Restart restoration calls an endpoint that does not exist

`templates/dashboard.html` posts to `/api/build` when navigation state says a
selection exists but data is not in memory. No route implements `/api/build`.
The request returns 404, progress immediately appears idle, and the dashboard
continues without intentionally restoring or rebuilding the selection.

The persisted-data restore code is currently reached through `/api/library` or
another `/api/selection` post, so startup behavior depends on incidental request
order. Replace this with one explicit synchronization/job API.

### Persistent data has no freshness policy

Once a selected playlist is loaded from SQLite, it is treated as complete
forever. There is no snapshot/version comparison, manual refresh endpoint, TTL,
or use of Spotify snapshot IDs. Playlist additions, removals, reordering,
renames, and deletions can therefore remain invisible indefinitely.

### Browser metric cache becomes incorrect

`static/js/workspace/api.js` caches each metric only by metric name. It does not
include selection, database revision, or synchronization revision in the key,
and the cache is not cleared after selection changes. A previously fetched
metric can be rendered for a new set of playlists.

### Combined analytics count memberships, not unique tracks

Most metric endpoints concatenate every selected playlist's tracks. A track in
five playlists is counted five times. This may be useful as a "playlist
presence" measure, but it is currently presented as combined-library analysis.
The API should expose both explicit modes: unique tracks and playlist
memberships.

### Duration extrema can use invalid rows

Average-length calculations filter missing durations into a duration list, but
find the shortest and longest item against the original unfiltered track list.
A local, unavailable, or malformed item with `duration_ms=None` can cause an
exception or select inconsistent extrema.

### Spotify errors can leave a build permanently opaque

The worker collapses every exception into `status="error"`, prints a traceback,
and exposes no reason through the progress endpoint. It does not distinguish
authentication expiry, unavailable endpoints, permissions, quota exhaustion,
rate limits, malformed items, or database failures. The UI can only say that a
generic error occurred.

## P1: Spotify request efficiency

### Artist enrichment is the dominant cost

Spotify Development Mode removed batch artist lookup, so synchronization now
makes one request per unique artist. A large personal library can require
thousands of calls. The in-memory artist cache disappears on restart even
though SQLite already contains artist data.

Before requesting an artist, hydrate the cache from SQLite and assign an
enrichment TTL. Make genre/artwork enrichment a separate resumable job so core
playlist synchronization does not wait for it.

### Album artwork performs repeated API calls

`/api/album-images` performs one Spotify request per album each time the
frontend asks. Artwork already appears in catalog/playlist responses in many
cases and should be stored during synchronization. Remaining lookups should use
the database cache and a bounded job rather than a request-time fan-out.

### Synchronization downloads complete playlists

The application does not store or compare Spotify playlist snapshot IDs. Every
refresh must download every page, even when nothing changed. Store playlist
metadata first, compare revisions, and only fetch contents for changed
playlists.

### Rate limiting can wait forever

`safe_spotify_call` retries HTTP 429 responses indefinitely. This is reasonable
for a short rate limit but wrong for quota exhaustion or a pathological
`Retry-After`. Add a retry ceiling, cancellation-aware waiting, structured error
reasons, and separate handling for `reason=QUOTA_EXCEEDED`.

### Playlist listing cache is process-local and arbitrary

Playlist metadata is cached for five minutes in a dictionary but is not tied to
the SQLite catalog or a manual sync revision. This creates another source of
truth with different freshness semantics.

## P1: persistence and state model

### SQLite is a side cache instead of the primary model

Analytics still require selection IDs from the session cookie and reconstruct
datasets into process memory. Queries do not use the relational catalog. The
database therefore cannot yet power global audits, history, smart collections,
or reliable restart behavior.

The next architecture should be:

`Spotify sync -> SQLite revision -> SQL-backed analysis -> optional write plan`

UI selection should be a query/filter preference, not the trigger that decides
what exists in the catalog.

### The same dataset is stored three times

Each normalized playlist lives in its full SQLite JSON document, relational
tables, and the Python process cache. Tracks shared between playlists are also
repeated inside each JSON document. This increases disk and memory consumption
and creates consistency risk.

Keep normalized relational rows as canonical. Temporary response caching can be
revision-keyed and bounded. Retain JSON only for immutable historical snapshots
if snapshot restoration needs it.

### There is no history despite snapshot-oriented goals

Saving a playlist overwrites its prior rows and JSON. There is no record of
added, removed, moved, or renamed items and no undo source. Add `sync_runs`,
playlist revisions, and membership history before implementing write-back.

### Catalog lifecycle is incomplete

The schema does not record ownership/collaboration, Spotify snapshot ID,
playlist description, visibility, folder/group, added-at timestamps, local
files, unavailable items, or tombstones for deleted playlists. Empty genres can
also overwrite previously enriched artist genres.

### Process state has no lifecycle

The global dictionaries have no locks, TTL, size limit, or startup recovery.
Logout removes some entries but normal long-lived use accumulates cached tracks
and artists. Raw dictionaries are acceptable for a short prototype but should
not coordinate synchronization.

### Daemon threads are not durable jobs

A server reload or crash silently terminates a synchronization. Multiple worker
processes would have different dictionaries and could start duplicate work.
For one home-server process, a SQLite-backed job table and a single worker loop
are sufficient; Redis is not necessary yet.

## P1: authentication and home-server security

### OAuth tokens are exposed to the browser

Starlette's session cookie is signed, not encrypted. The access token and
refresh token cannot be modified without invalidating the signature, but they
can be read by the browser or anyone who obtains the cookie. Store tokens in
SQLite using OS/file permissions (and preferably encryption at rest); keep only
an opaque session identifier in the cookie.

Spotipy also writes its default `.cache` token file because passing
`cache_handler=None` selects its file cache rather than disabling caching. The
application consequently has two token stores with unclear precedence.

### Large selections can exceed cookie limits

Selected and hidden playlist IDs are stored in the same cookie as Spotify
tokens. An extensive library can exceed the browser's roughly 4 KB cookie
limit, causing selection or authentication state to disappear. Move all of this
state server-side.

### Owner access is not enforced

Spotify's five-user allowlist limits who can call Spotify, but it is not an
application login boundary. Before exposing the home server outside a trusted
LAN/VPN, add an owner-only gate at the reverse proxy or application layer.

### State-changing routes lack CSRF protection

OAuth state validation is present, but application POST routes do not validate
CSRF tokens. This becomes critical once playlist writes exist. Logout should
also be POST rather than a state-changing GET.

### External strings are inconsistently escaped

Several pages construct `innerHTML` from Spotify playlist, track, artist, album,
and image values. Some workspace names use `escapeHtml`, but the dashboard and
metric modules are inconsistent. Treat all provider data as untrusted and use
DOM text properties or centralized escaping/URL validation.

## P2: backend organization and analytics

### Analytics are duplicated and repeatedly scan all data

`web/routes/analytics.py` is over 1,700 lines and independently loops through
the same tracks for duration, artists, release years, genres, albums, profile,
and relationships. Similar artist/genre/album/decade profile logic is repeated
in `profile_library.py` and `recommendations.py`.

Create one tested profile builder and either persist its revisioned result or
compute all base aggregates in one pass. Metric endpoints should be small
serializers over shared domain services.

### Relationship scoring is nonstandard and unstable

The function named `jaccard` multiplies Jaccard similarity by an additional
size-coverage ratio, double-penalizing different-sized playlists. Shared track
samples are random, so identical requests produce different output. Rename and
document the score or use standard metrics, and make samples deterministic.

### Recommendation scores are not normalized

Genre points increase once per matching genre while other signals are binary.
Scores therefore depend on how many tags Spotify assigns, and playlists with
broad genre vocabularies are favored. There is no confidence calibration,
negative evidence, minimum threshold, or held-out evaluation against your
actual filing decisions.

### Deprecated popularity remains wired through the application

The backend endpoint, workspace button/import, renderer, and charts remain even
though new Spotify data supplies no popularity. Remove it rather than carrying
a permanently empty feature.

### Demo and landing code is now dead

The template, landing JavaScript, demo endpoints, and large demo JSON file are
no longer reachable from `/`. Removing them will shorten `analytics.py`, reduce
static payloads, and eliminate the unauthenticated demo-data fallback.

### API response semantics are inconsistent

Some unauthenticated endpoints return HTTP 200 with `{error: ...}`, other paths
return `{status: "error"}`, and pages use redirects. Define typed response
models and use consistent 401, 404, 409, 422, 429, and 500 responses.

## P2: frontend behavior and maintainability

### Workspace initialization does duplicate work

It renders the playlist section twice, requests the current metric, and then
calls `setMetric`, which requests/renders it again. The cache usually prevents a
second server computation, but animation and rendering are duplicated.

### Async metric responses can race

Rapid metric or playlist changes start overlapping requests without an abort
controller or request generation check. A slower old response can overwrite a
newer choice. Relationship animation also needs guaranteed cancellation when
leaving the view.

### Dashboard artwork processing is brittle

It downloads and decodes every playlist image concurrently, reads it through a
canvas, and awaits one `Promise.all`. One CORS or decode failure can reject the
entire initialization. Bound concurrency, cache computed colors, and fall back
per image.

### Large monolithic files slow future changes

The dashboard template contains roughly 680 lines with its application logic
inline. The relationship renderer is roughly 1,375 lines. Move behavior into
modules and split domain calculations from DOM rendering before adding the
organization workspace.

## Dependency and test gaps

- There are no automated tests.
- `httpx` is absent, so FastAPI's `TestClient` cannot run.
- `requirements.txt` is a fully frozen environment rather than a minimal set of
  direct runtime and development dependencies.
- Redis is installed but unused; pandas is no longer used by current web code.
- There are no schema migrations or schema version table.
- There is no health check, structured logging, backup command, or sync fixture.

## Recommended implementation order

1. Replace cookie/global selection state with an owner record and server-side
   session; establish one canonical token store.
2. Replace the nonexistent build restoration path with a real `POST /api/sync`
   and a SQLite-backed single-worker job.
3. Make SQLite canonical: sync all owned/collaborative playlists and Liked Songs,
   store Spotify revisions, expose freshness and errors, and reuse persisted
   artist/album enrichment.
4. Add immutable sync history and tests for adds, removals, reorders, playlist
   deletion, unavailable tracks, duplicates, and interrupted jobs.
5. Consolidate analytics into a shared, revision-aware analysis service; define
   unique-track versus membership-weighted metrics explicitly.
6. Fix frontend cache keys/races, remove popularity and dead demo code, and
   centralize safe DOM rendering.
7. Only then build audit views and preview/undo/write-back operations.
8. Add Docker/Compose, backup tooling, and owner access controls for the home
   server after the local workflow is trustworthy.
