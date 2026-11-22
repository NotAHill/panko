# Panko — Research & Architecture Recommendation

*Researched 2026-11-21/22. Scope: a personal tool that turns your own Arabic study material into verified, reconfigurable Anki cards.*

---

## 0. What you told me (the requirements)

| Topic | Answer |
|---|---|
| Language | **Arabic**: MSA, Classical/Quranic, **and** a dialect (which one is still open) |
| Reviews happen on | Anki desktop, **AnkiMobile (iOS)**, AnkiWeb |
| Sources | Textbooks/PDFs, own notes/lists, media (YouTube/podcasts) |
| Card types | Vocab (root, wazn, plurals, masdar, form I–X), grammar/morphology, audio/listening |
| Harakat | **Configurable per card**, e.g. unvowelled front and vowelled back |
| Audience | Just you, for now |
| Budget | Quality first |
| "Configurable" means | **Change card format later without losing review history** |
| Existing cards | **Panko should manage them too**: enrich, reformat, dedupe |
| Review step | **Auto-add; flag the doubtful ones** |
| Interface | Not sure; I recommend one below |

---

## 1. The big decision: clone, fork, or standalone?

**Recommendation: build a standalone Python app that writes into your real Anki collection through AnkiConnect. Don't clone Anki and don't fork it.**

| Option | Verdict | Why |
|---|---|---|
| (a) Build an Anki clone | ❌ | You would lose AnkiMobile, AnkiWeb sync, FSRS and your review history. You would be rebuilding a mature scheduler and sync system to solve a *content* problem. |
| (b) Fork ankitects/anki | ❌ | The codebase is large (Rust, Python, Svelte) and AGPL-licensed, and you would be rebasing every 1–3 months. Fork-only features **would never reach AnkiMobile**, which is closed source. Only what sync carries survives: notes, fields, templates, CSS/JS, media and scheduling. |
| (c) Standalone app + AnkiConnect | ✅ | All the heavy LLM/NLP work stays outside Anki. Anki, AnkiWeb and AnkiMobile stay exactly as they are, and Panko just writes notes and templates. It's easy to test and to version. |
| (d) Anki add-on | ➖ later | Only worth it as a *thin* add-on later, e.g. a "Regenerate with Panko" button in the Browser that calls the backend. Running heavy work inside Anki freezes its UI, and every Anki release can break add-ons. |

The key insight: **everything that makes your cards better (content, fields, templates, CSS, JS, audio) travels through Anki's normal sync.** The things a fork would let you change (the scheduler, the review UI) are the things you *don't* need to change, and couldn't change on iOS anyway.

### Anki facts that shape the design (verified Nov 2026)
- **Anki 26.09.4** is stable and **26.11** is in beta. Stewardship passed from Damien Elmes to the **AnkiHub** team in Feb 2026, and releases are now more frequent.
- **AnkiConnect** moved from GitHub to `git.sr.ht/~foosoft/anki-connect`. It is **very active again**: near-daily commits in Oct–Nov 2026 and a new **JSON-RPC API v1**. Highlights: atomic `notes.createMany`, `noteTypes.editStructure` (field/template edits that keep card identity), a wrapper around Change Note Type, and a `collection.sync` that **stops and asks** when a full sync is required. The risk is that it has one maintainer, who was unreachable as recently as September.
- **Updating a note's fields keeps its cards and all review history.** That is the foundation for "change format later".
- **Changes that force a full sync**, where one side overwrites the other and unsynced mobile reviews can be lost: adding, removing or reordering *fields*; adding, removing or reordering *card templates*; changing the sort field; Change Note Type.
- **Changes that sync normally**: editing template HTML/CSS/JS, renaming a field, and editing note contents.
- The `anki` PyPI package can open the collection headlessly, but **only while desktop Anki is closed**: it takes an exclusive lock, so a clash fails cleanly rather than corrupting anything. Keep it as a fallback, pinned to the same version as your desktop app.
- When re-importing an `.apkg`, Anki matches notes by **GUID** and never touches existing cards or scheduling. This is a fallback path; genanki is effectively unmaintained.

---

## 2. Core design: the knowledge lives in Panko; Anki is a renderer

This is what makes "change the format later" safe.

