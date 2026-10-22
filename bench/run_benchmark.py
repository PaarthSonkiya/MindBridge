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
    "vi": ("vi", "vie", "vietnamese", "tiếng việt", "vi_vn", "vie_latn", "việt", "베트남어", "越南语"),
    "en": ("en", "eng", "english", "en_us", "eng_latn", "tiếng anh", "anh", "영어", "英语"),
    "ko": ("ko", "kor", "korean", "한국어", "ko_kr", "kor_hang", "tiếng hàn", "hàn", "韩语"),
    "zh": ("zh", "zho", "chinese", "中文", "zh_cn", "zho_hans", "cn", "mandarin", "tiếng trung", "tiếng hoa",
           "중국어", "汉语"),
}
# Letters in the organisers' sentence IDs, e.g. VE-0037 = Vietnamese speaker → English listener.
ID_LETTERS = {"v": "vi", "e": "en", "k": "ko", "c": "zh", "z": "zh"}
AUDIO_EXTS = (".wav", ".flac", ".mp3", ".ogg", ".m4a")
_GENERIC = re.compile(r"[\s_\-–—:]*(final|ref|reference|text|transcript|source|target|sentence|bản dịch|dịch)$")
_ID_RE = re.compile(r"^([A-Za-z]{1,4})[-_]?(\d+)$")


# ---------------------------------------------------------------------------
# Dataset loading — tolerant of CSV / TSV / JSONL / XLSX with language-named columns, plus the
# organisers' layouts: an .xlsx with an ID column next to wav/<ID>.wav, and <Lang>_text/<ID>.txt
# folders next to <Lang>_voice/<ID>.wav folders.
# ---------------------------------------------------------------------------
def _lang_of_column(name: str) -> str | None:
    n = " ".join(name.strip().lower().split())
    cands = [n, re.split(r"\s*[-–—:(|/]\s*", n)[0]]
    cands += [_GENERIC.sub("", c).strip() for c in cands]
    for c in cands:
        for code, aliases in LANG_ALIASES.items():
            if c in aliases or any(c.startswith(a + "_") or c.endswith("_" + a) for a in aliases[:3]):
                return code
    return None


def _langs_in_name(name: str) -> list[str]:
    """Languages named in a folder/file name: 'Vie-Eng dataset' → [vi, en]; 'Kor_voice' → [ko];
    'OneVoice_V_to_E_samples' → [vi, en]."""
    low = name.lower()
    m = re.search(r"(?:^|[\W_])([a-z])[\W_]+to[\W_]+([a-z])(?:[\W_]|$)", low)
    if m and m.group(1) in ID_LETTERS and m.group(2) in ID_LETTERS:
        return [ID_LETTERS[m.group(1)], ID_LETTERS[m.group(2)]]
    out: list[str] = []
    for tok in re.split(r"[\W_]+", low):
        for code, aliases in LANG_ALIASES.items():
            if tok and tok in aliases and code not in out:
                out.append(code)
    return out


def _id_langs(item_id: str) -> list[str]:
    m = _ID_RE.match(item_id or "")
    if not m or len(m.group(1)) != 2:
        return []
    langs = [ID_LETTERS.get(ch) for ch in m.group(1).lower()]
    return langs if all(langs) and langs[0] != langs[1] else []


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


def _id_column(keys: list[str], rows: list[dict]) -> str | None:
    for k in keys:
        if k.strip().lower() in ("id", "sentence_id", "utt_id", "uid", "utterance_id", "mã", "ma"):
            return k
    for k in keys:  # a column whose values all look like VE-0037
        vals = [str(r.get(k, "") or "").strip() for r in rows[:20]]
        if vals and all(_ID_RE.match(v) for v in vals):
            return k
    return None


