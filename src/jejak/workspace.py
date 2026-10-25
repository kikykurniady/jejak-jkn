"""Logika auditor workspace (tanpa Streamlit, supaya bisa dites).

- **Skor gabungan sementara**: rata-rata berbobot sinyal tiap engine. Ini *bukan* risk fusion
  final; bobotnya ditampilkan dan bisa diubah auditor di dashboard.
- **Keputusan auditor** disimpan lokal sebagai log CSV append-only (`keputusan_auditor.csv`);
  keputusan terbaru per klaim yang berlaku.
- Pembentuk data untuk timeline dan graf hubungan per kasus.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from .catalog import DIAGNOSES, PROCEDURES
from .process import build_event_log
from .rules import RULE_BY_CODE

# Sinyal per engine (0–1). Isolation Forest memberi persentil, jadi hanya 10% teratas yang
# dianggap sinyal: P90 -> 0, P100 -> 1.
SIGNALS = {
    "rule_score": "Aturan R01–R10",
    "ml_score": "XGBoost + SHAP",
    "graph_score": "Graph antar-klaim",
    "proc_score": "Process mining",
    "anomaly_signal": "Isolation Forest",
}
DEFAULT_WEIGHTS = {"rule_score": 0.35, "ml_score": 0.20, "graph_score": 0.20, "proc_score": 0.10,
                   "anomaly_signal": 0.15}
ANOMALY_FLOOR = 0.90
TIERS = [(0.50, "Tinggi"), (0.25, "Sedang"), (0.0, "Rendah")]

DECISIONS = ["Valid", "Need Clarification", "Irregular", "False Positive"]
DECISION_TEXT = {
    "Valid": "Valid — klaim wajar",
    "Need Clarification": "Need Clarification — minta klarifikasi faskes",
    "Irregular": "Irregular — ada ketidaksesuaian, lanjut pemeriksaan",
    "False Positive": "False Positive — sinyal sistem keliru",
}
DECISION_COLUMNS = ["waktu", "claim_id", "keputusan", "catatan", "auditor", "skor_saat_diputus"]
DECISION_FILE = "keputusan_auditor.csv"

PATTERNS = {"repeat": "Repeat Billing", "phantom": "Phantom Billing", "cloning": "Cloning"}
TS_COLS = ["service_timestamp", "claim_timestamp"]
REQUIRED_FILES = ["claims.csv", "risk_scores.csv", "rule_hits.csv", "graph_edges.csv"]


@dataclass
class WorkspaceData:
    claims: pd.DataFrame
    scores: pd.DataFrame  # satu baris per klaim: skor engine + alasan
    hits: pd.DataFrame  # satu baris per hit aturan
    edges: pd.DataFrame
    labels: pd.DataFrame | None  # hanya untuk mode evaluasi data sintetis


def missing_files(data_dir: Path) -> list[str]:
    return [f for f in REQUIRED_FILES if not (Path(data_dir) / f).exists()]


def load_workspace(data_dir: Path) -> WorkspaceData:
    d = Path(data_dir)
    claims = pd.read_csv(d / "claims.csv", parse_dates=TS_COLS,
                         dtype={"diagnosis_code": str, "procedure_code": str})
    str_cols = {c: str for c in ["reason_codes", "top_reason", "suspected_type", "proc_reason", "graph_reason",
                                 "anomaly_reason", "ml_reason"]}
    scores = pd.read_csv(d / "risk_scores.csv", dtype=str_cols, keep_default_na=False, na_values=[])
    for c in ["rule_score", "proc_score", "graph_score", "anomaly_score", "ml_score"]:
        scores[c] = pd.to_numeric(scores.get(c, 0.0), errors="coerce").fillna(0.0)
    hits = pd.read_csv(d / "rule_hits.csv")
    edges = pd.read_csv(d / "graph_edges.csv")
    labels = pd.read_csv(d / "labels.csv") if (d / "labels.csv").exists() else None
    return WorkspaceData(claims, scores, hits, edges, labels)


# ---------- Skor gabungan ----------
def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, w) for w in weights.values())
    if total <= 0:
        raise ValueError("Minimal satu bobot engine harus > 0")
    return {k: max(0.0, w) / total for k, w in weights.items()}


def signals(scores: pd.DataFrame) -> pd.DataFrame:
    s = scores[["claim_id", "rule_score", "ml_score", "graph_score", "proc_score"]].copy()
    s["anomaly_signal"] = ((scores.anomaly_score - ANOMALY_FLOOR) / (1 - ANOMALY_FLOOR)).clip(0, 1).round(4)
    return s


def tier(score: float) -> str:
    return next(name for lo, name in TIERS if score >= lo)


def suspected_pattern(row) -> str:
    """Dugaan pola utama, dari alasan yang paling kuat dan bisa dijelaskan."""
    if row.suspected_type in PATTERNS:
        return PATTERNS[row.suspected_type]
    g = row.graph_reason
    if g.startswith("Klaster"):
        return "Cloning"
    if g.startswith(("Salinan", "Hampir")):
        return "Repeat Billing"
    if row.proc_reason and row.proc_score >= 0.5:
        return "Phantom Billing"
    return "Anomali umum" if row.anomaly_signal > 0 else "-"


def build_queue(data: WorkspaceData, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Antrean prioritas: satu baris per klaim, urut skor gabungan lalu nominal."""
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    sig = signals(data.scores)
    q = data.scores.merge(sig[["claim_id", "anomaly_signal"]], on="claim_id")
    q["skor_gabungan"] = sum(sig.set_index("claim_id")[k].reindex(q.claim_id).to_numpy() * v
                             for k, v in w.items()).round(4)
    q["prioritas"] = q.skor_gabungan.map(tier)
    q["dugaan_pola"] = q.apply(suspected_pattern, axis=1)
    q["alasan_utama"] = np.select(
        [q.top_reason != "", q.graph_reason != "", q.proc_reason != "", q.ml_reason != ""],
        [q.top_reason, q.graph_reason, q.proc_reason, "Model: " + q.ml_reason], default=q.anomaly_reason)
    cols = ["claim_id", "participant_token", "facility_id", "facility_type", "diagnosis_code", "procedure_code",
            "service_timestamp", "claim_amount", "evidence_flag"]
    q = q.merge(data.claims[cols], on="claim_id")
    q = q.sort_values(["skor_gabungan", "claim_amount", "claim_id"], ascending=[False, False, True])
    q.insert(0, "peringkat", np.arange(1, len(q) + 1))
    return q.reset_index(drop=True)


