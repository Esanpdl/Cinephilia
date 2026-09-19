"""Identity helpers shared by fitting and explanations without training dependencies."""
FIELDS = ("overview", "keywords", "genres", "cast", "directors")


def identities(movie, field, max_cast):
    entries = movie[field]
    if field == "cast":
        entries = sorted(entries, key=lambda item: (item.get("order") is None, item.get("order") or 0, item["id"]))
    result = {}
    for entry in entries:
        identifier = entry["tmdb_id"] if field == "keywords" else entry["id"]
        result.setdefault(identifier, entry["name"])
        if field == "cast" and len(result) == max_cast:
            break
    return result
