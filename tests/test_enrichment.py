import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from web import catalog
from web.services.musicbrainz import _search_title, match_recording


class MusicBrainzTests(unittest.TestCase):
    def test_search_title_removes_remaster_decoration(self):
        self.assertEqual(_search_title('"Heroes" - 2017 Remaster'), "Heroes")
        self.assertEqual(_search_title("Song (Remastered Version)"), "Song")

    def test_metadata_match_uses_score_and_duration(self):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"recordings": [{
            "id": "mbid-1", "title": "Track", "score": 98, "length": 180500,
            "artist-credit": [{"name": "Artist"}],
        }]}
        session = Mock()
        session.get.return_value = response

        result = match_recording({
            "name": "Track", "artists": "Artist", "duration_ms": 180000, "isrc": None,
        }, session=session)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["recording_id"], "mbid-1")
        self.assertIn("recording", session.get.call_args.args[0])

    def test_low_confidence_match_is_held_for_review(self):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"recordings": [{
            "id": "maybe", "title": "Track", "score": 70, "length": 180000,
            "artist-credit": [{"name": "Artist"}],
        }]}
        session = Mock()
        session.get.return_value = response

        result = match_recording({"name": "Track", "artists": "Artist", "duration_ms": 180000}, session=session)

        self.assertEqual(result["status"], "review")
        self.assertIsNone(result["recording_id"])

    def test_closest_duration_breaks_equal_search_scores(self):
        response = Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.json.return_value = {"recordings": [
            {"id": "wrong-version", "title": "Song", "score": 100, "length": 300000, "artist-credit": [{"name": "Artist"}]},
            {"id": "right-version", "title": "Song", "score": 100, "length": 180500, "artist-credit": [{"name": "Artist"}]},
        ]}
        session = Mock()
        session.get.return_value = response

        result = match_recording({"name": "Song", "artists": "Artist", "duration_ms": 180000}, session=session)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["recording_id"], "right-version")

    @patch("web.services.musicbrainz.time.sleep")
    def test_temporary_unavailability_is_retried(self, sleep):
        unavailable = Mock(status_code=503, headers={})
        success = Mock(status_code=200, headers={})
        success.raise_for_status.return_value = None
        success.json.return_value = {"recordings": []}
        session = Mock()
        session.get.side_effect = [unavailable, success]

        result = match_recording({"name": "Track", "artists": "Artist"}, session=session)

        self.assertEqual(result["status"], "missing")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(1.05)


class EnrichmentCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_path = os.environ.get("MUSIC_DB_PATH")
        os.environ["MUSIC_DB_PATH"] = str(Path(self.temp_dir.name) / "enrichment.sqlite3")
        catalog.initialize_catalog()
        catalog.save_playlist_dataset("user-1", {
            "playlist_id": "playlist-1", "playlist_name": "Playlist",
            "tracks": [{"track_id": "track-1", "track_name": "Track", "isrc": "USABC1234567", "artists": []}],
        })

    def tearDown(self):
        if self.original_path is None:
            os.environ.pop("MUSIC_DB_PATH", None)
        else:
            os.environ["MUSIC_DB_PATH"] = self.original_path
        self.temp_dir.cleanup()

    def test_identity_and_job_progress_are_durable(self):
        candidates = catalog.enrichment_candidates("user-1")
        self.assertEqual(candidates[0]["isrc"], "USABC1234567")
        job_id = catalog.begin_enrichment_job("user-1", "musicbrainz", batch_limit=10)
        self.assertIsNotNone(job_id)
        self.assertIsNone(catalog.begin_enrichment_job("user-1", "musicbrainz"))

        catalog.save_track_identity(
            "track-1", recording_id="mbid-1", status="matched", method="isrc",
            confidence=1.0, candidates=[],
        )
        catalog.update_enrichment_job(job_id, completed_tracks=1, matched_tracks=1)
        catalog.finish_enrichment_job(job_id, "complete")

        status = catalog.enrichment_status("user-1")
        self.assertEqual(status["job"]["status"], "complete")
        self.assertEqual(status["job"]["batch_limit"], 10)
        self.assertEqual(status["job"]["failed_tracks"], 0)
        self.assertEqual(status["identity_counts"]["matched"], 1)
        self.assertEqual(status["recent_matches"][0]["musicbrainz_recording_id"], "mbid-1")
        self.assertEqual(catalog.enrichment_candidates("user-1"), [])


if __name__ == "__main__":
    unittest.main()
