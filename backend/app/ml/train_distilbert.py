from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune DistilBERT for WebIntel field extraction.")
    parser.add_argument("--train-jsonl", type=Path, required=True)
    parser.add_argument("--valid-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/distilbert-webintel"))
    parser.add_argument("--model", default="distilbert-base-uncased")
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        "Training template ready. Install transformers datasets evaluate, then wire tokenization "
        f"for {args.train_jsonl} and save to {args.output_dir}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