def _text_id_folders(root: Path) -> dict[Path, dict[str, dict[str, str]]]:
    """{parent: {lang: {id: text}}} for folders like Kor_text/VK-0143.txt (one sentence per file)."""
    found: dict[Path, dict[str, dict[str, str]]] = {}
    if not root.is_dir():
        return found
    for d in sorted(p for p in root.rglob("*") if p.is_dir()):
        txts = sorted(d.glob("*.txt"))
        langs = _langs_in_name(d.name)
        if not txts or len(langs) != 1 or not all(_ID_RE.match(t.stem) for t in txts):
            continue
        texts = {t.stem: t.read_text(encoding="utf-8-sig").strip() for t in txts}
        found.setdefault(d.parent, {})[langs[0]] = {k: v for k, v in texts.items() if v}
    return found


class _AudioIndex:
    """Every audio file under the dataset root, looked up by file stem (= sentence ID)."""

    def __init__(self, root: Path):
        self.root = root if root.is_dir() else root.parent
        self.by_stem: dict[str, list[Path]] = {}
        for p in sorted(self.root.rglob("*")):
            if p.suffix.lower() in AUDIO_EXTS and not p.name.startswith("."):
                self.by_stem.setdefault(p.stem.lower(), []).append(p)
        self.used: set[Path] = set()

    def lang_of(self, path: Path, item_id: str = "") -> str | None:
        try:
            parts = path.relative_to(self.root).parts[:-1]
        except ValueError:
            parts = path.parts[:-1]
        for part in reversed(parts):  # nearest folder that names exactly one language
            langs = _langs_in_name(part)
            if len(langs) == 1:
                return langs[0]
        idl = _id_langs(item_id or path.stem)
        if idl:  # the speaker's language comes first in the ID
            return idl[0]
        for part in reversed(parts):
            langs = _langs_in_name(part)
            if len(langs) == 2:
                return langs[0]
        return None

    def pair_of(self, path: Path) -> list[str]:
        """Both languages of the folder/ID an unlinked recording sits in (speaker first)."""
        idl = _id_langs(path.stem)
        if idl:
            return idl
        try:
            parts = path.relative_to(self.root).parts[:-1]
        except ValueError:
            parts = path.parts[:-1]
        for part in reversed(parts):
            langs = _langs_in_name(part)
            if len(langs) == 2:
                return langs
        return []

    def find(self, item_id: str, near: Path) -> dict[str, Path]:
        """{lang: path} for recordings named <item_id>.*, closest to `near` when there are several."""
        out: dict[str, tuple[int, Path]] = {}
        for p in self.by_stem.get(item_id.lower(), []):
            lang = self.lang_of(p, item_id)
            if not lang:
                continue
            common = len(Path(*_common_prefix(p.parts, near.parts)).parts) if near else 0
            if lang not in out or common > out[lang][0]:
                out[lang] = (common, p)
        return {k: v for k, (_, v) in out.items()}

    def unlinked(self) -> list[Path]:
        return [p for ps in self.by_stem.values() for p in ps if p not in self.used]


def _common_prefix(a: tuple, b: tuple) -> tuple:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n] or ("/",)


