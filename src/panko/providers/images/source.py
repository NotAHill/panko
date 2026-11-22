"""Pictures cropped from the material a word came from (PDF pages, video frames).
Filled by the ingestion pipeline (Phase 2); finds nothing for now."""
from panko.providers import register
from panko.providers.base import ImageSearch


@register("images", "source")
class SourceCrop(ImageSearch):
    def search(self, query, limit=6):
        return []
