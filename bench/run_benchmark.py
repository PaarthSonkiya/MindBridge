#!/usr/bin/env python3
"""MindBridge benchmark — produces the evidence the Phase 3 brief asks for.

    # translation quality on the organisers' sample set (text in, text out)
    python bench/run_benchmark.py --data data/sample_dataset --mode text

    # full voice pipeline: audio → ASR (NPU) → MT → TTS, per-stage latency + peak RAM
    python bench/run_benchmark.py --data data/sample_dataset --mode voice --limit 100

Writes bench/results/<timestamp>/ with:
    results.jsonl   one line per sentence (texts, scores, timings)
    summary.json    aggregate metrics per direction
    summary.md      the same as a table (paste into the submission template)
    run.log         device, model inventory, network state before/after, offline guard log
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mindbridge import offline_guard  # noqa: E402
from mindbridge.config import load_config  # noqa: E402
from mindbridge.metrics import PeakMemory, device_info, network_snapshot  # noqa: E402

LANG_ALIASES = {
    "vi": ("vi", "vie", "vietnamese", "tiếng việt", "vi_vn", "vie_latn"),
    "en": ("en", "eng", "english", "en_us", "eng_latn"),
    "ko": ("ko", "kor", "korean", "한국어", "ko_kr", "kor_hang"),
    "zh": ("zh", "zho", "chinese", "中文", "zh_cn", "zho_hans", "cn", "mandarin"),
}


# ---------------------------------------------------------------------------
# Dataset loading — tolerant of CSV / TSV / JSONL / XLSX with language-named columns
# ---------------------------------------------------------------------------
def _lang_of_column(name: str) -> str | None:
    n = name.strip().lower()
    for code, aliases in LANG_ALIASES.items():
        if n in aliases or any(n.startswith(a + "_") or n.endswith("_" + a) for a in aliases[:3]):
            return code
    return None


def _tables_from_file(path: Path) -> list[list[dict]]:
    """Each worksheet of an .xlsx is its own table; other formats are one table."""
    suf = path.suffix.lower()
    if suf in (".csv", ".tsv", ".txt"):
        with open(path, encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            delim = "\t" if suf == ".tsv" or sample.count("\t") > sample.count(",") else ","
            return [list(csv.DictReader(f, delimiter=delim))]
    if suf == ".jsonl":
        return [[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]]
    if suf == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [data if isinstance(data, list) else data.get("data", [])]
    if suf == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True)
        tables = []
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            header = [str(h or "").strip() for h in next(it, [])]
            rows = [dict(zip(header, [("" if v is None else str(v)) for v in r], strict=False)) for r in it]
            tables.append([r for r in rows if any(v for v in r.values())])
        return tables
    return []


_AUDIO_COL = re.compile(r"audio|wav|mp3|flac|path|file", re.I)


def _audio_lang(col: str) -> str | None:
    tag = re.sub(r"[_\-\s]*(audio|wav|mp3|flac|path|file)[_\-\s]*", "", col.lower())
    return _lang_of_column(tag) if tag else None


def load_pairs(data: Path) -> dict[tuple[str, str], list[dict]]:
    """Return {(vi, other): [{"a": vi_text, "b": other_text, "audio_a": path?, "audio_b": path?}]}."""
    exts = (".csv", ".tsv", ".jsonl", ".json", ".xlsx", ".txt")
    files = [data] if data.is_file() else sorted(p for p in data.rglob("*") if p.suffix.lower() in exts)
    out: dict[tuple[str, str], list[dict]] = {}
    for f in files:
        for ti, rows in enumerate(_tables_from_file(f)):
            if not rows:
                continue
            keys = list(rows[0].keys())
            audio_cols = [c for c in keys if _AUDIO_COL.search(c)]
            text_cols = [c for c in keys if c not in audio_cols]
            cols = {c: _lang_of_column(c) for c in text_cols}
            langs = [c for c, lang in cols.items() if lang]
            if len(langs) < 2:
                # e.g. columns "source","target" + a file name like vi-en.tsv
                stem = f.stem.lower().replace("_", "-")
                parts = [p for p in stem.split("-") if p in LANG_ALIASES]
                if len(parts) == 2 and len(text_cols) >= 2:
                    cols = {text_cols[0]: parts[0], text_cols[1]: parts[1]}
                    langs = text_cols[:2]
                else:
                    logging.warning("skip %s (table %d): cannot tell which columns are which language (%s)", f, ti, keys)
                    continue
            ca, cb = langs[0], langs[1]
            la, lb = cols[ca], cols[cb]
            if "vi" not in (la, lb) or la == lb:
                logging.warning("skip %s (table %d): need a Vietnamese column and one other language", f, ti)
                continue
            if la != "vi":
                ca, cb, la, lb = cb, ca, lb, la
            key = (la, lb)
            items = []
            for r in rows:
                a, b = str(r.get(ca, "") or "").strip(), str(r.get(cb, "") or "").strip()
                if not a or not b:
                    continue
                item = {"a": a, "b": b, "file": f.name}
                for c in audio_cols:
                    val = str(r.get(c, "") or "").strip()
                    lang = _audio_lang(c)
                    if val and lang in key:
                        p = (f.parent / val) if not Path(val).is_absolute() else Path(val)
                        item["audio_a" if lang == key[0] else "audio_b"] = str(p)
                items.append(item)
            out.setdefault(key, []).extend(items)
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def _norm(text: str) -> str:
    import re

    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def error_rate(ref: str, hyp: str, lang: str) -> float:
    r, h = _norm(ref), _norm(hyp)
    if lang in ("zh", "ko"):
        r, h = list(r.replace(" ", "")), list(h.replace(" ", ""))
    else:
        r, h = r.split(), h.split()
    return _edit_distance(r, h) / max(1, len(r))


def mt_scores(hyps: list[str], refs: list[str], tgt: str) -> dict:
    import sacrebleu

    tok = {"zh": "zh", "ko": "char"}.get(tgt, "13a")
    bleu = sacrebleu.corpus_bleu(hyps, [refs], tokenize=tok)
    chrf = sacrebleu.corpus_chrf(hyps, [refs], word_order=2)
    return {"bleu": round(bleu.score, 2), "chrf++": round(chrf.score, 2), "bleu_tokenizer": tok}


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return s[k]


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="dataset file or folder")
    ap.add_argument("--mode", choices=["text", "voice"], default="text")
    ap.add_argument("--pairs", default="", help="e.g. vi-en,vi-ko (default: all found)")
    ap.add_argument("--directions", default="both", choices=["both", "to-vi", "from-vi"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--require-offline", action="store_true", help="refuse to run if a default route exists")
    ap.add_argument("--allow-synthetic-audio", action="store_true",
                    help="voice mode without recordings: synthesise source audio with the device TTS (labelled)")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out or ROOT / "bench" / "results" / f"{stamp}-{args.mode}")
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(out / "run.log", encoding="utf-8"), logging.StreamHandler()],
    )
    log = logging.getLogger("bench")

    net_before = network_snapshot()
    log.info("device %s", json.dumps(device_info(), ensure_ascii=False))
    log.info("network before run %s", json.dumps(net_before))
    if args.require_offline and (net_before["has_default_route"]):
        sys.exit("Network has a default route. Disconnect Wi-Fi/Ethernet (airplane mode) and re-run.")
    offline_guard.install()

    cfg = load_config()
    from mindbridge.pipeline import MindBridge

    with PeakMemory() as mem_load:
        t0 = time.perf_counter()
        bridge = MindBridge(cfg, load_tts=(args.mode == "voice"), load_memory=False)
        load_s = time.perf_counter() - t0
    log.info("models loaded in %.1fs, peak %.0f MB", load_s, mem_load.peak_mb)
    inv = bridge.inventory()
    for row in inv:
        log.info("model %s", json.dumps(row, ensure_ascii=False))

    data = load_pairs(Path(args.data))
    if args.pairs:
        keep = {tuple(p.split("-")) for p in args.pairs.split(",")}
        data = {k: v for k, v in data.items() if k in keep}
    if not data:
        sys.exit(f"No usable sentence pairs under {args.data}")

    summary: dict = {"mode": args.mode, "started": stamp, "device": device_info(), "models": inv,
                     "load_seconds": round(load_s, 2), "directions": {}}
    results = open(out / "results.jsonl", "w", encoding="utf-8")

    with PeakMemory() as mem_run:
        for (_vi, other), items in data.items():
            if args.limit:
                items = items[: args.limit]
            dirs = []
            if args.directions in ("both", "from-vi"):
                dirs.append(("vi", other, "a", "b"))
            if args.directions in ("both", "to-vi"):
                dirs.append((other, "vi", "b", "a"))
            for src, tgt, sk, tk in dirs:
                key = f"{src}-{tgt}"
                log.info("== %s: %d sentences (%s)", key, len(items), args.mode)
                hyps, refs, asr_err, lat = [], [], [], {"asr": [], "mt": [], "tts": [], "total": [], "speech_to_translation": []}
                synthetic = 0
                for i, it in enumerate(items):
                    rec = {"direction": key, "i": i, "source": it[sk], "reference": it[tk]}
                    if args.mode == "text":
                        r = bridge.translate(it[sk], src, tgt)
                        rec["hypothesis"] = r.text
                        lat["mt"].append(r.timings_ms["mt"])
                    else:
                        audio_path = it.get(f"audio_{sk}")
                        if audio_path:
                            import soundfile as sf

                            audio, sr = sf.read(audio_path, dtype="float32", always_2d=False)
                            rec["audio"] = audio_path
                        elif args.allow_synthetic_audio and bridge.tts and bridge.tts.available(src):
                            s = bridge.tts.synthesize(it[sk], src)
                            audio, sr = s.audio, s.sample_rate
                            rec["audio"] = "synthetic-tts"
                            synthetic += 1
                        else:
                            log.error("no audio for %s #%d (pass --allow-synthetic-audio to synthesise)", key, i)
                            continue
                        turn = bridge.talk(audio, sr, src, tgt, "bench", remember=False)
                        rec.update(asr_text=turn.source_text, hypothesis=turn.translation, timings_ms=turn.timings_ms,
                                   asr_backend=turn.asr_backend, audio_seconds=round(turn.audio_seconds, 2))
                        er = error_rate(it[sk], turn.source_text, src)
                        rec["asr_error_rate"] = round(er, 4)
                        asr_err.append(er)
                        for k in lat:
                            if k in turn.timings_ms:
                                lat[k].append(turn.timings_ms[k])
                    hyps.append(rec["hypothesis"])
                    refs.append(it[tk])
                    results.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    if (i + 1) % 50 == 0:
                        log.info("  %d/%d", i + 1, len(items))
                if not hyps:
                    log.error("   %s: nothing scored (no usable audio/text)", key)
                    summary["directions"][key] = {"n": 0, "bleu": None, "chrf++": None}
                    continue
                d = {"n": len(hyps), **mt_scores(hyps, refs, tgt)}
                if asr_err:
                    d["asr_" + ("cer" if src in ("zh", "ko") else "wer")] = round(100 * statistics.mean(asr_err), 2)
                    d["synthetic_audio"] = synthetic
                for k, v in lat.items():
                    if v:
                        d[f"{k}_ms_mean"] = round(statistics.mean(v), 1)
                        d[f"{k}_ms_p50"] = round(pct(v, 0.5), 1)
                        d[f"{k}_ms_p90"] = round(pct(v, 0.9), 1)
                summary["directions"][key] = d
                log.info("   %s", json.dumps(d))
    results.close()

    net_after = network_snapshot()
    summary.update(
        peak_ram_mb=round(max(mem_load.peak_mb, mem_run.peak_mb), 1),
        network_before=net_before, network_after=net_after,
        offline_guard={"installed": offline_guard.is_installed(), "blocked_attempts": offline_guard.blocked_attempts},
        finished=time.strftime("%Y%m%d-%H%M%S"),
        total_model_mb=round(sum(r["size_mb"] for r in inv), 1),
    )
    log.info("network after run %s", json.dumps(net_after))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    (out / "summary.md").write_text(render_md(summary), encoding="utf-8")
    print(render_md(summary))
    print(f"\nResults in {out}")


def render_md(s: dict) -> str:
    lines = [f"### MindBridge benchmark ({s['mode']} mode, {s['started']})", ""]
    dev = s["device"]
    lines.append(f"Device: {dev.get('soc') or dev['machine']}, {dev['platform']}, {dev['total_ram_mb']} MB RAM. "
                 f"Network default route during run: {'yes' if s['network_before']['has_default_route'] else 'none'}. "
                 f"Outbound connections blocked: {len(s['offline_guard']['blocked_attempts'])}.")
    lines += ["", "| Stage | Model | Runs on | Size |", "|---|---|---|---|"]
    lines += [f"| {m['stage']} | {m['model']} | {m['unit']} | {m['size_mb']} MB |" for m in s["models"]]
    lines += [f"| **Total** | | | **{s['total_model_mb']} MB** |", "",
              f"Peak process RAM: **{s['peak_ram_mb']} MB**. Model load time: {s['load_seconds']} s.", ""]
    head = "| Direction | N | BLEU | chrF++ |"
    sep = "|---|---|---|---|"
    voice = s["mode"] == "voice"
    if voice:
        head += " ASR WER/CER | ASR ms p50 | MT ms p50 | TTS ms p50 | Speech→translation ms p50 | Total ms p90 |"
        sep += "---|---|---|---|---|---|"
    else:
        head += " MT ms mean | MT ms p90 |"
        sep += "---|---|"
    lines += [head, sep]
    for k, d in s["directions"].items():
        row = f"| {k} | {d['n']} | {d['bleu']} | {d['chrf++']} |"
        if voice:
            er = d.get("asr_wer", d.get("asr_cer", ""))
            row += (f" {er}% | {d.get('asr_ms_p50', '')} | {d.get('mt_ms_p50', '')} | {d.get('tts_ms_p50', '')} |"
                    f" {d.get('speech_to_translation_ms_p50', '')} | {d.get('total_ms_p90', '')} |")
        else:
            row += f" {d.get('mt_ms_mean', '')} | {d.get('mt_ms_p90', '')} |"
        lines.append(row)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
