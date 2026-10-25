"""Generator klaim JKN sintetis dengan skenario fraud yang disuntikkan.

Menghasilkan klaim "normal" dari episode layanan yang masuk akal, lalu menyuntikkan
skenario berlabel (ground truth) untuk Phantom Billing, Repeat Billing, dan Cloning.
Semua identitas adalah token acak; tidak ada data peserta asli.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .catalog import DIAGNOSES, ONE_OFF_PROCEDURES, PROCEDURES

CLAIM_COLUMNS = [
    "claim_id", "participant_token", "facility_id", "facility_type", "episode_id",
    "diagnosis_code", "procedure_code", "service_type", "referral_flag", "los_days",
    "service_timestamp", "claim_timestamp", "claim_amount", "evidence_flag",
]
LABEL_COLUMNS = ["claim_id", "label", "fraud_type", "scenario", "source_claim_id"]

# Porsi skenario terhadap jumlah klaim total
DEFAULT_SCENARIO_RATES = {
    "exact_duplicate": 0.015,
    "near_duplicate": 0.015,
    "repeated_procedure": 0.010,
    "missing_evidence": 0.015,
    "process_deviation": 0.015,
    "cloning": 0.010,
}
SCENARIO_FRAUD_TYPE = {
    "exact_duplicate": "repeat",
    "near_duplicate": "repeat",
    "repeated_procedure": "repeat",
    "missing_evidence": "phantom",
    "process_deviation": "phantom",
    "cloning": "cloning",
}


@dataclass
class GeneratorConfig:
    n_claims: int = 20_000
    seed: int = 42
    start: str = "2025-01-01"
    end: str = "2025-12-31"
    n_fktp: int = 80
    n_fkrtl: int = 30
    n_regions: int = 10
    scenario_rates: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCENARIO_RATES))
    # Derau pada data normal agar aturan tidak sempurna (false positive realistis)
    legit_missing_evidence_rate: float = 0.015
    legit_no_referral_rate: float = 0.01


@dataclass
class SyntheticDataset:
    claims: pd.DataFrame
    labels: pd.DataFrame
    facilities: pd.DataFrame
    participants: pd.DataFrame


def _token(rng: np.random.Generator) -> str:
    return "P" + hashlib.sha256(rng.bytes(16)).hexdigest()[:16].upper()


class _Builder:
    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.t0 = pd.Timestamp(cfg.start)
        self.span_days = (pd.Timestamp(cfg.end) - self.t0).days
        self.rows: list[dict] = []
        self.labels: list[dict] = []
        self._next_claim = 1
        self._next_episode = 1
        self._build_reference()

    # ---------- referensi ----------
    def _build_reference(self):
        rng, cfg = self.rng, self.cfg
        fac = []
        for i in range(cfg.n_fktp):
            fac.append(("FKTP-%04d" % (i + 1), "FKTP", "WIL-%02d" % (i % cfg.n_regions + 1),
                        round(float(rng.uniform(0.9, 1.1)), 3)))
        for i in range(cfg.n_fkrtl):
            fac.append(("FKRTL-%04d" % (i + 1), "FKRTL", "WIL-%02d" % (i % cfg.n_regions + 1),
                        round(float(rng.uniform(0.85, 1.25)), 3)))
        self.facilities = pd.DataFrame(fac, columns=["facility_id", "facility_type", "region", "cost_factor"])
        self.fac_factor = dict(zip(self.facilities.facility_id, self.facilities.cost_factor))
        self.fktp_by_region = self.facilities[self.facilities.facility_type == "FKTP"].groupby("region").facility_id.apply(list).to_dict()
        self.fkrtl_by_region = self.facilities[self.facilities.facility_type == "FKRTL"].groupby("region").facility_id.apply(list).to_dict()

        n_part = max(50, int(cfg.n_claims / 2.5))
        regions = rng.integers(1, cfg.n_regions + 1, n_part)
        self.participants = pd.DataFrame({
            "participant_token": [_token(rng) for _ in range(n_part)],
            "birth_year": rng.integers(1940, 2024, n_part),
            "sex": rng.choice(["L", "P"], n_part),
            "region": ["WIL-%02d" % r for r in regions],
        })
        self.participants["home_fktp"] = [
            self.fktp_by_region[r][int(rng.integers(len(self.fktp_by_region[r])))]
            for r in self.participants.region
        ]

    # ---------- utilitas ----------
    def _claim_id(self) -> str:
        cid = "CLM-%08d" % self._next_claim
        self._next_claim += 1
        return cid

    def _episode_id(self) -> str:
        eid = "EPS-%07d" % self._next_episode
        self._next_episode += 1
        return eid

    def _amount(self, proc_code: str, facility_id: str) -> int:
        base = PROCEDURES[proc_code].base_cost * self.fac_factor[facility_id]
        # Komponen tambahan (obat, BMHP) membuat nominal bervariasi
        amt = base * self.rng.lognormal(0, 0.12)
        return int(round(amt, -3))

    def _service_time(self, day: pd.Timestamp) -> pd.Timestamp:
        minutes = int(self.rng.integers(7 * 60, 20 * 60))
        return day.normalize() + pd.Timedelta(minutes=minutes)

    def _claim_time(self, service: pd.Timestamp, los: int) -> pd.Timestamp:
        lag = pd.Timedelta(days=los + int(self.rng.integers(1, 21)), minutes=int(self.rng.integers(0, 600)))
        return service + lag

    def _add(self, row: dict, scenario: str | None = None, source: str | None = None) -> dict:
        row = dict(row)
        row["claim_id"] = self._claim_id()
        self.rows.append(row)
        self.labels.append({
            "claim_id": row["claim_id"],
            "label": int(scenario is not None),
            "fraud_type": SCENARIO_FRAUD_TYPE.get(scenario, "normal"),
            "scenario": scenario or "normal",
            "source_claim_id": source,
        })
        return row

    def _make_row(self, participant: pd.Series, facility_id: str, episode_id: str, diag: str,
                  proc: str, service: pd.Timestamp, referral: bool) -> dict:
        p = PROCEDURES[proc]
        los = int(self.rng.integers(p.los[0], p.los[1] + 1)) if p.service_type == "RI" else 0
        return {
            "participant_token": participant.participant_token,
            "facility_id": facility_id,
            "facility_type": facility_id.split("-")[0],
            "episode_id": episode_id,
            "diagnosis_code": diag,
            "procedure_code": proc,
            "service_type": p.service_type,
            "referral_flag": referral,
            "los_days": los,
            "service_timestamp": service,
            "claim_timestamp": self._claim_time(service, los),
            "claim_amount": self._amount(proc, facility_id),
            "evidence_flag": True,
        }

    def _pick_fkrtl(self, region: str) -> str:
        options = self.fkrtl_by_region.get(region) or self.facilities[self.facilities.facility_type == "FKRTL"].facility_id.tolist()
        return options[int(self.rng.integers(len(options)))]

    # ---------- klaim normal ----------
    def _episode_claims(self, participant: pd.Series) -> list[dict]:
        rng = self.rng
        codes = list(DIAGNOSES)
        weights = np.array([DIAGNOSES[c].weight for c in codes])
        dx = DIAGNOSES[codes[rng.choice(len(codes), p=weights / weights.sum())]]
        day = self.t0 + pd.Timedelta(days=int(rng.integers(0, self.span_days)))
        eps = self._episode_id()
        fktp = participant.home_fktp
        out = []

        if dx.pathway == "single":
            out.append(self._make_row(participant, fktp, eps, dx.code, dx.procedures[0], self._service_time(day), False))
        elif dx.pathway == "chronic_visit":
            t = self._service_time(day)
            out.append(self._make_row(participant, fktp, eps, dx.code, "89.03", t, False))
            if rng.random() < 0.5:
                out.append(self._make_row(participant, fktp, eps, dx.code, "90.59", t + pd.Timedelta(minutes=30), False))
        elif dx.pathway in ("therapy_series", "dialysis_series"):
            fkrtl = self._pick_fkrtl(participant.region)
            n, gap = (int(rng.integers(4, 11)), 7) if dx.pathway == "therapy_series" else (int(rng.integers(6, 13)), 3)
            for k in range(n):
                t = self._service_time(day + pd.Timedelta(days=k * gap + int(rng.integers(0, 2))))
                out.append(self._make_row(participant, fkrtl, eps, dx.code, dx.procedures[0], t, True))
        else:  # referral_then_proc: konsultasi FKTP lalu rujukan ke FKRTL
            out.append(self._make_row(participant, fktp, eps, dx.code, "89.03", self._service_time(day), False))
            fkrtl = self._pick_fkrtl(participant.region)
            d = day + pd.Timedelta(days=int(rng.integers(1, 10)))
            for proc in dx.procedures:
                referral = rng.random() >= self.cfg.legit_no_referral_rate
                out.append(self._make_row(participant, fkrtl, eps, dx.code, proc, self._service_time(d), referral))
                d += pd.Timedelta(days=int(rng.integers(0, 3)))
        for row in out:
            if rng.random() < self.cfg.legit_missing_evidence_rate:
                row["evidence_flag"] = False
        return out

    def build_normal(self, n_normal: int):
        parts = self.participants
        while len(self.rows) < n_normal:
            participant = parts.iloc[int(self.rng.integers(len(parts)))]
            for row in self._episode_claims(participant):
                if len(self.rows) >= n_normal:
                    break
                self._add(row)

    # ---------- injeksi skenario ----------
    def _normal_rows(self) -> list[dict]:
        return [r for r, lab in zip(self.rows, self.labels) if lab["label"] == 0]

    def _sample_normals(self, k: int) -> list[dict]:
        normals = self._normal_rows()
        idx = self.rng.choice(len(normals), size=min(k, len(normals)), replace=False)
        return [normals[i] for i in idx]

    def inject_exact_duplicate(self, k: int):
        for src in self._sample_normals(k):
            row = dict(src)
            row["claim_timestamp"] = src["claim_timestamp"] + pd.Timedelta(days=int(self.rng.integers(3, 45)))
            self._add(row, "exact_duplicate", src["claim_id"])

    def inject_near_duplicate(self, k: int):
        for src in self._sample_normals(k):
            row = dict(src)
            shift = int(self.rng.choice([-2, -1, 1, 2]))
            row["service_timestamp"] = src["service_timestamp"] + pd.Timedelta(days=shift, minutes=int(self.rng.integers(-90, 90)))
            row["claim_timestamp"] = max(src["claim_timestamp"], row["service_timestamp"]) + pd.Timedelta(days=int(self.rng.integers(2, 30)))
            row["claim_amount"] = int(round(src["claim_amount"] * self.rng.uniform(0.97, 1.03), -3))
            if self.rng.random() < 0.5:
                row["episode_id"] = self._episode_id()  # disamarkan sebagai episode baru
            self._add(row, "near_duplicate", src["claim_id"])

    def inject_repeated_procedure(self, k: int):
        added = 0
        while added < k:
            participant = self.participants.iloc[int(self.rng.integers(len(self.participants)))]
            proc = ONE_OFF_PROCEDURES[int(self.rng.integers(len(ONE_OFF_PROCEDURES)))]
            dx = next(d.code for d in DIAGNOSES.values() if proc in d.procedures)
            fkrtl = self._pick_fkrtl(participant.region)
            eps = self._episode_id()
            day = self.t0 + pd.Timedelta(days=int(self.rng.integers(0, self.span_days - 60)))
            base = self._add(self._make_row(participant, fkrtl, eps, dx, proc, self._service_time(day), True))
            limit = PROCEDURES[proc].max_per_90d
            n_extra = int(self.rng.integers(limit + 1, limit + 4))
            for _ in range(n_extra):
                d = day + pd.Timedelta(days=int(self.rng.integers(7, 60)))
                row = self._make_row(participant, fkrtl, self._episode_id(), dx, proc, self._service_time(d), True)
                self._add(row, "repeated_procedure", base["claim_id"])
                added += 1

    def _phantom_base(self) -> dict:
        participant = self.participants.iloc[int(self.rng.integers(len(self.participants)))]
        proc = self.rng.choice([c for c, p in PROCEDURES.items() if p.level == "FKRTL"])
        dx = next(d.code for d in DIAGNOSES.values() if proc in d.procedures)
        fkrtl = self._pick_fkrtl(participant.region)
        day = self.t0 + pd.Timedelta(days=int(self.rng.integers(0, self.span_days)))
        return self._make_row(participant, fkrtl, self._episode_id(), dx, str(proc), self._service_time(day), True)

    def inject_missing_evidence(self, k: int):
        for _ in range(k):
            row = self._phantom_base()
            row["evidence_flag"] = False
            row["claim_amount"] = int(round(row["claim_amount"] * self.rng.uniform(1.3, 2.2), -3))
            self._add(row, "missing_evidence")

    def inject_process_deviation(self, k: int):
        kinds = ["claim_before_service", "no_referral", "level_mismatch"]
        for i in range(k):
            row = self._phantom_base()
            kind = kinds[i % len(kinds)]
            if kind == "claim_before_service":
                row["claim_timestamp"] = row["service_timestamp"] - pd.Timedelta(days=int(self.rng.integers(1, 15)))
            elif kind == "no_referral":
                row["referral_flag"] = False
            else:  # prosedur tingkat FKRTL ditagih oleh FKTP
                participant = self.participants[self.participants.participant_token == row["participant_token"]].iloc[0]
                row["facility_id"] = participant.home_fktp
                row["facility_type"] = "FKTP"
                row["claim_amount"] = self._amount(row["procedure_code"], row["facility_id"])
            self._add(row, "process_deviation")

    def inject_cloning(self, k: int):
        added = 0
        fac_ids = self.facilities.facility_id.tolist()
        while added < k:
            fac = fac_ids[int(self.rng.integers(len(fac_ids)))]
            ftype = fac.split("-")[0]
            procs = [c for c, p in PROCEDURES.items() if ftype == "FKRTL" or p.level == "FKTP"]
            proc = procs[int(self.rng.integers(len(procs)))]
            dx = next(d.code for d in DIAGNOSES.values() if proc in d.procedures)
            day = self.t0 + pd.Timedelta(days=int(self.rng.integers(0, self.span_days)))
            template = self._make_row(self.participants.iloc[0], fac, "", dx, proc, self._service_time(day), ftype == "FKRTL")
            group = int(self.rng.integers(6, 13))
            members = self.participants.sample(group, random_state=int(self.rng.integers(1 << 31)))
            for _, participant in members.iterrows():
                row = dict(template)
                row["participant_token"] = participant.participant_token
                row["episode_id"] = self._episode_id()
                row["service_timestamp"] = template["service_timestamp"] + pd.Timedelta(minutes=int(self.rng.integers(0, 20)))
                self._add(row, "cloning")
                added += 1


def generate(cfg: GeneratorConfig | None = None) -> SyntheticDataset:
    cfg = cfg or GeneratorConfig()
    b = _Builder(cfg)
    counts = {s: int(round(cfg.n_claims * r)) for s, r in cfg.scenario_rates.items()}
    b.build_normal(cfg.n_claims - sum(counts.values()))
    for scenario, k in counts.items():
        if k > 0:
            getattr(b, f"inject_{scenario}")(k)

    claims = pd.DataFrame(b.rows)[CLAIM_COLUMNS]
    labels = pd.DataFrame(b.labels)[LABEL_COLUMNS]
    # Acak urutan lalu beri ulang claim_id agar urutan tidak membocorkan label
    order = b.rng.permutation(len(claims))
    claims, labels = claims.iloc[order].reset_index(drop=True), labels.iloc[order].reset_index(drop=True)
    remap = {old: "CLM-%08d" % (i + 1) for i, old in enumerate(claims.claim_id)}
    claims["claim_id"] = claims.claim_id.map(remap)
    labels["claim_id"] = labels.claim_id.map(remap)
    labels["source_claim_id"] = labels.source_claim_id.map(remap)
    claims["claim_amount"] = claims.claim_amount.astype("int64")
    return SyntheticDataset(claims, labels, b.facilities, b.participants.drop(columns="home_fktp"))
