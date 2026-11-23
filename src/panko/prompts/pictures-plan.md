You decide the picture for flashcards for {{learner}} of {{language}}. The production card's front shows a
picture and the {{gloss_language}} gloss, and the learner says the word, so the picture should help them recall
it. It doesn't need to be realistic.

Each card is `{"id", "ar", "tl", "pos", "kind", "gloss", "note", "example_en"}`. Use the gloss, note and example to
pin the exact sense. For each, choose one:

1. **photo**: a concrete thing a photo shows clearly and unambiguously (objects, food, animals, plants, places,
   buildings, vehicles, clothes, body parts, tools, visible weather). Real photos come first. Give `query`: a plain
   {{gloss_language}} image-search query specific to the sense ("ewe sheep", "prickly pear cactus fruit",
   "mint tea in a small glass"); a culturally specific thing deserves a specific query. Also give a drawing
   `prompt`, used if no good photo turns up.
2. **draw**: everything else a picture can help with: actions, feelings, qualities, people's roles, situations,
   short everyday phrases ("Thank you", "How much is it?"). Abstract nouns get a concrete scene that evokes the
   sense ("proof": a detective holding a footprint cast next to a matching boot). Pronouns and position words get a
   simple scene when it's unambiguous (a cat under a table for "under").
3. **skip**: only {{picture_skip}}. Expect about 10–20% skips, each with its own `reason`.

Drawing prompts: one or two sentences, 15–45 words, describing only the scene (the house style is added
automatically, so no style words and no "illustration of"):
- one clear idea showing the exact sense of the gloss, not a neighbouring word ("to borrow" ≠ "to lend": show who
  receives); a visual cue that pins it (a gesture, before/after, a contrast pair, an exaggerated expression);
  concrete, a little vivid or playful, never mocking, sexual or gory;
- no writing anywhere: no signs, labels, letters, digits, or speech bubbles with words; to show a small number,
  show that many objects;
- name exactly the people the scene needs ("a man", "a girl and her grandfather").

The learner's picture rules:
{{picture_rules}}

Return `{"results": [{"id", "choice", "query", "prompt", "reason"}]}`, one per card; `query` is "" unless the
choice is photo, `prompt` is "" only for skips, `reason` is short.
