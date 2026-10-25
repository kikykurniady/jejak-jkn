"""Eksperimen jujur: semua engine dibandingkan dengan baseline aturan.

Protokol anti-kebocoran:
1. XGBoost dilatih pada dataset sintetis **terpisah** (seed lain, peserta lain) dan diuji pada
   batch yang dinilai. Bila ada token peserta yang sama di kedua set, eksperimen ditolak.
2. Fitur dihitung per dataset tanpa label; label hanya dipakai untuk melatih XGBoost
   dan untuk menghitung metrik.
3. **Leave-one-scenario-out**: XGBoost dilatih tanpa contoh positif satu skenario, lalu diukur
   pada skenario itu. Ini mendekati kondisi nyata: pola fraud baru yang belum pernah dilabeli.
4. **Ablasi**: XGBoost default tidak memakai fitur struktur episode/peserta (`STRUCTURAL_FEATURES`),
   karena generator membuat skenario suntikan sebagai episode baru berisi satu klaim. Model dengan
   fitur itu tetap dilaporkan sebagai pembanding.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .evaluate import average_precision, score_metrics
from .features import FEATURE_NAMES, FeatureSet, compute_features
from .models import RiskModel, anomaly_scores, train_xgb
from .rules import run_rules, score_claims

# Ambang per engine. Skor anomali adalah persentil, jadi ambangnya = 5% teratas.
THRESHOLDS = {"rule_score": 0.5, "proc_score": 0.5, "graph_score": 0.5, "anomaly_score": 0.95,
              "ml_score": 0.5, "ml_score_allfeat": 0.5}
ENGINE_NAMES = {
    "rule_score": "Aturan R01–R10 (baseline)",
    "proc_score": "Process mining (PM4Py)",
    "graph_score": "Graph antar-klaim",
    "anomaly_score": "Isolation Forest",
    "ml_score": "XGBoost (default, tanpa fitur struktur)",
    "ml_score_allfeat": "XGBoost + fitur struktur (ablasi)",
}


class LeakageError(ValueError):
    pass


def check_no_overlap(train_claims: pd.DataFrame, test_claims: pd.DataFrame) -> None:
    shared = set(train_claims.participant_token) & set(test_claims.participant_token)
    if shared:
        raise LeakageError(f"{len(shared)} token peserta muncul di data latih dan data uji; "
                           "pakai seed generator yang berbeda untuk data latih.")


@dataclass
class ExperimentResult:
    scores: pd.DataFrame  # satu baris per klaim uji: skor tiap engine + alasan
    metrics: pd.DataFrame  # satu baris per engine
    per_scenario: pd.DataFrame  # recall per skenario per engine
    loso: pd.DataFrame  # leave-one-scenario-out
    importance: pd.Series
    features: FeatureSet
    model: RiskModel


def score_batch(claims: pd.DataFrame, model: RiskModel | None = None, model_allfeat: RiskModel | None = None,
                features: FeatureSet | None = None, explain_top: int = 1000) -> tuple[pd.DataFrame, FeatureSet]:
    """Nilai satu batch klaim dengan semua engine (tanpa label)."""
    fs = features or compute_features(claims)
    rules = score_claims(claims, run_rules(claims))
    an = anomaly_scores(fs.features, explain_top=explain_top)
    out = (rules[["claim_id", "rule_score", "reason_codes", "top_reason", "suspected_type"]]
           .merge(fs.process[["claim_id", "proc_score", "proc_reason"]], on="claim_id")
           .merge(fs.graph[["claim_id", "graph_score", "graph_reason"]], on="claim_id")
           .merge(an[["claim_id", "anomaly_score", "anomaly_reason"]], on="claim_id"))
    if model is not None:
        out = out.merge(model.explain(fs.features), on="claim_id")
    if model_allfeat is not None:
        out = out.merge(model_allfeat.explain(fs.features).rename(
            columns={"ml_score": "ml_score_allfeat", "ml_reason": "ml_reason_allfeat"}), on="claim_id")
    sort_col = "ml_score" if model is not None else "rule_score"
    return out.sort_values([sort_col, "claim_id"], ascending=[False, True]).reset_index(drop=True), fs


def _loso(train_f: pd.DataFrame, train_labels: pd.DataFrame, test_f: pd.DataFrame, test_labels: pd.DataFrame,
          scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    t = test_f.merge(test_labels, on="claim_id").merge(scores[["claim_id", "rule_score", "anomaly_score"]], on="claim_id")
    for scen in sorted(s for s in test_labels.scenario.unique() if s != "normal"):
        keep = train_labels[train_labels.scenario != scen]
        model = train_xgb(train_f[train_f.claim_id.isin(keep.claim_id)], keep)
        t["held_out"] = model.predict(t)
        sub = t[(t.scenario == scen) | (t.label == 0)]
        y = (sub.scenario == scen).astype(int).to_numpy()
        pos = sub[sub.scenario == scen]
        rows.append({
            "skenario": scen, "n_uji": len(pos),
            "recall_xgb_tanpa_skenario": (pos.held_out >= 0.5).mean(),
            "pr_auc_xgb_tanpa_skenario": average_precision(y, sub.held_out.to_numpy()),
            "recall_aturan": (pos.rule_score >= 0.5).mean(),
            "pr_auc_aturan": average_precision(y, sub.rule_score.to_numpy()),
            "pr_auc_isolation_forest": average_precision(y, sub.anomaly_score.to_numpy()),
        })
    return pd.DataFrame(rows)


def run_experiment(claims: pd.DataFrame, labels: pd.DataFrame, train_claims: pd.DataFrame,
                   train_labels: pd.DataFrame, ks: tuple[int, ...] = (100, 500, 1000),
                   loso: bool = True, explain_top: int = 1000) -> ExperimentResult:
    check_no_overlap(train_claims, claims)
    train_fs = compute_features(train_claims)
    model = train_xgb(train_fs.features, train_labels)
    model_all = train_xgb(train_fs.features, train_labels, FEATURE_NAMES)

    scores, fs = score_batch(claims, model, model_all, explain_top=explain_top)
    m = scores.merge(labels, on="claim_id").sort_values("claim_id", kind="stable")  # ties diurutkan sama untuk semua engine
    y = m.label.to_numpy()

    metric_rows, scen_rows = [], []
    for col, name in ENGINE_NAMES.items():
        r = score_metrics(y, m[col].to_numpy(), THRESHOLDS[col], ks)
        row = {"engine": name, "ambang": r["threshold"], "precision": r["precision"], "recall": r["recall"],
               "f1": r["f1"], "pr_auc": r["pr_auc"]}
        for k, v in r["at_k"].items():
            row[f"P@{k}"] = v["precision"]
            row[f"R@{k}"] = v["recall"]
        metric_rows.append(row)
        detected = m[m.label == 1].assign(hit=lambda d: d[col] >= THRESHOLDS[col])
        scen_rows.append(detected.groupby("scenario").hit.mean().rename(name))
    per_scenario = pd.concat(scen_rows, axis=1).reset_index().rename(columns={"scenario": "skenario"})

    loso_df = _loso(train_fs.features, train_labels, fs.features, labels, scores) if loso else pd.DataFrame()
    return ExperimentResult(scores, pd.DataFrame(metric_rows), per_scenario, loso_df, model.importance(), fs, model)


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    fmt = lambda v: f"{v:.3f}" if isinstance(v, (float, np.floating)) else str(v)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def format_markdown(r: ExperimentResult, n_train: int, n_test: int, n_fraud: int) -> str:
    top = r.scores.head(5)[["claim_id", "ml_score", "rule_score", "ml_reason"]]
    imp = r.importance.head(10).reset_index().set_axis(["fitur", "porsi_gain"], axis=1)
    parts = [
        "# Laporan model risiko JEJAK-JKN (data sintetis)",
        f"Data latih XGBoost: {n_train:,} klaim (seed terpisah). Data uji: {n_test:,} klaim, {n_fraud:,} berlabel fraud.",
        "", "## Kinerja per engine", _md(r.metrics),
        "", "## Recall per skenario (pada ambang tiap engine)", _md(r.per_scenario),
    ]
    if len(r.loso):
        parts += ["", "## Leave-one-scenario-out (XGBoost tanpa contoh skenario itu)", _md(r.loso)]
    parts += ["", "## Fitur terpenting XGBoost (total gain)", _md(imp),
              "", "## Contoh alasan SHAP (5 klaim teratas)", _md(top)]
    return "\n".join(parts) + "\n"
