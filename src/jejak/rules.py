"""Rule engine: aturan yang bisa dijelaskan, masing-masing menghasilkan reason code.

Setiap aturan mengembalikan DataFrame hit dengan kolom
`claim_id, reason_code, detail`. Skor aturan per klaim digabung secara
noisy-OR: rule_score = 1 - prod(1 - bobot), sehingga beberapa alasan lemah
bisa menumpuk tanpa melewati 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .catalog import PROCEDURES


@dataclass(frozen=True)
class Rule:
    code: str
    fraud_type: str  # pola utama yang didukung: phantom / repeat / cloning
    weight: float
    description: str
    fn: Callable[[pd.DataFrame], pd.DataFrame]


HIT_COLUMNS = ["claim_id", "reason_code", "detail"]


def _hits(df: pd.DataFrame, code: str, detail: pd.Series | str) -> pd.DataFrame:
    out = pd.DataFrame({"claim_id": df.claim_id.values, "reason_code": code})
    out["detail"] = detail.values if isinstance(detail, pd.Series) else detail
    return out


def _fmt_rp(x: float) -> str:
    return "Rp" + f"{int(x):,}".replace(",", ".")


# ---------- Repeat Billing ----------
DUP_KEY = ["participant_token", "facility_id", "diagnosis_code", "procedure_code", "service_timestamp", "claim_amount"]


def r_exact_duplicate(df: pd.DataFrame) -> pd.DataFrame:
    s = df.sort_values(["claim_timestamp", "claim_id"])
    first = s.groupby(DUP_KEY, sort=False).claim_id.transform("first")
    dup = s[s.duplicated(DUP_KEY, keep="first")]
    return _hits(dup, "R01_EXACT_DUP", "Identik dengan klaim " + first[dup.index])


def _near_dup_window_days(max_days: int) -> dict[str, int]:
    """Jendela kemiripan per prosedur: prosedur yang wajar sering (mis. hemodialisis
    2x/minggu) hanya dianggap duplikat bila jaraknya jauh lebih rapat dari jadwal normal."""
    return {c: max(1, min(max_days, int(90 / p.max_per_90d / 2))) for c, p in PROCEDURES.items()}


def r_near_duplicate(df: pd.DataFrame, max_days: int = 3, amount_tol: float = 0.05) -> pd.DataFrame:
    cols = ["claim_id", "participant_token", "facility_id", "procedure_code",
            "service_timestamp", "claim_timestamp", "claim_amount"]
    a = df[cols]
    m = a.merge(a, on=["participant_token", "facility_id", "procedure_code"], suffixes=("", "_o"))
    m = m[m.claim_id != m.claim_id_o]
    gap = (m.service_timestamp - m.service_timestamp_o).abs()
    rel = (m.claim_amount - m.claim_amount_o).abs() / m.claim_amount_o
    exact = (m.service_timestamp == m.service_timestamp_o) & (m.claim_amount == m.claim_amount_o)
    # Klaim yang diajukan belakangan dianggap salinan
    later = (m.claim_timestamp > m.claim_timestamp_o) | ((m.claim_timestamp == m.claim_timestamp_o) & (m.claim_id > m.claim_id_o))
    window = pd.to_timedelta(m.procedure_code.map(_near_dup_window_days(max_days)), unit="D")
    m = m[(gap <= window) & (rel <= amount_tol) & ~exact & later]
    m = m.sort_values("claim_timestamp_o").drop_duplicates("claim_id")
    days = (m.service_timestamp - m.service_timestamp_o).abs().dt.days
    detail = "Mirip klaim " + m.claim_id_o + " (selisih " + days.astype(str) + " hari, nominal ±5%)"
    return _hits(m, "R02_NEAR_DUP", detail)


def r_repeated_procedure(df: pd.DataFrame, window: str = "90D") -> pd.DataFrame:
    key = ["participant_token", "procedure_code"]
    # Urut per kunci lalu waktu, supaya urutan hasil groupby-rolling sama dengan urutan baris
    s = df[["claim_id", *key, "service_timestamp"]].sort_values([*key, "service_timestamp"]).assign(one=1)
    counts = s.groupby(key).rolling(window, on="service_timestamp").one.sum()
    s["n_90d"] = counts.to_numpy()
    s["limit"] = s.procedure_code.map({c: p.max_per_90d for c, p in PROCEDURES.items()})
    hit = s[s.n_90d > s.limit]
    detail = ("Prosedur " + hit.procedure_code + " ke-" + hit.n_90d.astype(int).astype(str)
              + " dalam 90 hari (batas wajar " + hit.limit.astype(str) + ")")
    return _hits(hit, "R03_REPEAT_PROC", detail)


# ---------- Phantom Billing ----------
def _amount_p90(df: pd.DataFrame) -> pd.Series:
    return df.groupby("procedure_code").claim_amount.transform(lambda x: x.quantile(0.90))


def r_missing_evidence(df: pd.DataFrame) -> pd.DataFrame:
    hit = df[~df.evidence_flag]
    return _hits(hit, "R04_NO_EVIDENCE", "Bukti layanan tidak dilampirkan")


def r_missing_evidence_high_amount(df: pd.DataFrame) -> pd.DataFrame:
    p90 = _amount_p90(df)
    hit = df[~df.evidence_flag & (df.claim_amount > p90)]
    detail = "Tanpa bukti dan nominal " + hit.claim_amount.map(_fmt_rp).astype(str) + " di atas P90 prosedur (" + p90[hit.index].map(_fmt_rp).astype(str) + ")"
    return _hits(hit, "R05_NO_EVIDENCE_HIGH_AMT", detail)


def r_claim_before_service(df: pd.DataFrame) -> pd.DataFrame:
    hit = df[df.claim_timestamp < df.service_timestamp]
    return _hits(hit, "R06_CLAIM_BEFORE_SERVICE", "Klaim diajukan sebelum tanggal layanan")


def r_no_referral(df: pd.DataFrame) -> pd.DataFrame:
    hit = df[(df.facility_type == "FKRTL") & ~df.referral_flag]
    return _hits(hit, "R07_NO_REFERRAL", "Layanan FKRTL tanpa rujukan dari FKTP")


def r_level_mismatch(df: pd.DataFrame) -> pd.DataFrame:
    need_fkrtl = df.procedure_code.map({c: p.level == "FKRTL" for c, p in PROCEDURES.items()})
    hit = df[(df.facility_type == "FKTP") & need_fkrtl]
    return _hits(hit, "R08_LEVEL_MISMATCH", "Prosedur tingkat FKRTL ditagihkan oleh FKTP " + hit.facility_id)


def r_amount_outlier(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("procedure_code").claim_amount
    q1, q3 = g.transform(lambda x: x.quantile(0.25)), g.transform(lambda x: x.quantile(0.75))
    upper = q3 + 3 * (q3 - q1)
    hit = df[df.claim_amount > upper]
    return _hits(hit, "R10_AMOUNT_OUTLIER", "Nominal " + hit.claim_amount.map(_fmt_rp).astype(str) + " jauh di atas sebaran prosedur")


# ---------- Cloning ----------
def r_clone_template(df: pd.DataFrame, min_group: int = 5) -> pd.DataFrame:
    s = df.assign(service_date=df.service_timestamp.dt.date)
    key = ["facility_id", "service_date", "diagnosis_code", "procedure_code", "claim_amount"]
    n = s.groupby(key).participant_token.transform("nunique")
    hit = s[n >= min_group]
    detail = (n[hit.index].astype(str) + " peserta berbeda di " + hit.facility_id
              + " dengan diagnosis, prosedur, tanggal, dan nominal identik")
    return _hits(hit, "R09_CLONE_TEMPLATE", detail)


RULES: list[Rule] = [
    Rule("R01_EXACT_DUP", "repeat", 0.90, "Klaim identik dengan klaim sebelumnya", r_exact_duplicate),
    Rule("R02_NEAR_DUP", "repeat", 0.70, "Klaim hampir sama (≤3 hari sesuai prosedur, ±5% nominal)", r_near_duplicate),
    Rule("R03_REPEAT_PROC", "repeat", 0.60, "Prosedur berulang melebihi batas wajar 90 hari", r_repeated_procedure),
    Rule("R04_NO_EVIDENCE", "phantom", 0.40, "Bukti layanan tidak ada", r_missing_evidence),
    Rule("R05_NO_EVIDENCE_HIGH_AMT", "phantom", 0.40, "Tanpa bukti dan nominal tinggi", r_missing_evidence_high_amount),
    Rule("R06_CLAIM_BEFORE_SERVICE", "phantom", 0.85, "Klaim sebelum layanan", r_claim_before_service),
    Rule("R07_NO_REFERRAL", "phantom", 0.50, "FKRTL tanpa rujukan", r_no_referral),
    Rule("R08_LEVEL_MISMATCH", "phantom", 0.70, "Prosedur tidak sesuai tingkat faskes", r_level_mismatch),
    Rule("R09_CLONE_TEMPLATE", "cloning", 0.75, "Klaim template di banyak peserta", r_clone_template),
    Rule("R10_AMOUNT_OUTLIER", "phantom", 0.25, "Nominal pencilan", r_amount_outlier),
]
RULE_BY_CODE = {r.code: r for r in RULES}


def run_rules(df: pd.DataFrame, rules: list[Rule] | None = None) -> pd.DataFrame:
    """Jalankan semua aturan; kembalikan satu baris per hit."""
    parts = [r.fn(df) for r in (rules or RULES)]
    hits = pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) \
        else pd.DataFrame(columns=HIT_COLUMNS)
    hits["weight"] = hits.reason_code.map({r.code: r.weight for r in RULES})
    hits["fraud_type"] = hits.reason_code.map({r.code: r.fraud_type for r in RULES})
    return hits[HIT_COLUMNS + ["weight", "fraud_type"]]


def score_claims(df: pd.DataFrame, hits: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ringkas hit menjadi satu baris per klaim: rule_score, reason_codes, alasan teratas."""
    hits = run_rules(df) if hits is None else hits
    h = hits.sort_values("weight", ascending=False)
    agg = h.groupby("claim_id").agg(
        rule_score=("weight", lambda w: 1 - (1 - w).prod()),
        reason_codes=("reason_code", ";".join),
        top_reason=("detail", "first"),
        suspected_type=("fraud_type", "first"),
        n_reasons=("reason_code", "size"),
    )
    out = df[["claim_id"]].merge(agg, on="claim_id", how="left")
    out["rule_score"] = out.rule_score.fillna(0.0).round(4)
    out["n_reasons"] = out.n_reasons.fillna(0).astype(int)
    out[["reason_codes", "top_reason", "suspected_type"]] = out[["reason_codes", "top_reason", "suspected_type"]].fillna("")
    return out.sort_values(["rule_score", "claim_id"], ascending=[False, True]).reset_index(drop=True)
