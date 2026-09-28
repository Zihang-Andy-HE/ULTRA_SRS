import hashlib
import pytest
from ultra.setup import install_asset


def test_asset_integrity_and_atomic_failure(tmp_path):
    original = tmp_path/'input'
    original.write_bytes(b'fixed asset')
    spec = {'sha256': hashlib.sha256(original.read_bytes()).hexdigest(), 'url': None}
    target = tmp_path/'models'/'weights'
    install_asset(spec, target, original)
    install_asset(spec, target, original)
    assert target.read_bytes() == original.read_bytes()
    broken = tmp_path/'models'/'broken'
    with pytest.raises(ValueError, match='checksum'):
        install_asset({'sha256': '0'*64}, broken, original)
    assert not broken.exists()
    assert not list(broken.parent.glob('.download-*'))


def test_missing_url_is_explicit(tmp_path):
    with pytest.raises(ValueError, match='URL'):
        install_asset({'sha256': '0'*64, 'url': None}, tmp_path/'missing')