```
 Sources ──► Ingest ──► Extract candidates ──► Ground & enrich ──► Verify ──► Panko DB ──► Render ──► AnkiConnect ──► Anki ⇄ AnkiWeb ⇄ AnkiMobile
 (PDF, notes,   (vision LLM,   (LLM + CAMeL       (LLM picks sense,   (deterministic  (canonical   (recipes →
  media)         OCR, ASR)      morphology)        writes glosses;     tools + judge)  lexemes,      note fields
                                                   tools give facts)                   provenance)   + templates)
```

### 2.1 Canonical store (SQLite)
Panko's own database holds **lexemes and items**, independent of any card format. A lexeme has a lemma, root, pattern, form, plurals, masdar, glosses by register (MSA, Classical, dialect), examples, audio hashes, sources/provenance and a per-field verification status. Each one links to the Anki note ID plus a stable `panko_id`.

### 2.2 "Future-proof" Panko note types (avoiding full syncs)
Design each note type **once**, with a generous field set, so that later "format changes" are almost always template/CSS edits, which sync normally:

- **Fields (fixed up front):** `PankoID`, `Ar_Full`, `Ar_Bare`, `Ar_Partial`, `Root`, `Pattern`, `VerbForm`, `Plurals`, `Masdar`, `Gloss`, `Register`, `Dialect`, `Example_Full`, `Example_Bare`, `Example_Gloss`, `Audio`, `ExampleAudio`, `Conjugation` (HTML), `Notes`, `Source`, `Verification`, `Data` (hidden JSON for anything new), plus a few `Spare1..3`.
- **Card templates gated by "enable" fields.** Anki only creates a card when the template's front renders non-empty. So define all the card types you might want up front (Recognition, Production, Listening, Root/Wazn, Plural, Masdar, Conjugation). Gate each one with `{{#Enable_Listening}}…{{/Enable_Listening}}`. **Turning on listening cards for 500 notes then just fills one field**: no schema change, no full sync, and existing history is untouched.
- **Harakat per card.** Python precomputes `Ar_Full`, `Ar_Bare` and `Ar_Partial` (vowelled only where ambiguous) at build time. Each template simply picks the variant it wants. That's more robust on AnkiMobile than JavaScript stripping, and stripping ranges in the wild are usually incomplete: they need U+064B–065F, U+0670, U+06D6–06ED and U+0640.
- Genuine schema changes (a new field or template) are batched rarely. Panko then runs an explicit routine: "sync all devices → apply → upload from desktop".

### 2.3 Recipes (per-deck configuration)
A **recipe** is a declarative YAML/TOML file per deck or subject. It sets which note type to use, which card types are enabled, the harakat rule per side, register and dialect, TTS voice, gloss style and example difficulty. Changing a recipe recomputes affected fields or template HTML and pushes the diff through `notes.update` and `noteTypes.update`. Review history stays intact.

### 2.4 Taking over your existing cards
This is a one-time, deliberate migration:
1. Panko first reads them without changing anything (`findNotes`/`notesInfo`).
2. It shows you a mapping plan.
3. It runs **Change Note Type** onto the Panko note type, mapping old templates to the new ones so card IDs and history survive.

This is one full sync, done when all devices are synced. From then on, enrichment happens through ordinary field updates. Your existing cards also seed Panko's "already known" set for dedup.

---

## 3. Arabic: what makes this hard and how to make it reliable

### 3.1 The problem
Research from 2025–26 is consistent. Frontier LLMs are now **good at MSA diacritization in context**: in an LREC 2026 study, GPT-4o reached about 2% CER and beat the specialized tools (CATT about 10%). But LLMs:
- sometimes **change the base letters**, not just the vowels (1–3% of words);
- are **weak on morphology, i'rab and syntax** (ALPS, AraLingBench, YallaMorph);
- are **weaker on dialects**. On the Levantine SHAMS benchmark, a dialect-specific tool beat every frontier LLM.

Claude models scored *below* some competitors on these diacritization benchmarks. So Panko should keep the LLM layer swappable and **pick models per task using a small eval built from your own material**, rather than trusting any one vendor.

**Principle:** deterministic tools supply the *facts* (root, pattern, forms, plurals, conjugations). The LLM *selects, explains and writes*. Every LLM-produced field gets checked.

