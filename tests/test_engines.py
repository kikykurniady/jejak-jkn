import numpy as np
import pandas as pd
import pytest

from jejak.evaluate import average_precision
from jejak.experiment import LeakageError, check_no_overlap, run_experiment
from jejak.features import FEATURE_NAMES, compute_features, format_feature
from jejak.generator import GeneratorConfig, generate
from jejak.graph import claim_edges, graph_features
from jejak.models import MODEL_FEATURES, STRUCTURAL_FEATURES, anomaly_scores, train_xgb
from jejak.process import build_event_log, process_scores
from jejak.schema import validate_claims


@pytest.fixture(scope="module")
def test_ds():
    ds = generate(GeneratorConfig(n_claims=10_000, seed=7))
    return validate_claims(ds.claims), ds.labels


@pytest.fixture(scope="module")
def train_ds():
    ds = generate(GeneratorConfig(n_claims=10_000, seed=8))
    return validate_claims(ds.claims), ds.labels


@pytest.fixture(scope="module")
def fs(test_ds):
    return compute_features(test_ds[0])


@pytest.fixture(scope="module")
def experiment(test_ds, train_ds):
    return run_experiment(*test_ds, *train_ds, loso=False, explain_top=200)


def _with_labels(df, labels):
    return df.merge(labels, on="claim_id")


# ---------- fitur ----------
def test_features_are_label_free_and_complete(fs, test_ds):
    f = fs.features
    assert list(f.columns) == ["claim_id", *FEATURE_NAMES]
    assert len(f) == len(test_ds[0]) and f.claim_id.is_unique
    assert not f[FEATURE_NAMES].isna().any().any()
    assert not {"label", "scenario", "fraud_type", "source_claim_id", "episode_id"} & set(f.columns)


def test_features_do_not_depend_on_row_order(test_ds):
    claims = test_ds[0].head(3000)
    a = compute_features(claims, with_fitness=False).features.set_index("claim_id").sort_index()
    b = compute_features(claims.sample(frac=1, random_state=0), with_fitness=False).features.set_index("claim_id").sort_index()
    pd.testing.assert_frame_equal(a, b)


def test_binary_feature_reason_only_when_true():
    assert format_feature("no_evidence", 0) is None
    assert format_feature("no_evidence", 1) == "Bukti layanan tidak dilampirkan"
    assert "sebelum layanan" in format_feature("claim_lag_days", -3.5)


# ---------- process mining ----------
def test_event_log_has_service_and_claim_event_per_claim(test_ds):
    claims = test_ds[0]
    log = build_event_log(claims)
    assert (log["concept:name"] == "Klaim diajukan").sum() == len(claims)
    assert log.claim_id.value_counts().min() >= 2


def test_claim_before_service_is_a_rare_process(fs, test_ds):
    claims, labels = test_ds
    p = fs.process.merge(claims[["claim_id", "claim_timestamp", "service_timestamp"]], on="claim_id")
    before = p[p.claim_timestamp < p.service_timestamp]
    assert len(before) > 0
    assert before.proc_score.mean() > 3 * p.proc_score.median()
    assert before.proc_reason.str.contains("Klaim diajukan").mean() > 0.9


# ---------- graph ----------
def test_graph_links_duplicate_copy_to_source(fs, test_ds):
    _, labels = test_ds
    dup = labels[labels.scenario == "exact_duplicate"]
    e = fs.edges[fs.edges.edge_type == "duplikat"]
    pairs = set(map(frozenset, zip(e.claim_a, e.claim_b)))
    assert all(frozenset(p) in pairs for p in zip(dup.claim_id, dup.source_claim_id))
    g = fs.graph.set_index("claim_id")
    assert (g.loc[dup.claim_id, "graph_score"] >= 0.9).all()
    assert (g.loc[dup.source_claim_id, "graph_score"] < 0.5).all()  # klaim asal hanya konteks


def test_graph_finds_clone_clusters(fs, test_ds):
    _, labels = test_ds
    g = _with_labels(fs.graph, labels)
    clones = g[g.scenario == "cloning"]
    assert (clones.clone_participants >= 5).mean() > 0.95
    assert clones.graph_reason.str.startswith("Klaster").all()
    assert (g[g.label == 0].clone_participants >= 5).mean() < 0.01


def test_clone_edges_need_different_participants(test_ds):
    claims = test_ds[0].head(1)
    twin = claims.assign(claim_id="CLM-99999999")  # peserta sama: bukan kloning
    e = claim_edges(pd.concat([claims, twin], ignore_index=True))
    assert set(e.edge_type) == {"duplikat"}


# ---------- model ----------
def test_anomaly_scores_range_and_reasons(fs):
    a = anomaly_scores(fs.features, explain_top=50)
    assert a.anomaly_score.between(0, 1).all()
    top = a.nlargest(50, "anomaly_raw")
    assert (top.anomaly_reason.str.len() > 0).all()


def test_xgb_shap_is_additive(fs, train_ds):
    tf = compute_features(train_ds[0]).features
    model = train_xgb(tf, train_ds[1])
    assert model.features == MODEL_FEATURES and not set(STRUCTURAL_FEATURES) & set(model.features)
    x = fs.features.head(200)
    sv = model.shap_values(x)
    prob = 1 / (1 + np.exp(-sv.sum(axis=1)))
    np.testing.assert_allclose(prob, model.predict(x), rtol=1e-4, atol=1e-5)


def test_leakage_guard_rejects_shared_participants(test_ds):
    claims = test_ds[0]
    with pytest.raises(LeakageError):
        check_no_overlap(claims, claims.head(100))


def test_experiment_beats_chance_and_explains(experiment, test_ds):
    m = experiment.metrics.set_index("engine")
    prevalence = test_ds[1].label.mean()
    assert (m.pr_auc > prevalence).all()
    assert m.loc["Aturan R01–R10 (baseline)", "pr_auc"] > 0.8
    top = experiment.scores.head(100)
    assert (top.ml_reason.str.len() > 0).mean() > 0.95
    assert {"rule_score", "proc_score", "graph_score", "anomaly_score", "ml_score"} <= set(experiment.scores.columns)


def test_leave_one_scenario_out_runs(test_ds, train_ds):
    r = run_experiment(*test_ds, *train_ds, loso=True, explain_top=0)
    assert set(r.loso.skenario) == set(test_ds[1].scenario) - {"normal"}
    assert r.loso.recall_xgb_tanpa_skenario.between(0, 1).all()


def test_average_precision_ignores_tie_order():
    y = np.array([1, 0, 1, 0])
    s = np.array([0.5, 0.5, 0.5, 0.5])
    assert average_precision(y, s) == average_precision(y[::-1], s) == 0.5
