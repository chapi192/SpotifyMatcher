from collections import Counter
import statistics

def build_playlist_profiles(dataset):

    profiles = {}

    for pid, playlist in dataset.items():

        tracks = playlist["tracks"]

        if not tracks:
            continue

        durations = []
        track_pops = []
        artist_counter = Counter()
        genre_counter = Counter()
        decade_counter = Counter()

        for track in tracks:
            try:
                if track.get("duration_ms"):
                    durations.append(track["duration_ms"])

                if track.get("popularity") is not None:
                    track_pops.append(track["popularity"])

                album = track.get("album") or {}
                release_date = album.get("release_date")

                if isinstance(release_date, str) and len(release_date) >= 4:
                    try:
                        year = int(release_date[:4])
                        decade = (year // 10) * 10
                        decade_counter[decade] += 1
                    except Exception:
                        pass

                for artist in track.get("artists", []):
                    name = artist.get("artist_name")
                    if name:
                        artist_counter[name] += 1

                    for genre in artist.get("genres", []):
                        genre_counter[genre] += 1
                
            except Exception as e:
                print("PROFILE ERROR ON TRACK:")
                print(track)
                raise

        profiles[pid] = {
            "playlist_id": pid,
            "playlist_name": playlist["playlist_name"],
            "track_count": len(tracks),
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
            "avg_track_popularity": round(sum(track_pops) / len(track_pops), 2) if track_pops else None,
            "unique_artists": len(artist_counter),
            "genre_counts": dict(genre_counter),
            "decade_counts": dict(decade_counter)
        }

    return profiles
