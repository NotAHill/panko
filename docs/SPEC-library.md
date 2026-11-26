# The deck library (S10 step 2)

**Goal:** a learner can take a ready-made, checked deck instead of building one from sources. Someone with only
Anki imports an `.apkg`. Someone with Panko imports the deck into their own store. From there they keep building:
their own sources, card design and voices, with duplicates against what they already have handled like any other
source.

Settled (your call, 2026-11-26):
- A deck ships as a **Panko pack** plus an **.apkg** built from it.
- The library is a **separate public GitHub repo**: an `index.json` lists the decks, and the files are attached to
  releases, because they run to hundreds of MB.
- **Only you publish**, for now.
- Learners get decks from a **library page in the hub** and from `panko library`.

## The pack

`<deck>-v<N>.panko.zip`, one file:

| Path | What |
|---|---|
| `pack.json` | `format` (1), `id` (slug, e.g. `darija-peace-corps`), `version`, `title`, `description`, `language`, `varieties`, `panko` (version that built it), `counts` (words, phrases, pictures, audio), `licence` (for the card text), `credits` summary, `created` |
| `entries.jsonl` | One shared entry per line: the store entry as `apkg._shared` leaves it, without sources, review flags or personal tags. MyNotes is never included. `origin` = `{pack, id}` |
| `media/` | The pictures and the audio already made. Never native lesson clips. |
| `credits.json` | Per media file: provider, author, licence, page (what `pictures.apply` already records) and, for audio, the voice provider |

The `.apkg` is built from the pack, not from the store, so both always hold the same cards. Note guids come from
`pack id + origin id`, so a newer `.apkg` updates the notes from the old one instead of adding copies (as
`panko export` already does with the Panko id).

A **no-audio** variant of both files is optional, for size: Panko users can make the audio again with their own
voices.

## Publishing (`panko publish`)

`panko publish ID --title T [--description D] [--variety V] [--tag T] [--version N] [--no-audio] [--no-apkg]
[--index FILE] [--out DIR] [--dry-run]` builds the pack and the `.apkg` into `[export] dir`. It also writes
`<id>-v<N>.index.json`: id, version, title, description, language, varieties, counts, the card-text licence, picture
licences, sizes, sha256 and three sample entries. With `--index`, that entry replaces the deck's entry in your
clone's `index.json`. A report of what it left out goes in `<id>-v<N>.report.md`, which names your sources, so it is
never uploaded. `--dry-run` prints the report and writes nothing. Before building it checks:

- **Pictures:** the licence is read from the end of the credit. CC licences (NC, ND and SA too, since the library is
  free), public domain, the Pexels and Pixabay licences, and drawings made for Panko are fine. Any other photo is
  left out and the card goes without it. Credits go in `credits.json`, and the index counts each licence.
- **Private content:** a sentence goes in only if Panko wrote it or its source's name starts with one of
  `[library] public_sources` (e.g. `"Peace Corps textbook"`); a public source keeps its name as attribution. Words
  and glosses are fine.
- **Names:** people named in the titles of private sources ("Lesson with X", "X's notes") and `[library]
  private_names` are looked for in the card text. Put `private_names` in `config/hub.toml`: it isn't tracked. An
  example, note or picture prompt naming one is dropped. A card whose word or gloss names one is left out. Picture
  credits aren't searched: they must stay.
- **Doubtful:** entries tagged `panko::doubtful`, or still in the inbox, are left out.
- **Version:** one more than the last in the index or in the output folder. Entries keep their id across versions.

The card text is published under `[library] licence` (default CC BY-SA 4.0).

Uploading stays a manual step (`gh release create …` and a pull request to the index), printed at the end.
Panko never publishes on its own.

## Getting a deck

