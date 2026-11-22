# Panko: Note Type Spec v0.2 (draft)

## Changes in v0.3 (2026-11-23)
- Production front = picture (if any) + English. The picture-only card is retired.
- Recognition front = Arabic + audio. The separate Listening card is retired.
- Darija audio uses two voices: the headword is read by both, and examples alternate.
- Every word and phrase, Darija or Fusha, makes two cards: recognition (Arabic + audio) and production (picture + English). Plural / verb-form / root cards are off; that information is on the back.
- Decks: `Panko Sandbox::Darija` and `Panko Sandbox::Fusha` for now; words vs phrases is a tag (`kind::word` / `kind::phrase`).
- Scripture examples show their reference under the example ("Quran 16:75 (An-Nahl)").
- Card direction is pinned LTR; only Arabic text is RTL.

## Changes in v0.2 (2026-11-22, from your v0.1 phone test)
These override anything below that disagrees.
- **No register badge.** The deck (Darija / Fusha) says which variety a card is. `Register` stays as a field (for search/sorting) but is never shown.
- **Fronts show only the prompt.** Production = the English meaning only. No GlossNote, no "say it in…". Plural / verb-forms / root cards keep a one-word cue (`plural`, `present · masdar`, `root`) because otherwise the question is ambiguous.
- **No provenance in the card body.** Examples don't say "you said it" or "teacher's correction". A lesson example looks like any other. Sources, audio and picture credits appear only in the collapsed **Sources** section at the bottom.
- **No correction cards.** Words the teacher said that aren't in Panko yet become normal cards. Clips of the teacher's voice become the example audio.
- **Grammar line in words.** "noun, masculine · root خ ز ن". For verbs, a second line: present · imperative · masdar. `MorphologyHTML` now holds this line, rendered by `cards/render.py`.
- **Examples.** Arabic, then the main transliteration, then English. A small ▶ appears only if audio exists. Example audio is tap-to-play mp3, never autoplayed (see DECISIONS.md). The scholarly transliteration appears on the headword only, to keep examples light.
- **"Links" is now "Related".** A two-column list: Arabic | transliteration · meaning. Fusha equivalents are marked "(Fusha)" in the meaning.
- **Pictures.** A found photo comes before a generated image. Every concrete noun gets a picture card. Abstract words may still get a picture on the back, but no picture card.
- **Audio.** Never use a voice that speaks the wrong variety. Darija cards stay silent until ElevenLabs/Azure or a teacher clip provides audio, and Listening cards appear only then.


*Draft 2026-11-22. This defines how Panko's cards are built inside Anki. Everything here is meant to be challenged before anything gets created in your collection.*

---

## 1. Design rules

1. **The note holds everything you know about the word; each card tests one thing.** A note carries the word, its audio, picture, meaning, morphology, examples, links and notes. Every card made from it asks exactly one question.
2. **The field list is fixed from day one.** Adding, removing or reordering fields or card templates forces a full sync, and a full sync can wipe reviews your phone hasn't synced yet. So every field and card template we might need is created up front, including spares.
3. **Card types are switched on by filling a field.** Anki creates a card only when its front side has content, so each card type is wrapped in `{{#EnableX}}…{{/EnableX}}`. Turning on listening cards for 500 notes means filling one field per note: no schema change, no lost history.
4. **Fields come in two kinds.** Anything a card **tests** is a plain field: word, meaning, audio, picture. Display-only extras (examples, morphology tables, links, sources) are **pre-built HTML panels** that Panko writes. Changing how panels look is a CSS edit. Changing their structure means Panko rewrites the fields, which syncs normally and keeps your history.
5. **Every fact shows where it came from.** Each example, audio clip and note says whether it came from your teacher, Peace Corps, a media clip, the Quran, a dictionary, or Panko itself.
6. **You always win.** If you edit a Panko-written field in Anki, Panko notices on its next sync and never overwrites that field again until you unlock it. There is also one field, `MyNotes`, that Panko never writes at all.

---

## 2. Decks & tags

**Decks (two).** While in the sandbox they are `Panko Sandbox::Fusha` and `Panko Sandbox::Darija`; the names below are the eventual ones.
- `Arabic::Fusha`: MSA and Quranic. Quranic words are Fusha, so they share a deck and are told apart by tag.
- `Arabic::Darija`

