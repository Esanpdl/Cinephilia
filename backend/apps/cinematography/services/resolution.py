"""Conservative TMDB title resolution; ambiguity is a review result, not a guess."""
import json
from pathlib import Path

from apps.movies.services.catalog import normalize_details
from apps.movies.services.tmdb import TMDBError, write_json
from .source_lists import SourceError, title_key, similarity, fuzzy_title_agrees


class Resolver:
    def __init__(self, client, directory):
        self.client = client
        self.directory = Path(directory)
        self.details_cache = {}

    def detail(self, movie_id):
        if movie_id not in self.details_cache:
            path = self.directory / "details" / f"{movie_id}.json"
            # Run-local immutable evidence, independent of the transport cache TTL.
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = self.client.details(movie_id)
                normalize_details(payload, self.client.language)
                write_json(path, payload)
            if payload.get("id") != movie_id:
                raise SourceError(f"Detail evidence has an incorrect TMDB ID: {movie_id}.")
            normalize_details(payload, self.client.language)
            self.details_cache[movie_id] = payload
        return self.details_cache[movie_id]

    def resolve(self, members, broad=False):
        found, truncated = {}, False
        source_years = {member["year"] for member in members if member["year"] is not None}
        search_year = next(iter(source_years)) if len(source_years) == 1 and not broad else None
        titles = {}
        for member in members:
            titles.setdefault(title_key(member["match_title"]), member["match_title"])
        for title in titles.values():
            page = 1
            while True:
                response = self.client.search_movies(title, page, year=search_year)
                # Some premiere years differ from the primary release. Broaden
                # only an empty year-filtered query, then verify release evidence.
                if page == 1 and search_year is not None and response.get("results") == []:
                    response = self.client.search_movies(title, page)
                    active_year = None
                elif page == 1:
                    active_year = search_year
                elif active_year is None:
                    response = self.client.search_movies(title, page)
                if response.get("page") != page or type(response.get("total_pages")) is not int or not isinstance(response.get("results"), list):
                    raise TMDBError("Invalid TMDB search response; resolution stopped.")
                for candidate in response["results"]:
                    if type(candidate.get("id")) is not int or candidate["id"] <= 0 or not isinstance(candidate.get("title"), str):
                        raise TMDBError("TMDB search result is missing its identity.")
                    found[candidate["id"]] = candidate
                if page >= response["total_pages"]:
                    break
                if page == 5:
                    truncated = True
                    break
                page += 1
        candidates = []
        for movie_id, summary in sorted(found.items()):
            names = [summary["title"], summary.get("original_title") or ""]
            title_score = max(similarity(member["match_title"], name) for member in members for name in names)
            # Search itself supports alternate titles. Inspect aliases for weak
            # primary-title matches instead of assuming search rank proves identity.
            year_text = (summary.get("release_date") or "")[:4]
            year = int(year_text) if year_text.isdigit() else None
            years = {member["year"] for member in members if member["year"] is not None}
            year_ok = not years or year in years
            verified_release_years = {year} if year else set()
            if not year_ok and year is not None and any(abs(source_year - year) <= 3 for source_year in years):
                releases = self.client.get(f"/movie/{movie_id}/release_dates")
                if not isinstance(releases.get("results"), list):
                    raise TMDBError("Invalid TMDB release-date response.")
                for region in releases["results"]:
                    for release in region.get("release_dates", []):
                        value = (release.get("release_date") or "")[:4]
                        if value.isdigit() and release.get("type") in {1, 2, 3, 6}:
                            verified_release_years.add(int(value))
                year_ok = years.issubset(verified_release_years)
            if not year_ok:
                candidates.append({"tmdb_id": movie_id, "title": summary["title"], "year": year, "eligible": False, "reason": "year differs"})
                continue
            if any(not any(title_key(member["match_title"]) == title_key(name) for name in names) for member in members):
                aliases = self.client.alternative_titles(movie_id)
                if not isinstance(aliases.get("titles"), list):
                    raise TMDBError("Invalid TMDB alternative-title response.")
                names += [entry["title"] for entry in aliases["titles"] if isinstance(entry.get("title"), str)]
            if max(similarity(member["match_title"], name) for member in members for name in names) < .94:
                candidates.append({"tmdb_id": movie_id, "title": summary["title"], "year": year, "eligible": False, "reason": "titles differ, including aliases"})
                continue
            payload = self.detail(movie_id)
            names += [payload["title"], payload.get("original_title") or ""]
            director_people = [entry for entry in payload["credits"]["crew"] if entry.get("job") == "Director"]
            director_names = [entry["name"] for entry in director_people]
            tests = []
            for member in members:
                exact = any(title_key(member["match_title"]) == title_key(name) for name in names)
                fuzzy = any(fuzzy_title_agrees(member["match_title"], name) for name in names)
                source_director = title_key(member["director"] or "")
                # Every credited director must appear in the supplied source text;
                # any unrecognized extra words require review rather than inference.
                remaining = source_director
                found_director = False
                for person in director_people:
                    if not remaining:
                        break
                    names_for_person = [person["name"]]
                    if source_director and title_key(person["name"]) not in source_director:
                        person_payload = self.client.get(f"/person/{person['id']}")
                        names_for_person += person_payload.get("also_known_as", [])
                    matches = [title_key(name) for name in names_for_person if title_key(name) and title_key(name) in remaining]
                    if matches:
                        remaining = remaining.replace(max(matches, key=len), "")
                        found_director = True
                remaining = " ".join(word for word in remaining.split() if word not in {"and", "et"})
                # Sources often credit only a supervising director. Verify all
                # supplied names, without requiring every extra TMDB credit.
                director_ok = not source_director or (found_director and not remaining)
                payload_year = (payload.get("release_date") or "")[:4]
                detail_year_ok = member["year"] is None or str(member["year"]) == payload_year or member["year"] in verified_release_years
                tests.append(detail_year_ok and director_ok and (exact or fuzzy and member["year"] is not None and bool(source_director)))
            eligible = all(tests) and not payload.get("adult") and not payload.get("video")
            candidates.append({
                "tmdb_id": movie_id, "title": payload["title"], "year": year,
                "directors": director_names, "eligible": eligible,
                "verified_release_years": sorted(verified_release_years),
                "url": f"https://www.themoviedb.org/movie/{movie_id}",
                "reason": "title and available source clues agree" if eligible else "title, source clues, or movie type need review",
            })
        accepted = [candidate for candidate in candidates if candidate["eligible"]]
        if not accepted and search_year is not None:
            return self.resolve(members, broad=True)
        if len(accepted) == 1 and not truncated:
            return {"status": "resolved", "tmdb_id": accepted[0]["tmdb_id"], "method": "unique_title_and_clues", "candidates": candidates}
        return {
            "status": "review", "tmdb_id": None, "candidates": candidates,
            "reason": "search pagination capped" if truncated else "multiple identities fit" if len(accepted) > 1 else "no verified identity",
        }


