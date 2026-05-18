"""Tests for pickled_state: fingerprint + pack/unpack helpers."""

from optimizerapi.pickled_state import compute_fingerprint


SAMPLE_DATA = [
    {"xi": [651, 56, 722, "Ræv"], "yi": [1]},
    {"xi": [651, 42, 722, "Ræv"], "yi": [0.2]},
]

SAMPLE_CONFIG = {
    "baseEstimator": "GP",
    "acqFunc": "gp_hedge",
    "initialPoints": 2,
    "kappa": 1.96,
    "xi": 0.012,
    "space": [
        {"type": "discrete", "name": "Sukker", "from": 0, "to": 1000},
        {"type": "continuous", "name": "Peber", "from": 0, "to": 1000},
        {"type": "continuous", "name": "Hvedemel", "from": 0, "to": 1000},
        {"type": "category", "name": "Kunde", "categories": ["Mus", "Ræv"]},
    ],
}


def test_fingerprint_is_deterministic():
    fp1 = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    fp2 = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # sha256 hex


def test_fingerprint_is_independent_of_dict_key_order():
    reordered_config = {
        "space": SAMPLE_CONFIG["space"],
        "xi": SAMPLE_CONFIG["xi"],
        "kappa": SAMPLE_CONFIG["kappa"],
        "initialPoints": SAMPLE_CONFIG["initialPoints"],
        "acqFunc": SAMPLE_CONFIG["acqFunc"],
        "baseEstimator": SAMPLE_CONFIG["baseEstimator"],
    }
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) == compute_fingerprint(
        SAMPLE_DATA, reordered_config
    )


def test_fingerprint_changes_when_data_changes():
    other_data = SAMPLE_DATA + [{"xi": [100, 100, 100, "Mus"], "yi": [0.5]}]
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) != compute_fingerprint(
        other_data, SAMPLE_CONFIG
    )


def test_fingerprint_changes_when_config_changes():
    other_config = dict(SAMPLE_CONFIG, kappa=2.0)
    assert compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG) != compute_fingerprint(
        SAMPLE_DATA, other_config
    )


import logging  # noqa: E402

from optimizerapi.pickled_state import pack, unpack_if_valid  # noqa: E402
from optimizerapi.securepickle import get_crypto, pickleToString  # noqa: E402


def _crypto():
    return get_crypto()


def test_pack_unpack_round_trip():
    crypto = _crypto()
    fingerprint = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    blob = pack(result="result-sentinel", next_points=["next-sentinel"],
                optimizer="opt-sentinel", fingerprint=fingerprint, crypto=crypto)
    assert isinstance(blob, str) and len(blob) > 0

    payload = unpack_if_valid(blob, expected_fingerprint=fingerprint, crypto=crypto)
    assert payload is not None
    assert payload["result"] == "result-sentinel"
    assert payload["next"] == ["next-sentinel"]
    assert payload["optimizer"] == "opt-sentinel"
    assert payload["fingerprint"] == fingerprint


def test_unpack_returns_none_on_fingerprint_mismatch(caplog):
    crypto = _crypto()
    fingerprint = compute_fingerprint(SAMPLE_DATA, SAMPLE_CONFIG)
    blob = pack(result="r", next_points=[], optimizer="o",
                fingerprint=fingerprint, crypto=crypto)

    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid(blob, expected_fingerprint="0" * 64, crypto=crypto)
    assert result is None
    assert any("fingerprint_mismatch" in record.message for record in caplog.records)


def test_unpack_returns_none_on_decrypt_failure(caplog):
    crypto = _crypto()
    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid("not-a-valid-blob", expected_fingerprint="x" * 64,
                                 crypto=crypto)
    assert result is None
    assert any("decrypt_failed" in record.message for record in caplog.records)


def test_unpack_returns_none_on_bad_structure(caplog):
    crypto = _crypto()
    # Encrypt a non-dict payload using the same machinery.
    bogus_blob = pickleToString(["not", "a", "dict"], crypto)

    with caplog.at_level(logging.WARNING, logger="optimizerapi.pickled_state"):
        result = unpack_if_valid(bogus_blob, expected_fingerprint="x" * 64,
                                 crypto=crypto)
    assert result is None
    assert any("bad_structure" in record.message for record in caplog.records)
