"""CLI: python -m jejak <generate|validate|rules|evaluate|pipeline|ml>."""
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
    # Kode ICD dibaca sebagai teks; kalau tidak "74.10" bisa berubah menjadi 74.1
    return pd.read_csv(path, parse_dates=TS_COLS, dtype={"diagnosis_code": str, "procedure_code": str})


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


def cmd_ml(a):
    from .experiment import format_markdown, run_experiment, score_batch
    from .models import train_xgb
    from .features import FEATURE_NAMES, compute_features

    d = Path(a.data)
    claims = validate_claims(load_claims(d / "claims.csv"))
    train = generate(GeneratorConfig(n_claims=a.n_train, seed=a.train_seed))
    train_claims = validate_claims(train.claims)
    print(f"Data latih XGBoost: {len(train_claims):,} klaim sintetis terpisah (seed {a.train_seed})")
    labels_path = d / "labels.csv"
    if labels_path.exists() and not a.no_eval:
        labels = pd.read_csv(labels_path)
        r = run_experiment(claims, labels, train_claims, train.labels, loso=not a.no_loso)
        scores, fs, model = r.scores, r.features, r.model
        report = format_markdown(r, len(train_claims), len(claims), int(labels.label.sum()))
        (d / "ml_report.md").write_text(report)
        print(report)
    else:
        from .experiment import check_no_overlap
        check_no_overlap(train_claims, claims)
        tf = compute_features(train_claims).features
        model = train_xgb(tf, train.labels)
        scores, fs = score_batch(claims, model, train_xgb(tf, train.labels, FEATURE_NAMES))
    model.save(d / "model_xgb.json")
    scores.to_csv(d / "risk_scores.csv", index=False)
    fs.edges.to_csv(d / "graph_edges.csv", index=False)
    fs.features.to_csv(d / "features.csv", index=False)
    print(f"-> {d}/risk_scores.csv, graph_edges.csv, features.csv, model_xgb.json"
          + (", ml_report.md" if (d / "ml_report.md").exists() else ""))


def main(argv=None):
    p = argparse.ArgumentParser(prog="jejak", description="JEJAK-JKN: data sintetis, rule engine, dan model risiko")
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
    ml = sub.add_parser("ml", help="process mining + graph + Isolation Forest + XGBoost/SHAP, evaluasi vs aturan")
    ml.add_argument("--data", default="data")
    ml.add_argument("--n-train", type=int, default=20_000, help="jumlah klaim data latih XGBoost")
    ml.add_argument("--train-seed", type=int, default=1042, help="harus berbeda dari seed data uji")
    ml.add_argument("--no-loso", action="store_true", help="lewati uji leave-one-scenario-out")
    ml.add_argument("--no-eval", action="store_true", help="hanya menilai, tanpa evaluasi label")
    ml.set_defaults(fn=cmd_ml)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
