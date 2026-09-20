# Cinephilia — Bug Fixes & Small Feature Requests

Fix the 7 issues below. Follow these rules for every single one, no exceptions:

1. **Understand the project before touching anything.** Before starting, read the original master build prompt I gave you, along with any documentation, README, or `.md` files already present in the project (created by you or an earlier AI session). Use these to understand the project's objectives, architecture, coding style/conventions, and existing features, so your fixes match how the rest of the project is built rather than introducing inconsistent patterns.
2. **Diagnose before touching code.** For each item, first check whether the feature already exists in the codebase and whether it currently works. If it exists but is broken, fix it. If it doesn't exist at all, build it. Don't assume — actually check.
3. **Scope discipline.** Only touch what's needed for these 7 items. Do not refactor, rename, or "improve" anything else along the way, even if you notice something else that looks off — just note it separately at the end instead.
4. **Explain before implementing.** Before writing any code, tell me: which files/components you'll change, what section of the app it affects, and what the expected impact is (including anything downstream that could be affected, e.g. removing a movie affecting a carousel). Wait for my approval or corrections before implementing.
5. **Ask if anything is unclear.** Don't guess at ambiguous instructions — ask me directly.
6. **Document every change as you make it.** For each fix, record what changed and why in the project's documentation (e.g. a changelog file, or update the relevant existing `.md` file) — specific enough that another AI agent picking up this project later, with no memory of this session, can understand what was done and why without re-reading the full diff.
7. **Self-check at the end.** After implementing all 7 fixes, verify each one actually works end-to-end (not just that it compiles/runs) — check it the way a user would. Report the result of each check. If you spot related issues or improvements worth making, list them as suggestions, but do not implement them without my go-ahead.

---

## The 7 issues

1. **Star rating doesn't render after saving.** On the movie detail page, saving a rating stores it correctly (the number is correct, e.g. "5/5 stars" text) but the star icons themselves don't visually fill in. Fix this so stars render correctly, and make sure half-star increments display properly — e.g. a 4.5 rating should show as 4 full stars + 1 half star, not rounded up or down.

2. **Logo doesn't return to homepage.** Clicking the "CINEPHILIA." wordmark in the navbar should take the user back to the homepage (Discover feed). Check if this is wired up at all; add it if missing.

3. **"Refresh selection" on the For You page does nothing.** Clicking it should fetch a new/different set of recommended films, not repeat the same set every time. Fix the underlying logic so it actually requests a fresh selection.

4. **No aggregate community star rating is shown.** On the movie detail page, TMDB's rating is shown, but there's no display of *our own users'* average rating (personal ratings are stored and shown individually, but never aggregated/displayed). Add or fix this: show the average of all users' ratings on this platform as stars, positioned next to the TMDB rating, so it updates as more users rate a film.

5. **Letterboxd rating embed is too large.** The box showing the Letterboxd rating distribution (title, year, bar chart, "View on Letterboxd" link) takes up too much space. Shrink it to a more compact size. If it can't be reasonably resized without breaking the embed, remove it entirely instead.

6. **Fully remove "Avatar Aang: The Last Airbender" from the app.** Delete it from the database and make sure it doesn't appear anywhere — homepage hero/featured section, "Essential Viewing"/highest-rated carousel, search, or any other listing. Whatever logic currently selects it for those slots should naturally fall through to the next eligible film once it's removed — confirm that actually happens rather than leaving a gap or an error.

7. **Rename "Film Students" to "Film Analysis" in the navbar.** Label text only — don't change the route or underlying functionality unless it's directly tied to the label itself.

---

Reference screenshots of the current (broken) behavior are attached separately — check them before starting, especially for #1 (star rendering) and #5 (Letterboxd box sizing), since visual details matter there.
