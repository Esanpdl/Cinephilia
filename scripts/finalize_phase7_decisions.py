"""Record reviewed identities from the retained source and TMDB evidence.

This is a run-specific audit record, not an automatic title-matching heuristic.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / "data/phase7/1bfb521f24cd2ecb715b"
path = directory / "decisions.json"
payload = json.loads(path.read_text(encoding="utf-8"))
movies = {
    246: (43118, "Ivan the Terrible Part II is a separate Eisenstein film, TMDB 43118, runtime 82 minutes. Source gives its 1946 production year; TMDB uses its 1958 release. Do not link Part I (9797)."),
    58: (14696, "Source Ugetsu Monogatari is Ugetsu: same 1953 Mizoguchi film, also verified by Letterboxd rank 120."),
    126: (43878, "Same Renoir short. Criterion confirms production in 1936 and release in 1946; preserve the original source year in its citation."),
    153: (27432, "Same Charles Burnett film, also Letterboxd rank 384; source gives 1977 and TMDB primary release 1978."),
    154: (626, "Same Bunuel short, original title and director agree; source gives 1928 and TMDB release 1929."),
    195: (44379, "The Gleaners & I is The Gleaners and I: same Varda film, year and Letterboxd rank 903 agree."),
    272: (977, "Tabu is Tabu: A Story of the South Seas; same Murnau film, year and Letterboxd rank 450 agree."),
    273: (803, "Same Resnais short Night and Fog; source gives 1955 and TMDB primary release 1956."),
    372: (94528, "Complete Out 1 movie, not Spectre or one episode: Rivette, source 729 minutes and TMDB 743 minutes. BFI documents the complete 1971 work; TMDB movie uses a 1990 release date. Preserve both records' original fields."),
    427: (133919, "The source explicitly lists the 168-minute film cut of Scenes from a Marriage, matching the 169-minute TMDB movie and Letterboxd rank 267. Source year 1973, TMDB theatrical release 1974. Do not map the TV series."),
    462: (697, "October expands to October (Ten Days that Shook the World); both directors and 1928 agree with actual full TMDB credits."),
    629: (378, "Same Raising Arizona 1987: TMDB credits Joel as Director and Ethan as Screenplay/Producer; source credits both Coens."),
    652: (35124, "Same Bunuel Nazarin, also Letterboxd rank 971; source gives 1958 and TMDB 1959."),
    751: (379, "Same Miller's Crossing 1990: TMDB credits Joel as Director and Ethan as Screenplay/Producer; source credits both Coens."),
    753: (10754, "Same Kieslowski A Short Film About Killing; source gives 1987 and TMDB 1988, full film runtime 85 minutes."),
    757: (71041, "Same Fritz Lang Tiger of Eschnapur, 101 minutes; source gives 1958 and TMDB 1959. The 1938 film has a different director."),
    769: (105583, "Same Jonas Mekas Diaries, Notes and Sketches, source 177 minutes/TMDB 180; source year 1969 and TMDB 1968."),
    806: (420240, "Complete Dog Star Man movie: Stan Brakhage, TMDB 78 minutes versus source 75; source year 1964 and TMDB primary release 1965. This ID represents the whole film, not its individual parts or the collection."),
    807: (87561, "Un chant d'amour is Song of Love, Jean Genet's 26-minute film. Cinematheque confirms the original 1950 work. TMDB uses a 1972 primary release date; retain source and TMDB dates separately."),
    897: (42006, "Same Zhang Yimou Red Sorghum, 91 minutes; source gives 1987 and TMDB primary release 1988."),
    961: (11368, "Same Blood Simple: source credits both Coens; TMDB Joel Director, Ethan Screenplay/Producer. Source 1984 appears in TMDB release evidence although the primary release is 1985."),
}
evidence_urls = {
    126: "https://www.criterion.com/films/28072-a-day-in-the-country",
    372: "https://www.bfi.org.uk/features/where-begin-jacques-rivette",
    807: "https://www.cinematheque.fr/film/54392.html",
}
for rank, (movie_id, reason) in movies.items():
    payload["decisions"][f"tspdt_top1000:{rank}"] = {
        "tmdb_id": movie_id, "reason": reason,
        "evidence_url": evidence_urls.get(rank, f"https://www.themoviedb.org/movie/{movie_id}"),
    }
for rank, tv_id in {140: 206647, 171: 42699, 335: 43189, 514: 1920, 925: 43059}.items():
    decision = {
        "tmdb_id": None, "tmdb_tv_id": tv_id,
        "reason": "Verified TMDB TV identity; preserve the source citation and exclude the series from the movie catalog, as approved by the user.",
        "evidence_url": f"https://www.themoviedb.org/tv/{tv_id}",
    }
    if rank == 514:
        decision.update(tmdb_season_number=3, evidence_url="https://www.themoviedb.org/tv/1920/season/3", reason="Twin Peaks: The Return is specifically season 3, verified as 18 episodes beginning 2017-05-21. Preserve this season-specific citation without importing a Movie.")
    payload["decisions"][f"tspdt_top1000:{rank}"] = decision
payload["decisions"]["tspdt_top1000:988"] = {
    "tmdb_id": None, "status": "unmatched",
    "reason": "User explicitly approved preserving Olympia (1938), listed as one combined 201-minute work, as unmatched. TMDB movies 677 and 685 are separate parts; import neither part from this citation.",
    "evidence_url": "https://theyshootpictures.com/gf1000_all1000films.htm",
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(payload['decisions'])} reviewed source decisions.")
