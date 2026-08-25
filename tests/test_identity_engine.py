import pytest

from orbit_core import IdentityEngine


def test_default_identity_has_expected_values() -> None:
    identity = IdentityEngine.default_identity()

    assert identity.name == "Orbit"
    assert "modular" in identity.traits


def test_identity_validation_rejects_blank_name() -> None:
    identity = IdentityEngine(name="", version="0.1.0", mission="x")

    with pytest.raises(ValueError):
        identity.validate()