### 3.2 Grounding stack (defaults)
| Need | Default | Notes / license |
|---|---|---|
| Morphology (root, pattern, lemma, POS, features) | **CAMeL Tools 1.6** (NYU Abu Dhabi) + Camel Morph MSA DB | Code MIT. The MSA/Egyptian DBs are GPL (fine for personal use). Gulf DB is CC BY 4.0. **No open Levantine morphology DB.** |
| Second opinion | SinaTools (Birzeit, MIT), linked to the **Qabas** lexicon (about 58K lemmas, Classical + MSA + dialect) | Qabas data license unverified |
| Forms: plurals, masdar, verb forms, conjugation tables | **Wiktionary via kaikki.org** (CC BY-SA) + CAMeL generator | Verified: has form-I–X tags, masdars and broken plurals. Root tagging is inconsistent. |
| Classical / Quranic meanings | **Lane's Lexicon** (Perseus TEI, CC BY-SA) | Hans Wehr is copyrighted; don't ingest it |
| Quran text | **Tanzil**: store verbatim, never regenerate | CC BY 3.0, no modification |
| Quranic morphology / i'rab | **Quranic Arabic Corpus** (GPL, non-commercial) + **MASAQ** (CC BY) | The only reliable i'rab ground truth |
| Diacritization check | LLM output must be one of CAMeL's analyses; **CATT** as second vote | Never check dialect text with MSA tools |
| Dialect | CAMeL dialect ID; Egyptian (`calima-egy`) or Gulf (`calima-glf`) DBs; MADAR lexicon (personal use) | **Egyptian or Gulf have far better tooling than Levantine or Maghrebi** |

### 3.3 Verification rules (what gets the `panko::needs-review` tag)
| Field | Check |
|---|---|
| Base letters | With harakat stripped, the text must match the source exactly; otherwise reject |
| Tashkeel | Every word's vocalization must be in CAMeL's analysis set; disagreement with CATT → flag |
| Root | At least 2 of 3 agree (CAMeL, Qabas, kaikki); for Quranic words, QAC/MASAQ decides |
| Wazn / verb form | Must match CAMeL's pattern feature exactly |
| Plurals / masdar | The LLM's list must be a subset of kaikki/CAMeL-generated forms |
| Conjugation tables | **Generated deterministically** by CAMeL. The LLM only writes the explanation |
| I'rab | Verified for Quran (QAC/MASAQ); elsewhere it must agree with CAMeL's case/mood features, and is otherwise marked "unverified" |
| Audio | TTS gets verified full tashkeel; ASR back-transcription mismatch → flag |
| Gloss | Soft check: at least one dictionary source has an overlapping sense |

Matching what you asked for: cards are **auto-added**, failures are **tagged and listed** in Panko's UI, and nothing is silently "fixed".

### 3.4 Ingestion
- **Textbooks/PDFs:** a frontier **vision LLM reads page images** at high resolution, and **QARI-OCR** (an open Arabic OCR model) runs independently. Panko diffs the two, first on base letters and then on harakat, and flags disagreements. Tesseract drops harakat, so don't use it.
- **Your notes and lists:** typed lists go straight in. Photos of notebooks go through the vision LLM, followed by a confirm step.
- **Media:** `yt-dlp` fetches subtitles where they exist. Otherwise a frontier audio LLM transcribes (best on dialect in 2026 benchmarks), with a Whisper Arabic fine-tune as cross-check. Whisper large-v3 tends to replace dialect with MSA.

### 3.5 Audio (TTS)
- **Azure Neural**: 16 Arabic locales, each with a male and a female voice. `ar-SA` for MSA, and the matching locale (ar-EG, ar-JO, ar-LB, ar-SY, ar-AE…) for your dialect. Azure improved its Arabic diacritizer, but **send fully vowelled, verified text**, which removes ambiguity. Use SSML for fixes. Caveat: many "dialect" voices are MSA with a local accent, so test yours.
- Open fallback: SILMA TTS (Apache-2.0, accepts tashkeel), or Habibi for dialects.
- Cache audio by hash of (text, voice, settings), so regenerating a card never re-buys audio it already has.

### 3.6 Anki rendering on iOS
- Wrap Arabic in `<div dir="rtl" lang="ar">` and wrap English inside a line in `<bdi>`.
- AnkiMobile has a known issue where **shadda + another mark gets clipped**. Use a generous `line-height` (about 2) plus padding, and test fonts on your phone: Scheherazade New, Amiri, Noto Naskh Arabic (all OFL), bundled as `_Font.ttf` media.

---

## 4. What already exists (and why it doesn't solve your problem)