Decks stay few because a deck is a *scheduling* choice. Everything else goes in tags, which cost nothing and can be filtered.

**Tag families:**
| Tag | Example | Purpose |
|---|---|---|
| `src::` | `src::lesson::2026-11-18`, `src::teacher::m06-hanout`, `src::aby::1::ch01`, `src::peace-corps::l08`, `src::media::<show>::s01e03` | Where the item was first met (you can have several) |
| `register::` | `register::fusha`, `register::quranic`, `register::darija` | Register |
| `pos::` | `pos::verb`, `pos::noun`, `pos::expression` | Part of speech |
| `root::` | `root::ن_ظ_ر` | Browse a whole root family |
| `topic::` | `topic::food`, `topic::shopping` | Theme |
| `panko::` | `panko::needs-review`, `panko::user-edited`, `panko::generated-example`, `panko::correction` (from a teacher correction) | Status and quality flags |

---

## 3. Note type `Panko • Word`

Covers all vocabulary for both registers: nouns, adjectives, verbs, particles, and multi-word expressions that behave like one word (e.g. مول الحانوت).

### 3.1 Fields
(🧪 = a card tests this · 🖼 = display panel · 🔒 = hidden · ✍️ = yours only)

**Identity**
| Field | Fusha | Darija | Notes |
|---|---|---|---|
| `Word` 🧪 | fully vowelled: مَثَّلَ | as your teacher writes it: الكارني | First field, so it's what the Browser shows |
| `WordBare` | مثل | الكارني | Harakat stripped by code, never by the LLM |
| `WordPartial` | vowelled only where ambiguous | — | Fusha only |
| `WordPrompt` | Panko fills it from your deck settings (bare, partial or full) | same | **The form shown on the card front.** Change the harakat rule and Panko rewrites this one field. |
| `Translit` | scholarly: maththala | **teacher Arabizi**: l-karni | Main transliteration |
| `TranslitAlt` | — | Peace Corps scholarly: l-karni / ḥḍāš | Secondary transliteration |
| `Register` | Fusha / Quranic | Darija | Shown as a badge |
| `POS` | verb | noun | |
| `Gloss` 🧪 | to represent; to play (a role) | credit notebook (tab) | The answer on recognition cards; keep it short |
| `GlossNote` | "as in representing a country" | "the shop's IOU book" | Narrows the sense; shown on the production prompt |

**Media**
| Field | Notes |
|---|---|
| `Audio` 🧪 | `[sound:…]` for the word. Native audio is preferred; TTS only as a fallback |
| `AudioSource` | e.g. "Peace Corps L08 (native)" or "Azure ar-SA (TTS)". Shown in small print |
| `Image` 🧪 | `<img>`: cropped from your source if there is one, otherwise found online |
| `ImageSource` | Where the picture came from |

**Morphology** (always filled for Fusha; filled for Darija only when known)
| Field | Example |
|---|---|
| `Root` | م ث ل |
| `Pattern` | فَعَّلَ |
| `VerbForm` | II |
| `Present` | يُمَثِّلُ (Darija: يبغي ybghi) |
| `Imperative` | مَثِّلْ |
| `Masdar` | تَمْثِيل |
| `Preposition` | (إِلَى), as in your current verb cards |
| `Gender` | m / f |
| `Plural` 🧪 | قِطَع: the plural moves off the front of the card into its own field |

**Panels** (HTML written by Panko)
| Field | Contents |
|---|---|
| `ExamplesHTML` | **Required, at least one.** Up to 3 examples, most trusted source first. Each one shows the Arabic sentence, both transliterations (Darija), English, a source badge and an audio button. Real examples are preferred to generated ones, and generated ones are labelled. |
| `MorphologyHTML` | Conjugation or declension table, produced by code rather than the LLM (Fusha) |
| `LinksHTML` | Fusha ↔ Darija cognates (الثقة tiqa ↔ ثِقَة), words from the same root that are already in your deck, equivalents in the other register |
| `NotesHTML` | Teacher notes, usage and etiquette (e.g. "say عفاك"), regional variation |
| `SourcesHTML` | Full source list: teacher sheet + page, Peace Corps lesson, dictionary links (Wiktionary etc.) |
| `MyNotes` ✍️ | Your own notes. **Panko never writes here.** |

