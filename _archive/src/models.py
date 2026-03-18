# models.py
# Shared data models for Exportify

class Track:
    def __init__(
        self,
        track_uri,
        track_name,
        album_name,
        artist_names,
        release_date,
        genres,
        duration_ms,
        popularity,
        explicit,
        associated_playlists,

        # Spotify-like audio features
        danceability=None,
        energy=None,
        key=None,
        loudness=None,
        mode=None,
        speechiness=None,
        acousticness=None,
        instrumentalness=None,
        liveness=None,
        valence=None,
        tempo=None,

        # Additional modern analysis features
        happiness=None,    # mood / brightness (0-100)
        camelot=None       # e.g., "8B", "11A"
    ):
        # Core metadata
        self.track_uri = track_uri
        self.track_name = track_name
        self.album_name = album_name
        self.artist_names = artist_names
        self.release_date = release_date
        self.genres = genres
        self.duration_ms = duration_ms
        self.popularity = popularity
        self.explicit = explicit
        self.associated_playlists = associated_playlists

        # Spotify-style features (from audio_features API)
        self.danceability = danceability
        self.energy = energy
        self.key = key
        self.loudness = loudness
        self.mode = mode
        self.speechiness = speechiness
        self.acousticness = acousticness
        self.instrumentalness = instrumentalness
        self.liveness = liveness
        self.valence = valence
        self.tempo = tempo

        # Additional features from external analysis APIs
        self.happiness = happiness
        self.camelot = camelot

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def to_dict(self):
        return self.__dict__


class Playlist:
    def __init__(self, playlist_id, name, description, owner, contained_tracks):
        self.playlist_id = playlist_id
        self.name = name
        self.description = description
        self.owner = owner
        self.contained_tracks = contained_tracks

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def to_dict(self):
        return self.__dict__
