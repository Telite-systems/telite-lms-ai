"""Certificate generation must not send verification tokens to external services."""
from types import SimpleNamespace

import pytest

from app.services import certificate_service as module


@pytest.mark.parametrize("url", ["https://api.qrserver.com/?data=synthetic-token", "http://127.0.0.1/", "file:///etc/passwd"])
def test_pdf_fetcher_denies_remote_and_local_resources(url):
    with pytest.raises(ValueError):
        module.certificate_url_fetcher(url)


def test_qr_is_embedded_locally_and_renderer_is_restricted(monkeypatch):
    seen = {}

    class FakeHTML:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def write_pdf(self):
            return b"synthetic-pdf"

    monkeypatch.setattr(module, "HTML", FakeHTML)
    monkeypatch.setattr(module, "WEASYPRINT_AVAILABLE", True)
    service = module.CertificateService(None)
    user = SimpleNamespace(full_name="Synthetic Employee", email="synthetic@example.invalid")
    course = SimpleNamespace(name="Synthetic Course")
    result = service._generate_pdf(user, course, None, "https://example.invalid/verify/synthetic-token", "synthetic-hash")
    assert result == b"synthetic-pdf"
    assert "data:image/png;base64," in seen["string"]
    assert "qrserver.com" not in seen["string"]
    assert seen["url_fetcher"] is module.certificate_url_fetcher
