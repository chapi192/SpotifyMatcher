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

        counts = {}
        total_tracks = 0

        for track in tracks:
            total_tracks += 1
            for artist in track.get("artists", []):
                name = artist.get("artist_name")
                if not name:
                    continue
                counts[name] = counts.get(name, 0) + 1

        if not counts:
            return None

        sorted_artists = sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        top_10 = sorted_artists[:10]
        top_5_total = sum(c for _, c in sorted_artists[:5])
        top_1_total = sorted_artists[0][1]

        dominance_pct = round(top_1_total / total_tracks * 100, 1)
        concentration_pct = round(top_5_total / total_tracks * 100, 1)

        long_tail_count = len([c for _, c in sorted_artists if c == 1])
        long_tail_pct = round(long_tail_count / len(sorted_artists) * 100, 1)

        artist_density = round(len(sorted_artists) / total_tracks, 2)

        return {
            "track_count": total_tracks,
            "unique_artists": len(sorted_artists),
            "artist_density": artist_density,
            "dominance_pct": dominance_pct,
            "concentration_pct": concentration_pct,
            "long_tail_pct": long_tail_pct,
            "top_10": [
                {"artist_name": n, "count": c}
                for n, c in top_10
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
            "recency_score": recency_score
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