from itertools import count

from fastapi import APIRouter, Request
from web.spotify_auth import get_spotify_client
from web.routes.library import get_active_dataset_and_profiles
import math
import statistics
from collections import Counter

router = APIRouter()


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------

def get_dataset(request: Request):
    sp = get_spotify_client(request)
    if not sp:
        return None, {"status": "error", "message": "Not logged in"}

    dataset, profiles, err = get_active_dataset_and_profiles(request, sp)
    if err:
        return None, err

    return (dataset, profiles), None


# ------------------------------------------------------------
# Average Length
# ------------------------------------------------------------

@router.get("/api/avg-length")
def avg_length(request: Request):

    result, err = get_dataset(request)
    if err:
        return err

    dataset, _profiles = result

    def compute_stats(durations, tracks):

        n = len(durations)
        if n == 0:
            return None

        durations_sorted = sorted(durations)

        avg = sum(durations_sorted) / n

        if n % 2:
            median = durations_sorted[n // 2]
        else:
            median = (
                durations_sorted[n // 2 - 1] +
                durations_sorted[n // 2]
            ) / 2

        min_v = min(durations)
        max_v = max(durations)

        variance = sum((x - avg) ** 2 for x in durations) / n
        std_dev = math.sqrt(variance)

        short_pct = len([x for x in durations if x < 150]) / n * 100
        long_pct = len([x for x in durations if x > 300]) / n * 100
        radio_pct = len([x for x in durations if 150 <= x <= 270]) / n * 100

        # Total runtime (seconds)
        total_runtime_seconds = sum(durations)

        # Flow density: % of tracks within ±30 sec of average
        flow_band = 30
        flow_count = len([
            x for x in durations
            if abs(x - avg) <= flow_band
        ])
        flow_density = (flow_count / n) * 100

        # Find actual track objects
        shortest_track = min(tracks, key=lambda t: t["duration_ms"])
        longest_track = max(tracks, key=lambda t: t["duration_ms"])

        return {
            "average_length_seconds": round(avg, 2),
            "median_length_seconds": round(median, 2),
            "std_dev_seconds": round(std_dev, 2),
            "track_count": n,
            "short_pct": round(short_pct, 2),
            "long_pct": round(long_pct, 2),
            "radio_pct": round(radio_pct, 2),
            "durations": durations_sorted,
            "total_runtime_seconds": round(total_runtime_seconds, 2),
            "flow_density_pct": round(flow_density, 2),
            "shortest_track": {
                "name": shortest_track["track_name"],
                "seconds": round(min_v, 2),
                "url": shortest_track["spotify_url"]
            },
            "longest_track": {
                "name": longest_track["track_name"],
                "seconds": round(max_v, 2),
                "url": longest_track["spotify_url"]
            }
        }               

    combined_durations = []
    combined_tracks = []
    per_playlist = {}

    for pid, playlist in dataset.items():

        durations = []

        for track in playlist.get("tracks", []):
            duration = track.get("duration_ms")
            if duration:
                durations.append(duration / 1000)

        stats = compute_stats(durations, playlist["tracks"])

        if not stats:
            continue

        per_playlist[pid] = {
            "playlist_name": playlist["playlist_name"],
            **stats
        }

        combined_durations.extend(durations)
        combined_tracks.extend(playlist["tracks"])

    if not combined_durations:
        return {"status": "empty"}

    combined_stats = compute_stats(combined_durations, combined_tracks)

    return {
        "status": "ready",
        "data": {
            "combined": combined_stats,
            "playlists": per_playlist
        }
    }


# ------------------------------------------------------------
# Popularity
# ------------------------------------------------------------

@router.get("/api/popularity")
def popularity(request: Request):

    result, err = get_dataset(request)
    if err:
        return err

    dataset, _profiles = result

    def compute_metrics(tracks):

        popularities = [
            t.get("popularity")
            for t in tracks
            if t.get("popularity") is not None
        ]

        if not popularities:
            return None

        n = len(popularities)

        avg_pop = statistics.mean(popularities)
        median_pop = statistics.median(popularities)
        std_dev = statistics.pstdev(popularities) if n > 1 else 0

        # Tier breakdown
        tiers = {
            "underground": len([p for p in popularities if p < 30]),
            "emerging": len([p for p in popularities if 30 <= p < 60]),
            "popular": len([p for p in popularities if 60 <= p < 80]),
            "hit": len([p for p in popularities if p >= 80]),
        }

        tier_pct = {
            k: round((v / n) * 100, 1)
            for k, v in tiers.items()
        }

        # Extremes
        most_popular = max(
            tracks,
            key=lambda t: t.get("popularity", -1)
        )

        least_popular = min(
            tracks,
            key=lambda t: t.get("popularity", 101)
        )

        # Derived metrics
        mainstream_index = round(avg_pop * (1 - std_dev / 100), 1)

        if std_dev < 15:
            spread_label = "Highly Consistent"
        elif std_dev < 30:
            spread_label = "Balanced Mix"
        else:
            spread_label = "Wide Popularity Range"

        return {
            "average_popularity": round(avg_pop, 1),
            "median_popularity": round(median_pop, 1),
            "std_dev": round(std_dev, 1),
            "track_count": n,
            "distribution": popularities,
            "tier_counts": tiers,
            "tier_percentages": tier_pct,
            "mainstream_index": mainstream_index,
            "popularity_spread_label": spread_label,
            "most_popular_track": {
                "name": most_popular["track_name"],
                "popularity": most_popular["popularity"],
                "url": most_popular["spotify_url"]
            },
            "least_popular_track": {
                "name": least_popular["track_name"],
                "popularity": least_popular["popularity"],
                "url": least_popular["spotify_url"]
            }
        }

    combined_tracks = []
    per_playlist = {}

    for pid, playlist in dataset.items():

        tracks = playlist.get("tracks", [])

        stats = compute_metrics(tracks)

        if not stats:
            continue

        per_playlist[pid] = {
            "playlist_name": playlist["playlist_name"],
            **stats
        }

        combined_tracks.extend(tracks)

    if not combined_tracks:
        return {"status": "empty"}

    combined_stats = compute_metrics(combined_tracks)

    return {
        "status": "ready",
        "data": {
            "combined": combined_stats,
            "playlists": per_playlist
        }
    }

# ------------------------------------------------------------
# Artist Frequency
# ------------------------------------------------------------

@router.get("/api/artist-frequency")
def artist_frequency(request: Request):

    result, err = get_dataset(request)
    if err:
        return err

    dataset, _profiles = result

    def compute_artist_metrics(tracks):

        import math

        total_tracks = 0
        total_artist_instances = 0
        max_artists_on_track = 0
        multi_artist_tracks = 0
        max_artist_track = None

        counts = {}
        artist_meta_lookup = {}

        for track in tracks:
            total_tracks += 1

            track_artists = track.get("artists", [])
            artist_count_on_track = len(track_artists)

            total_artist_instances += artist_count_on_track

            if artist_count_on_track > max_artists_on_track:
                max_artists_on_track = artist_count_on_track
                max_artist_track = track

            if artist_count_on_track > 1:
                multi_artist_tracks += 1

            for artist in track_artists:
                artist_id = artist.get("artist_id")
                artist_name = artist.get("artist_name")

                if not artist_id or not artist_name:
                    continue

                counts[artist_id] = counts.get(artist_id, 0) + 1

                # store metadata once
                if artist_id not in artist_meta_lookup:
                    artist_meta_lookup[artist_id] = {
                        "artist_name": artist_name,
                        "image_url": artist.get("image_url")
                    }

        if not counts or total_artist_instances == 0:
            return None

        sorted_artists = sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        unique_artists = len(sorted_artists)

        # ---------------------------------
        # Top Artist
        # ---------------------------------

        top_artist_id = sorted_artists[0][0]
        top_artist_count = sorted_artists[0][1]

        top_artist_name = artist_meta_lookup[top_artist_id]["artist_name"]

        # we assume artist_id is available in track["artists"]
        top_artist_id = None
        for track in tracks:
            for artist in track.get("artists", []):
                if artist.get("artist_name") == top_artist_name:
                    top_artist_id = artist.get("artist_id")
                    break
            if top_artist_id:
                break

        dominance_pct = round(top_artist_count / total_artist_instances * 100, 1)

        # ---------------------------------
        # Long Tail
        # ---------------------------------

        artists_1x = len([c for _, c in sorted_artists if c == 1])
        unique_appearance_pct = round(artists_1x / unique_artists * 100, 1)

        # ---------------------------------
        # Diversity + Concentration
        # ---------------------------------

        entropy = 0
        hhi = 0

        for _, count in sorted_artists:
            p = count / total_artist_instances
            entropy += -p * math.log(p)
            hhi += p ** 2

        max_entropy = math.log(unique_artists) if unique_artists > 1 else 1
        diversity_score = round((entropy / max_entropy) * 100, 1)

        concentration_value = hhi * 100

        # categorical mapping
        if concentration_value < 2:
            concentration = "Very Diverse"
        elif concentration_value < 5:
            concentration = "Diverse"
        elif concentration_value < 10:
            concentration = "Balanced"
        elif concentration_value < 25:
            concentration = "Leaning"
        else:
            concentration = "Dominated"

        # ---------------------------------
        # Averages
        # ---------------------------------

        avg_tracks_per_artist = round(total_artist_instances / unique_artists, 2)
        avg_artists_per_track = round(total_artist_instances / total_tracks, 2)
        multi_artist_track_pct = round(multi_artist_tracks / total_tracks * 100, 1)

        # ---------------------------------
        # Max Artist Track Info
        # ---------------------------------

        max_artist_track_name = None
        max_artist_track_id = None

        if max_artist_track:
            max_artist_track_name = max_artist_track.get("track_name")
            max_artist_track_id = max_artist_track.get("track_id")

        return {
            "track_count": total_tracks,
            "unique_artists": unique_artists,

            "diversity_score": diversity_score,
            "concentration": concentration,

            "top_artist_name": top_artist_name,
            "top_artist_id": top_artist_id,
            "dominance_pct": dominance_pct,

            "unique_appearance_pct": unique_appearance_pct,

            "avg_tracks_per_artist": avg_tracks_per_artist,

            "avg_artists_per_track": avg_artists_per_track,
            "multi_artist_track_pct": multi_artist_track_pct,

            "max_artists_on_track": max_artists_on_track,
            "max_artist_track_name": max_artist_track_name,
            "max_artist_track_id": max_artist_track_id,

            "top_10": [
                {
                    "artist_id": artist_id,
                    "artist_name": artist_meta_lookup[artist_id]["artist_name"],
                    "count": count,
                    "image_url": artist_meta_lookup[artist_id]["image_url"]
                }
                for artist_id, count in sorted_artists[:10]
            ]
        }

    combined_tracks = []
    per_playlist = {}

    for pid, playlist in dataset.items():

        tracks = playlist.get("tracks", [])

        stats = compute_artist_metrics(tracks)
        if not stats:
            continue

        per_playlist[pid] = {
            "playlist_name": playlist["playlist_name"],
            **stats
        }

        combined_tracks.extend(tracks)

    if not combined_tracks:
        return {"status": "empty"}

    combined_stats = compute_artist_metrics(combined_tracks)

    return {
        "status": "ready",
        "data": {
            "combined": combined_stats,
            "playlists": per_playlist
        }
    }

# ------------------------------------------------------------
# Release Years
# ------------------------------------------------------------

@router.get("/api/release-years")
def release_years(request: Request):

    result, err = get_dataset(request)
    if err:
        return err

    dataset, _profiles = result

    def compute_year_metrics(tracks):

        oldest_track = None
        newest_track = None

        years = []

        for track in tracks:
            release_date = track.get("album", {}).get("release_date")
            if release_date and len(release_date) >= 4:
                try:
                    years.append(int(release_date[:4]))
                except:
                    continue

        if not years:
            return None

        counts = Counter(years)

        oldest = min(years)
        newest = max(years)
        median_year = int(statistics.median(years))
        span = newest - oldest

        for track in tracks:
            release_date = track.get("album", {}).get("release_date")
            if release_date and len(release_date) >= 4:
                year = int(release_date[:4])

                if year == oldest and not oldest_track:
                    oldest_track = {
                        "name": track.get("name"),
                        "url": track.get("external_urls", {}).get("spotify")
                    }

                if year == newest and not newest_track:
                    newest_track = {
                        "name": track.get("name"),
                        "url": track.get("external_urls", {}).get("spotify")
                    }

        # Decade buckets
        decade_counts = {}
        for y in years:
            decade = (y // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + 1

        sorted_years = dict(sorted(counts.items()))
        sorted_decades = dict(sorted(decade_counts.items()))

        # Recency score
        avg_year = statistics.mean(years)
        recency_score = round((avg_year - oldest) / (span + 1) * 100, 1)

        return {
            "track_count": len(years),
            "year_counts": sorted_years,
            "decade_counts": sorted_decades,
            "oldest_year": oldest,
            "newest_year": newest,
            "median_year": median_year,
            "year_span": span,
            "recency_score": recency_score, 
            "oldest_track": oldest_track,
            "newest_track": newest_track
        }

    combined_tracks = []
    per_playlist = {}

    for pid, playlist in dataset.items():

        tracks = playlist.get("tracks", [])

        stats = compute_year_metrics(tracks)
        if not stats:
            continue

        per_playlist[pid] = {
            "playlist_name": playlist["playlist_name"],
            **stats
        }

        combined_tracks.extend(tracks)

    if not combined_tracks:
        return {"status": "empty"}

    combined_stats = compute_year_metrics(combined_tracks)

    return {
        "status": "ready",
        "data": {
            "combined": combined_stats,
            "playlists": per_playlist
        }
    }

# ------------------------------------------------------------
# Playlist Profile
# ------------------------------------------------------------

@router.get("/api/playlist-profile")
def playlist_profile(request: Request):

    result, err = get_dataset(request)
    if err:
        return err

    dataset, profiles = result

    if not profiles:
        return {"status": "empty"}

    # DEFINE THIS FIRST
    def compute_profile_metrics(profile):

        track_count = profile.get("track_count", 0)
        genre_counts = profile.get("genre_counts", {})
        decade_counts = profile.get("decade_counts", {})

        if not track_count:
            return None

        # Top genre
        if genre_counts:
            sorted_genres = sorted(
                genre_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            top_genre, top_genre_count = sorted_genres[0]
            top_genre_pct = round(top_genre_count / track_count * 100, 1)
            genre_spread = len(genre_counts)
        else:
            top_genre = None
            top_genre_pct = 0
            genre_spread = 0

        # Decade focus
        if decade_counts:
            sorted_decades = sorted(
                decade_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            dominant_decade, dominant_count = sorted_decades[0]
            decade_focus_pct = round(dominant_count / track_count * 100, 1)
        else:
            dominant_decade = None
            decade_focus_pct = 0

        diversity_score = round(
            (profile.get("unique_artists", 0) / track_count) * 100,
            1
        )

        return {
            **profile,
            "top_genre": top_genre,
            "top_genre_pct": top_genre_pct,
            "genre_spread": genre_spread,
            "dominant_decade": dominant_decade,
            "decade_focus_pct": decade_focus_pct,
            "diversity_score": diversity_score
        }

    per_playlist = {}

    for pid, profile in profiles.items():
        stats = compute_profile_metrics(profile)
        if stats:
            per_playlist[pid] = stats

    # Combined aggregation
    combined_profile = {
        "track_count": 0,
        "avg_duration_ms": 0,
        "avg_track_popularity": 0,
        "unique_artists": 0,
        "genre_counts": {},
        "decade_counts": {}
    }

    total_playlists = len(per_playlist)

    for profile in per_playlist.values():

        combined_profile["track_count"] += profile["track_count"]
        combined_profile["avg_duration_ms"] += profile["avg_duration_ms"]
        combined_profile["avg_track_popularity"] += profile["avg_track_popularity"]
        combined_profile["unique_artists"] += profile["unique_artists"]

        for g, c in profile.get("genre_counts", {}).items():
            combined_profile["genre_counts"][g] = (
                combined_profile["genre_counts"].get(g, 0) + c
            )

        for d, c in profile.get("decade_counts", {}).items():
            combined_profile["decade_counts"][d] = (
                combined_profile["decade_counts"].get(d, 0) + c
            )

    if combined_profile["track_count"] > 0 and total_playlists > 0:
        combined_profile["avg_duration_ms"] = round(
            combined_profile["avg_duration_ms"] / total_playlists,
            0
        )
        combined_profile["avg_track_popularity"] = round(
            combined_profile["avg_track_popularity"] / total_playlists,
            2
        )

        combined_profile = compute_profile_metrics(combined_profile)
    else:
        combined_profile = None

    return {
        "status": "ready",
        "data": {
            "combined": combined_profile,
            "playlists": per_playlist
        }
    }