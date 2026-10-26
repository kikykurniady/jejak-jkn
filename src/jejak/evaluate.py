"""Evaluasi skor terhadap label ground truth sintetis.

Metrik: Precision, Recall, F1 (pada ambang), PR-AUC (average precision),
Precision@K dan Recall@K, plus kinerja per aturan dan recall per skenario.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    """PR-AUC sebagai average precision. Skor yang sama (ties) diperlakukan sebagai satu ambang,
    sehingga hasil tidak bergantung pada urutan baris."""
    y, score = np.asarray(y), np.asarray(score, dtype=float)
    if y.sum() == 0:
        return 0.0
    order = np.argsort(-score, kind="stable")
    y, score = y[order], score[order]
    last = np.r_[score[1:] != score[:-1], True]  # posisi terakhir tiap nilai skor
    tp = np.cumsum(y)[last]
    n = np.arange(1, len(y) + 1)[last]
    precision, recall = tp / n, tp / y.sum()
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def score_metrics(y: np.ndarray, s: np.ndarray, threshold: float = 0.5,
                  ks: tuple[int, ...] = (100, 500, 1000)) -> dict:
    """Precision/Recall/F1 pada ambang, PR-AUC, dan Precision@K/Recall@K untuk satu skor."""
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pred = s >= threshold
    tp = int((pred & (y == 1)).sum())
    precision = tp / max(pred.sum(), 1)
    recall = tp / max(y.sum(), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    order = np.argsort(-s, kind="stable")
    at_k = {}
    for k in ks:
        top = y[order[:k]].sum()
        at_k[k] = {"precision": top / k, "recall": top / max(y.sum(), 1)}
    return {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1,
            "pr_auc": average_precision(y, s), "at_k": at_k}


def evaluate(scored: pd.DataFrame, labels: pd.DataFrame, hits: pd.DataFrame,
             threshold: float = 0.5, ks: tuple[int, ...] = (100, 500, 1000)) -> dict:
    m = scored.merge(labels, on="claim_id").sort_values("claim_id", kind="stable")
    y, s = m.label.to_numpy(), m.rule_score.to_numpy()
    base = score_metrics(y, s, threshold, ks)
    pred = s >= threshold

    h = hits.merge(labels[["claim_id", "label"]], on="claim_id")
    per_rule = (h.groupby("reason_code").label.agg(hits="size", true_positive="sum")
                .assign(precision=lambda d: d.true_positive / d.hits).reset_index())

    m["detected"] = pred
    per_scenario = (m[m.label == 1].groupby("scenario").detected.agg(n="size", recall="mean").reset_index())

    return {
        "n_claims": len(m), "n_fraud": int(y.sum()), **base,
        "per_rule": per_rule, "per_scenario": per_scenario,
    }


def format_report(r: dict) -> str:
    lines = [
        f"Klaim: {r['n_claims']:,} | fraud berlabel: {r['n_fraud']:,}",
        f"Ambang {r['threshold']}: precision {r['precision']:.3f}, recall {r['recall']:.3f}, F1 {r['f1']:.3f}",
        f"PR-AUC (average precision): {r['pr_auc']:.3f}",
    ]
    for k, v in r["at_k"].items():
        lines.append(f"Precision@{k}: {v['precision']:.3f} | Recall@{k}: {v['recall']:.3f}")
    lines += ["", "Per aturan:", r["per_rule"].to_string(index=False, float_format="%.3f"),
              "", "Recall per skenario:", r["per_scenario"].to_string(index=False, float_format="%.3f")]
    return "\n".join(lines)
