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


def test_resolve_dayforce_adapter_from_url():
    adapter = get_adapter("https://jobs.dayforcehcm.com/en-US/ohmc/CANDIDATEPORTAL/jobs/6570")
    assert adapter.manifest.family == "dayforce"


def test_dayforce_dom_markers_exclude_broad_domain_string():
    adapter = get_adapter("https://jobs.dayforcehcm.com/en-US/ohmc/CANDIDATEPORTAL/jobs/6570")
    assert "dayforcehcm" not in adapter.manifest.dom_markers