def contributions(row: pd.Series, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Rincian skor gabungan satu klaim: sinyal × bobot = kontribusi."""
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    rows = [{"engine": SIGNALS[k], "sinyal": float(row[k]), "bobot": v, "kontribusi": float(row[k]) * v}
            for k, v in w.items()]
    return pd.DataFrame(rows)


# ---------- Alasan ----------
def rule_reasons(hits: pd.DataFrame, claim_id: str) -> pd.DataFrame:
    h = hits[hits.claim_id == claim_id].sort_values("weight", ascending=False)
    return pd.DataFrame({
        "kode": h.reason_code, "aturan": h.reason_code.map(lambda c: RULE_BY_CODE[c].description),
        "pola": h.fraud_type.map(PATTERNS), "bobot": h.weight, "detail": h.detail,
    }).reset_index(drop=True)


def split_reasons(text: str) -> list[str]:
    return [t.strip() for t in str(text).split(";") if t.strip()]


# ---------- Keputusan auditor ----------
def load_decisions(data_dir: Path) -> pd.DataFrame:
    p = Path(data_dir) / DECISION_FILE
    if not p.exists():
        return pd.DataFrame(columns=DECISION_COLUMNS)
    return pd.read_csv(p, dtype={"catatan": str, "auditor": str}, keep_default_na=False)


def latest_decisions(decisions: pd.DataFrame) -> pd.DataFrame:
    """Keputusan terbaru per klaim (log append-only, baris terakhir yang berlaku)."""
    return decisions.drop_duplicates("claim_id", keep="last").set_index("claim_id")


def save_decision(data_dir: Path, claim_id: str, decision: str, note: str = "", auditor: str = "",
                  score: float | None = None, when: datetime | None = None) -> pd.DataFrame:
    if decision not in DECISIONS:
        raise ValueError(f"Keputusan harus salah satu dari {DECISIONS}")
    p = Path(data_dir) / DECISION_FILE
    row = pd.DataFrame([{
        "waktu": (when or datetime.now()).isoformat(timespec="seconds"), "claim_id": claim_id,
        "keputusan": decision, "catatan": note.strip(), "auditor": auditor.strip(),
        "skor_saat_diputus": score,
    }])[DECISION_COLUMNS]
    row.to_csv(p, mode="a", header=not p.exists(), index=False)
    return row


# ---------- Timeline ----------
def participant_history(claims: pd.DataFrame, participant: str) -> pd.DataFrame:
    h = claims[claims.participant_token == participant].sort_values(["service_timestamp", "claim_id"]).copy()
    h["prosedur"] = h.procedure_code.map(lambda c: f"{c} {PROCEDURES[c].name}")
    h["diagnosis"] = h.diagnosis_code.map(lambda c: f"{c} {DIAGNOSES[c].name}" if c in DIAGNOSES else c)
    return h


def episode_events(claims: pd.DataFrame, episode_id: str) -> pd.DataFrame:
    """Urutan event proses layanan (format yang sama dengan process mining)."""
    log = build_event_log(claims[claims.episode_id == episode_id])
    return log.rename(columns={"concept:name": "aktivitas", "time:timestamp": "waktu"})[
        ["waktu", "aktivitas", "claim_id"]].reset_index(drop=True)


# ---------- Graf hubungan ----------
EDGE_TEXT = {"duplikat": "Duplikat identik", "hampir_duplikat": "Hampir duplikat", "kloning": "Kloning",
             "peserta": "Klaim milik peserta", "faskes": "Ditagih oleh faskes"}


def related_graph(data: WorkspaceData, claim_id: str, max_claims: int = 30) -> nx.Graph:
    """Graf kecil di sekitar satu klaim: klaim terkait (edge graph engine, 2 langkah),
    plus node peserta dan faskes dari klaim-klaim itu."""
    e = data.edges
    g_claims = nx.Graph()
    g_claims.add_edges_from((a, b, {"edge_type": t, "similarity": s}) for a, b, t, s in
                            e[["claim_a", "claim_b", "edge_type", "similarity"]].itertuples(index=False))
    g_claims.add_node(claim_id)
    near = nx.single_source_shortest_path_length(g_claims, claim_id, cutoff=2)
    keep = sorted(near, key=lambda n: (near[n], n))[:max_claims]

    c = data.claims.set_index("claim_id")
    g = nx.Graph()
    for n in keep:
        r = c.loc[n]
        g.add_node(n, kind="klaim", focus=n == claim_id, label=n,
                   info=f"{r.service_timestamp:%Y-%m-%d} · {r.procedure_code} · Rp{int(r.claim_amount):,}".replace(",", "."))
        g.add_node(r.participant_token, kind="peserta", label=r.participant_token, info="Peserta (token pseudonim)")
        g.add_node(r.facility_id, kind="faskes", label=r.facility_id, info=f"Faskes {r.facility_type}")
        g.add_edge(n, r.participant_token, edge_type="peserta")
        g.add_edge(n, r.facility_id, edge_type="faskes")
    for a, b, d in g_claims.subgraph(keep).edges(data=True):
        g.add_edge(a, b, **d)
    return g
