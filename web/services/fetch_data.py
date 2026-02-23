import time
import spotipy
import spotipy.exceptions


def safe_spotify_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 2))
                time.sleep(retry_after)
            else:
                raise


def fetch_single_playlist(sp, pid, artist_cache=None, progress_callback=None):

    if artist_cache is None:
        artist_cache = {}

    playlist_tracks = []

    # =====================================================
    # HANDLE LIKED SONGS
    # =====================================================
    if pid == "__liked__":

        playlist_name = "Liked Songs"
        playlist_image = "https://misc.scdn.co/liked-songs/liked-songs-300.png"

        meta = safe_spotify_call(
            sp.current_user_saved_tracks,
            limit=1
        )

        playlist_total_tracks = meta["total"]

        results = safe_spotify_call(
            sp.current_user_saved_tracks,
            limit=50
        )

        while True:

            page_items = results["items"]
            fetched_this_page = len(page_items)

            if progress_callback:
                progress_callback(fetched_this_page)

            page_artist_ids = set()

            for item in page_items:
                track = item["track"]
                if not track:
                    continue

                for artist in track["artists"]:
                    if artist["id"] not in artist_cache:
                        page_artist_ids.add(artist["id"])

            if page_artist_ids:
                artist_list = list(page_artist_ids)

                for i in range(0, len(artist_list), 50):
                    batch = artist_list[i:i + 50]
                    artist_results = safe_spotify_call(sp.artists, batch)

                    for artist in artist_results["artists"]:
                        artist_cache[artist["id"]] = {
                            "genres": artist["genres"],
                            "popularity": artist["popularity"]
                        }

            for item in page_items:
                track = item["track"]
                if not track:
                    continue

                track_artists = []

                for a in track["artists"]:
                    meta = artist_cache.get(a["id"], {})
                    track_artists.append({
                        "artist_id": a["id"],
                        "artist_name": a["name"],
                        "genres": meta.get("genres", []),
                        "artist_popularity": meta.get("popularity")
                    })

                playlist_tracks.append({
                    "track_id": track["id"],
                    "track_name": track["name"],
                    "popularity": track["popularity"],
                    "duration_ms": track["duration_ms"],
                    "explicit": track["explicit"],
                    "track_number": track["track_number"],
                    "disc_number": track["disc_number"],
                    "preview_url": track["preview_url"],
                    "spotify_url": track["external_urls"]["spotify"],
                    "album": {
                        "album_id": track["album"]["id"],
                        "album_name": track["album"]["name"],
                        "release_date": track["album"]["release_date"],
                        "total_tracks": track["album"]["total_tracks"]
                    },
                    "artists": track_artists
                })

            if not results["next"]:
                break

            results = safe_spotify_call(sp.next, results)

    # =====================================================
    # HANDLE NORMAL PLAYLISTS
    # =====================================================
    else:

        playlist_meta = safe_spotify_call(
            sp.playlist,
            pid,
            fields="id,name,images,tracks.total"
        )

        playlist_name = playlist_meta["name"]
        playlist_total_tracks = playlist_meta["tracks"]["total"]

        playlist_image = None
        if playlist_meta.get("images"):
            playlist_image = playlist_meta["images"][0]["url"]

        results = safe_spotify_call(
            sp.playlist_items,
            pid,
            limit=100,
            fields="items(track(id,name,popularity,duration_ms,explicit,track_number,disc_number,preview_url,external_urls,album(id,name,release_date,total_tracks),artists(id,name))),next"
        )

        while True:

            page_items = results["items"]
            fetched_this_page = len(page_items)

            if progress_callback:
                progress_callback(fetched_this_page)
                
            page_artist_ids = set()

            for item in page_items:
                track = item["track"]
                if not track:
                    continue

                for artist in track["artists"]:
                    if artist["id"] not in artist_cache:
                        page_artist_ids.add(artist["id"])

            if page_artist_ids:
                artist_list = list(page_artist_ids)

                for i in range(0, len(artist_list), 50):
                    batch = artist_list[i:i + 50]
                    artist_results = safe_spotify_call(sp.artists, batch)

                    for artist in artist_results["artists"]:
                        artist_cache[artist["id"]] = {
                            "genres": artist["genres"],
                            "popularity": artist["popularity"]
                        }

            for item in page_items:
                track = item["track"]
                if not track:
                    continue

                track_artists = []

                for a in track["artists"]:
                    meta = artist_cache.get(a["id"], {})
                    track_artists.append({
                        "artist_id": a["id"],
                        "artist_name": a["name"],
                        "genres": meta.get("genres", []),
                        "artist_popularity": meta.get("popularity")
                    })

                playlist_tracks.append({
                    "track_id": track["id"],
                    "track_name": track["name"],
                    "popularity": track["popularity"],
                    "duration_ms": track["duration_ms"],
                    "explicit": track["explicit"],
                    "track_number": track["track_number"],
                    "disc_number": track["disc_number"],
                    "preview_url": track["preview_url"],
                    "spotify_url": track["external_urls"]["spotify"],
                    "album": {
                        "album_id": track["album"]["id"],
                        "album_name": track["album"]["name"],
                        "release_date": track["album"]["release_date"],
                        "total_tracks": track["album"]["total_tracks"]
                    },
                    "artists": track_artists
                })

            if not results["next"]:
                break

            results = safe_spotify_call(sp.next, results)

    return {
        "playlist_id": pid,
        "playlist_name": playlist_name,
        "image": playlist_image,
        "playlist_track_total": playlist_total_tracks,
        "tracks": playlist_tracks
    }