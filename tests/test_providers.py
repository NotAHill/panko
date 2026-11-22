from panko import providers


def test_every_configured_provider_is_registered():
    from panko.config import settings
    for cap in ("audio", "images"):
        for name in settings()[cap]["chain"]:
            assert name in providers.available(cap)


def test_providers_without_keys_are_skipped(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert "elevenlabs" not in [p.name for p in providers.chain("audio")]
