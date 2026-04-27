from app.site_adapters import adapter_count, get_adapter


def test_adapter_registry_autoloads_family_modules():
    assert adapter_count() >= 7


def test_resolve_workday_adapter_from_url():
    adapter = get_adapter("https://example.myworkdayjobs.com/en-US/careers")
    assert adapter.manifest.family == "workday"
    assert adapter.manifest.variant == "base"


def test_generic_adapter_is_fallback():
    adapter = get_adapter("https://example.com/careers")
    assert adapter.manifest.family == "generic"