**Card switches** (empty = off, any value = on)
`EnableProduction`, `EnableListening`, `EnablePicture`, `EnablePlural`, `EnableVerbForms`, `EnableRoot`, `EnableTyped`, `EnableSpare1`, `EnableSpare2`

**Hidden**
`PankoID` 🔒 · `PankoData` 🔒 (JSON: what was checked and how, field hashes for detecting your edits, schema version) · `Spare1`–`Spare4` 🔒

### 3.2 Card types (all created up front)
| # | Card | Front | Answer | Created when | Default on for |
|---|---|---|---|---|---|
| 1 | **Recognition** | `WordPrompt` (+ audio button) | Gloss + everything | always | everything |
| 2 | **Production** | Gloss + GlossNote (+ picture) | Arabic + translit + audio | `EnableProduction` | **Darija** (you want to speak); Fusha only if you choose |
| 3 | **Listening** | audio only | Word + gloss | `EnableListening` + `Audio` | Darija with native audio |
| 4 | **Picture** | picture only | Word + audio | `EnablePicture` + `Image` | Concrete Darija nouns, like your iExplore and Serious Explorer cards |
| 5 | **Plural** | singular + "plural?" | Plural | `EnablePlural` + `Plural` | Fusha nouns with broken plurals |
| 6 | **Verb forms** | past tense → "present / masdar?" | Present + Masdar | `EnableVerbForms` + `Masdar` | Fusha verbs |
| 7 | **Root** | word → "root?" | Root + family | `EnableRoot` + `Root` | off (opt-in) |
| 8 | **Typed** | Gloss → type the Arabic | your answer compared with the correct one | `EnableTyped` | off |
| 9–10 | **Spare 1/2** | (empty) | — | `EnableSpare1/2` | Placeholders that create no cards. Writing their template later adds a whole new card type **without a full sync**. |

### 3.3 Answer layout (top to bottom)
`register badge · POS` → picture → **Word (fully vowelled) 🔊** → `Translit` / `TranslitAlt` → **Gloss** → morphology line (root · form · masdar · plural) → **Examples** (always shown) → links → notes → `MyNotes` → sources and verification badge, collapsed by default.

---

## 4. Note type `Panko • Phrase`

For sentences, set phrases and dialogue lines. Your teacher's sheets are mostly these, e.g. "كتبها عليا فالكارني".

