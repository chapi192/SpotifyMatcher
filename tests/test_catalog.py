import os
import tempfile
import unittest
from pathlib import Path

from web import catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_path = os.environ.get("MUSIC_DB_PATH")
        os.environ["MUSIC_DB_PATH"] = str(Path(self.temp_dir.name) / "catalog.sqlite3")
        catalog.initialize_catalog()

    def tearDown(self):
        if self.original_path is None:
            os.environ.pop("MUSIC_DB_PATH", None)
        else:
            os.environ["MUSIC_DB_PATH"] = self.original_path
        self.temp_dir.cleanup()

    def test_playlist_round_trip_and_snapshot_match(self):
        dataset = {
            "playlist_id": "playlist-1",
            "playlist_name": "Test playlist",
            "image": None,
            "tracks": [{
                "track_id": "track-1",
                "track_name": "Test track",
                "duration_ms": 123000,
                "explicit": False,
                "spotify_url": "https://open.spotify.com/track/track-1",
                "album": {
                    "album_id": "album-1",
                    "album_name": "Test album",
                    "release_date": "2026",
                    "total_tracks": 1,
                },
                "artists": [{
                    "artist_id": "artist-1",
                    "artist_name": "Test artist",
                    "genres": ["Test Genre"],
                    "image_url": None,
                }],
            }],
        }
        catalog.save_playlist_dataset(
            "user-1",
            dataset,
            metadata={"owner_id": "user-1", "snapshot_id": "snapshot-1"},
        )

        loaded = catalog.load_playlist_dataset("user-1", "playlist-1")
        self.assertEqual(loaded, dataset)
        self.assertTrue(catalog.playlist_snapshot_matches(
            "user-1", "playlist-1", "snapshot-1"
        ))
        self.assertFalse(catalog.playlist_snapshot_matches(
            "user-1", "playlist-1", "snapshot-2"
        ))
        self.assertEqual(
            catalog.load_artist_cache()["artist-1"]["genres"],
            ["Test Genre"],
        )

    def test_sync_run_and_selection_lifecycle(self):
        run_id = catalog.begin_sync_run("user-1")
        self.assertIsNotNone(run_id)
        self.assertIsNone(catalog.begin_sync_run("user-1"))

        catalog.update_sync_run(
            run_id,
            total_playlists=3,
            completed_playlists=1,
            current_playlist="Test playlist",
        )
        running = catalog.latest_sync_run("user-1")
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["completed_playlists"], 1)

        catalog.finish_sync_run(run_id, "complete")
        self.assertEqual(catalog.latest_sync_run("user-1")["status"], "complete")

        catalog.save_selection("user-1", ["p1", "p2"], ["p3"], "p1")
        self.assertEqual(catalog.load_selection("user-1"), {
            "selected_ids": ["p1", "p2"],
            "hidden_ids": ["p3"],
            "breakdown_source": "p1",
        })


if __name__ == "__main__":
    unittest.main()
