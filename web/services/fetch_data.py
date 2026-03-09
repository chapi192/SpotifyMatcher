import time
import spotipy
import spotipy.exceptions

def format_genre(g):
    if not g:
        return g

    g = " ".join(word.capitalize() for word in g.split())
    g = g.replace("R&b", "R&B")
    g = g.replace("Edm", "EDM")
    g = g.replace("Uk ", "UK ")
    return g

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

def _hydrate_artists(sp, artist_ids, artist_cache):
    if not artist_ids:
        return

    artist_list = list(artist_ids)

    for i in range(0, len(artist_list), 50):
        batch = artist_list[i:i + 50]
        artist_results = safe_spotify_call(sp.artists, batch)

        for artist in (artist_results.get("artists") or []):
            if not artist:
                continue

            aid = artist.get("id")
            if not aid:
                continue

            images = artist.get("images") or []
            image_url = images[0]["url"] if images else None

            artist_cache[aid] = {
                "genres": [format_genre(g) for g in (artist.get("genres") or [])],
                "image_url": image_url
            }

def _append_tracks_from_page(page_items, playlist_tracks, artist_cache):
    for item in page_items:
        track = item.get("track")
        if not track:
            continue

        track_id = track.get("id")
        track_name = track.get("name")

        album_data = track.get("album") or {}

        external_urls = track.get("external_urls") or {}
        spotify_url = external_urls.get("spotify")

        track_artists = []
        for a in (track.get("artists") or []):
            if not a:
                continue

            aid = a.get("id")
            aname = a.get("name")
            if not aid or not aname:
                continue

            meta = artist_cache.get(aid, {})
            track_artists.append({
                "artist_id": aid,
                "artist_name": aname,
                "genres": meta.get("genres", []),
                "image_url": meta.get("image_url"),
            })

        playlist_tracks.append({
            "track_id": track_id,
            "track_name": track_name,
            "popularity": track.get("popularity"),
            "duration_ms": track.get("duration_ms"),
            "explicit": track.get("explicit"),
            "track_number": track.get("track_number"),
            "disc_number": track.get("disc_number"),
            "preview_url": track.get("preview_url"),
            "spotify_url": spotify_url,
            "album": {
                "album_id": album_data.get("id"),
                "album_name": album_data.get("name"),
                "release_date": album_data.get("release_date"),
                "total_tracks": album_data.get("total_tracks"),
            },
            "artists": track_artists
        })

def fetch_single_playlist(sp, pid, artist_cache=None, progress_callback=None, cancel_check=None):

    if artist_cache is None:
        artist_cache = {}

    playlist_tracks = []

    if pid == "__liked__":
        playlist_name = "Liked Songs"
        playlist_image = "https://misc.scdn.co/liked-songs/liked-songs-300.png"

        meta = safe_spotify_call(sp.current_user_saved_tracks, limit=1)
        playlist_total_tracks = meta["total"]

        results = safe_spotify_call(sp.current_user_saved_tracks, limit=50)

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

        if cancel_check and cancel_check():
            return None

        page_items = results.get("items") or []

        if progress_callback:
            progress_callback(len(page_items))

        page_artist_ids = set()

        for item in page_items:
            track = item.get("track")
            if not track:
                continue

            for artist in (track.get("artists") or []):
                aid = artist.get("id")
                if aid and aid not in artist_cache:
                    page_artist_ids.add(aid)

        _hydrate_artists(sp, page_artist_ids, artist_cache)

        _append_tracks_from_page(page_items, playlist_tracks, artist_cache)

        if not results.get("next"):
            break

        if cancel_check and cancel_check():
            return None

        results = safe_spotify_call(sp.next, results)

    return {
        "playlist_id": pid,
        "playlist_name": playlist_name,
        "image": playlist_image,
        "playlist_track_total": playlist_total_tracks,
        "tracks": playlist_tracks
    }