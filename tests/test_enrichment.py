import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from web import catalog
from web.services.musicbrainz import _search_title, match_recording
from web.services import feature_providers
from web.routes.enrichment import run_full_enrichment_pipeline, run_retry_enrichment_pipeline


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
        self.assertIn("passed", result["reason"])
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
        self.assertIn("below", result["reason"])

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
        self.assertIn("no recording", result["reason"])
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
            reason="Accepted test identity.",
        )
        catalog.update_enrichment_job(job_id, completed_tracks=1, matched_tracks=1)
        catalog.finish_enrichment_job(job_id, "complete")

        status = catalog.enrichment_status("user-1")
        self.assertEqual(status["job"]["status"], "complete")
        self.assertEqual(status["job"]["batch_limit"], 10)
        self.assertEqual(status["job"]["failed_tracks"], 0)
        self.assertEqual(status["identity_counts"]["matched"], 1)
        self.assertEqual(status["recent_matches"][0]["musicbrainz_recording_id"], "mbid-1")
        self.assertEqual(status["recent_matches"][0]["decision_reason"], "Accepted test identity.")
        self.assertEqual(catalog.enrichment_candidates("user-1"), [])

        catalog.save_provider_result("track-1", "listenbrainz", "complete", [
            {"name": "tags", "value": [{"name": "rock", "count": 4}]},
        ])
        comparison = catalog.feature_comparison("user-1")
        self.assertEqual(comparison[0]["providers"]["listenbrainz"]["features"]["tags"]["value"][0]["name"], "rock")
        self.assertEqual(catalog.feature_enrichment_candidates("user-1", "listenbrainz"), [])

        profile = catalog.track_profile("user-1", "track-1")
        self.assertEqual(profile["track"]["name"], "Track")
        self.assertEqual(profile["identity"]["musicbrainz_recording_id"], "mbid-1")
        self.assertEqual(profile["in_playlists"][0]["name"], "Playlist")
        self.assertEqual(profile["providers"]["listenbrainz"]["status"], "complete")
        self.assertIsNone(catalog.track_profile("another-user", "track-1"))

    def test_retry_candidates_include_unsuccessful_results(self):
        catalog.save_track_identity(
            "track-1", recording_id=None, status="missing", method="metadata",
            confidence=None, candidates=[], reason="No candidate found.",
        )
        self.assertEqual(catalog.enrichment_candidates("user-1"), [])
        self.assertEqual(
            [item["track_id"] for item in catalog.enrichment_candidates(
                "user-1", retry_unsuccessful=True,
            )],
            ["track-1"],
        )

        catalog.save_track_identity(
            "track-1", recording_id="mbid-1", status="matched", method="metadata",
            confidence=1.0, candidates=[], reason="Matched.",
        )
        catalog.save_provider_result("track-1", "listenbrainz", "missing", [], "No entry.")
        self.assertEqual(catalog.feature_enrichment_candidates("user-1", "listenbrainz"), [])
        self.assertEqual(
            [item["track_id"] for item in catalog.feature_enrichment_candidates(
                "user-1", "listenbrainz", retry_unsuccessful=True,
            )],
            ["track-1"],
        )


class FeatureProviderTests(unittest.TestCase):
    @patch("web.services.feature_providers._get_optional")
    def test_acousticbrainz_normalizes_selected_features(self, get):
        get.side_effect = [
            {"highlevel": {"mood_happy": {"value": "happy", "probability": 0.8}}},
            {"rhythm": {"bpm": 120.5}, "tonal": {"key_key": "C", "key_scale": "major"}, "lowlevel": {"dynamic_complexity": 4.2}},
        ]
        observations = feature_providers.acousticbrainz({"musicbrainz_recording_id": "mbid"})
        values = {item["name"]: item["value"] for item in observations}
        self.assertEqual(values["mood_happy"], "happy")
        self.assertEqual(values["bpm"], 120.5)
        self.assertEqual(values["key"], "C")

    @patch("web.services.feature_providers._get")
    def test_listenbrainz_combines_and_ranks_tags(self, get):
        get.return_value = {"mbid": {"tag": {
            "recording": [{"tag": "rock", "count": 5}],
            "artist": [{"tag": "indie", "count": 8}, {"tag": "rock", "count": 3}],
        }, "recording": {"first_release_date": "2020-01-01", "isrcs": ["ABC"]}}}
        observations = feature_providers.listenbrainz({"musicbrainz_recording_id": "mbid"})
        values = {item["name"]: item["value"] for item in observations}
        self.assertEqual([tag["name"] for tag in values["tags"]], ["indie", "rock"])
        self.assertEqual(values["isrcs"], ["ABC"])

    @patch("web.services.feature_providers._get")
    def test_reccobeats_rejects_fuzzy_wrong_recording(self, get):
        get.return_value = {"content": [{
            "id": "remix", "trackTitle": "Song Remix", "durationMs": 180000,
            "artists": [{"name": "Artist"}],
        }]}
        result = feature_providers.reccobeats({"name": "Song", "artists": "Artist", "duration_ms": 180000})
        self.assertEqual(result, [])
        self.assertEqual(get.call_count, 1)

    @patch("web.routes.enrichment._run_feature_job")
    @patch("web.routes.enrichment._run_musicbrainz_job")
    @patch("web.routes.enrichment.begin_feature_enrichment_job")
    @patch("web.routes.enrichment.begin_enrichment_job")
    def test_full_pipeline_runs_identity_then_every_provider(
        self, begin_identity, begin_feature, run_identity, run_feature
    ):
        begin_identity.return_value = 1
        begin_feature.side_effect = [2, 3, 4]

        run_full_enrichment_pipeline("user-1")

        run_identity.assert_called_once_with(1, "user-1", 10000)
        self.assertEqual(
            [call.args[2] for call in run_feature.call_args_list],
            ["acousticbrainz", "listenbrainz", "reccobeats"],
        )

    @patch("web.routes.enrichment._run_feature_job")
    @patch("web.routes.enrichment._run_musicbrainz_job")
    @patch("web.routes.enrichment.begin_feature_enrichment_job")
    @patch("web.routes.enrichment.begin_enrichment_job")
    def test_retry_pipeline_rechecks_only_unsuccessful_results(
        self, begin_identity, begin_feature, run_identity, run_feature
    ):
        begin_identity.return_value = 11
        begin_feature.side_effect = [12, 13]

        run_retry_enrichment_pipeline("user-1")

        self.assertTrue(begin_identity.call_args.kwargs["retry_unsuccessful"])
        self.assertTrue(run_identity.call_args.kwargs["retry_unsuccessful"])
        self.assertEqual(
            [call.args[1] for call in begin_feature.call_args_list],
            ["acousticbrainz", "listenbrainz"],
        )
        self.assertTrue(all(
            call.kwargs["retry_unsuccessful"] for call in run_feature.call_args_list
        ))


if __name__ == "__main__":
    unittest.main()
