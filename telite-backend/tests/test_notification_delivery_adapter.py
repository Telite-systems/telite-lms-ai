import pytest

from app.services import email


def test_missing_smtp_does_not_open_connection(monkeypatch):
    monkeypatch.setattr(email, "SMTP_USER", "")
    def forbidden(*args, **kwargs):
        raise AssertionError("SMTP connection without credentials")
    monkeypatch.setattr(email.smtplib, "SMTP", forbidden)
    assert not email._dispatch_notification_email(to_email="a@example.invalid", name="A", title="Synthetic", body="Synthetic")


@pytest.mark.parametrize("refused", [False, True])
def test_delivery_requires_tls_and_records_refused_recipient(monkeypatch, refused):
    events = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            assert kwargs["timeout"] == 15
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def ehlo(self):
            events.append("ehlo")
        def starttls(self):
            events.append("tls")
        def login(self, *args):
            events.append("login")
        def sendmail(self, sender, recipients, message):
            events.append("send")
            assert recipients == ["a@example.invalid"]
            assert "Content-Type: text/plain" in message
            return {"a@example.invalid": (550, b"refused")} if refused else {}
    monkeypatch.setattr(email, "SMTP_USER", "synthetic@example.invalid")
    monkeypatch.setattr(email, "SMTP_PASSWORD", "synthetic")
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    assert email._dispatch_notification_email(to_email="a@example.invalid", name="A", title="Synthetic", body="Synthetic") is (not refused)
    assert events == ["ehlo", "tls", "ehlo", "login", "send"]
