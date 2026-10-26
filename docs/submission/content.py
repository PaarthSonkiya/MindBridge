"""Text of MindBridge's Prototype Submission (filled into the organisers' template by build_submission.py).

Demo device for Phase 3: a MacBook Air (Apple M5, 16 GB), the "other hardware prepared by the team" the
brief allows. Its benchmark runs (made with Wi-Fi off) live in bench/results/published/mac_m5_text/ and
mac_m5_voice/ and are read automatically; until they exist, their values stay as [TO FILL …].
The Qualcomm RB3 Gen 2 is the target platform: its NPU numbers come from Qualcomm AI Hub's hosted devices
and are always labelled as such. `board` is an optional benchmark run on a physical RB3 Gen 2.
Keep answers short: the template asks for concise answers that link to existing material.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PUB = ROOT / "bench" / "results" / "published"
REPO = "https://github.com/PaarthSonkiya/MindBridge"
BRANCH = "main"
VERSION = "0.4.0"
MAC_TEXT, MAC_VOICE = "mac_m5_text", "mac_m5_voice"
ORDER = ["vi-en", "en-vi", "vi-ko", "ko-vi", "vi-zh", "zh-vi"]
NAMES = {"vi": "Vietnamese", "en": "English", "ko": "Korean", "zh": "Chinese"}


def _json(rel: str):
    p = PUB / rel
    return json.loads(p.read_text()) if p.exists() else None


def _git_sha() -> str:
    """The commit this document (and the package built alongside it) comes from."""
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "[TO FILL: commit]"


def _fmt(v, nd=1, unit=""):
    # round half up (18.45 → 18.5), as people expect, instead of binary-float rounding
    return "[TO FILL]" if v is None else f"{v + (0.5 * 10 ** -nd if v >= 0 else 0) * 1e-6:,.{nd}f}{unit}"


def _arrow(d: str) -> str:
    a, b = d.split("-")
    return f"{a.upper()}→{b.upper()}"


def _date(stamp: str | None) -> str:
    m = re.match(r"(\d{4})(\d{2})(\d{2})", stamp or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else "[TO FILL: date]"


def fields(board: dict | None) -> dict:
    sha = _git_sha()
    tree = f"{REPO}/tree/{BRANCH}"
    # Demo-device runs (MacBook, Wi-Fi off) and development runs (x86-64 VM, offline guard only).
    MT, MV = _json(f"{MAC_TEXT}/summary.json"), _json(f"{MAC_VOICE}/summary.json")
    DT = _json("onevoice_sample_text/summary.json") or {"directions": {}}
    DV = {"directions": {}}
    for part in ("onevoice_sample_voice", "onevoice_sample_voice_ko", "onevoice_sample_voice_zh"):
        r = _json(f"{part}/summary.json")
        if r:
            DV["directions"].update(r["directions"])
    turbo = {r["model"]: r for r in (_json("aihub_whisper_turbo_qcs6490/summary.json") or [])}
    small = {r["model"]: r for r in (_json("aihub_whisper_small_qcs6490/summary.json") or [])}
    enc, dec = turbo.get("encoder.bin", {}), turbo.get("decoder.bin", {})
    dev = (MV or MT or {}).get("device", {})
    chip = dev.get("soc") or "Apple M5"
    macos = dev.get("os") or "[TO FILL: macOS version]"
    cores = dev.get("cpu_count")
    ram_gb = round(dev["total_ram_mb"] / 1024) if dev.get("total_ram_mb") else 16

    def get(summary, d, k):
        return (summary or {}).get("directions", {}).get(d, {}).get(k)

    def mt(d, k):
        return get(MT, d, k)

    def mv(d, k):
        return get(MV, d, k)

    def bd(d, k):
        return get(board, d, k)

    def text_scores(summary):
        return "; ".join(f"{_arrow(d)} {_fmt(get(summary, d, 'bleu'))} / {_fmt(get(summary, d, 'chrf++'))} "
                         f"(n={get(summary, d, 'n')})" for d in ORDER if get(summary, d, "bleu") is not None)

    def voice_scores(summary):
        parts = []
        for d in ORDER:
            if get(summary, d, "bleu") is None:
                continue
            src = d.split("-")[0]
            er = get(summary, d, "asr_cer" if src in ("ko", "zh") else "asr_wer")
            kind = "character" if src in ("ko", "zh") else "word"
            parts.append(f"{_arrow(d)} {_fmt(get(summary, d, 'bleu'))} / {_fmt(get(summary, d, 'chrf++'))}, "
                         f"{NAMES[src]} {kind} error rate {_fmt(er, 1, '%')} (n={get(summary, d, 'n')})")
        return "; ".join(parts)

    # ---------------------------------------------------------------- section 1
    summary = {
        "Team / individual participant": "MindBridge",
        "Project name": "MindBridge: offline voice translation with operational memory for multilingual factory floors",
        "Submitted build": f"MindBridge v{VERSION}, git commit {sha} (branch {BRANCH}, {REPO}); offline package "
                           f"mindbridge-offline-{VERSION}-macos-arm64.tar.gz built from that commit. "
                           "[TO FILL: date of the build shown in the video]",
        "Demo language(s)": "Vietnamese ⇄ English, both directions (registered pair). Vietnamese ⇄ Korean, both "
                            "directions (scenario Part B, if a Korean speaker is available). Vietnamese ⇄ Chinese can "
                            "be selected on screen and is benchmarked, but is not part of the recorded demo.",
        "Test scenario": (
            "A day shift at a Korean-owned electronics plant near Ho Chi Minh City. Roles: a Supervisor (English in "
            "Part A, Korean in Part B), a Vietnamese line Operator and a Technician, sharing one MindBridge unit.\n\n"
            "Flow, 42 turns in about 30 minutes: greeting and production target → oil-check instruction → safety "
            "restriction \"Do not restart Machine 4 until the pressure valve is replaced\" with a spoken understanding "
            "check → lock-out/tag-out → Machine 6 vibration report and load reduction → a second supervisor orders "
            "\"Start Machine 4 now\" and MindBridge raises a conflict alert in both languages → the operator asks "
            "\"Can we restart Machine 4?\" and gets the answer from memory → valve replaced, restriction cleared → "
            "PPE instruction → shift handover read aloud. Part B repeats the key moments in Vietnamese ⇄ Korean.\n\n"
            f"Script: {tree}/docs/demo_scenario.md"),
        "Test conditions": "[TO FILL after recording: actual duration; room and noise (e.g. room with a fan running); "
                           "built-in microphone, distance of each speaker from the laptop]",
        "Actual demo device": (
            f"Apple MacBook Air, {chip}" + (f" ({cores}-core CPU)" if cores else "") + f", {ram_gb} GB unified memory, "
            f"512 GB SSD; {macos}. Built-in microphone and speakers. All inference on the CPU (no GPU/Neural Engine "
            "use). This is team-prepared hardware, as Section 3 of the Brief allows; the team has no physical "
            "Qualcomm board before the on-site rounds."),
        "Current capability & progress": (
            "End to end and offline on the demo laptop: each speaker taps their side (or presses 1 / 2) and talks; "
            "Whisper recognises the speech, the translation appears on screen and is spoken. On top, operational "
            "memory: conflict alerts, understanding checks, questions answered from memory and a spoken shift "
            "handover.\n\n"
            "Qualcomm target: the same app has an RB3 Gen 2 (QCS6490) build that runs Whisper on the Hexagon NPU. On "
            "Qualcomm AI Hub's hosted RB3 Gen 2 devices we profiled both Whisper NPU builds and ran MindBridge's own "
            "decoding loop on the Whisper-small build (exact transcript of an English test clip). The full app has "
            "not yet run on a physical board.\n\n"
            "Changes since Phase 2 (same product and direction): speech recognition moved from SenseVoice (no "
            "Vietnamese) to Whisper large-v3-turbo; translation uses envit5 for English ⇄ Vietnamese and NLLB-200 "
            "1.3B for Korean and Chinese, chosen by measurement; memory extraction is a deterministic rule engine "
            "instead of a small LLM; Korean speech uses Supertonic-3; the badge's e-ink card is shown on screen; the "
            "Phase 3 demo runs on a laptop because the team has no Qualcomm hardware yet. Team unchanged.\n\n"
            "Main limitation: Korean → Vietnamese is our weakest direction "
            f"(BLEU {_fmt(mt('ko-vi', 'bleu') or get(DT, 'ko-vi', 'bleu'))} on the organisers' samples)."),
    }

    # ---------------------------------------------------------------- 3.1 / 3.2 / 3.3 / 3.4
    pkg = f"mindbridge-offline-{VERSION}-macos-arm64.tar.gz"
    package_contents = (
        f"{pkg} unpacks to: install_offline_mac.sh (installer, entry point); python/ (a standalone Python 3.12 for "
        "Apple Silicon, so nothing has to be installed first); wheels/ (every Python dependency, pinned by "
        "requirements-macos-arm64.lock); models/ (Whisper large-v3-turbo, envit5 and NLLB-200 1.3B translators, "
        "Silero VAD, Piper and Supertonic voices, manifest.json with the size and sha256 of every model file and "
        "the licences); app/ (source code, UI, config/, scripts/run.sh launcher, README.md, docs/, bench/ "
        "benchmark tool, tests/, samples/ with four short test recordings).\n\n"
        "The RB3 Gen 2 package (Ubuntu aarch64, Whisper on the NPU) is built from the same repository with "
        "scripts/build_offline_bundle.sh; see docs/hardware.md.")

    impl = (
        "One Python process on the device. Push-to-talk audio is high-pass filtered and trimmed by Silero VAD, which "
        "also ends the turn on silence. Whisper large-v3-turbo transcribes it with the speaker's language forced "
        "from the button pressed; the text goes to the translator for the pair (envit5 for English ⇄ Vietnamese, "
        "NLLB-200 distilled 1.3B for Korean/Chinese, both int8 on CTranslate2), then to Piper/Supertonic speech "
        "synthesis. The English pivot of each turn feeds the rule-based operational memory (SQLite). The UI is "
        "served on 127.0.0.1 only; an offline guard blocks outbound connections from the MindBridge process, and "
        "the benchmark refuses to start while the device has a network route.\n\n"
        "Precision and placement: on the demo MacBook every model runs on the CPU in int8 (Whisper as an int8 "
        "CTranslate2 model). On the Qualcomm RB3 Gen 2, Whisper instead runs as Qualcomm AI Hub's w8a16 QNN context "
        "binaries on the Hexagon NPU through ONNX Runtime's QNN execution provider (CPU fallback disabled), with "
        "Whisper-small int8 on the CPU as a fallback. The configuration file picks the path; the code is the same.\n\n"
        "Development tools, not part of the runtime: Qualcomm AI Hub (download and profiling of the QCS6490 Whisper "
        "builds on hosted devices). The submitted package needs no account, key or network.")

    mac_peak = (MV or {}).get("peak_ram_mb")
    requirements = {
        "Processor / accelerator": (
            f"Apple Silicon Mac (M1 or later): tested on {chip}; older M-series chips estimated (slower). Qualcomm "
            "QCS6490 (RB3 Gen 2) with Hexagon HTP v68: NPU models tested on Qualcomm AI Hub's hosted RB3 Gen 2 "
            "devices; the full app on a physical board is not yet tested."),
        "Memory and storage": (
            f"RAM: {ram_gb} GB tested (peak {_fmt(mac_peak, 0)} MB for the MindBridge process with all three pairs' "
            "models loaded); 8 GB Macs estimated to work. Storage: about 8 GB free for the unpacked package and "
            "installed environment; estimated."),
        "OS and software": (
            f"macOS on Apple Silicon (tested: {macos}). Bundled: Python 3.12 (standalone build), CTranslate2 4.8.3, "
            "sherpa-onnx 1.13.8, numpy 2.5.4, FastAPI 0.159.1, uvicorn 0.54.0; every version pinned in "
            "app/requirements-macos-arm64.lock. No admin rights, Homebrew, Xcode or internet needed. RB3 Gen 2 "
            "build: Ubuntu 24.04 aarch64 + onnxruntime-qnn 2.7.0 (QAIRT 2.51), pinned in requirements-aarch64.lock."),
        "Audio and peripherals": (
            "The Mac's built-in microphone and speakers (tested); a USB headset or speakerphone works too and helps in "
            "noise. Keyboard keys 1 / 2 (or Page Up / Page Down, e.g. a presenter clicker) as push-to-talk."),
    }

    steps = {
        "Prepare:": (
            f"Download {pkg} and {pkg}.sha256 from the link in 3.1 into Downloads on an Apple Silicon Mac. Nothing "
            "else needs downloading or installing."),
        "Install:": (
            f"In Terminal: `cd ~/Downloads && shasum -a 256 -c {pkg}.sha256 && tar -xzf {pkg} && "
            f"cd mindbridge-offline-{VERSION}-macos-arm64 && bash install_offline_mac.sh`. The installer sets up "
            "Python from the bundled files, checks every model against its sha256 sum and runs a self-test."),
        "Disconnect and launch:": (
            "Turn Wi-Fi off (Control Center → Wi-Fi). Run `cd app && bash scripts/run.sh`. The UI opens full screen; "
            "it is ready when the chips at the top read \"Offline: no network\" and \"Speech on CPU\" with the Mac's "
            "chip name. The first time you speak, allow Terminal to use the microphone. Run details (top right) shows "
            "each model, where it runs, sizes, memory and the network state."),
        "Run the scenario:": (
            "Pick the pair in the top bar (Tiếng Việt ⇄ English, ⇄ 한국어 or ⇄ 中文). Each person clicks their own button "
            "(or presses 1 / 2), speaks one or two sentences and stops; recording also ends after about a second of "
            "silence. Each turn appears as a card with the translation in large type under the original in small "
            "type, and the translation is spoken aloud. Follow docs/demo_scenario.md for the 30-minute script."),
        "Reset or troubleshoot:": (
            "Restart: Ctrl+C in the Terminal window, then `bash scripts/run.sh` again; \"Clear\" under Remembered "
            "resets the memory. Nothing recognised: allow Terminal in System Settings → Privacy & Security → "
            "Microphone, then restart. Self-check from app/: `.venv/bin/python -m mindbridge doctor --run`. Logs: "
            "app/data/mindbridge.log. No microphone at all: `.venv/bin/python -m mindbridge file samples/vi_*.wav "
            "--src vi --tgt en`. Full guide: docs/mac.md."),
    }

    # ---------------------------------------------------------------- 4. results
    dev_note = ("Development runs on an x86-64 virtual machine (same models, offline guard on, host network not "
                "disconnected) give: text " + (text_scores(DT) or "–") + ". Voice: " + (voice_scores(DV) or "–") + ".")
    if MT or MV:
        quality = (
            "Metric: sacreBLEU corpus BLEU / chrF++ (13a tokenizer; zh tokenizer for Chinese, characters for Korean) "
            "on the organisers' sample set, measured on the demo MacBook with Wi-Fi off. Speech-recognition error "
            "rates are corpus-level.\n\n"
            "Text in: " + (text_scores(MT) or "[TO FILL]") + ".\n\n"
            "Voice in (organisers' recordings → speech recognition → translation): " + (voice_scores(MV) or "[TO FILL]")
            + ". The 100 EN→VI recordings came without reference texts (the folder holds the VI→EN sheet), so EN→VI "
            "is not scored; their transcripts and translations are in the voice results.jsonl.\n\n")
    else:
        quality = (
            "Metric: sacreBLEU corpus BLEU / chrF++ (13a tokenizer; zh tokenizer for Chinese, characters for Korean) "
            "on the organisers' sample set. [TO FILL: demo-MacBook run with Wi-Fi off, bench/results/published/"
            f"{MAC_TEXT} and {MAC_VOICE}] " + dev_note + "\n\n")
    quality += (
        "Examples: \"Tôi muốn thuê xe đạp khoảng hai tiếng.\" → \"I'd like to rent a bicycle for two hours.\" "
        "Failure: \"Anh cần thêm dây không?\" → \"You need more rope?\" (reference: \"an extra cable\"): \"dây\" is "
        "ambiguous without context.")
    q_ev = (f"{tree}/bench/results/published/: {MAC_TEXT}/, {MAC_VOICE}/ (demo MacBook); onevoice_sample_*/ "
            "(development VM). Each has results.jsonl (every sentence with source, reference, output; recognised text "
            "and per-stage timing for voice), run.log and summary.md.")

    if MV:
        lat_parts = [f"{_arrow(d)} {_fmt(mv(d, 'speech_to_translation_ms_p50'), 0)} ms (speech recognition "
                     f"{_fmt(mv(d, 'asr_ms_p50'), 0)} + translation {_fmt(mv(d, 'mt_ms_p50'), 0)})"
                     for d in ORDER if mv(d, "speech_to_translation_ms_p50") is not None]
        mac_lat = (f"Demo MacBook ({chip}, CPU, Wi-Fi off), median over the organisers' recordings, speech→translation: "
                   + "; ".join(lat_parts) + f". Including speech synthesis, p90 total {_fmt(mv('vi-en', 'total_ms_p90'), 0)}"
                   " ms for VI→EN.")
    else:
        mac_lat = ("Demo MacBook: [TO FILL from bench/results/published/mac_m5_voice: speech→translation p50 per "
                   "direction and total p90].")
    board_lat = ""
    if board:
        board_lat = (f"\n\nPhysical RB3 Gen 2: speech→translation median {_fmt(bd('vi-en', 'speech_to_translation_ms_p50'), 0)}"
                     " ms VI→EN.")
    latency = (
        f"{mac_lat}\n\n"
        f"Qualcomm target (AI Hub profile on a hosted RB3 Gen 2, the exact NPU binaries of our RB3 build): Whisper "
        f"large-v3-turbo encoder {_fmt(enc.get('inference_ms'), 0)} ms per utterance + "
        f"{_fmt(dec.get('inference_ms'), 1)} ms per output token (about 1.8 s for a 20-token sentence); Whisper-small "
        f"{_fmt(small.get('encoder.bin', {}).get('inference_ms'), 0)} ms + "
        f"{_fmt(small.get('decoder.bin', {}).get('inference_ms'), 1)} ms/token.{board_lat}\n\n"
        "Timing points: speech→translation runs from the end of recording (button released or silence detected) to "
        "the translated text being ready; total adds speech synthesis. Per-turn timings are shown on screen.")
    lat_ev = (f"{tree}/bench/results/published/{MAC_VOICE}/ (summary.md, results.jsonl); README.md there for the "
              "AI Hub job links")

    MS = _json("model_sizes_mac.json") or {"models_mb": {}, "loaded_per_configuration_mb": {}}
    RB = _json("model_sizes.json") or {"loaded_per_configuration_mb": {}}
    m = MS["models_mb"]
    cfgs = {k: x["total"] for k, x in MS["loaded_per_configuration_mb"].items()}
    rb = {k: x["total"] for k, x in RB["loaded_per_configuration_mb"].items()}
    size_text = (
        f"Demo MacBook, model files loaded for VI ⇄ EN: {_fmt(cfgs.get('VI ⇄ EN (CPU)'), 0)} MB = Whisper "
        f"large-v3-turbo int8 CTranslate2 {_fmt(m.get('asr/ct2-whisper-large-v3-turbo'), 0)} MB (fp16 on disk, int8 "
        f"in memory) + envit5 {_fmt(m.get('mt/envit5-translation-ct2-int8'), 0)} MB + Piper voices "
        f"{_fmt(m.get('tts/vits-piper-vi_VN-vais1000-medium'), 0)} + {_fmt(m.get('tts/vits-piper-en_US-amy-low'), 0)} MB "
        f"+ Silero VAD {_fmt(m.get('vad/silero_vad.onnx'))} MB. VI ⇄ KO: {_fmt(cfgs.get('VI ⇄ KO (CPU)'), 0)} MB "
        f"(adds NLLB-200 1.3B int8 {_fmt(m.get('mt/nllb-200-distilled-1.3B-ct2-int8'), 0)} MB, and Supertonic-3 "
        f"{_fmt(m.get('tts/sherpa-onnx-supertonic-3-tts-int8-2026-05-11'), 0)} MB in place of the English voice). "
        f"All models in the Mac package: {_fmt(MS.get('all_shipped_models_mb'), 0)} MB.\n\n"
        f"RB3 Gen 2 build (Whisper as w8a16 NPU binaries): {_fmt(rb.get('VI ⇄ EN (NPU)'), 0)} MB for VI ⇄ EN.")
    size_ev = f"{tree}/bench/results/published/model_sizes_mac.json and model_sizes.json (bench/model_sizes.py)"

    if mac_peak:
        mem = (f"Demo MacBook: {_fmt(mac_peak, 0)} MB peak resident memory of the MindBridge process during the voice "
               "benchmark (all three pairs' models loaded; psutil sampler plus the kernel's high-water mark), Wi-Fi off. "
               f"Text-only run: {_fmt((MT or {}).get('peak_ram_mb'), 0)} MB.")
    else:
        mem = "Demo MacBook: [TO FILL: peak_ram_mb from bench/results/published/mac_m5_voice/summary.json]."
    mem += (f"\n\nQualcomm target (AI Hub profile): Whisper turbo needs {_fmt(enc.get('peak_memory_mb'))} MB "
            f"(encoder) and {_fmt(dec.get('peak_memory_mb'))} MB (decoder) of NPU-side memory.")
    mem_ev = f"{MAC_VOICE}/summary.json and {MAC_TEXT}/summary.json → peak_ram_mb; run.log"

    ux = ("[TO FILL after recording: whether the 30-minute scenario completed, actual duration, any repeated turns "
          "or restarts.] Controls: one large push-to-talk button per speaker (keys 1 / 2 or a clicker), automatic "
          "stop on silence, language pair switch, Ask about the line, Shift handover, Clear (memory); safety light and "
          "check questions answered by voice.")
    ux_ev = "[TO FILL: video timestamps]"

    limitations = (
        "Demonstrated on a laptop's CPU, not yet on a physical Qualcomm board: the RB3 Gen 2 NPU path is validated "
        "only on Qualcomm AI Hub's hosted devices. "
        f"Korean → Vietnamese is the weakest direction (BLEU {_fmt(mt('ko-vi', 'bleu') or get(DT, 'ko-vi', 'bleu'))} "
        f"on the samples, against {_fmt(mt('vi-en', 'bleu') or get(DT, 'vi-en', 'bleu'))} for VI→EN). Overlapping "
        "speech is not supported (push-to-talk, one speaker at a time). The memory layer understands common factory "
        "phrasing in English, Vietnamese, Korean and Chinese but not every paraphrase. The wearable badge from "
        "Phase 2 is shown on screen rather than built.")
    next_steps = (
        "1) Run the RB3 Gen 2 build on a physical board (VNG Campus devices or our own) and tune NPU performance mode "
        "and CPU threads; check: speech→translation p50 for VI→EN in the board's benchmark log. 2) Improve Korean ⇄ "
        "Vietnamese with a larger or fine-tuned translator; check: BLEU on the organisers' VK samples. 3) Noise "
        "robustness for the factory floor (close-talk headset, VAD threshold); check: word error rate on recordings "
        "with factory noise.")

    started = (MV or MT or {}).get("started")
    return {
        "summary": summary,
        "video_link": "[TO FILL: YouTube/Drive link, viewable by anyone with the link]",
        "video_duration": "[TO FILL: mm:ss]",
        "video_timestamps": "[TO FILL: network disconnected — mm:ss; first complete voice-to-voice exchange — mm:ss; "
                            "conflict alert — mm:ss; answer from memory — mm:ss; shift handover — mm:ss]",
        "package_url": f"[TO FILL: download URL]; {pkg}; v{VERSION}",
        "package_format": "Packaged source + models: the Python app, all models, every dependency as a wheel, a "
                          "standalone Python and an offline installer, for Apple Silicon Macs.",
        "source_repo": f"{REPO} (branch {BRANCH}, commit {sha})",
        "package_contents": package_contents,
        "implementation_notes": impl,
        "requirements": requirements,
        "steps": steps,
        "test_record": (
            f"{_date(started) if started else '[TO FILL: date of the MacBook run]'}; MindBridge v{VERSION} on the demo "
            f"MacBook (Section 1), Wi-Fi off (the benchmark refuses to run with a network route). Organisers' sample "
            f"set: VI→EN {get(DT, 'vi-en', 'n')} sentences with recordings; VI ⇄ KO {get(DT, 'vi-ko', 'n')} pairs and "
            f"VI ⇄ ZH {get(DT, 'vi-zh', 'n')} pairs, recordings on both sides; EN→VI 100 recordings without texts. "
            "Recordings played from files, no added noise. Qualcomm NPU figures: Qualcomm AI Hub profiles on hosted "
            "RB3 Gen 2 devices (Oct 2026).\n"),
        "evidence_folder": f"{tree}/bench/results/published",
        "results": {
            "Translation quality": (quality, q_ev),
            "Inference / response time": (latency, lat_ev),
            "Model size": (size_text, size_ev),
            "Peak memory": (mem, mem_ev),
            "Device operation & UX": (ux, ux_ev),
        },
        "limitations": limitations,
        "next_steps": next_steps,
    }