def read_overrides(path, input_hashes, entry_keys):
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise SourceError(f"Cannot read matching decisions: {error}") from None
    if not isinstance(payload, dict) or payload.get("input_hashes") != input_hashes or not isinstance(payload.get("decisions"), dict):
        raise SourceError("Review decisions must identify the current input_hashes and contain a decisions object.")
    decisions = payload["decisions"]
    for key, decision in decisions.items():
        if key not in entry_keys or not isinstance(decision, dict):
            raise SourceError("Review decision names an unknown source/rank.")
        movie_id = decision.get("tmdb_id")
        if movie_id is not None and (type(movie_id) is not int or movie_id <= 0):
            raise SourceError(f"{key}: tmdb_id must be a positive integer, or null for a reviewed exclusion.")
        if decision.get("status") == "unmatched" and (movie_id is not None or decision.get("tmdb_tv_id") is not None):
            raise SourceError(f"{key}: unmatched decisions cannot assign a movie or series.")
        if movie_id is None and decision.get("status") != "unmatched" and (type(decision.get("tmdb_tv_id")) is not int or decision["tmdb_tv_id"] <= 0):
            raise SourceError(f"{key}: TV exclusions require the verified tmdb_tv_id.")
        if "tmdb_season_number" in decision and (type(decision["tmdb_season_number"]) is not int or decision["tmdb_season_number"] < 0 or movie_id is not None or not decision.get("tmdb_tv_id")):
            raise SourceError(f"{key}: a season requires a verified TV exclusion and nonnegative season number.")
        if "tmdb_id" not in decision or not isinstance(decision.get("reason"), str) or not decision["reason"].strip() or not isinstance(decision.get("evidence_url"), str) or not decision["evidence_url"].startswith("https://"):
            raise SourceError(f"{key}: every manual decision requires tmdb_id, reason, and an HTTPS evidence_url.")
    return decisions


def manual_result(decision, resolver):
    movie_id = decision["tmdb_id"]
    if movie_id is not None:
        payload = resolver.detail(movie_id)
        if payload.get("adult") or payload.get("video"):
            raise SourceError("A reviewed mapping points to an adult/non-movie video entry; investigate it before importing.")
    result = {"status": "resolved" if movie_id else "unmatched" if decision.get("status") == "unmatched" else "excluded", "tmdb_id": movie_id, "method": "reviewed", "reason": decision["reason"], "evidence_url": decision["evidence_url"]}
    if result["status"] == "excluded":
        tv_id = decision["tmdb_tv_id"]
        series = resolver.client.get(f"/tv/{tv_id}", {"language": resolver.client.language})
        if series.get("id") != tv_id or not series.get("name"):
            raise SourceError("The exclusion could not be verified as a TMDB TV series.")
        write_json(resolver.directory / "excluded_tv" / f"{tv_id}.json", series)
        result["tmdb_tv_id"] = tv_id
        result["tmdb_name"] = series["name"]
        if "tmdb_season_number" in decision:
            number = decision["tmdb_season_number"]
            season = resolver.client.get(f"/tv/{tv_id}/season/{number}", {"language": resolver.client.language})
            if season.get("season_number") != number or not season.get("episodes"):
                raise SourceError("The excluded season could not be verified.")
            write_json(resolver.directory / "excluded_tv" / f"{tv_id}-season-{number}.json", season)
            result["tmdb_season_number"] = number
            result["tmdb_season_air_date"] = season.get("air_date")
    return result