| Tool | What to take from it |
|---|---|
| **anki-llm** (MIT, CLI) | The closest thing to Panko: file-based config, picking which cards to import, rollback. No dictionary checks, no document sources. Worth studying. |
| **Smart Notes** (add-on) | Prompts chained per field and a solid TTS provider layer. It enriches existing notes; it doesn't create cards from sources. |
| **Yomitan / asbplayer / Migaku** | Mining one sentence at a time, focused on Japanese. No LLM grounding, and weak for Arabic. |
| **AnkiMorphs** | Tracked which words you know ("i+1"). **Archived Oct 2026**, so this niche is now empty. |
| Web AI generators (Quizgecko, StudyFetch…) | Generic, not language-aware, often lock you in. |

**The gap Panko fills:** mixed sources → the items worth learning → cards **checked against morphology and dictionaries** → a card format you can change later without losing history → dedup against your real collection. For Arabic specifically, nothing comes close.

Recurring complaints about AI cards that Panko must design against:
1. Prompting takes as long as writing cards.
2. Mistakes that sound plausible.
3. Floods of low-value cards.
4. Cards that test more than one thing.
5. Answers that leak into the prompt.
6. No way to edit in bulk.

Built-in fixes: one fact per card, rule-based checks for leaks and compound prompts, a cap on new cards per source, and prefer **real** sentences (from your source, Tanzil or hadith corpora) over invented ones.

---

## 5. Recommended stack

| Layer | Choice |
|---|---|
| Language | **Python 3.12+**, managed with `uv`: CAMeL Tools, OCR, ASR and TTS SDKs are all Python-first |
| Storage | SQLite (SQLModel) + `sqlite-vec` for near-duplicate detection; content-addressed media folder |
| Anki | **AnkiConnect API v1**, with headless `anki` pylib (version-pinned) as fallback when desktop is closed |
| LLM | Behind a thin interface. Start with **Claude Opus 5.5** (quality first) using structured outputs, prompt caching and the Batch API for bulk runs; benchmark against alternatives on an Arabic eval |
| Jobs | In-process resumable job queue (OCR, ASR and batch runs are long) |
| Interface | **Local web UI** (FastAPI + HTMX, on localhost) for dropping in sources, browsing flags, previewing cards and editing recipes. **Plus a CLI** on the same core for batch work. An Anki add-on button comes later, if wanted. |

Why a web UI rather than a CLI alone: Arabic card previews (RTL, harakat, audio) and the review queue for flagged cards are naturally visual. A desktop wrapper adds packaging pain for no benefit.

---

## 6. Phased plan

**Phase 0: Spikes (de-risk; about 1 session each)**
1. Confirm AnkiConnect v1 works on your Anki version. Read-only export of your existing Arabic decks to see what we're migrating.
2. Install CAMeL Tools and run it on a page of your real material. Measure how often root, pattern and plurals come out right.
3. **Arabic eval:** 30–50 items from your material, used to compare models on tashkeel, roots, plurals and glosses.
4. Template test on **your iPhone**: fonts, harakat clipping, RTL, the three harakat variants.

**Phase 1: MVP vocab loop (CLI)**
Vocab list or text → candidates → grounded and verified vocab notes → AnkiConnect into a test deck, with flags.

**Phase 2: Panko note types + migration + web UI**
Final note-type design, migration of your existing decks, and a review queue for flagged cards.

**Phase 3: Textbooks + audio**
Vision/QARI ingestion of PDFs; Azure TTS with verified tashkeel; ASR back-check.

**Phase 4: Grammar/morphology + media**
Conjugation and wazn cards (deterministic tables), i'rab for Quranic text, YouTube and podcast ingestion.

**Phase 5: Reconfiguration engine & polish**
Recipe editing → automatic field/template diffs, known-word tracking (the gap AnkiMorphs left), and an optional thin add-on.

---

## 7. Risks
| Risk | Mitigation |
|---|---|
| A full sync wipes unsynced mobile reviews | Avoid schema changes by design (§2.2); a guided "sync everything first" flow when one is unavoidable |
| AnkiConnect has one maintainer | Keep the Anki adapter behind an interface; pylib/apkg fallback; Tsunagi is a compatible alternative to watch |
| Anki or AnkiConnect changes after the AnkiHub transition | Pin versions; integration tests against a throwaway profile |
| LLM Arabic errors | Deterministic verification (§3.3); flags instead of silent trust; per-task model choice from the eval |
| Dialect tooling gaps (Levantine, Maghrebi) | Lean on LLM + MADAR + manual review for dialect fields; mark them lower confidence |
| AnkiWeb terms for headless sync (unverified) | Only use the AnkiConnect path, which goes through your own desktop app; a self-hosted sync server is an option if ever needed |
| License creep (GPL/NC data) | Fine for personal use. If Panko is ever distributed, switch to the CC BY/MIT stack listed in §3.2 |

