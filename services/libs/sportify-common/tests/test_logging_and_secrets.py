import pytest

from sportify_common.logging import redact
from sportify_common.secrets import SecretNotAvailableError, read_secret_file


def test_redacts_bearer_tokens_and_secrets() -> None:
    text = 'Authorization: Bearer abc.def.ghi password="hunter2" api_key=XYZ'
    out = redact(text)
    assert "abc.def.ghi" not in out
    assert "hunter2" not in out
    assert "XYZ" not in out


def test_redacts_private_key_blocks() -> None:
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    assert "MIIabc" not in redact(f"key={pem}")


def test_read_secret_file(tmp_path, monkeypatch) -> None:
    f = tmp_path / "s"
    f.write_text("  value \n")
    monkeypatch.setenv("MY_SECRET_FILE", str(f))
    assert read_secret_file("MY_SECRET_FILE") == "value"


def test_missing_secret_raises(monkeypatch) -> None:
    monkeypatch.delenv("NOPE_FILE", raising=False)
    with pytest.raises(SecretNotAvailableError):
        read_secret_file("NOPE_FILE")
    assert read_secret_file("NOPE_FILE", required=False) is None