- `panko library list` reads the index from `[library] index` (default: the library repo's raw `index.json`).
- `panko library get ID [--activate]` downloads the pack into `[library] dir` (checking sha256 and free space first;
  default `cache/library`), then imports it.
- `panko library import FILE` imports a pack from a file.
- **Hub:** a library page lists the decks (title, language, varieties, counts, size, licences, sample entries),
  with a download for the `.apkg` and an import button for the pack. The import runs as a job.

**Importing is ingest.** A pack is a source of kind `pack`. Each entry goes through the same duplicate checks as
any unit:
- A word you already have gets a sighting and the pack's examples.
- A near-duplicate is held for you to decide.
- A word you rejected stays rejected.
- New entries get your own ids and land in the inbox, or go straight to active with `--activate`.

Media is copied into `data/media` under its own file name.

**How a pack goes through ingest (settled 2026-11-26).** Ingest takes extracted items (word, gloss, examples), and a
pack holds whole cards. They meet in the unit queue, not in a new path:

- `panko library import` registers the pack as a work source of type `pack` and writes its entries as units of 25,
  already **submitted**. Each item is the whole card plus `origin` = `{pack, id, version, hash}`. These units skip
  the extraction schema: Panko built them, so `pack.json`'s format version is checked instead.
- `ingest_source` then runs unchanged in what it decides: a known word, a held near-duplicate, a word you set aside,
  or a new card. Held cards appear on the source's page in the hub and are settled with `work decide`, like any
  other source's.
- **New cards are written whole.** Ingest already builds a new entry from every `ENTRY_KEYS` field of the item, so
  the picture, card types, notes, related words and the check come across. They get your own ids. Their sources
  are the pack's title (packs carry none of their own), and the tag `src::pack::<id>`. The pack's verdict becomes
  the item's verdict, so nothing is checked again by a model; the free tool checks (`checks.flag`) still run.
- **A word you already have keeps your card.** It gets a sighting, and the pack's real sentences as examples
  (written-by-Panko ones are skipped, as for any source). A gap is filled only where your card has none: a picture,
  for now. Nothing of yours is overwritten.
- **Origin lives on the sighting** (`sightings.origin`, which already exists) and, for a new card, on the entry. L4
  finds a pack's cards by those, and the `hash` is how it tells your edits from the pack's.
- **Language and varieties must match.** A pack in another language is refused. Cards of a variety you don't
  learn are skipped and counted; add the variety to `[learner] varieties` to take them.
- **A pack's cards stay apart.** Two cards the pack keeps separate (يبس ybes and يبّس yebbes) stay two cards:
  once ingest has found a pack card new, the write step doesn't look it up again by its letters.
- `role` on the sighting is `pack` (not `taught`), so a pack counts as weaker evidence than a lesson.
- Audio isn't a field: sync names each file by its text and voice, so with the same voices the pack's audio is
  found and nothing is paid. With other voices, the next sync makes new audio as usual.

**Updates.** Importing v2 over v1 matches entries by `origin`. A field the pack changed is updated unless you
edited it since the last import: Panko keeps a hash of what each pack gave, and your edits win, as with MyNotes. An
entry the pack dropped is not removed; it is listed for you.

## Build order

| Step | What "done" means |
|---|---|
| L1 ✅ | Pack format, `panko pack build` and `panko library import FILE`. Round trip tested: a pack from one store into an empty store, then into a store with overlaps (sightings, holds, rejected stays rejected). Built 2026-11-26 (`panko.library`); tried on 210 real food cards (39 MB): all imported, and a dry-run sync in the new Panko found every clip but the 4 never made. |
| L2 ✅ | `panko publish`: the checks above, the `.apkg` from the pack, the index entry and the report. Built 2026-11-26; tried on the 728 Peace Corps cards (112 MB each for the pack and the .apkg; the .apkg imports into a fresh Anki as 728 notes). |
| L3 | Library repo with `index.json`; `panko library list|get`; the hub's library page. |
| L4 | Updates: v2 over v1, your edits kept, dropped entries listed. |

**First deck:** the Peace Corps *Moroccan Arabic* words (the source is public domain, and nothing in it comes from
a teacher), once its pictures are done.

## Open
- **Audio terms:** whether the voice provider's terms allow sharing the audio it made in a free public deck, on the
  plan that made it. Check before the first deck with audio; if not, publish the no-audio variant.
- **Licence for the card text:** CC BY-SA 4.0 is the default (`[library] licence`). Photos keep their own licences.
- **DODa sentences:** DODa allows personal, research and educational use. Whether its corpus sentences can go in a
  free public deck is your call; until then they are left out (add `"DODa"` to `public_sources` to include them).
- **Repo name:** e.g. `panko-decks`.
- **Reference data in packs:** none. Packs carry cards, not DODa or Wiktionary data (their licences are summed up in
  the archived research, `docs/archive/research-2026-11.md` §7).
