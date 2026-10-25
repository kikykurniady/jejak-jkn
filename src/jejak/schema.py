"""Skema Pandera untuk klaim.

Skema hanya memeriksa **struktur dan domain nilai** (tipe, format, rentang).
Logika bisnis yang mencurigakan (mis. klaim sebelum layanan) sengaja lolos di sini
dan ditangkap oleh rule engine, supaya klaim berisiko tidak terbuang saat validasi.
"""
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from .catalog import DIAGNOSES, PROCEDURES

ClaimSchema = DataFrameSchema(
    {
        "claim_id": Column(str, Check.str_matches(r"^CLM-\d{8}$"), unique=True),
        "participant_token": Column(str, Check.str_matches(r"^P[0-9A-F]{16}$")),
        "facility_id": Column(str, Check.str_matches(r"^(FKTP|FKRTL)-\d{4}$")),
        "facility_type": Column(str, Check.isin(["FKTP", "FKRTL"])),
        "episode_id": Column(str, Check.str_matches(r"^EPS-\d{7}$")),
        "diagnosis_code": Column(str, Check.isin(list(DIAGNOSES))),
        "procedure_code": Column(str, Check.isin(list(PROCEDURES))),
        "service_type": Column(str, Check.isin(["RJ", "RI"])),
        "referral_flag": Column(bool),
        "los_days": Column(int, Check.in_range(0, 60)),
        "service_timestamp": Column("datetime64[ns]"),
        "claim_timestamp": Column("datetime64[ns]"),
        "claim_amount": Column(int, Check.gt(0)),
        "evidence_flag": Column(bool),
    },
    checks=[
        Check(lambda df: df.facility_id.str.split("-").str[0] == df.facility_type,
              element_wise=False, error="facility_type harus sesuai prefiks facility_id"),
    ],
    strict=True,
    coerce=True,
    name="ClaimSchema",
)

LabelSchema = DataFrameSchema(
    {
        "claim_id": Column(str, unique=True),
        "label": Column(int, Check.isin([0, 1])),
        "fraud_type": Column(str, Check.isin(["normal", "phantom", "repeat", "cloning"])),
        "scenario": Column(str),
        "source_claim_id": Column(str, nullable=True),
    },
    coerce=True,
    name="LabelSchema",
)


def validate_claims(df, lazy: bool = True):
    """Validasi klaim; dengan lazy=True semua pelanggaran dikumpulkan sekaligus."""
    return ClaimSchema.validate(df, lazy=lazy)


SchemaErrors = pa.errors.SchemaErrors
