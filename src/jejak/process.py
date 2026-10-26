"""Process mining (PM4Py): penyimpangan alur layanan per episode.

Setiap klaim diubah menjadi event: `Rujukan FKTP` (bila FKRTL dengan rujukan),
`Layanan <tingkat>: <prosedur>` pada waktu layanan, dan `Klaim diajukan` pada waktu
pengajuan. Satu episode = satu *case*. Dari log ini dihitung dua sinyal tanpa label:

- **kelangkaan transisi** (directly-follows graph): seberapa jarang urutan
  `aktivitas sebelumnya → aktivitas ini` muncul di seluruh episode. Transisi langka
  dijadikan alasan, mis. *"Episode diawali 'Klaim diajukan' (hanya 0,5% episode)"*.
- **fitness token replay** terhadap model Petri yang ditemukan Inductive Miner dari
  varian yang umum (cakupan ≥1%), noise 0,2.

PM4Py berlisensi AGPL v3; cocok untuk prototipe lomba yang kodenya terbuka.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .catalog import PROCEDURES

os.environ.setdefault("PM4PY_SHOW_PROGRESS_BAR", "False")

START = "▶ Mulai episode"
CLAIM_EVENT = "Klaim diajukan"
REFERRAL_EVENT = "Rujukan FKTP"
CASE, ACT, TS = "case:concept:name", "concept:name", "time:timestamp"


def activity_name(facility_type: str, procedure_code: str) -> str:
    return f"Layanan {facility_type}: {PROCEDURES[procedure_code].name}"


def build_event_log(claims: pd.DataFrame) -> pd.DataFrame:
    """Event log berformat PM4Py; kolom `claim_id` menautkan event ke klaim."""
    c = claims
    service = pd.DataFrame({
        CASE: c.episode_id.values, ACT: [activity_name(f, p) for f, p in zip(c.facility_type, c.procedure_code)],
        TS: c.service_timestamp.values, "claim_id": c.claim_id.values, "order": 1,
    })
    submit = pd.DataFrame({CASE: c.episode_id.values, ACT: CLAIM_EVENT, TS: c.claim_timestamp.values,
                           "claim_id": c.claim_id.values, "order": 2})
    ref = c[(c.facility_type == "FKRTL") & c.referral_flag]
    referral = pd.DataFrame({CASE: ref.episode_id.values, ACT: REFERRAL_EVENT,
                             TS: (ref.service_timestamp - pd.Timedelta(minutes=1)).values,
                             "claim_id": ref.claim_id.values, "order": 0})
    log = pd.concat([referral, service, submit], ignore_index=True)
    return log.sort_values([CASE, TS, "order", "claim_id"], kind="stable").reset_index(drop=True)


def _transition_rarity(log: pd.DataFrame) -> pd.DataFrame:
    """Untuk tiap event: transisi masuknya dan porsi episode yang memuat transisi itu."""
    case, act = log[CASE].to_numpy(), log[ACT].to_numpy()
    first = np.r_[True, case[1:] != case[:-1]]
    log = log.assign(prev=np.where(first, START, np.concatenate([[START], act[:-1]])))
    n_cases = log[CASE].nunique()
    share = log.groupby(["prev", ACT])[CASE].nunique().rename("share") / n_cases
    return log.join(share, on=["prev", ACT])


def _fitness(log: pd.DataFrame) -> pd.Series:
    import pm4py

    common = pm4py.filter_variants_by_coverage_percentage(log, 0.01)
    net, im, fm = pm4py.discover_petri_net_inductive(common, noise_threshold=0.2)
    diag = pm4py.conformance_diagnostics_token_based_replay(log, net, im, fm, return_diagnostics_dataframe=True)
    return diag.set_index("case_id").trace_fitness


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def process_scores(claims: pd.DataFrame, with_fitness: bool = True) -> pd.DataFrame:
    """Satu baris per klaim: `proc_rarity` (0–1), `proc_fitness`, `episode_n_claims`,
    `proc_score` (0–1) dan `proc_reason` berbahasa Indonesia."""
    log = _transition_rarity(build_event_log(claims))
    rarest = log.sort_values("share", kind="stable").drop_duplicates("claim_id").set_index("claim_id")
    out = claims[["claim_id", "episode_id"]].copy()
    r = rarest.reindex(out.claim_id)
    out["proc_min_share"] = r.share.to_numpy()
    # 10% episode -> 0, 0,1% episode -> 1
    out["proc_rarity"] = np.clip((-np.log10(out.proc_min_share) - 1) / 2, 0, 1).round(4)
    out["proc_fitness"] = out.episode_id.map(_fitness(log)).fillna(1.0).round(4) if with_fitness else 1.0
    out["episode_n_claims"] = out.groupby("episode_id").claim_id.transform("size")
    out["proc_score"] = (0.7 * out.proc_rarity + 0.3 * (1 - out.proc_fitness)).round(4)

    prev, act, share = r.prev.to_numpy(), r[ACT].to_numpy(), out.proc_min_share.to_numpy()
    reason = np.where(prev == START, "Episode diawali '" + act + "'", "Urutan '" + prev + "' → '" + act + "'")
    reason = reason + " (hanya " + pd.Series(share).map(_pct).to_numpy() + " episode)"
    out["proc_reason"] = np.where(out.proc_rarity > 0, reason, "")
    return out.drop(columns="episode_id")
