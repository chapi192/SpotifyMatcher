import json
import os
import sqlite3
import threading
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
    with _DB_LOCK, _connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                user_id TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                name TEXT NOT NULL,
                image_url TEXT,
                track_total INTEGER NOT NULL DEFAULT 0,
                dataset_json TEXT NOT NULL,
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
            """
        )


def save_playlist_dataset(user_id: str, dataset: dict) -> None:
    if not user_id or not dataset:
        return

    playlist_id = dataset.get("playlist_id")
    if not playlist_id:
        return

    tracks = dataset.get("tracks") or []
    payload = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))

    with _DB_LOCK, _connect() as db:
        db.execute(
            """
            INSERT INTO playlists (
                user_id, playlist_id, name, image_url, track_total, dataset_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, playlist_id) DO UPDATE SET
                name = excluded.name,
                image_url = excluded.image_url,
                track_total = excluded.track_total,
                dataset_json = excluded.dataset_json,
                synced_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                playlist_id,
                dataset.get("playlist_name") or playlist_id,
                dataset.get("image"),
                len(tracks),
                payload,
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
                    album_id, album_name, release_date, album_track_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    name = excluded.name,
                    duration_ms = excluded.duration_ms,
                    explicit = excluded.explicit,
                    spotify_url = excluded.spotify_url,
                    album_id = excluded.album_id,
                    album_name = excluded.album_name,
                    release_date = excluded.release_date,
                    album_track_total = excluded.album_track_total,
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


def load_playlist_dataset(user_id: str, playlist_id: str) -> dict | None:
    initialize_catalog()
    with _DB_LOCK, _connect() as db:
        row = db.execute(
            """
            SELECT dataset_json
            FROM playlists
            WHERE user_id = ? AND playlist_id = ?
            """,
            (user_id, playlist_id),
        ).fetchone()
    return json.loads(row["dataset_json"]) if row else None