---

## 8. Open questions for you
1. **Which dialect?** It decides how much can be verified automatically. Egyptian and Gulf have good tooling; Levantine and Maghrebi much less.
2. **Can you share 3–5 of your existing hand-made cards** (an export, or a description of the fields/templates) plus a sample page of a textbook you use?
3. Do you have **AnkiConnect** installed, and which Anki version is on your desktop?
4. Are you OK with Python for the backend, and with Anthropic + Azure API keys (or another TTS)?
5. Roughly how big are your existing Arabic decks: hundreds of notes or thousands?

---

## 9. Findings from your real material and collection (2026-11-22)

**Learning targets:** Fusha/Quranic plus **Moroccan Darija** (Maghrebi, which has the weakest open tooling). Both scripts on cards. Pictures cropped from sources, otherwise found online. Media: movies and TV clips.

### Teacher sheets (El Yadari Oussama, *Mol l-7anut* and *Bargaining at the Souk*)
- These are the teacher's own sheets, not Peace Corps. They use **Arabizi** (3 = ع, 7 = ح, 9 = ق, 2 = ء) and have **no harakat**.
- Content is mostly **phrases, dialogues, measure words with usage examples, etiquette notes and quizzes**. There are no pictures.
- **Arabizi spelling is inconsistent** even within one sheet: Bshhal/Bcha7al, zarbiya/zerbiya/zerabi, wash/wach, mol/moul, akhir/akher. Matching therefore has to be fuzzy, while the teacher's spelling is shown exactly as written.
- **The PDF text layers can't be trusted.** In the souk sheet, broken font encoding turns the text layer into garbage. In the hanout sheet, Arabic word order comes out reversed in the tables. Panko must **read the rendered page images with a vision model**, never the extracted text.

### Your collection (read-only survey through the Anki MCP add-on)
| Area | Decks | Notes | Studied |
|---|---|---|---|
| MSA | Arabiyyah Bayna Yadayk 1–3 (types: Arabic nouns / Arabic verbs, with Root, Form, Hans Wehr link) | 1,526 | 535 |
| MSA | iExplore (Wiktionary-link cards) | 137 | 82 |
| Darija | Shared decks: Darija, Casablanca 1–2, Dave's Darija, Most Used Moroccan, Peace Corps Dictionary | ~9,900 | **~110 (about 1%)** |
| Darija | Serious Explorer (picture + audio) | 60 | 60 |
| Darija | Basic Introduction to Moroccan Arabic (AR • Vocabulary++ / Sentence+ / Cloze+ / Grammar++ / Contrast++) | 374 | 29 |

- **The shared Darija decks are mostly unstudied**, which is the quality problem you described. They do hold **native audio and images**, so the plan is to **mine them as a source** instead of reviewing them as they are.
- **The *Basic Introduction* deck already uses Panko's core pattern:**
  - card types gated by enable fields (`ModeEN2AR`, `ModeListen`, `ModeRoot`, `ModeContext`, `ModeType`);
  - `source::` / `register::` / `voice::` tags;
  - native Peace Corps audio;
  - morphology HTML cards.
  - **Decision (2026-11-22): don't reuse it; design Panko's note types fresh.** The deck will be deleted. Panko takes Peace Corps audio from the **original course release** instead: the 2011 *Moroccan Arabic* textbook plus about 10 long lesson MP3s, free via Live Lingua. Panko cuts word and sentence clips out of those MP3s by lining the audio up with the textbook text, and checks each clip against that text.
- **Decision: transliteration.** Cards show both scripts and **both transliterations**: the teacher's Arabizi as the main one and Peace Corps scholarly as secondary. **Example sentences are required** on every word card.
- **Three transliteration systems are in use:** teacher Arabizi (3tini), Peace Corps scholarly (bġīt, ḥḍāš), and ad-hoc (feen). Panko needs one canonical display, with the others stored as alternates.

