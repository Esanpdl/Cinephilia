"""Validate and batch-upsert authentic TMDB detail payloads into the catalog."""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.movies.models import Genre, Movie, MovieCredit, Person
from .media import select_trailer
from .tmdb import TMDBError


MOVIE_UPDATE_FIELDS = [
    "imdb_id", "title", "original_title", "overview", "tagline", "release_date",
    "original_language", "runtime", "vote_average", "vote_count", "popularity",
    "poster_path", "backdrop_path", "trailer_key", "trailer_name", "trailer_official",
    "keywords", "source_tags", "catalog_rank", "tmdb_synced_at", "updated_at",
]


def normalize_details(payload, language):
    """Reject incomplete detail responses before changing any catalog records."""
    try:
        movie_id = payload["id"]
        if not isinstance(movie_id, int) or movie_id <= 0 or not payload["title"]:
            raise ValueError("Invalid identity")
        votes = payload["vote_count"]
        average = Decimal(str(payload["vote_average"]))
        if not isinstance(votes, int) or votes < 0 or not Decimal(0) <= average <= Decimal(10):
            raise ValueError("Invalid votes")
        release = date.fromisoformat(payload["release_date"]) if payload.get("release_date") else None
        genres = payload["genres"]
        keywords = payload["keywords"]["keywords"]
        cast = payload["credits"]["cast"]
        crew = payload["credits"]["crew"]
        videos = payload["videos"]["results"]
        for values in (genres, keywords, cast, crew, videos):
            if not isinstance(values, list):
                raise ValueError("Invalid appended response")
        for entry in [*genres, *keywords, *cast, *crew]:
            if not isinstance(entry["id"], int) or entry["id"] <= 0 or not entry["name"]:
                raise ValueError("Invalid related entity")
        trailer = select_trailer(videos, language)
        credits = [dict(person, role=MovieCredit.Role.CAST) for person in cast]
        credits += [dict(person, role=MovieCredit.Role.DIRECTOR) for person in crew if person.get("job") == "Director"]
        if any(not credit.get("credit_id") for credit in credits):
            raise ValueError("Missing credit ID")
        return {
            "tmdb_id": movie_id,
            "imdb_id": payload.get("imdb_id") or "",
            "title": payload["title"],
            "original_title": payload.get("original_title") or "",
            "overview": payload.get("overview") or "",
            "tagline": payload.get("tagline") or "",
            "release_date": release,
            "original_language": payload.get("original_language") or "",
            "runtime": payload.get("runtime"),
            "vote_average": average,
            "vote_count": votes,
            "popularity": payload.get("popularity", 0),
            "poster_path": payload.get("poster_path") or "",
            "backdrop_path": payload.get("backdrop_path") or "",
            "trailer_key": trailer["key"] if trailer else "",
            "trailer_name": trailer.get("name", "") if trailer else "",
            "trailer_official": bool(trailer.get("official")) if trailer else False,
            "keywords": [{"tmdb_id": item["id"], "name": item["name"]} for item in keywords],
            "_genres": genres,
            "_credits": credits,
            "_adult": payload.get("adult", False),
            "_video": payload.get("video", False),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise TMDBError("TMDB movie details are missing required fields or contain invalid values; nothing was invented.") from None


@transaction.atomic
def upsert_movies(normalized, ranks):
    """A fixed number of batched queries per chunk, including relations."""
    ids = [item["tmdb_id"] for item in normalized]
    existing_sources = dict(Movie.objects.select_for_update().filter(tmdb_id__in=ids).values_list("tmdb_id", "source_tags"))
    genres = {}
    people = {}
    movies = []
    synced_at = timezone.now()
    for item in normalized:
        for genre in item["_genres"]:
            genres[genre["id"]] = Genre(tmdb_id=genre["id"], name=genre["name"])
        for credit in item["_credits"]:
            people[credit["id"]] = Person(tmdb_id=credit["id"], name=credit["name"], profile_path=credit.get("profile_path") or "")
        values = {key: value for key, value in item.items() if not key.startswith("_")}
        values.update({
            "source_tags": sorted(set(existing_sources.get(item["tmdb_id"], [])) | {Movie.Source.TMDB}),
            "catalog_rank": ranks[item["tmdb_id"]],
            "tmdb_synced_at": synced_at,
        })
        movies.append(Movie(**values))
    Genre.objects.bulk_create(genres.values(), update_conflicts=True, unique_fields=["tmdb_id"], update_fields=["name"], batch_size=1000)
    Person.objects.bulk_create(people.values(), update_conflicts=True, unique_fields=["tmdb_id"], update_fields=["name", "profile_path"], batch_size=1000)
    Movie.objects.bulk_create(movies, update_conflicts=True, unique_fields=["tmdb_id"], update_fields=MOVIE_UPDATE_FIELDS, batch_size=100)
    genre_ids = dict(Genre.objects.filter(tmdb_id__in=genres).values_list("tmdb_id", "id"))
    person_ids = dict(Person.objects.filter(tmdb_id__in=people).values_list("tmdb_id", "id"))
    movie_ids = dict(Movie.objects.filter(tmdb_id__in=ids).values_list("tmdb_id", "id"))
    through = Movie.genres.through
    through.objects.filter(movie_id__in=movie_ids.values()).delete()
    MovieCredit.objects.filter(movie_id__in=movie_ids.values()).delete()
    genre_links = {}
    credit_links = {}
    for item in normalized:
        movie_pk = movie_ids[item["tmdb_id"]]
        for genre in item["_genres"]:
            genre_pk = genre_ids[genre["id"]]
            genre_links[(movie_pk, genre_pk)] = through(movie_id=movie_pk, genre_id=genre_pk)
        for credit in item["_credits"]:
            credit_links[(movie_pk, credit["credit_id"])] = MovieCredit(
                movie_id=movie_pk, person_id=person_ids[credit["id"]],
                tmdb_credit_id=credit["credit_id"], role=credit["role"],
                character=credit.get("character") or "",
                cast_order=credit.get("order") if credit["role"] == MovieCredit.Role.CAST else None,
            )
    through.objects.bulk_create(genre_links.values(), batch_size=1000)
    MovieCredit.objects.bulk_create(credit_links.values(), batch_size=1000)
    return len(movies)
