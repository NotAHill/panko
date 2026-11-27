"""Your own pictures: those already on your cards (another variety, or another language in this folder) whose
meaning matches the search. Free and local; first in every photo search (`[images] reuse = false` turns it off)."""
from panko.providers import register
from panko.providers.base import ImageSearch


@register("images", "yours")
class Yours(ImageSearch):
    label = "Your pictures"

    def search(self, query, limit=6):
        from panko.media import reuse
        try:
            return reuse.search(query, limit)
        except Exception:  # noqa: BLE001  your own pictures never stop a search of the sites
            return []
