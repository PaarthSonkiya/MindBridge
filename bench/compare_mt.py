#!/usr/bin/env python3
"""Compare translation models on the same sentences (how MindBridge's translator was chosen).

    python bench/compare_mt.py --data <dataset> --out bench/results/published/mt_compare_sample.json \
        --model nllb1.3b=models/mt/nllb-200-distilled-1.3B-ct2-int8 \
        --model nllb3.3b=/path/to/nllb-200-3.3B-ct2-int8 \
        --model envit5=/path/to/envit5-translation-ct2-int8

Model kind is taken from the directory: `spiece.model` → envit5 (EN⇄VI only), otherwise NLLB.
Each model is scored with sacreBLEU (BLEU, chrF++) per direction, plus CPU seconds per sentence
(batch of 1, as in the live app).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("run_benchmark", ROOT / "bench" / "run_benchmark.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)


class Envit5:
    """VietAI envit5-translation (T5, 275M) on CTranslate2: 'vi: …' → 'en: …'."""

    pairs = {("vi", "en"), ("en", "vi")}

    def __init__(self, model_dir: Path, beam_size: int = 1, threads: int = 0):
        import ctranslate2
        import sentencepiece as spm

        self.tr = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8", intra_threads=threads)
        self.sp = spm.SentencePieceProcessor(model_file=str(model_dir / "spiece.model"))
        self.beam = beam_size

    def translate(self, text: str, src: str, tgt: str) -> str:
        toks = self.sp.encode(f"{src}: {text}", out_type=str) + ["</s>"]
        res = self.tr.translate_batch([toks], beam_size=self.beam, max_decoding_length=256)
        out = self.sp.decode(res[0].hypotheses[0])
        return re.sub(r"^\s*(en|vi)\s*:\s*", "", out).strip()


class Nllb:
    pairs = None  # every pair

    def __init__(self, model_dir: Path, beam_size: int = 2, threads: int = 0, pivot: str = ""):
        from mindbridge.mt import NllbTranslator

        self.mt = NllbTranslator(model_dir, beam_size=beam_size, threads=threads)
        self.pivot = pivot

    def translate(self, text: str, src: str, tgt: str) -> str:
        if self.pivot and self.pivot not in (src, tgt):
            text = self.mt.translate(text, src, self.pivot).text
            src = self.pivot
        return self.mt.translate(text, src, tgt).text


class Hybrid:
    """Pivot through English, using the best model for each leg: NLLB for X⇄EN, envit5 for EN⇄VI."""

    pairs = None

    def __init__(self, nllb_dir: Path, envit5_dir: Path, beam_size: int = 2, threads: int = 0):
        self.nllb = Nllb(nllb_dir, beam_size=beam_size, threads=threads)
        self.envit5 = Envit5(envit5_dir, beam_size=1, threads=threads)

    def _leg(self, text, src, tgt):
        m = self.envit5 if {src, tgt} == {"en", "vi"} else self.nllb
        return m.translate(text, src, tgt)

    def translate(self, text: str, src: str, tgt: str) -> str:
        if "en" in (src, tgt):
            return self._leg(text, src, tgt)
        return self._leg(self._leg(text, src, "en"), "en", tgt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", action="append", required=True,
                    help="name=dir[:beam[:pivot]], e.g. nllb-pivot=mt/nllb-200-distilled-1.3B-ct2-int8:2:en; "
                         "name=nllb_dir+envit5_dir[:beam] pivots through English with the best model per leg")
    ap.add_argument("--directions", default="", help="e.g. vi-en,ko-vi (default: what the dataset declares)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--save-hyps", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    data, _ = rb.load_dataset(Path(args.data))
    sets: dict[str, tuple[list[str], list[str], list[str]]] = {}
    for (_vi, other), items in data.items():
        for src, tgt, sk, tk in (("vi", other, "a", "b"), (other, "vi", "b", "a")):
            key = f"{src}-{tgt}"
            if args.directions and key not in args.directions.split(","):
                continue
            use = [it for it in items if "native" not in it or key in it["native"] or args.directions]
            if args.limit:
                use = use[: args.limit]
            if use:
                sets[key] = ([it[sk] for it in use], [it[tk] for it in use], [it.get("id", "") for it in use])

    out = Path(args.out)
    report = json.loads(out.read_text()) if out.exists() else {}
    report.setdefault("data", str(args.data))
    report.setdefault("results", {})
    for spec in args.model:
        name, rest = spec.split("=", 1)
        path, beam, pivot = (rest.split(":") + ["", ""])[:3]
        if "+" in path:  # hybrid: nllb_dir+envit5_dir
            dirs = [Path(x) if Path(x).is_absolute() else ROOT / "models" / x for x in path.split("+")]
            mdir, kind, beam_size = dirs[0], Hybrid, int(beam) if beam else 2
            model = Hybrid(dirs[0], dirs[1], beam_size=beam_size, threads=args.threads)
        else:
            mdir = Path(path) if Path(path).is_absolute() else ROOT / "models" / path
            kind = Envit5 if (mdir / "spiece.model").exists() else Nllb
            beam_size = int(beam) if beam else (1 if kind is Envit5 else 2)
            model = kind(mdir, beam_size=beam_size, threads=args.threads, **({"pivot": pivot} if pivot else {}))
        for key, (srcs, refs, ids) in sets.items():
            src, tgt = key.split("-")
            if kind.pairs is not None and (src, tgt) not in kind.pairs:
                continue
            t0 = time.perf_counter()
            hyps = [model.translate(s, src, tgt) for s in srcs]
            dt = (time.perf_counter() - t0) / len(srcs)
            sc = rb.mt_scores(hyps, refs, tgt)
            row = {"n": len(srcs), **sc, "sec_per_sentence": round(dt, 3), "beam": beam_size,
                   "model_dir": mdir.name, **({"pivot": pivot} if pivot else {})}
            if args.save_hyps:
                row["hypotheses"] = [{"id": i, "src": s, "ref": r, "hyp": h} for i, s, r, h in zip(ids, srcs, refs, hyps, strict=True)]
            report["results"].setdefault(name, {})[key] = row
            logging.info("%s %s %s", name, key, {k: v for k, v in row.items() if k != "hypotheses"})
            out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
        del model


if __name__ == "__main__":
    main()