def load_dataset(data: Path) -> tuple[dict[tuple[str, str], list[dict]], list[dict]]:
    """Return ({(vi, other): [item]}, unlinked_recordings).

    item = {"a": vi_text, "b": other_text, "file": name, optional "id", "audio_a", "audio_b",
    "native": ["vi-en", ...]}. `native` lists the directions the dataset itself declares (from which
    side has a recording, else the ID letters, else the file/folder name); items without it are
    usable in both directions.
    """
    exts = (".csv", ".tsv", ".jsonl", ".json", ".xlsx", ".txt")
    text_dirs = _text_id_folders(data)
    skip_dirs = set()
    for parent in text_dirs:
        for d in parent.iterdir():
            if d.is_dir() and len(_langs_in_name(d.name)) == 1 and any(d.glob("*.txt")):
                skip_dirs.add(d)
    files = [data] if data.is_file() else sorted(
        p for p in data.rglob("*")
        if p.suffix.lower() in exts and not p.name.startswith(".") and p.parent not in skip_dirs
    )
    audio = _AudioIndex(data)

    tables: list[tuple[str, Path, list[dict]]] = []
    for f in files:
        for ti, rows in enumerate(_tables_from_file(f)):
            tables.append((f"{f.name}" + (f"#{ti}" if ti else ""), f, rows))
    for parent, by_lang in text_dirs.items():
        if "vi" not in by_lang:
            continue
        for lang, texts in by_lang.items():
            if lang == "vi":
                continue
            ids = sorted(set(texts) & set(by_lang["vi"]))
            rows = [{"ID": i, "vi": by_lang["vi"][i], lang: texts[i]} for i in ids]
            tables.append((f"{parent.name}/<lang>_text", parent / "_", rows))

    out: dict[tuple[str, str], list[dict]] = {}
    seen: dict[tuple, dict] = {}
    for label, f, rows in tables:
        if not rows:
            continue
        keys = list(rows[0].keys())
        audio_cols = [c for c in keys if _AUDIO_COL.search(c)]
        id_col = _id_column(keys, rows)
        text_cols = [c for c in keys if c not in audio_cols and c != id_col]
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
                logging.warning("skip %s: cannot tell which columns are which language (%s)", label, keys)
                continue
        ca, cb = langs[0], langs[1]
        la, lb = cols[ca], cols[cb]
        if "vi" not in (la, lb) or la == lb:
            logging.warning("skip %s: need a Vietnamese column and one other language", label)
            continue
        if la != "vi":
            ca, cb, la, lb = cb, ca, lb, la
        key = (la, lb)
        declared = _langs_in_name(f.stem) or next(
            (ls for ls in (_langs_in_name(p) for p in reversed(f.parent.parts)) if len(ls) == 2), [])
        table_items: list[dict] = []
        table_recorded: set[str] = set()
        for r in rows:
            a, b = str(r.get(ca, "") or "").strip(), str(r.get(cb, "") or "").strip()
            if not a or not b:
                continue
            item: dict = {"a": a, "b": b, "file": label}
            rid = str(r.get(id_col, "") or "").strip() if id_col else ""
            if rid:
                item["id"] = rid
            for c in audio_cols:
                val = str(r.get(c, "") or "").strip()
                lang = _audio_lang(c)
                if val and lang in key:
                    p = (f.parent / val) if not Path(val).is_absolute() else Path(val)
                    item["audio_a" if lang == key[0] else "audio_b"] = str(p)
                    audio.used.add(p)
            if rid:
                for lang, p in audio.find(rid, f.parent).items():
                    if lang in key and f"audio_{'a' if lang == key[0] else 'b'}" not in item:
                        item["audio_a" if lang == key[0] else "audio_b"] = str(p)
                        audio.used.add(p)
            recorded = [f"{la}-{lb}"] * bool(item.get("audio_a")) + [f"{lb}-{la}"] * bool(item.get("audio_b"))
            table_recorded.update(recorded)
            native = recorded
            if not native:
                d = _id_langs(rid) or (declared if len(declared) == 2 else [])
                if sorted(d) == sorted(key):
                    native = [f"{d[0]}-{d[1]}"]
            if native:
                item["native"] = native
            if rid:  # the same sentence listed twice (e.g. a copied spreadsheet): merge
                k = (key, rid)
                if k in seen:
                    old = seen[k]
                    for fld in ("audio_a", "audio_b"):
                        if fld in item and fld not in old:
                            old[fld] = item[fld]
                    old["native"] = sorted(set(old.get("native", [])) | set(item.get("native", [])))
                    continue
                seen[k] = item
            out.setdefault(key, []).append(item)
            table_items.append(item)
        # A table declares a direction when any of its sentences was recorded on that side; text-mode
        # runs then cover every sentence of the table in that direction, even if a recording is missing.
        if table_recorded:
            for it in table_items:
                it["native"] = sorted(table_recorded)

    unlinked = []
    for p in audio.unlinked():
        pair = audio.pair_of(p)
        lang = audio.lang_of(p)
        other = next((x for x in pair if x != lang), None)
        unlinked.append({"audio": str(p), "id": p.stem, "src": lang, "tgt": other})
    return out, unlinked


def load_pairs(data: Path) -> dict[tuple[str, str], list[dict]]:
    """Sentence pairs only (see load_dataset)."""
    return load_dataset(data)[0]


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
def _read_audio(path: str):
    import soundfile as sf

    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sr


