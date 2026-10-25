import pandas as pd
import pytest

from jejak.experiment import score_batch
from jejak.features import compute_features
from jejak.generator import GeneratorConfig, generate
from jejak.rules import run_rules
from jejak.schema import validate_claims
from jejak.workspace import (DEFAULT_WEIGHTS, DECISIONS, WorkspaceData, build_queue, contributions, episode_events,
                             latest_decisions, load_decisions, normalize_weights, related_graph, rule_reasons,
                             save_decision, signals)


@pytest.fixture(scope="module")
def ws():
    claims = validate_claims(generate(GeneratorConfig(n_claims=10_000, seed=11)).claims)
    fs = compute_features(claims)
    scores, fs = score_batch(claims, features=fs, explain_top=100)
    scores["ml_score"], scores["ml_reason"] = 0.0, ""  # tanpa XGBoost: dashboard tetap jalan
    return WorkspaceData(claims, scores, run_rules(claims), fs.edges, None)


def test_queue_sorted_and_complete(ws):
    q = build_queue(ws)
    assert len(q) == len(ws.claims) and q.claim_id.is_unique
    assert q.skor_gabungan.is_monotonic_decreasing
    assert q.peringkat.tolist() == list(range(1, len(q) + 1))
    assert q.skor_gabungan.between(0, 1).all()
    assert set(q.prioritas) <= {"Tinggi", "Sedang", "Rendah"}
    assert (q.loc[q.prioritas == "Tinggi", "skor_gabungan"] >= 0.5).all()


def test_combined_score_is_weighted_mean(ws):
    q = build_queue(ws)
    row = q.iloc[0]
    c = contributions(row)
    assert c.bobot.sum() == pytest.approx(1)
    assert c.kontribusi.sum() == pytest.approx(row.skor_gabungan, abs=1e-3)
    # Bobot hanya aturan -> skor gabungan = skor aturan
    only_rules = build_queue(ws, {k: (1.0 if k == "rule_score" else 0.0) for k in DEFAULT_WEIGHTS})
    m = only_rules.set_index("claim_id")
    assert (m.skor_gabungan - m.rule_score).abs().max() < 1e-3


def test_anomaly_signal_only_top_decile(ws):
    s = signals(ws.scores).merge(ws.scores[["claim_id", "anomaly_score"]], on="claim_id")
    assert (s.loc[s.anomaly_score < 0.9, "anomaly_signal"] == 0).all()
    assert s.anomaly_signal.max() == pytest.approx(1, abs=1e-3)


def test_weights_validation():
    with pytest.raises(ValueError):
        normalize_weights({k: 0 for k in DEFAULT_WEIGHTS})


def test_decisions_append_latest_wins(tmp_path):
    save_decision(tmp_path, "CLM-1", "Need Clarification", "minta resume medis", "A1", 0.8)
    save_decision(tmp_path, "CLM-2", "Valid")
    save_decision(tmp_path, "CLM-1", "Irregular", "dokumen tidak ada", "A1", 0.8)
    log = load_decisions(tmp_path)
    assert len(log) == 3
    latest = latest_decisions(log)
    assert latest.loc["CLM-1", "keputusan"] == "Irregular"
    assert latest.loc["CLM-2", "keputusan"] == "Valid"
    with pytest.raises(ValueError):
        save_decision(tmp_path, "CLM-3", "Fraud")
    assert set(latest.keputusan) <= set(DECISIONS)


def test_case_views(ws):
    q = build_queue(ws)
    clone = q[q.dugaan_pola == "Cloning"].iloc[0]
    g = related_graph(ws, clone.claim_id)
    kinds = pd.Series(dict(g.nodes(data="kind")))
    assert (kinds == "klaim").sum() >= 5  # klaster kloning
    assert any(d["edge_type"] == "kloning" for *_, d in g.edges(data=True))
    assert g.nodes[clone.claim_id]["focus"]

    dup = q[q.reason_codes.str.contains("R01_EXACT_DUP")].iloc[0]
    rr = rule_reasons(ws.hits, dup.claim_id)
    assert rr.kode.iloc[0] == "R01_EXACT_DUP" and rr.bobot.is_monotonic_decreasing

    c = ws.claims.set_index("claim_id").loc[dup.claim_id]
    ev = episode_events(ws.claims, c.episode_id)
    assert dup.claim_id in set(ev.claim_id) and ev.waktu.is_monotonic_increasing
