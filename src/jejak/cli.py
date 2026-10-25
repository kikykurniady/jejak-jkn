"""CLI: python -m jejak <generate|validate|rules|evaluate|pipeline>."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .evaluate import evaluate, format_report
from .generator import GeneratorConfig, generate
from .rules import run_rules, score_claims
from .schema import SchemaErrors, validate_claims

TS_COLS = ["service_timestamp", "claim_timestamp"]


def load_claims(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=TS_COLS)


def cmd_generate(a):
    ds = generate(GeneratorConfig(n_claims=a.n, seed=a.seed))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ds.claims.to_csv(out / "claims.csv", index=False)
    ds.labels.to_csv(out / "labels.csv", index=False)
    ds.facilities.to_csv(out / "facilities.csv", index=False)
    ds.participants.to_csv(out / "participants.csv", index=False)
    print(f"{len(ds.claims):,} klaim ({int(ds.labels.label.sum()):,} berlabel fraud) -> {out}/")
    print(ds.labels.scenario.value_counts().to_string())


def cmd_validate(a):
    try:
        validate_claims(load_claims(Path(a.data) / "claims.csv"))
        print("Validasi skema: OK")
    except SchemaErrors as e:
        print(e.failure_cases.head(50).to_string())
        raise SystemExit(1)


def cmd_rules(a):
    d = Path(a.data)
    claims = validate_claims(load_claims(d / "claims.csv"))
    hits = run_rules(claims)
    scored = score_claims(claims, hits)
    hits.to_csv(d / "rule_hits.csv", index=False)
    scored.to_csv(d / "rule_scores.csv", index=False)
    print(f"{len(hits):,} hit aturan pada {int((scored.rule_score > 0).sum()):,} klaim -> {d}/rule_scores.csv")
    print(scored.head(10)[["claim_id", "rule_score", "reason_codes", "top_reason"]].to_string(index=False))


def cmd_evaluate(a):
    d = Path(a.data)
    report = evaluate(pd.read_csv(d / "rule_scores.csv"), pd.read_csv(d / "labels.csv"),
                      pd.read_csv(d / "rule_hits.csv"), threshold=a.threshold)
    print(format_report(report))


def cmd_pipeline(a):
    cmd_generate(a)
    a.data = a.out
    cmd_validate(a)
    cmd_rules(a)
    print()
    cmd_evaluate(a)


def main(argv=None):
    p = argparse.ArgumentParser(prog="jejak", description="JEJAK-JKN: data sintetis dan rule engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    def gen_args(sp):
        sp.add_argument("--n", type=int, default=20_000, help="jumlah klaim (10k–50k)")
        sp.add_argument("--seed", type=int, default=42)
        sp.add_argument("--out", default="data")

    gen_args(g := sub.add_parser("generate", help="buat data sintetis + label"))
    g.set_defaults(fn=cmd_generate)
    for name, fn in [("validate", cmd_validate), ("rules", cmd_rules), ("evaluate", cmd_evaluate)]:
        sp = sub.add_parser(name)
        sp.add_argument("--data", default="data")
        sp.add_argument("--threshold", type=float, default=0.5)
        sp.set_defaults(fn=fn)
    pl = sub.add_parser("pipeline", help="generate -> validate -> rules -> evaluate")
    gen_args(pl)
    pl.add_argument("--threshold", type=float, default=0.5)
    pl.set_defaults(fn=cmd_pipeline)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
