import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web import catalog
from web.routes.sync import _fetch_sync_targets, _run_sync


class FakeSpotify:
    def current_user_playlists(self, limit):
        return {
            "items": [
                {
                    "id": "owned",
                    "name": "Owned",
                    "owner": {"id": "me"},
                    "collaborative": False,
                    "items": {"total": 2},
                    "images": [],
                    "snapshot_id": "s1",
                },
                {
                    "id": "followed",
                    "name": "Followed",
                    "owner": {"id": "someone-else"},
                    "collaborative": False,
                    "items": {"total": 4},
                    "images": [],
                    "snapshot_id": "s2",
                },
                {
                    "id": "collaborative",
                    "name": "Collaborative",
                    "owner": {"id": "someone-else"},
                    "collaborative": True,
                    "tracks": {"total": 3},
                    "images": [],
                    "snapshot_id": "s3",
                },
            ],
            "next": None,
        }

    def current_user_saved_tracks(self, limit):
        return {"total": 5}


class SyncTargetTests(unittest.TestCase):
    def test_only_actionable_playlists_and_liked_songs_are_targets(self):
        targets = _fetch_sync_targets(FakeSpotify(), "me")
        self.assertEqual(
            [target["id"] for target in targets],
            ["owned", "collaborative", "__liked__"],
        )
        self.assertEqual(targets[0]["track_count"], 2)
        self.assertEqual(targets[1]["track_count"], 3)
        self.assertEqual(targets[2]["track_count"], 5)


class SyncWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_path = os.environ.get("MUSIC_DB_PATH")
        os.environ["MUSIC_DB_PATH"] = str(Path(self.temp_dir.name) / "sync.sqlite3")
        os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-client")
        os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-secret")
        os.environ.setdefault("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
        catalog.initialize_catalog()

    def tearDown(self):
        if self.original_path is None:
            os.environ.pop("MUSIC_DB_PATH", None)
        else:
            os.environ["MUSIC_DB_PATH"] = self.original_path
        self.temp_dir.cleanup()

    @patch("web.routes.sync.fetch_single_playlist")
    @patch("web.routes.sync._fetch_sync_targets")
    @patch("web.routes.sync.spotipy.Spotify")
    @patch("web.routes.enrichment.launch_full_enrichment")
    def test_worker_persists_dataset_and_completes_run(
        self, launch_enrichment, spotify_class, fetch_targets, fetch_playlist
    ):
        fetch_targets.return_value = [{
            "id": "playlist-1",
            "name": "Playlist",
            "track_count": 0,
            "image": None,
            "is_owner": True,
            "owner_id": "user-1",
            "collaborative": False,
            "snapshot_id": "snapshot-1",
            "is_liked": False,
        }]
        fetch_playlist.return_value = {
            "playlist_id": "playlist-1",
            "playlist_name": "Playlist",
            "image": None,
            "playlist_track_total": 0,
            "tracks": [],
        }
        run_id = catalog.begin_sync_run("user-1")

        _run_sync(run_id, "user-1", {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_at": 9999999999,
            "scope": "user-read-private playlist-read-private playlist-read-collaborative user-library-read",
        })

        sync = catalog.latest_sync_run("user-1")
        self.assertEqual(sync["status"], "complete")
        self.assertEqual(sync["new_playlists"], 1)
        self.assertEqual(sync["changed_playlists"], 0)
        self.assertEqual(sync["skipped_playlists"], 0)
        launch_enrichment.assert_called_once_with("user-1")
        self.assertIsNotNone(catalog.load_playlist_dataset("user-1", "playlist-1"))
        spotify_class.assert_called_once()


if __name__ == "__main__":
    unittest.main()