**Fields:**
- `Phrase` 🧪 (as the source writes it) · `PhraseFull` (vowelled, Fusha only) · `PhrasePrompt`
- `Translit` (Arabizi) · `TranslitAlt` (scholarly) · `Register`
- `Translation` 🧪 · `Literal` (word by word: "write-it on-me in-the-tab")
- `Audio` 🧪 · `AudioSource` · `Image` · `ImageSource`
- `UsageHTML` ("how and when to use it", taken from the teacher's notes)
- `KeyWordsHTML` (links to the `Panko • Word` notes it contains) · `DialogueHTML` (the lines around it, for context)
- `SourcesHTML` · `MyNotes` ✍️
- Switches: `EnableProduction`, `EnableListening`, `EnableTyped`, `EnableSpare1`, `EnableSpare2`
- `PankoID` 🔒 · `PankoData` 🔒 · `Spare1`–`Spare4` 🔒

**Cards:**
| # | Card | Front | Default |
|---|---|---|---|
| 1 | Recognition | phrase (+ audio button) → meaning | always |
| 2 | Production | English + usage note → say it in Darija | **on for Darija** |
| 3 | Listening | audio → meaning | when native audio exists |
| 4 | Typed | English → type it | off |
| 5–6 | Spare 1/2 | — | placeholders |

**The link between the two types:** words found inside a phrase become (or link to) `Panko • Word` notes, and the phrase becomes one of their examples. Learning a phrase therefore strengthens its words, and each word card shows real phrases from your lessons.

---

## 5. Later note types (not needed for v1)
Creating a **new** note type doesn't force a full sync, so these can wait:
- `Panko • Grammar`: a grammar point tested *inside example sentences*, e.g. negation ما…ش or i'rab of a case ending.
- `Panko • Ayah`: Quranic ayah and word-in-context study with verified i'rab (QAC/MASAQ) and recitation audio.
- `Panko • Cloze`: only if needed. Research suggests leaving cloze off by default, because a bad cloze card fails without anyone noticing.

---

## 6. Harakat, script & transliteration rules

| | Fusha / Quranic | Darija |
|---|---|---|
| Arabic shown | Full, bare or partial, chosen per card type (`WordPrompt`); the answer side is always fully vowelled | As the source writes it; **Panko adds no harakat** because there's no standard to check them against |
| Quran text | Copied word for word from Tanzil, never regenerated | — |
| Main transliteration | Scholarly (optional) | **Teacher Arabizi** (3tini) |
| Secondary transliteration | — | Peace Corps scholarly (bġīt) |
| Spelling differences | — | Your teacher's spelling is shown as written. Variants (Bshhal/Bcha7al) are kept in `PankoData` for matching and dedup |

**Rendering:**
- Arabic goes inside `<div dir="rtl" lang="ar">` and Latin text inside `<bdi>`.
- `line-height: 2` plus padding stops AnkiMobile clipping stacked marks like shadda plus a vowel.
- Fonts are bundled as `_PankoNaskh.ttf`. Scheherazade New, Amiri and Noto Naskh will be tested on your phone first.
- Dark theme by default, matching your current cards.

---

## 7. Example policy (required on every Word)

1. Each Word gets **at least one** example and at most three.
2. Order of preference: **lesson recording (teacher's voice)** → teacher sheet → Peace Corps (native audio) → media clip (film or TV) → Quran or hadith (Fusha) → dictionary or corpus → **Panko-generated (last resort)**.
3. Generated examples are tagged `panko::generated-example` and must pass the deterministic checks. For Darija they also go to review.
4. At least one example should have audio when any is available.
5. Each example shows: Arabic · Arabizi · scholarly transliteration (Darija) · English · source badge · audio button.

---

## 8. Moving your existing studied notes (history kept)

Notes you've **studied** are converted in place with Anki's Change Note Type, mapping each old card type to a Panko card so review history is kept. **Unstudied** notes aren't converted; they're mined as source material and then retired.

| Current | Studied | Field mapping (draft) | Card mapping |
|---|---|---|---|
| Arabic verbs (ABY 1–3) | part of 535 | `Front` "نَظَرَ (إِلَى) \ يَنْظُرُ \ اُنْظُرْ \ نَظَرٌ" → `Word` / `Preposition` / `Present` / `Imperative` / `Masdar`; `Back` → `Gloss`; `Form` → `VerbForm`; `Root` → `Root`; Hans link → `SourcesHTML` | Card 1 → Recognition |
| Arabic nouns (ABY 1–3) | part of 535 | to be inspected (likely singular \ plural → `Word` / `Plural`) | Card 1 → Recognition |
| iExplore | 82 | `Front` → `Word`; `Back` → `Gloss`; Wiktionary link → `SourcesHTML` | Card 1 → Recognition, Card 2 → Production |
| Serious Explorer | 60 | the front's picture of text → OCR → `Word` + `Translit`; front sound → `Audio`; back picture → `Image`; back text → `Gloss` | Card 1 → Recognition, Card 2 → Picture |
| Shared Darija decks | ~110 | to be inspected per note type | per note type |

**How it runs:**
1. Close Anki.
2. A script uses the official `anki` library, pinned to your desktop version. The MCP add-on can't change note types.
3. Convert a test batch of about 10 notes and check them on your phone.
4. Convert the rest.
5. One full upload.

Before starting: sync every device and make a full backup.

---

## 9. Things to test before building (Phase 0)

| Question | Why it matters |
|---|---|
| Does audio inside the examples panel **auto-play** on AnkiMobile? Anki plays every `[sound:]` on a side automatically. | We may need play buttons instead of `[sound:]` tags for examples. |
| Do collapsible `<details>` sections work on AnkiMobile? | The collapsed sources panel depends on it |
| Which font gives the cleanest harakat on your iPhone | Readability |
| Can the original Peace Corps lesson MP3s be lined up with the textbook text and cut into clips cleanly? | The native audio pipeline depends on it |
| How do the existing **Arabic nouns** and shared-deck note types map? | Completes §8 |

---

## 10. Open questions for you
1. **Two decks (Fusha incl. Quranic, Darija) or three (separate Quranic)?**
2. **Fusha production cards:** on by default, or recognition only unless you switch them on?
3. **Fusha transliteration:** show scholarly transliteration on Fusha cards, or Arabic only? You can already read vowelled Arabic.
4. **Picture cards for Darija:** on for every concrete noun, or only when the source provided a picture?
