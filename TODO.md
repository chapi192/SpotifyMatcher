# WrappedNow: Local-First Music Library Workbench

WrappedNow is becoming a personal music-library database and organization
workbench. Spotify is an import and write-back provider; the local database is
the durable source for analysis, history, custom organization, and proposed
changes.

The primary target is one owner running the application locally or on a private
home server. Spotify Development Mode is sufficient for this use case.

## Product principles

- Keep a durable local copy of normalized library metadata.
- Never make destructive Spotify changes without a preview and confirmation.
- Record enough information to explain and undo every write-back operation.
- Prefer deterministic analysis; use AI for language, classification, and
  explanations rather than as the source of truth.
- Keep provider-specific code behind a normalization boundary so another music
  source can be added later.

## Phase 1: durable personal synchronization

- [x] Add a local SQLite catalog.
- [x] Persist normalized playlists, tracks, artists, album metadata, ordering,
  and sync timestamps when a selected playlist is loaded.
- [x] Restore persisted playlist datasets after a server restart.
- [x] Accept both Spotify's old `tracks/track` and 2026 `items/item` shapes.
- [x] Replace removed batch artist hydration with individual cached requests.
- [x] Add an explicit "Sync library" screen and sync all owned/collaborative
  playlists without requiring dashboard selection.
- [x] Record sync-run history with failures, playlist additions/removals, track
  membership changes, unchanged counts, and duration.
- [ ] Preserve full playlist snapshots so track moves and historical states can
  be inspected and restored, rather than retaining only aggregate run changes.
- [ ] Move OAuth tokens out of the signed browser cookie into server-side
  storage.
- [x] Persist synchronization status and error details in a SQLite job table.
- [ ] Resume interrupted synchronization jobs automatically.
- [ ] Add retry ceilings and clear errors for quota exhaustion versus temporary
  Spotify rate limiting.

## Phase 2: library health and audit

- [x] Add a durable local profile for every track, including identity evidence,
  provider observations, confidence, Spotify link, and playlist membership.
- [x] Add a local, read-only Library Health dashboard with searchable audit
  results and basic playlist-size statistics.
- [x] Identify Liked Songs that are not in another active playlist ("orphans").
- [x] Identify playlist tracks that are not in Liked Songs.
- [x] Identify tracks placed in multiple active playlists.
- [ ] Detect alternate releases/remasters and unavailable tracks.
- [ ] Rank playlist overlap and suggest merge/split candidates.
- [ ] Show stale playlists and how each playlist changed between snapshots.
- [ ] Add filters and exportable reports.

## Phase 3: organization workspace

- [ ] Add local tags, notes, collection groups, and rule-based smart collections.
- [ ] Add a review queue for ambiguous tracks.
- [ ] Preview playlist create/add/remove/reorder/rename operations.
- [ ] Store an undo manifest before every Spotify write.
- [ ] Require explicit confirmation before write-back.
- [ ] Support restoring a playlist from a historical snapshot.

## Phase 4: placement and recommendation engine

- [x] Add durable track identities, provider observations, resolved features,
  manual-override fields, and resumable enrichment job storage.
- [x] Add a cached, rate-limited MusicBrainz identity-matching first pass.
- [x] Support bounded 10–100 track matching batches with visible match decisions
  so provider quality can be vetted before catalog-wide enrichment.
- [x] Retry MusicBrainz throttling/capacity responses and isolate temporary
  provider failures to individual tracks without losing batch progress.
- [ ] Add review controls for uncertain MusicBrainz matches.
- [x] Persist and display the reason behind automatic, held, missing, and
  temporary-error MusicBrainz decisions.
- [x] Add bounded AcousticBrainz, ListenBrainz, and optional ReccoBeats
  enrichment adapters with permanently cached normalized observations.
- [x] Add a side-by-side provider inspection view for actual returned features,
  coverage failures, confidence, and semantic tags.
- [ ] Recommend existing destinations for newly liked or unfiled tracks.
- [ ] Score matches using artists, albums, genres/tags, era, and the owner's
  previous filing decisions.
- [ ] Explain every recommendation and expose the signals and weights.
- [ ] Detect coherent clusters that justify a new playlist.
- [ ] Learn local preferences from accepted/rejected suggestions without
  training on or redistributing Spotify content.

## Phase 5: optional AI assistant

- [ ] Translate natural-language requests into read-only catalog queries.
- [ ] Generate playlist/cluster names and short explanations.
- [ ] Propose organization plans as structured, reviewable operations.
- [ ] Support either a hosted model or a local model; send compact metadata
  summaries rather than OAuth tokens or the entire database.
- [ ] Keep AI-triggered Spotify writes disabled until the normal preview,
  confirmation, and undo workflow exists.
- [ ] Optionally analyze legally owned local audio with Essentia; match files to
  catalog tracks using ISRC, metadata, duration, and acoustic fingerprints.

## Operations and home-server deployment

- [x] Make debug mode and secure-cookie behavior environment configurable.
- [x] Document local startup and environment variables.
- [ ] Add a health endpoint and structured application logging.
- [ ] Add database backup/restore commands.
- [ ] Add a Dockerfile and Compose configuration for the home server.
- [ ] Put the app behind a TLS reverse proxy and restrict it to the LAN, VPN, or
  an authenticated gateway.
- [ ] Add CSRF protection for every state-changing application endpoint.
- [ ] Add an application-level owner login if the server is reachable outside
  the trusted network.
- [ ] Add automated database and synchronization tests.
