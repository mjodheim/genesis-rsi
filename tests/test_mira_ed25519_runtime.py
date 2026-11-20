import pytest

def test_milestone_2_ed25519_runtime_compatibility():
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        pytest.fail(f"Ed25519 indisponible dans l’image pytest : {exc}")

    message = b"Genesis-rsi milestone 2"
    altered_message = b"Genesis-rsi milestone 3"

    try:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        signature = private_key.sign(message)

        assert public_key.verify(signature, message) is None
        with pytest.raises(InvalidSignature):
            public_key.verify(signature, altered_message)
    except (UnsupportedAlgorithm, NotImplementedError) as exc:
        pytest.fail(f"Ed25519 indisponible dans l’image pytest : {exc}")
