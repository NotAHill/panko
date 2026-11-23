"""JSON schemas for each prompt's answer. Every property is required and objects are closed, so the same schema
works with Claude's structured outputs and OpenAI's strict mode; "" or [] means "nothing to say"."""
from __future__ import annotations


def obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


S = {"type": "string"}
S_ = arr(S)


def enum(*vals) -> dict:
    return {"type": "string", "enum": list(vals)}


EXAMPLE = obj(ar=S, tl=S, en=S, source=S)
RELATED = obj(ar=S, tl=S, meaning=S)
POS = enum("noun", "verb", "adjective", "adverb", "preposition", "pronoun", "conjunction", "interjection",
           "particle", "number", "")

ITEM_FIELDS = dict(
    kind=enum("word", "phrase"), variety=S, ar=S, tl=S, tl_alt=S, gloss=S, gloss_note=S, pos=POS,
    gender=enum("m", "f", ""), plural=S, present=S, imperative=S, literal=S, usage=S, notes=S,
    examples=arr(EXAMPLE), related=arr(RELATED), tags=S_,
)
CONFIDENCE = obj(confidence=enum("high", "medium", "low"), why=S)
VERDICT = obj(verdict=enum("ok", "fix", "regional", "uncommon", "doubtful", "drop"), region=S, urban_rural=S,
              register=S, usual_word=S, learner_note=S, confidence=enum("high", "medium", "low"), summary=S,
              evidence=S_)

SCHEMAS = {
    "extract": obj(items=arr(obj(**ITEM_FIELDS, check=CONFIDENCE))),
    "deck": obj(
        items=arr(obj(src_id=S, **ITEM_FIELDS, region=S, cards=arr(enum("recognition", "production")), check=VERDICT)),
        dropped=arr(obj(src_id=S, ar=S, why=S)),
    ),
    "check": obj(results=arr(obj(
        id=S, verdict=enum("ok", "fix", "regional", "uncommon", "doubtful", "drop"),
        fix=arr(obj(field=S, value=S)), region=S, urban_rural=S, register=S, usual_word=S, learner_note=S,
        confidence=enum("high", "medium", "low"), evidence=S_, summary=S,
    ))),
    "examples": obj(results=arr(obj(id=S, examples=arr(obj(ar=S, tl=S, en=S, source=S, candidate=S)), note=S))),
    "pictures-plan": obj(results=arr(obj(id=S, choice=enum("photo", "draw", "skip"), query=S, prompt=S, reason=S))),
    "clashes": obj(results=arr(obj(id=S, decisions=arr(obj(
        entry_id=S, action=enum("keep", "gloss", "recognition", "drop"), gloss=S, note=S, why=S))))),
    "pictures-pick": obj(results=arr(obj(id=S, index={"type": "integer"}, prompt=S, reason=S))),
}