### Design updates
- **What counts as truth for Darija, most trusted first:** teacher sheets → native recordings (Peace Corps, your own) → shared decks → LLM. Every fact shows where it came from.
- **Phrase/sentence notes are first-class for Darija**, because the teacher's material is mostly phrases. Each word card pulls example phrases from every source where the word appears.
- **Fusha cognate links** are a cheap, high-value win. Examples: الثقة tiqa ↔ ثِقَة, الصرف ↔ صَرْف, خبزة ↔ خُبْز.
- **Anki MCP add-on** (port 3141) is confirmed working. Destructive tools are disabled; keep it that way. Panko's writes go through its own layer, which uses `add_notes` / `update_notes`.

---

## 10. Sources and the candidate inbox

Every source feeds the same pipeline through its own **source adapter**. Panko records a **sighting** each time a word or phrase appears anywhere. When something you don't have in Anki keeps being sighted, it becomes a **candidate**.

```
 adapters ──► sightings (word/phrase + source + timestamp/page + audio span) ──► match against your collection
                                                                                  ├─ already known → add example/audio to existing note
                                                                                  └─ new → candidate inbox → rank → auto-add / park
```

### Source adapters (planned)
| Adapter | Input | What it yields | Trust |
|---|---|---|---|
| **Lesson recordings** | Your recordings and transcripts of lessons with your teacher | Words and phrases the teacher **taught, explained or corrected**; clips of the teacher's voice; your mistakes | ★★★★★ |
| Teacher sheets | PDFs (read as page images) | Vocabulary, phrases, usage notes, dialogues | ★★★★★ |
| Peace Corps course | 2011 textbook + lesson MP3s | Words and sentences with native clips cut from the MP3s | ★★★★ |
| Media | Film/TV episodes (video + subtitles, or transcribed) | Real usage sentences + clips | ★★★ |
| Your notes | Typed lists, photos of notebook pages | Words you wrote down | ★★★★ |
| Shared decks (mined, then retired) | Existing Anki notes | Audio, images, glosses as raw material | ★★ |
| Fusha references | Arabiyyah Bayna Yadayk, Quran (Tanzil), hadith, Wiktionary, Lane | Fusha vocabulary, verified forms, examples | ★★★★ |

### Lesson recordings: the most valuable source
- **Transcription:** lessons mix Darija, English and possibly French. Whisper handles this poorly, so the default is a frontier audio model with **speaker separation** (teacher vs. you).
- **Teaching moments:** an LLM pass finds moments such as "X means Y", "we say X", "no, it's X not Y", and spelled-out words. These count as *taught*, which is stronger than *mentioned*.
- **Corrections become cards:** when the teacher corrects you, Panko creates the card for the correct form, tagged `panko::correction`. Where it helps, the back of the card notes your mistake.
- **Teacher audio:** each sighting keeps its timestamp, so the teacher saying the word or phrase becomes the card's native audio, ranked above TTS and any other recording.
- **Missed words:** anything taught in a lesson that isn't in your deck or on that lesson's sheet goes into the inbox.

### Lesson capture: what Granola does and doesn't give us (checked 2026-11-22)
- **Granola keeps no audio.** On desktop it transcribes live and discards the sound; on iOS the audio is cached only until transcription finishes. **Past lessons therefore exist as transcripts only.**
- **Granola's speech recognition mangles Darija.** In the 21 Nov lesson:
  - كيف كانت السفر came out as "Give Kent Safar".
  - غسالة came out as "Rosala / رسالة".
  - تخفيض came out **in Hebrew script**.
  - The Arabic-script stretches and the "Me/Them" speaker split are usable. Candidates taken from transcript text alone are therefore **low trust**: a Darija-aware model reconstructs them, and they're cross-checked against sheets and dictionaries and flagged for review.
- **Future lessons:** Panko records the lesson itself as **two tracks, your microphone and the call audio**, which separates the speakers for free, the same way Granola does. On macOS 13+ it uses ScreenCaptureKit plus the microphone. The audio is processed **after** the lesson; live processing isn't needed to make cards. A simpler stopgap is the call app's own recording, e.g. Zoom's separate audio file per participant.
- **Trial run on the 21 Nov transcript (furniture and shopping lesson, ~50 min):**
  - It yielded about 37 vocabulary items, 5 grammar points, about 5 corrections of your mistakes, and 1 regional-variation note.
  - Searching the collection while ignoring harakat: 9 items don't appear anywhere (كنابي، طابلة، خزانة، الحيط، تخفيض، ليفريزون، الفاتورة، الكوزينة، خصني).
  - Most of the rest appear only in **unstudied** shared decks. Only about 3 are in cards you've actually studied.

