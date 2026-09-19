# Design and asset references

- [Be UI Motion](https://beui.dev/components/motion): inspiration for spring-based
  button feedback and animated active navigation underlines. Implemented locally
  with Motion; no remote registry execution or runtime dependency on Be UI.
- [Criterion Channel film catalog](https://films.criterionchannel.com/): user-supplied
  aesthetic reference for a film-focused, editorial interface.
- [TMDB](https://www.themoviedb.org/): actual catalog facts, poster/backdrop URLs,
  and trailer metadata supplied through Django. User-facing attribution is in
  the footer. Trailers are embedded from YouTube when the user activates the player.
- Oswald and DM Sans: local Fontsource variable-font packages. Package license
  files are retained with installed dependencies.
- Lucide supplies interface icons; Motion supplies animation. Dependency versions
  are pinned in package-lock.json and their license files remain in node_modules.

The filmmaker names supplied by the user are visual references only. No
filmmaker endorsement, director preference, or director-specific catalog has
been introduced.

