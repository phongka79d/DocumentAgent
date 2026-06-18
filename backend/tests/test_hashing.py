from app.services.hashing import compute_sha256


def test_compute_sha256_returns_expected_digest_for_bytes():
    payload = b"RagDocument upload bytes"

    assert compute_sha256(payload) == (
        "854619721141a8bb9a30c069d3d564840c8b8662aae5d56e4eb0877835daefbc"
    )
