import json
import os
import sqlite3
import threading
from collections import Counter
from contextlib import closing
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "wrappednow.sqlite3"
_DB_LOCK = threading.RLock()


def database_path() -> Path:
    configured = os.getenv("MUSIC_DB_PATH")
    path = Path(configured).expanduser() if configured else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_catalog() -> None:
    with _DB_LOCK, closing(_connect()) as db, db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                user_id TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                name TEXT NOT NULL,
                image_url TEXT,
                track_total INTEGER NOT NULL DEFAULT 0,
                dataset_json TEXT NOT NULL,
                owner_id TEXT,
                collaborative INTEGER NOT NULL DEFAULT 0,
                snapshot_id TEXT,
                is_liked INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, playlist_id)
            );

            CREATE TABLE IF NOT EXISTS tracks (
                track_id TEXT PRIMARY KEY,
                name TEXT,
                duration_ms INTEGER,
                explicit INTEGER,
                spotify_url TEXT,
                album_id TEXT,
                album_name TEXT,
                release_date TEXT,
                album_track_total INTEGER,
                isrc TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS artists (
                artist_id TEXT PRIMARY KEY,
                name TEXT,
                genres_json TEXT NOT NULL DEFAULT '[]',
                image_url TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS track_artists (
                track_id TEXT NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
                artist_id TEXT NOT NULL REFERENCES artists(artist_id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                PRIMARY KEY (track_id, artist_id)
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                user_id TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                track_id TEXT NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                PRIMARY KEY (user_id, playlist_id, position),
                FOREIGN KEY (user_id, playlist_id)
                    REFERENCES playlists(user_id, playlist_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track
                ON playlist_tracks(track_id);
            CREATE INDEX IF NOT EXISTS idx_track_artists_artist
                ON track_artists(artist_id);

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                total_playlists INTEGER NOT NULL DEFAULT 0,
                completed_playlists INTEGER NOT NULL DEFAULT 0,
                skipped_playlists INTEGER NOT NULL DEFAULT 0,
                tracks_processed INTEGER NOT NULL DEFAULT 0,
                new_playlists INTEGER NOT NULL DEFAULT 0,
                changed_playlists INTEGER NOT NULL DEFAULT 0,
                removed_playlists INTEGER NOT NULL DEFAULT 0,
                added_tracks INTEGER NOT NULL DEFAULT 0,
                removed_tracks INTEGER NOT NULL DEFAULT 0,
                current_playlist TEXT,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_sync_runs_user_started
                ON sync_runs(user_id, started_at DESC);

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                selected_ids_json TEXT NOT NULL DEFAULT '[]',
                hidden_ids_json TEXT NOT NULL DEFAULT '[]',
                breakdown_source TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS track_identities (
                track_id TEXT PRIMARY KEY REFERENCES tracks(track_id) ON DELETE CASCADE,
                musicbrainz_recording_id TEXT,
                match_status TEXT NOT NULL DEFAULT 'pending',
                match_method TEXT,
                confidence REAL,
                decision_reason TEXT,
                candidates_json TEXT NOT NULL DEFAULT '[]',
                manually_locked INTEGER NOT NULL DEFAULT 0,
                checked_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feature_observations (
                track_id TEXT NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                numeric_value REAL,
                text_value TEXT,
                json_value TEXT,
                confidence REAL,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, provider, feature_name)
            );

            CREATE TABLE IF NOT EXISTS resolved_features (
                track_id TEXT NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
                feature_name TEXT NOT NULL,
                numeric_value REAL,
                text_value TEXT,
                json_value TEXT,
                resolution_mode TEXT NOT NULL DEFAULT 'consensus',
                preferred_provider TEXT,
                manually_locked INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, feature_name)
            );

            CREATE TABLE IF NOT EXISTS enrichment_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                batch_limit INTEGER,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                total_tracks INTEGER NOT NULL DEFAULT 0,
                completed_tracks INTEGER NOT NULL DEFAULT 0,
                matched_tracks INTEGER NOT NULL DEFAULT 0,
                review_tracks INTEGER NOT NULL DEFAULT 0,
                missing_tracks INTEGER NOT NULL DEFAULT 0,
                failed_tracks INTEGER NOT NULL DEFAULT 0,
                current_track TEXT,
                error TEXT
            );
            """
        )

        # Existing local catalogs predate the sync metadata columns. SQLite has
        # no ADD COLUMN IF NOT EXISTS, so keep the small migration explicit.
        existing_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(playlists)")
        }
        migrations = {
            "owner_id": "ALTER TABLE playlists ADD COLUMN owner_id TEXT",
            "collaborative": "ALTER TABLE playlists ADD COLUMN collaborative INTEGER NOT NULL DEFAULT 0",
            "snapshot_id": "ALTER TABLE playlists ADD COLUMN snapshot_id TEXT",
            "is_liked": "ALTER TABLE playlists ADD COLUMN is_liked INTEGER NOT NULL DEFAULT 0",
            "is_active": "ALTER TABLE playlists ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
        }
        for column, statement in migrations.items():
            if column not in existing_columns:
                db.execute(statement)

        sync_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(sync_runs)")
        }
        sync_migrations = {
            "new_playlists": "ALTER TABLE sync_runs ADD COLUMN new_playlists INTEGER NOT NULL DEFAULT 0",
            "changed_playlists": "ALTER TABLE sync_runs ADD COLUMN changed_playlists INTEGER NOT NULL DEFAULT 0",
            "removed_playlists": "ALTER TABLE sync_runs ADD COLUMN removed_playlists INTEGER NOT NULL DEFAULT 0",
            "added_tracks": "ALTER TABLE sync_runs ADD COLUMN added_tracks INTEGER NOT NULL DEFAULT 0",
            "removed_tracks": "ALTER TABLE sync_runs ADD COLUMN removed_tracks INTEGER NOT NULL DEFAULT 0",
        }
        for column, statement in sync_migrations.items():
            if column not in sync_columns:
                db.execute(statement)

        track_columns = {row["name"] for row in db.execute("PRAGMA table_info(tracks)")}
        if "isrc" not in track_columns:
            db.execute("ALTER TABLE tracks ADD COLUMN isrc TEXT")

        enrichment_columns = {row["name"] for row in db.execute("PRAGMA table_info(enrichment_jobs)")}
        if "batch_limit" not in enrichment_columns:
            db.execute("ALTER TABLE enrichment_jobs ADD COLUMN batch_limit INTEGER")
        if "failed_tracks" not in enrichment_columns:
            db.execute("ALTER TABLE enrichment_jobs ADD COLUMN failed_tracks INTEGER NOT NULL DEFAULT 0")

        identity_columns = {row["name"] for row in db.execute("PRAGMA table_info(track_identities)")}
        if "decision_reason" not in identity_columns:
            db.execute("ALTER TABLE track_identities ADD COLUMN decision_reason TEXT")



def recover_interrupted_sync_runs() -> None:
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            """
            UPDATE sync_runs
            SET status = 'interrupted',
                completed_at = CURRENT_TIMESTAMP,
                error = COALESCE(error, 'Application stopped during synchronization')
            WHERE status = 'running'
            """
        )
        db.execute(
            """
            UPDATE enrichment_jobs
            SET status = 'interrupted', completed_at = CURRENT_TIMESTAMP,
                error = COALESCE(error, 'Application stopped during enrichment')
            WHERE status = 'running'
            """
        )


def save_playlist_dataset(user_id: str, dataset: dict, metadata: dict | None = None) -> dict:
    if not user_id or not dataset:
        return {"is_new": False, "changed": False, "added_tracks": 0, "removed_tracks": 0}

    playlist_id = dataset.get("playlist_id")
    if not playlist_id:
        return {"is_new": False, "changed": False, "added_tracks": 0, "removed_tracks": 0}

    tracks = dataset.get("tracks") or []
    payload = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    metadata = metadata or {}

    with _DB_LOCK, closing(_connect()) as db, db:
        existing = db.execute(
            "SELECT dataset_json FROM playlists WHERE user_id = ? AND playlist_id = ?",
            (user_id, playlist_id),
        ).fetchone()
        old_tracks = Counter(
            row["track_id"] for row in db.execute(
                "SELECT track_id FROM playlist_tracks WHERE user_id = ? AND playlist_id = ?",
                (user_id, playlist_id),
            )
        )
        new_tracks = Counter(
            track.get("track_id") for track in tracks if track.get("track_id")
        )
        added_tracks = sum((new_tracks - old_tracks).values())
        removed_tracks = sum((old_tracks - new_tracks).values())
        changed = existing is None or existing["dataset_json"] != payload

        db.execute(
            """
            INSERT INTO playlists (
                user_id, playlist_id, name, image_url, track_total, dataset_json,
                owner_id, collaborative, snapshot_id, is_liked, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id, playlist_id) DO UPDATE SET
                name = excluded.name,
                image_url = excluded.image_url,
                track_total = excluded.track_total,
                dataset_json = excluded.dataset_json,
                owner_id = excluded.owner_id,
                collaborative = excluded.collaborative,
                snapshot_id = excluded.snapshot_id,
                is_liked = excluded.is_liked,
                is_active = 1,
                synced_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                playlist_id,
                dataset.get("playlist_name") or playlist_id,
                dataset.get("image"),
                len(tracks),
                payload,
                metadata.get("owner_id"),
                int(bool(metadata.get("collaborative"))),
                metadata.get("snapshot_id"),
                int(bool(metadata.get("is_liked"))),
            ),
        )
        db.execute(
            "DELETE FROM playlist_tracks WHERE user_id = ? AND playlist_id = ?",
            (user_id, playlist_id),
        )

        for position, track in enumerate(tracks):
            track_id = track.get("track_id")
            if not track_id:
                continue

            album = track.get("album") or {}
            db.execute(
                """
                INSERT INTO tracks (
                    track_id, name, duration_ms, explicit, spotify_url,
                    album_id, album_name, release_date, album_track_total, isrc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    name = excluded.name,
                    duration_ms = excluded.duration_ms,
                    explicit = excluded.explicit,
                    spotify_url = excluded.spotify_url,
                    album_id = excluded.album_id,
                    album_name = excluded.album_name,
                    release_date = excluded.release_date,
                    album_track_total = excluded.album_track_total,
                    isrc = COALESCE(excluded.isrc, tracks.isrc),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    track_id,
                    track.get("track_name"),
                    track.get("duration_ms"),
                    int(bool(track.get("explicit"))),
                    track.get("spotify_url"),
                    album.get("album_id"),
                    album.get("album_name"),
                    album.get("release_date"),
                    album.get("total_tracks"),
                    track.get("isrc"),
                ),
            )
            db.execute("DELETE FROM track_artists WHERE track_id = ?", (track_id,))

            for artist_position, artist in enumerate(track.get("artists") or []):
                artist_id = artist.get("artist_id")
                if not artist_id:
                    continue
                db.execute(
                    """
                    INSERT INTO artists (artist_id, name, genres_json, image_url)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(artist_id) DO UPDATE SET
                        name = excluded.name,
                        genres_json = excluded.genres_json,
                        image_url = COALESCE(excluded.image_url, artists.image_url),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        artist_id,
                        artist.get("artist_name"),
                        json.dumps(artist.get("genres") or []),
                        artist.get("image_url"),
                    ),
                )
                db.execute(
                    """
                    INSERT INTO track_artists (track_id, artist_id, position)
                    VALUES (?, ?, ?)
                    """,
                    (track_id, artist_id, artist_position),
                )

            db.execute(
                """
                INSERT INTO playlist_tracks (user_id, playlist_id, track_id, position)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, playlist_id, track_id, position),
            )

    return {
        "is_new": existing is None,
        "changed": changed,
        "added_tracks": added_tracks,
        "removed_tracks": removed_tracks,
    }


def load_playlist_dataset(user_id: str, playlist_id: str) -> dict | None:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        row = db.execute(
            """
            SELECT dataset_json
            FROM playlists
            WHERE user_id = ? AND playlist_id = ?
            """,
            (user_id, playlist_id),
        ).fetchone()
    return json.loads(row["dataset_json"]) if row else None


def load_artist_cache() -> dict:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        rows = db.execute(
            "SELECT artist_id, genres_json, image_url FROM artists"
        ).fetchall()
    return {
        row["artist_id"]: {
            "genres": json.loads(row["genres_json"] or "[]"),
            "image_url": row["image_url"],
        }
        for row in rows
    }


def playlist_snapshot_matches(user_id: str, playlist_id: str, snapshot_id: str | None) -> bool:
    if not snapshot_id:
        return False
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        row = db.execute(
            """
            SELECT 1 FROM playlists
            WHERE user_id = ? AND playlist_id = ? AND snapshot_id = ?
              AND is_active = 1
            """,
            (user_id, playlist_id, snapshot_id),
        ).fetchone()
    return row is not None


def refresh_playlist_metadata(user_id: str, metadata: dict) -> None:
    playlist_id = metadata.get("id")
    if not playlist_id:
        return
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        row = db.execute(
            "SELECT dataset_json FROM playlists WHERE user_id = ? AND playlist_id = ?",
            (user_id, playlist_id),
        ).fetchone()
        if not row:
            return
        dataset = json.loads(row["dataset_json"])
        dataset["playlist_name"] = metadata.get("name") or dataset.get("playlist_name")
        dataset["image"] = metadata.get("image")
        dataset["playlist_track_total"] = metadata.get("track_count", len(dataset.get("tracks") or []))
        db.execute(
            """
            UPDATE playlists SET
                name = ?, image_url = ?, track_total = ?, dataset_json = ?,
                owner_id = ?, collaborative = ?, snapshot_id = ?,
                is_liked = ?, is_active = 1, synced_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND playlist_id = ?
            """,
            (
                dataset["playlist_name"],
                dataset.get("image"),
                dataset["playlist_track_total"],
                json.dumps(dataset, ensure_ascii=False, separators=(",", ":")),
                metadata.get("owner_id"),
                int(bool(metadata.get("collaborative"))),
                metadata.get("snapshot_id"),
                int(bool(metadata.get("is_liked"))),
                user_id,
                playlist_id,
            ),
        )


def set_active_playlists(user_id: str, playlist_ids: list[str]) -> dict:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        active_ids = set(playlist_ids)
        removed = []
        for row in db.execute(
            "SELECT playlist_id, name FROM playlists WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ):
            if row["playlist_id"] not in active_ids:
                track_count = db.execute(
                    "SELECT COUNT(*) FROM playlist_tracks WHERE user_id = ? AND playlist_id = ?",
                    (user_id, row["playlist_id"]),
                ).fetchone()[0]
                removed.append({"id": row["playlist_id"], "name": row["name"], "track_count": track_count})
        db.execute("UPDATE playlists SET is_active = 0 WHERE user_id = ?", (user_id,))
        db.executemany(
            """
            UPDATE playlists SET is_active = 1
            WHERE user_id = ? AND playlist_id = ?
            """,
            [(user_id, playlist_id) for playlist_id in playlist_ids],
        )
    return {
        "removed_playlists": len(removed),
        "removed_tracks": sum(item["track_count"] for item in removed),
    }


def begin_sync_run(user_id: str) -> int | None:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        running = db.execute(
            "SELECT id FROM sync_runs WHERE user_id = ? AND status = 'running'",
            (user_id,),
        ).fetchone()
        if running:
            return None
        cursor = db.execute(
            "INSERT INTO sync_runs (user_id, status) VALUES (?, 'running')",
            (user_id,),
        )
        return int(cursor.lastrowid)


def update_sync_run(run_id: int, **values) -> None:
    allowed = {
        "total_playlists", "completed_playlists", "skipped_playlists",
        "tracks_processed", "current_playlist", "error",
        "new_playlists", "changed_playlists", "removed_playlists",
        "added_tracks", "removed_tracks",
    }
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            f"UPDATE sync_runs SET {assignments} WHERE id = ? AND status = 'running'",
            (*updates.values(), run_id),
        )


def finish_sync_run(run_id: int, status: str, error: str | None = None) -> None:
    if status not in {"complete", "error", "interrupted"}:
        raise ValueError(f"Invalid terminal sync status: {status}")
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            """
            UPDATE sync_runs
            SET status = ?, completed_at = CURRENT_TIMESTAMP,
                current_playlist = NULL, error = ?
            WHERE id = ?
            """,
            (status, error, run_id),
        )


def latest_sync_run(user_id: str) -> dict | None:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        row = db.execute(
            """
            SELECT *, ROUND(
                (julianday(COALESCE(completed_at, CURRENT_TIMESTAMP)) - julianday(started_at)) * 86400,
                1
            ) AS elapsed_seconds FROM sync_runs
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def sync_history(user_id: str, limit: int = 10) -> list[dict]:
    initialize_catalog()
    limit = max(1, min(int(limit), 50))
    with _DB_LOCK, closing(_connect()) as db, db:
        rows = db.execute(
            """
            SELECT *, ROUND(
                (julianday(COALESCE(completed_at, CURRENT_TIMESTAMP)) - julianday(started_at)) * 86400,
                1
            ) AS elapsed_seconds FROM sync_runs
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def library_health(user_id: str, detail_limit: int = 250) -> dict:
    """Analyze active local playlist memberships without contacting Spotify."""
    initialize_catalog()
    detail_limit = max(1, min(int(detail_limit), 1000))
    with _DB_LOCK, closing(_connect()) as db, db:
        base = """
            SELECT t.track_id, t.name, t.spotify_url, t.album_name,
                   COALESCE((
                       SELECT GROUP_CONCAT(a.name, ', ')
                       FROM track_artists ta JOIN artists a ON a.artist_id = ta.artist_id
                       WHERE ta.track_id = t.track_id
                       ORDER BY ta.position
                   ), 'Unknown artist') AS artists
            FROM tracks t
        """
        liked_exists = db.execute(
            "SELECT 1 FROM playlists WHERE user_id = ? AND playlist_id = '__liked__' AND is_active = 1",
            (user_id,),
        ).fetchone() is not None

        orphan_count = db.execute(
            """
            SELECT COUNT(DISTINCT liked.track_id)
            FROM playlist_tracks liked
            JOIN playlists lp ON lp.user_id = liked.user_id AND lp.playlist_id = liked.playlist_id
            WHERE liked.user_id = ? AND lp.is_liked = 1 AND lp.is_active = 1
              AND NOT EXISTS (
                  SELECT 1 FROM playlist_tracks other
                  JOIN playlists op ON op.user_id = other.user_id AND op.playlist_id = other.playlist_id
                  WHERE other.user_id = liked.user_id AND other.track_id = liked.track_id
                    AND op.is_active = 1 AND op.is_liked = 0
              )
            """,
            (user_id,),
        ).fetchone()[0]
        orphans = db.execute(
            base + """
            WHERE EXISTS (
                SELECT 1 FROM playlist_tracks liked
                JOIN playlists lp ON lp.user_id = liked.user_id AND lp.playlist_id = liked.playlist_id
                WHERE liked.user_id = ? AND liked.track_id = t.track_id
                  AND lp.is_liked = 1 AND lp.is_active = 1
            ) AND NOT EXISTS (
                SELECT 1 FROM playlist_tracks other
                JOIN playlists op ON op.user_id = other.user_id AND op.playlist_id = other.playlist_id
                WHERE other.user_id = ? AND other.track_id = t.track_id
                  AND op.is_active = 1 AND op.is_liked = 0
            ) ORDER BY t.name COLLATE NOCASE LIMIT ?
            """,
            (user_id, user_id, detail_limit),
        ).fetchall()

        unliked_count = db.execute(
            """
            SELECT COUNT(DISTINCT pt.track_id)
            FROM playlist_tracks pt
            JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
            WHERE pt.user_id = ? AND p.is_active = 1 AND p.is_liked = 0
              AND NOT EXISTS (
                  SELECT 1 FROM playlist_tracks liked
                  JOIN playlists lp ON lp.user_id = liked.user_id AND lp.playlist_id = liked.playlist_id
                  WHERE liked.user_id = pt.user_id AND liked.track_id = pt.track_id
                    AND lp.is_active = 1 AND lp.is_liked = 1
              )
            """,
            (user_id,),
        ).fetchone()[0]
        unliked = db.execute(
            base + """
            WHERE EXISTS (
                SELECT 1 FROM playlist_tracks pt
                JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
                WHERE pt.user_id = ? AND pt.track_id = t.track_id
                  AND p.is_active = 1 AND p.is_liked = 0
            ) AND NOT EXISTS (
                SELECT 1 FROM playlist_tracks liked
                JOIN playlists lp ON lp.user_id = liked.user_id AND lp.playlist_id = liked.playlist_id
                WHERE liked.user_id = ? AND liked.track_id = t.track_id
                  AND lp.is_active = 1 AND lp.is_liked = 1
            ) ORDER BY t.name COLLATE NOCASE LIMIT ?
            """,
            (user_id, user_id, detail_limit),
        ).fetchall()

        duplicate_count = db.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT pt.track_id
                FROM playlist_tracks pt
                JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
                WHERE pt.user_id = ? AND p.is_active = 1 AND p.is_liked = 0
                GROUP BY pt.track_id HAVING COUNT(DISTINCT pt.playlist_id) > 1
            )
            """,
            (user_id,),
        ).fetchone()[0]
        duplicates = db.execute(
            """
            SELECT t.track_id, t.name, t.spotify_url, t.album_name,
                   COALESCE((SELECT GROUP_CONCAT(a.name, ', ') FROM track_artists ta
                       JOIN artists a ON a.artist_id = ta.artist_id WHERE ta.track_id = t.track_id), 'Unknown artist') AS artists,
                   COUNT(DISTINCT pt.playlist_id) AS playlist_count,
                   GROUP_CONCAT(DISTINCT p.name) AS playlists
            FROM tracks t
            JOIN playlist_tracks pt ON pt.track_id = t.track_id
            JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
            WHERE pt.user_id = ? AND p.is_active = 1 AND p.is_liked = 0
            GROUP BY t.track_id HAVING COUNT(DISTINCT pt.playlist_id) > 1
            ORDER BY playlist_count DESC, t.name COLLATE NOCASE LIMIT ?
            """,
            (user_id, detail_limit),
        ).fetchall()

        playlist_stats = db.execute(
            """
            SELECT COUNT(*) AS active_playlists,
                   SUM(CASE WHEN track_total = 0 THEN 1 ELSE 0 END) AS empty_playlists,
                   MAX(track_total) AS largest_playlist
            FROM playlists WHERE user_id = ? AND is_active = 1 AND is_liked = 0
            """,
            (user_id,),
        ).fetchone()

    return {
        "status": "ready" if liked_exists else "sync_required",
        "detail_limit": detail_limit,
        "summary": {
            "orphan_liked": orphan_count,
            "not_liked": unliked_count,
            "duplicate_placements": duplicate_count,
            "active_playlists": playlist_stats["active_playlists"] or 0,
            "empty_playlists": playlist_stats["empty_playlists"] or 0,
            "largest_playlist": playlist_stats["largest_playlist"] or 0,
        },
        "orphan_liked": [dict(row) for row in orphans],
        "not_liked": [dict(row) for row in unliked],
        "duplicate_placements": [dict(row) for row in duplicates],
    }


def begin_enrichment_job(user_id: str, provider: str, batch_limit: int = 25) -> int | None:
    initialize_catalog()
    batch_limit = max(1, min(int(batch_limit), 100))
    with _DB_LOCK, closing(_connect()) as db, db:
        if db.execute(
            "SELECT 1 FROM enrichment_jobs WHERE user_id = ? AND provider = ? AND status = 'running'",
            (user_id, provider),
        ).fetchone():
            return None
        total = db.execute(
            """
            SELECT COUNT(DISTINCT pt.track_id) FROM playlist_tracks pt
            JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
            LEFT JOIN track_identities ti ON ti.track_id = pt.track_id
            WHERE pt.user_id = ? AND p.is_active = 1
              AND (ti.track_id IS NULL OR ti.match_status IN ('pending', 'error'))
            """,
            (user_id,),
        ).fetchone()[0]
        total = min(total, batch_limit)
        cursor = db.execute(
            "INSERT INTO enrichment_jobs (user_id, provider, status, total_tracks, batch_limit) VALUES (?, ?, 'running', ?, ?)",
            (user_id, provider, total, batch_limit),
        )
        return int(cursor.lastrowid)


def enrichment_candidates(user_id: str, limit: int | None = None) -> list[dict]:
    initialize_catalog()
    limit = max(1, min(int(limit), 100)) if limit is not None else None
    with _DB_LOCK, closing(_connect()) as db, db:
        rows = db.execute(
            """
            SELECT DISTINCT t.track_id, t.name, t.duration_ms, t.album_name, t.isrc,
                   COALESCE((SELECT GROUP_CONCAT(a.name, ', ') FROM track_artists ta
                       JOIN artists a ON a.artist_id = ta.artist_id WHERE ta.track_id = t.track_id), '') AS artists
            FROM tracks t
            JOIN playlist_tracks pt ON pt.track_id = t.track_id
            JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
            LEFT JOIN track_identities ti ON ti.track_id = t.track_id
            WHERE pt.user_id = ? AND p.is_active = 1
              AND (ti.track_id IS NULL OR ti.match_status IN ('pending', 'error'))
            ORDER BY t.name COLLATE NOCASE, t.track_id
            LIMIT COALESCE(?, -1)
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def save_track_identity(track_id: str, *, recording_id: str | None, status: str,
                        method: str, confidence: float | None, candidates: list[dict],
                        reason: str | None = None) -> None:
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            """
            INSERT INTO track_identities (
                track_id, musicbrainz_recording_id, match_status, match_method,
                confidence, decision_reason, candidates_json, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(track_id) DO UPDATE SET
                musicbrainz_recording_id = CASE WHEN manually_locked = 1 THEN musicbrainz_recording_id ELSE excluded.musicbrainz_recording_id END,
                match_status = CASE WHEN manually_locked = 1 THEN match_status ELSE excluded.match_status END,
                match_method = CASE WHEN manually_locked = 1 THEN match_method ELSE excluded.match_method END,
                confidence = CASE WHEN manually_locked = 1 THEN confidence ELSE excluded.confidence END,
                decision_reason = CASE WHEN manually_locked = 1 THEN decision_reason ELSE excluded.decision_reason END,
                candidates_json = CASE WHEN manually_locked = 1 THEN candidates_json ELSE excluded.candidates_json END,
                checked_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            """,
            (track_id, recording_id, status, method, confidence, reason, json.dumps(candidates)),
        )


def update_enrichment_job(job_id: int, **values) -> None:
    allowed = {"completed_tracks", "matched_tracks", "review_tracks", "missing_tracks", "failed_tracks", "current_track", "error"}
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(f"UPDATE enrichment_jobs SET {assignments} WHERE id = ? AND status = 'running'", (*updates.values(), job_id))


def finish_enrichment_job(job_id: int, status: str, error: str | None = None) -> None:
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            "UPDATE enrichment_jobs SET status = ?, completed_at = CURRENT_TIMESTAMP, current_track = NULL, error = ? WHERE id = ?",
            (status, error, job_id),
        )


def enrichment_status(user_id: str) -> dict:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        job = db.execute("SELECT * FROM enrichment_jobs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        counts = db.execute(
            """
            SELECT COUNT(DISTINCT ti.track_id) AS checked,
                   SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS matched,
                   SUM(CASE WHEN match_status = 'review' THEN 1 ELSE 0 END) AS review,
                   SUM(CASE WHEN match_status = 'missing' THEN 1 ELSE 0 END) AS missing
            FROM track_identities ti
            WHERE EXISTS (
                SELECT 1 FROM playlist_tracks pt
                JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
                WHERE pt.track_id = ti.track_id AND pt.user_id = ? AND p.is_active = 1
            )
            """,
            (user_id,),
        ).fetchone()
        recent = db.execute(
            """
            SELECT ti.track_id, t.name, t.album_name, ti.musicbrainz_recording_id,
                   ti.match_status, ti.match_method, ti.confidence, ti.candidates_json,
                   ti.decision_reason,
                   ti.checked_at,
                   COALESCE((SELECT GROUP_CONCAT(a.name, ', ') FROM track_artists ta
                       JOIN artists a ON a.artist_id = ta.artist_id WHERE ta.track_id = ti.track_id), '') AS artists
            FROM track_identities ti JOIN tracks t ON t.track_id = ti.track_id
            WHERE EXISTS (
                SELECT 1 FROM playlist_tracks pt
                JOIN playlists p ON p.user_id = pt.user_id AND p.playlist_id = pt.playlist_id
                WHERE pt.track_id = ti.track_id AND pt.user_id = ? AND p.is_active = 1
            )
            ORDER BY ti.checked_at DESC, t.name COLLATE NOCASE LIMIT 100
            """,
            (user_id,),
        ).fetchall()
    recent_matches = []
    for row in recent:
        item = dict(row)
        item["candidates"] = json.loads(item.pop("candidates_json") or "[]")
        recent_matches.append(item)
    return {
        "job": dict(job) if job else None,
        "identity_counts": {key: counts[key] or 0 for key in counts.keys()},
        "recent_matches": recent_matches,
    }


def save_selection(user_id: str, selected_ids: list[str], hidden_ids: list[str], breakdown_source: str | None) -> None:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        db.execute(
            """
            INSERT INTO user_preferences (user_id, selected_ids_json, hidden_ids_json, breakdown_source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                selected_ids_json = excluded.selected_ids_json,
                hidden_ids_json = excluded.hidden_ids_json,
                breakdown_source = excluded.breakdown_source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, json.dumps(selected_ids), json.dumps(hidden_ids), breakdown_source),
        )


def load_selection(user_id: str) -> dict:
    initialize_catalog()
    with _DB_LOCK, closing(_connect()) as db, db:
        row = db.execute(
            "SELECT selected_ids_json, hidden_ids_json, breakdown_source FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return {"selected_ids": [], "hidden_ids": [], "breakdown_source": None}
    return {
        "selected_ids": json.loads(row["selected_ids_json"] or "[]"),
        "hidden_ids": json.loads(row["hidden_ids_json"] or "[]"),
        "breakdown_source": row["breakdown_source"],
    }