def _summarise(hyps, refs, tgt, asr_err, src, lat, extra) -> dict:
    d = {"n": len(hyps), **extra}
    if refs:
        d.update(mt_scores(hyps, refs, tgt))
    else:
        d.update(bleu=None, **{"chrf++": None}, note="no reference translations supplied")
    if asr_err:
        d["asr_" + ("cer" if src in ("zh", "ko") else "wer")] = round(100 * statistics.mean(asr_err), 2)
    for k, v in lat.items():
        if v:
            d[f"{k}_ms_mean"] = round(statistics.mean(v), 1)
            d[f"{k}_ms_p50"] = round(pct(v, 0.5), 1)
            d[f"{k}_ms_p90"] = round(pct(v, 0.9), 1)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="dataset file or folder")
    ap.add_argument("--mode", choices=["text", "voice"], default="text")
    ap.add_argument("--pairs", default="", help="e.g. vi-en,vi-ko (default: all found)")
    ap.add_argument("--directions", default="auto", choices=["auto", "both", "to-vi", "from-vi"],
                    help="auto (default): the directions the dataset declares (which side was recorded, the "
                         "ID letters such as VE-, or a V_to_E file name); both directions when it declares none")
    ap.add_argument("--limit", type=int, default=0, help="first N sentences per direction")
    ap.add_argument("--out", default="")
    ap.add_argument("--require-offline", action="store_true", help="refuse to run if a default route exists")
    ap.add_argument("--allow-synthetic-audio", action="store_true",
                    help="voice mode without recordings: synthesise source audio with the device TTS (labelled)")
    ap.add_argument("--unscored-audio", action="store_true",
                    help="voice mode: also run recordings that have no matching text (latency and transcripts only)")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out or ROOT / "bench" / "results" / f"{stamp}-{args.mode}")
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(out / "run.log", encoding="utf-8"), logging.StreamHandler()],
    )
    log = logging.getLogger("bench")
    log.info("command %s", " ".join(sys.argv))

    net_before = network_snapshot()
    log.info("device %s", json.dumps(device_info(), ensure_ascii=False))
    log.info("network before run %s", json.dumps(net_before))
    if args.require_offline and (net_before["has_default_route"]):
        sys.exit("Network has a default route. Disconnect Wi-Fi/Ethernet (airplane mode) and re-run.")
    offline_guard.install()

    data, unlinked = load_dataset(Path(args.data))
    if args.pairs:
        keep = {tuple(p.split("-")) for p in args.pairs.split(",")}
        data = {k: v for k, v in data.items() if k in keep}
    for k, v in data.items():
        log.info("dataset %s-%s: %d sentence pairs, %d with Vietnamese audio, %d with %s audio", *k, len(v),
                 sum(1 for i in v if i.get("audio_a")), sum(1 for i in v if i.get("audio_b")), k[1])
    if unlinked:
        folders = sorted({str(Path(u["audio"]).parent) for u in unlinked})
        log.warning("%d recordings have no matching sentence text (e.g. %s) in %s", len(unlinked),
                    unlinked[0]["id"], folders)
    if not data and not (args.unscored_audio and unlinked):
        sys.exit(f"No usable sentence pairs under {args.data}")

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

    summary: dict = {"mode": args.mode, "started": stamp, "data": str(args.data), "device": device_info(),
                     "models": inv, "load_seconds": round(load_s, 2), "directions": {},
                     "unlinked_recordings": len(unlinked)}
    results = open(out / "results.jsonl", "w", encoding="utf-8")
    lat_keys = ("asr", "mt", "tts", "total", "speech_to_translation")

    with PeakMemory() as mem_run:
        for (_vi, other), all_items in data.items():
            dirs = []
            if args.directions in ("auto", "both", "from-vi"):
                dirs.append(("vi", other, "a", "b"))
            if args.directions in ("auto", "both", "to-vi"):
                dirs.append((other, "vi", "b", "a"))
            for src, tgt, sk, tk in dirs:
                key = f"{src}-{tgt}"
                items = [it for it in all_items
                         if args.directions != "auto" or "native" not in it or key in it["native"]]
                if args.mode == "voice" and not args.allow_synthetic_audio:
                    missing = sum(1 for it in items if not it.get(f"audio_{sk}"))
                    items = [it for it in items if it.get(f"audio_{sk}")]
                    if missing:
                        log.info("   %s: %d sentences have no %s recording (skipped)", key, missing, src)
                if args.limit:
                    items = items[: args.limit]
                if not items:
                    continue
                log.info("== %s: %d sentences (%s)", key, len(items), args.mode)
                hyps, refs, asr_err, lat = [], [], [], {k: [] for k in lat_keys}
                synthetic = 0
                for i, it in enumerate(items):
                    rec = {"direction": key, "i": i, "id": it.get("id", ""), "source": it[sk], "reference": it[tk]}
                    if args.mode == "text":
                        r = bridge.translate(it[sk], src, tgt)
                        rec["hypothesis"] = r.text
                        lat["mt"].append(r.timings_ms["mt"])
                    else:
                        audio_path = it.get(f"audio_{sk}")
                        if audio_path:
                            audio, sr = _read_audio(audio_path)
                            rec["audio"] = audio_path
                        else:
                            s = bridge.tts.synthesize(it[sk], src)
                            audio, sr = s.audio, s.sample_rate
                            rec["audio"] = "synthetic-tts"
                            synthetic += 1
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
                    results.flush()
                    if (i + 1) % 25 == 0:
                        log.info("  %d/%d", i + 1, len(items))
                extra = {"synthetic_audio": synthetic} if args.mode == "voice" else {}
                d = _summarise(hyps, refs, tgt, asr_err, src, lat, extra)
                summary["directions"][key] = d
                log.info("   %s", json.dumps(d))

        if args.mode == "voice" and args.unscored_audio and unlinked:
            groups: dict[str, list[dict]] = {}
            for u in unlinked:
                if u["src"] and u["tgt"]:
                    groups.setdefault(f"{u['src']}-{u['tgt']}", []).append(u)
            for key, us in groups.items():
                src, tgt = key.split("-")
                bridge.preload_pair(key)
                us = sorted(us, key=lambda u: u["id"])[: args.limit or None]
                label = f"{key} (no reference)"
                log.info("== %s: %d recordings without text", label, len(us))
                hyps, lat = [], {k: [] for k in lat_keys}
                for i, u in enumerate(us):
                    audio, sr = _read_audio(u["audio"])
                    turn = bridge.talk(audio, sr, src, tgt, "bench", remember=False)
                    hyps.append(turn.translation)
                    for k in lat:
                        if k in turn.timings_ms:
                            lat[k].append(turn.timings_ms[k])
                    results.write(json.dumps({"direction": label, "i": i, "id": u["id"], "audio": u["audio"],
                                              "asr_text": turn.source_text, "hypothesis": turn.translation,
                                              "timings_ms": turn.timings_ms, "asr_backend": turn.asr_backend,
                                              "audio_seconds": round(turn.audio_seconds, 2)},
                                             ensure_ascii=False) + "\n")
                    results.flush()
                summary["directions"][label] = _summarise(hyps, [], tgt, [], src, lat, {})
                log.info("   %s", json.dumps(summary["directions"][label]))
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

    def f(v, unit=""):
        return "—" if v is None or v == "" else f"{v}{unit}"

    for k, d in s["directions"].items():
        row = f"| {k} | {d['n']} | {f(d['bleu'])} | {f(d['chrf++'])} |"
        if voice:
            er = d.get("asr_wer", d.get("asr_cer"))
            row += (f" {f(er, '%')} | {f(d.get('asr_ms_p50'))} | {f(d.get('mt_ms_p50'))} | {f(d.get('tts_ms_p50'))} |"
                    f" {f(d.get('speech_to_translation_ms_p50'))} | {f(d.get('total_ms_p90'))} |")
        else:
            row += f" {f(d.get('mt_ms_mean'))} | {f(d.get('mt_ms_p90'))} |"
        lines.append(row)
    if s.get("unlinked_recordings"):
        lines += ["", f"{s['unlinked_recordings']} recordings in the dataset have no matching sentence text."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
