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
