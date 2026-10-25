"""Fitur per klaim untuk model risiko (tanpa label).

Fitur dihitung hanya dari kolom klaim, process mining, dan graf. Yang **sengaja tidak dipakai**:
`claim_id`, `episode_id`, dan token peserta/faskes sebagai angka, karena urutan ID dari generator
bisa membocorkan apakah sebuah klaim disuntikkan belakangan (kebocoran label).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .catalog import PROCEDURES
from .graph import claim_edges, graph_features
from .process import process_scores


@dataclass(frozen=True)
class Feature:
    name: str
    group: str  # klaim / pengulangan / proses / graf
    text: str  # templat alasan; {v} = nilai fitur
    binary: bool = False  # alasan hanya disebut bila nilainya 1


def _rp_ratio(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


FEATURES: list[Feature] = [
    Feature("amount_ratio", "klaim", "Nominal {v}× median prosedur di faskes sejenis"),
    Feature("no_evidence", "klaim", "Bukti layanan tidak dilampirkan", binary=True),
    Feature("fkrtl_no_referral", "klaim", "Layanan FKRTL tanpa rujukan", binary=True),
    Feature("level_mismatch", "klaim", "Prosedur tingkat FKRTL ditagih oleh FKTP", binary=True),
    Feature("claim_lag_days", "klaim", "Jarak layanan ke pengajuan klaim {v} hari"),
    Feature("los_days", "klaim", "Lama rawat {v} hari"),
    Feature("proc_freq_ratio", "pengulangan", "Frekuensi prosedur 90 hari {v}× batas wajar"),
    Feature("gap_ratio", "pengulangan", "Jarak ke klaim serupa {v}× jadwal wajar prosedur"),
    Feature("nearest_amount_diff", "pengulangan", "Selisih nominal dengan klaim serupa terdekat {v}"),
    Feature("proc_rarity", "proses", "Alur episode langka (skor {v})"),
    Feature("proc_fitness", "proses", "Kecocokan alur dengan model proses {v}"),
    Feature("episode_n_claims", "proses", "Episode berisi {v} klaim"),
    Feature("deg_dup", "graf", "Terhubung ke {v} klaim identik"),
    Feature("deg_near", "graf", "Terhubung ke {v} klaim hampir sama"),
    Feature("dup_is_later", "graf", "Diajukan setelah klaim identiknya", binary=True),
    Feature("near_is_later", "graf", "Diajukan setelah klaim yang hampir sama", binary=True),
    Feature("clone_participants", "graf", "Klaster kloning berisi {v} peserta"),
    Feature("pf_visits", "graf", "Peserta datang {v} kali ke faskes ini"),
    Feature("participant_n_facilities", "graf", "Peserta memakai {v} faskes"),
    Feature("facility_clone_share", "graf", "Porsi klaim faskes dalam klaster kloning {v}"),
]
FEATURE_NAMES = [f.name for f in FEATURES]
FEATURE_BY_NAME = {f.name: f for f in FEATURES}


def format_feature(name: str, value: float) -> str | None:
    """Teks alasan untuk satu fitur; None bila fitur biner bernilai 0 (tidak layak disebut)."""
    v = float(value)
    if FEATURE_BY_NAME[name].binary and v == 0:
        return None
    if name == "claim_lag_days" and v < 0:
        return f"Klaim diajukan {_rp_ratio(-v)} hari sebelum layanan"
    shown = str(int(v)) if v == int(v) else _rp_ratio(v)
    return FEATURE_BY_NAME[name].text.format(v=shown)


@dataclass
class FeatureSet:
    features: pd.DataFrame  # claim_id + FEATURE_NAMES
    process: pd.DataFrame  # keluaran process_scores
    graph: pd.DataFrame  # keluaran graph_features
    edges: pd.DataFrame  # edge antar-klaim


def _claim_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["claim_id"]].copy()
    # Median per (prosedur, faskes) bila cukup data, kalau tidak per prosedur
    med_pf = df.groupby(["procedure_code", "facility_id"]).claim_amount.transform("median")
    n_pf = df.groupby(["procedure_code", "facility_id"]).claim_amount.transform("size")
    med_p = df.groupby("procedure_code").claim_amount.transform("median")
    out["amount_ratio"] = (df.claim_amount / np.where(n_pf >= 5, med_pf, med_p)).round(4)
    out["no_evidence"] = (~df.evidence_flag).astype(int)
    out["fkrtl_no_referral"] = ((df.facility_type == "FKRTL") & ~df.referral_flag).astype(int)
    need_fkrtl = df.procedure_code.map({c: p.level == "FKRTL" for c, p in PROCEDURES.items()})
    out["level_mismatch"] = ((df.facility_type == "FKTP") & need_fkrtl).astype(int)
    out["claim_lag_days"] = ((df.claim_timestamp - df.service_timestamp).dt.total_seconds() / 86400).round(2)
    out["los_days"] = df.los_days
    return out


def _repeat_features(df: pd.DataFrame) -> pd.DataFrame:
    key = ["participant_token", "procedure_code"]
    s = df[["claim_id", "facility_id", *key, "service_timestamp", "claim_amount"]].sort_values([*key, "service_timestamp", "claim_id"]).assign(one=1)
    s["n_90d"] = s.groupby(key).rolling("90D", on="service_timestamp").one.sum().to_numpy()
    limit = s.procedure_code.map({c: p.max_per_90d for c, p in PROCEDURES.items()})
    s["proc_freq_ratio"] = (s.n_90d / limit).round(4)

    # Klaim serupa terdekat: peserta, faskes, prosedur sama
    g = s.sort_values(["participant_token", "facility_id", "procedure_code", "service_timestamp", "claim_id"])
    grp = g.groupby(["participant_token", "facility_id", "procedure_code"])
    days = g.service_timestamp.astype("int64") / 86_400e9
    prev_gap = days - grp.service_timestamp.shift(1).astype("int64").where(grp.cumcount() > 0) / 86_400e9
    next_gap = grp.service_timestamp.shift(-1).astype("int64").where(grp.cumcount(ascending=False) > 0) / 86_400e9 - days
    prev_amt = (g.claim_amount - grp.claim_amount.shift(1)).abs() / g.claim_amount
    next_amt = (g.claim_amount - grp.claim_amount.shift(-1)).abs() / g.claim_amount
    use_prev = prev_gap.fillna(np.inf) <= next_gap.fillna(np.inf)
    gap = np.where(use_prev, prev_gap, next_gap)
    amt = np.where(use_prev, prev_amt, next_amt)
    expected = g.procedure_code.map({c: 90 / p.max_per_90d for c, p in PROCEDURES.items()})
    g = g.assign(gap_ratio=np.clip(np.nan_to_num(gap / expected, nan=10.0), 0, 10).round(4),
                 nearest_amount_diff=np.nan_to_num(amt, nan=1.0).clip(0, 1).round(4))
    return df[["claim_id"]].merge(s[["claim_id", "proc_freq_ratio"]], on="claim_id") \
        .merge(g[["claim_id", "gap_ratio", "nearest_amount_diff"]], on="claim_id")


def compute_features(claims: pd.DataFrame, with_fitness: bool = True) -> FeatureSet:
    """Hitung semua fitur tanpa melihat label. `claims` harus sudah divalidasi skema."""
    edges = claim_edges(claims)
    proc = process_scores(claims, with_fitness=with_fitness)
    graph = graph_features(claims, edges)
    f = (_claim_features(claims).merge(_repeat_features(claims), on="claim_id")
         .merge(proc, on="claim_id").merge(graph, on="claim_id"))
    return FeatureSet(f[["claim_id", *FEATURE_NAMES]], proc, graph, edges)
