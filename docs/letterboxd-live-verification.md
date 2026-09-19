# Letterboxd live-display verification

17 September 2026. Tested with installed Google Chrome in a fresh, headless
context, loading the actual Cinephilia film page and two isolated format checks.

| Check | Response | Visible result |
| --- | --- | --- |
| Cinephilia `/films/238`, TMDB-ID embed | HTTP 403, Cloudflare challenge | Browser blocked iframe |
| Official film-slug format, `film/the-godfather` | HTTP 403, Cloudflare challenge | Browser blocked iframe |
| Letterboxd's own documented TMDB 399057 example | HTTP 403, Cloudflare challenge | Browser blocked iframe |

All challenge responses include `X-Frame-Options: SAMEORIGIN`. Chrome reports
`net::ERR_BLOCKED_BY_RESPONSE`. A screenshot was visually inspected: the film page
shows the browser's broken-frame panel above the functional Letterboxd link.

This does not establish that the embed fails for every visitor or deployed origin.
It establishes that no live ratings rendered in any of these checks. A check in
the user's usual browser was requested separately; no successful manual result
has been recorded. The integration must not be described as live-display verified.

Evidence: `data/expansion/letterboxd-live-verification.json` and
`data/expansion/screenshots/{live-film-page,official-slug-format,letterboxd-own-example}.png`.
Repeat with `node scripts/verify-letterboxd-live.mjs` from `frontend/` while local
services are running. This diagnostic uses the installed Windows Chrome path.

## Alternatives

1. **Most dependable immediate option:** show TMDB's existing score and a separate
   Cinephilia community average/vote count computed from our real user ratings.
   Keep a direct Letterboxd link. A community aggregate would need implementation;
   the existing review list and personal stars are not themselves an aggregate.
   Empty aggregates must say “No ratings yet.” This adds no external API dependency.
2. **External rating option:** use Trakt's own audience score and rating distribution
   through its official movie-ratings API. Fetch through Django and cache responses,
   rather than depending on a third-party iframe. Requires a registered Trakt app
   and valid API key; account eligibility/terms and live API access must be checked
   before choosing it. Trakt scores are not Letterboxd scores. The current official
   endpoint also documents `?extended=all`, which can return Letterboxd ratings and
   links among other sources. Those values may be null. This is a promising route
   to investigate if preserving Letterboxd ratings is essential, but actual coverage
   and public-display permissions remain unverified. IMDb output can be ignored.

Letterboxd's official API currently says it does not grant access to recommendation
projects, so it is not a dependable alternative for this project. Third-party
aggregators should not be treated as guaranteeing Letterboxd redistribution rights
merely because they expose a rating field. No provider switch was implemented here.

Primary references:

- [Official Letterboxd embed](https://letterboxd.com/about/embed-our-ratings/)
- [Letterboxd API eligibility](https://letterboxd.com/api-beta/)
- [Trakt movie ratings](https://docs.trakt.tv/reference/getmoviesratings)
- [Trakt authentication](https://docs.trakt.tv/docs/authentication-oauth)
