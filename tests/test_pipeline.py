import pandas as pd
import pytest

from jejak.evaluate import average_precision, evaluate
from jejak.generator import GeneratorConfig, generate
from jejak.rules import run_rules, score_claims
from jejak.schema import SchemaErrors, validate_claims


@pytest.fixture(scope="module")
def ds():
    return generate(GeneratorConfig(n_claims=10_000, seed=1))


@pytest.fixture(scope="module")
def scored(ds):
    claims = validate_claims(ds.claims)
    hits = run_rules(claims)
    return claims, hits, score_claims(claims, hits)


def test_generator_size_and_labels(ds):
    assert 9_900 <= len(ds.claims) <= 10_300
    assert ds.claims.claim_id.is_unique
    assert set(ds.labels.claim_id) == set(ds.claims.claim_id)
    assert set(ds.labels.scenario) >= {"normal", "exact_duplicate", "near_duplicate", "repeated_procedure",
                                       "missing_evidence", "process_deviation", "cloning"}
    assert 0.05 < ds.labels.label.mean() < 0.12


def test_generator_is_deterministic():
    a = generate(GeneratorConfig(n_claims=10_000, seed=5)).claims
    b = generate(GeneratorConfig(n_claims=10_000, seed=5)).claims
    pd.testing.assert_frame_equal(a, b)


def test_duplicates_point_to_existing_source(ds):
    dup = ds.labels[ds.labels.scenario == "exact_duplicate"]
    assert dup.source_claim_id.isin(ds.claims.claim_id).all()


def test_schema_accepts_generated_data(ds):
    validate_claims(ds.claims)


def test_schema_rejects_bad_rows(ds):
    bad = ds.claims.head(5).copy()
    bad.loc[bad.index[0], "claim_amount"] = -10
    bad.loc[bad.index[1], "procedure_code"] = "XX.99"
    bad.loc[bad.index[2], "facility_type"] = "FKRTL" if bad.iloc[2].facility_type == "FKTP" else "FKTP"
    with pytest.raises(SchemaErrors):
        validate_claims(bad)


def test_every_hit_has_reason_and_detail(scored):
    _, hits, _ = scored
    assert hits.reason_code.notna().all() and (hits.detail.str.len() > 0).all()


def test_scenarios_are_caught(ds, scored):
    _, _, s = scored
    m = s.merge(ds.labels, on="claim_id")
    caught = m[m.label == 1].groupby("scenario").rule_score.apply(lambda x: (x >= 0.5).mean())
    for scenario in ["exact_duplicate", "cloning", "process_deviation"]:
        assert caught[scenario] > 0.95, scenario
    assert caught.min() > 0.6


def test_ranking_quality(ds, scored):
    _, hits, s = scored
    r = evaluate(s, ds.labels, hits, ks=(100,))
    assert r["at_k"][100]["precision"] > 0.95
    assert r["pr_auc"] > 0.8


def test_exact_duplicate_flags_later_copy_only():
    base = generate(GeneratorConfig(n_claims=10_000, seed=3, scenario_rates={})).claims.head(1)
    copy = base.assign(claim_id="CLM-99999999", claim_timestamp=base.claim_timestamp + pd.Timedelta(days=5))
    hits = run_rules(pd.concat([base, copy], ignore_index=True))
    dup = hits[hits.reason_code == "R01_EXACT_DUP"]
    assert dup.claim_id.tolist() == ["CLM-99999999"]


def test_average_precision_perfect_and_worst():
    import numpy as np
    y = np.array([1, 1, 0, 0])
    assert average_precision(y, np.array([0.9, 0.8, 0.1, 0.0])) == 1.0
    assert average_precision(y, np.array([0.0, 0.1, 0.8, 0.9])) < 0.6
