# Videos needing replacement or verified provenance

Review completed on 18 September 2026. Twenty of the 32 flagged sources were
cleared after any necessary frame exclusions. The following 12 remain withheld;
all retain their places in the selected 500 films.

Use a traceable trailer or distributor/archive scene clip containing footage
from that film only. Keep the source URL alongside the download. The project
owner can provide any local file path; the import workflow can rename and place
it in `data/raw/trailers/` after checking its movie identity.

| Film | Target filename | Current issue |
| --- | --- | --- |
| Pather Panchali (1955) | `5801.mp4` | Apu Trilogy compilation |
| The World of Apu (1959) | `896.mp4` | Apu Trilogy compilation |
| Aparajito (1956) | `897.mp4` | Apu Trilogy compilation |
| Germany, Year Zero (1948) | `8016.mp4` | War Trilogy compilation |
| Paisan (1946) | `8429.mp4` | War Trilogy compilation |
| Our Hospitality (1923) | `701.mp4` | Multi-film Keaton box-set promo |
| Steamboat Bill, Jr. (1928) | `25768.mp4` | Multi-film Keaton box-set promo |
| Gertrud (1964) | `34181.mp4` | Premiere/interview coverage rather than film footage |
| Greed (1924) | `1405.mp4` | Selective gold/tinted source edition not verified |
| October (Ten Days that Shook the World) (1928) | `697.mp4` | Strong red tint; source edition not verified |
| The Scarlet Empress (1934) | `31527.mp4` | Fan montage with unverified editing/edition provenance |
| Life, and Nothing More… (1992) | `83761.mp4` | Music-edited scene upload with unverified provenance |

For the final four entries, uncertainty about provenance does **not** establish
that their footage or coloring is inauthentic. Reliable documentation of the
existing source edition could resolve the review without another download.

**The Lady Vanishes needs no replacement.** The supplied video has been retained
as a promotional featurette; 29 clean samples are published after excluding
numbered graphics, captions and a blurred transition. Its source is documented
by [Criterion's Three Reasons page](https://www.criterion.com/current/posts/2097-three-reasons-the-lady-vanishes).

The exact current URLs, reasons, checksums and review inputs are preserved in
[`training/visual/source-reviews.json`](../training/visual/source-reviews.json).
After accepting a replacement, record a fresh checksum-bound decision, re-extract
with `--force`, run the full cached extraction to restore the inventory receipt,
then import and verify as described in [the film-student guide](film-student-guide.md).