### Dialect speech recognition: strategy and scope (2026-11-22)
- **Lessons happen on Preply** (an in-browser classroom). Preply's own Lesson Insights recordings cover English lessons only. Panko therefore records on your Mac: browser audio ("Them") and microphone ("Me"), **with your teacher's consent**. There's a backlog of 4–5 Granola transcripts that can be mined now (low trust).
- **Expected error rates:** Darija speech recognition is roughly 38% word error, per your earlier dialect-tutor research. The best Levantine result found in this research was about 28% (Gemini). Whisper tends to replace dialect with MSA, and Darija/English/French code-switching makes all of this worse. ElevenLabs Scribe has no published Darija numbers that I found; treat it as a contender to test, not as better by default.
- **Panko doesn't need good open transcription.** It needs *recognition with strong hints*:
  1. **Give the model context:** the lesson sheet, your lexicon, and the Granola transcript as hints.
  2. **Only teaching moments and word clips matter.** Misheard small talk is harmless.
  3. **When the text is already known, line it up instead of recognising it.** Peace Corps lessons and teacher-sheet phrases only need the audio matched to text, which is far easier than recognition.
  4. **Run several engines.** Where they disagree, flag the item.
  5. **"Questions for your teacher":** Panko lists the items it's unsure of, to confirm at the start of the next lesson. Your teacher is the final check.
- **Benchmark before choosing:** hand-correct about 10 minutes of a recorded lesson, then compare Gemini, an OpenAI transcription model, ElevenLabs Scribe, Whisper large-v3 and a Darija fine-tune. Transcription sits behind a swappable interface.
- **No pre-training, ever. Fine-tuning is optional and much later.** At about 1 hour of lessons a week, Panko builds up corrected, time-aligned transcripts of your teacher. After a few months that's enough for a small LoRA fine-tune of Whisper.
- **Scope boundary with the dialect-tutor idea (Idea 02):**
  - *Panko* uses speech technology: transcription, alignment, TTS.
  - *Idea 02* owns building speech technology: training or fine-tuning ASR, voice cloning, a conversation partner, pronunciation scoring.
  - Panko's verified lexicon and aligned audio, tagged with source and licence, are exactly the dataset Idea 02 needs. **Build Panko first; it becomes the foundation for Idea 02.**
- **More Darija resources to add** (from the Idea 02 research): the **DODa** lexicon (Darija Open Dataset, Arabizi + Arabic script, non-commercial licence, fine for personal use), **Atlas-Chat** (a Darija LLM), and **Habibi TTS**.

### Candidate ranking and add policy
- **Ranked by:** taught in a lesson > on a teacher sheet > sighted in several sources > frequency in your media > appears once.
- **Auto-added** (matching your "auto-add, flag the doubtful ones" choice): items taught or corrected in a lesson, and teacher-sheet items.
- **Parked in the inbox** for you to promote: things only mentioned in passing, or seen once in media.

---

### Key sources
- Anki releases: https://github.com/ankitects/anki/releases · stewardship change: https://forums.ankiweb.net/t/ankis-growing-up/68610
- AnkiConnect (current home): https://git.sr.ht/~foosoft/anki-connect
- Headless Anki: https://github.com/ankitects/anki/blob/main/docs-site/addons/command-line-use.mdx
- CAMeL Tools: https://camel-tools.readthedocs.io · Camel Morph: https://github.com/CAMeL-Lab/camel_morph
- kaikki Arabic: https://kaikki.org/dictionary/Arabic/ · Lane's Lexicon XML: https://laneslexicon.github.io/
- Quranic Arabic Corpus: https://corpus.quran.com · MASAQ: https://data.mendeley.com/datasets/9yvrzxktmr/2 · Tanzil: https://tanzil.net/docs/
- LLM diacritization (LREC 2026): https://aclanthology.org/2026.lrec-1.40/ · SHAMS (Levantine): https://arxiv.org/abs/2610.01427
- QARI-OCR: https://arxiv.org/abs/2506.02295 · Azure Arabic voices: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
- AnkiMobile harakat clipping: https://forums.ankiweb.net/t/arabic-diacritic-when-shaddah-another-the-display-on-ankimobile-ios-gets-cut-off/67313
- anki-llm: https://github.com/raine/anki-llm · AnkiMorphs (archived): https://github.com/mortii/anki-morphs
