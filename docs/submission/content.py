"""Text of MindBridge's Prototype Submission (filled into the organisers' template by build_submission.py).

Numbers come from the published result files. `board` is the summary.json of a voice benchmark run
made on the team's own RB3 Gen 2; until it exists, board-only values stay as [TO FILL …].
Keep answers short: the template asks for concise answers that link to existing material.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PUB = ROOT / "bench" / "results" / "published"
REPO = "https://github.com/PaarthSonkiya/MindBridge"
BRANCH = "phase3-prototype"
VERSION = "0.4.0"


def _json(rel: str):
    p = PUB / rel
    return json.loads(p.read_text()) if p.exists() else None


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "[TO FILL: commit]"


def _fmt(v, nd=1, unit=""):
    return "[TO FILL]" if v is None else f"{v:,.{nd}f}{unit}"


def fields(board: dict | None) -> dict:
    sha = _git_sha()
    tree = f"{REPO}/tree/{BRANCH}"
    T = _json("onevoice_sample_text/summary.json") or {"directions": {}}
    V = _json("onevoice_sample_voice/summary.json") or {"directions": {}}
    turbo = {r["model"]: r for r in (_json("aihub_whisper_turbo_qcs6490/summary.json") or [])}
    small = {r["model"]: r for r in (_json("aihub_whisper_small_qcs6490/summary.json") or [])}
    enc, dec = turbo.get("encoder.bin", {}), turbo.get("decoder.bin", {})

    def t(d, k):
        return T["directions"].get(d, {}).get(k)

    def v(d, k):
        return V["directions"].get(d, {}).get(k)

    def bd(d, k):
        return (board or {}).get("directions", {}).get(d, {}).get(k)

    # ---------------------------------------------------------------- board-dependent values
    if board:
        b_lat = (f"End-to-end on our RB3 Gen 2 (voice benchmark, organisers' recordings): speech→translation median "
                 f"{_fmt(bd('vi-en', 'speech_to_translation_ms_p50'), 0)} ms VI→EN, "
                 f"{_fmt(bd('ko-vi', 'speech_to_translation_ms_p50'), 0)} ms KO→VI; including speech synthesis, p90 "
                 f"{_fmt(bd('vi-en', 'total_ms_p90'), 0)} ms VI→EN.")
        b_mem = f"{_fmt(board.get('peak_ram_mb'), 0)} MB peak process RAM (psutil RSS sampler) during that run."
        b_dev = "board voice run: bench/results/published/rb3gen2_voice/"
    else:
        b_lat = ("End-to-end on our own RB3 Gen 2: [TO FILL from `bench/run_benchmark.py --mode voice` on the board: "
                 "speech→translation p50 and total p90 per direction].")
        b_mem = "On the RB3 Gen 2: [TO FILL: peak RAM from the board voice run]."
        b_dev = "[TO FILL: board run folder]"

    summary = {
        "Team / individual participant": "MindBridge",
        "Project name": "MindBridge: offline voice translation with operational memory for multilingual factory floors",
        "Submitted build": f"MindBridge v{VERSION}, git commit {sha} on branch {BRANCH}, "
                           f"{REPO}. [TO FILL: release tag and date of the build shown in the video]",
        "Demo language(s)": "Vietnamese ⇄ English, both directions (registered pair). Vietnamese ⇄ Korean, both "
                            "directions (scenario Part B). Vietnamese ⇄ Chinese can be selected on screen but is not "
                            "part of the recorded demo.",
        "Test scenario": (
            "A day shift at a Korean-owned electronics plant near Ho Chi Minh City. Roles: a Supervisor (English in "
            "Part A, Korean in Part B), a Vietnamese line Operator and a Technician, sharing one MindBridge unit.\n\n"
            "Flow, 35 turns in about 30 minutes: greeting and production target → oil-check instruction → safety "
            "restriction \"Do not restart Machine 4 until the pressure valve is replaced\" with a spoken understanding "
            "check → lock-out/tag-out → Machine 6 vibration report and load reduction → a second supervisor orders "
            "\"Start Machine 4 now\" and MindBridge raises a conflict alert in both languages → the operator asks "
            "\"Can we restart Machine 4?\" and gets the answer from memory → valve replaced, restriction cleared → "
            "PPE instruction → shift handover read aloud. Part B repeats the key moments in Vietnamese ⇄ Korean.\n\n"
            f"Script: {tree}/docs/demo_scenario.md"),
        "Test conditions": "[TO FILL after recording: actual duration; room and noise (e.g. office with factory noise "
                           "played from a speaker at about … dB); microphone type and distance to each speaker]",
        "Actual demo device": "Qualcomm RB3 Gen 2 Core Kit: QCS6490 SoC (8-core Kryo 670 CPU, Adreno 643 GPU, Hexagon "
                              "NPU with HTP v68), 6 GB LPDDR5 RAM, 128 GB UFS; Ubuntu 24.04 LTS for Qualcomm IoT. "
                              "[TO FILL: microphone and speaker models; display]",
        "Current capability & progress": (
            "Works end to end and offline: each speaker taps their side (or presses 1 / 2) and talks; Whisper "
            "recognises the speech on the Hexagon NPU, the translation appears on screen and is spoken. On top, "
            "operational memory: conflict alerts, understanding checks, questions answered from memory and a "
            "spoken shift handover.\n\n"
            "Changes since Phase 2 (same product and direction): speech recognition moved from SenseVoice (no "
            "Vietnamese) to Whisper large-v3-turbo compiled by Qualcomm AI Hub for QCS6490; translation uses envit5 "
            "for English ⇄ Vietnamese and NLLB-200 1.3B for Korean and Chinese, chosen by measurement; memory "
            "extraction is a deterministic rule engine instead of a small LLM; Korean speech uses Supertonic-3; the "
            "badge's e-ink card is shown on screen. Team unchanged.\n\n"
            "Main limitation: translation runs on the CPU, and Korean → Vietnamese is our weakest direction "
            f"(BLEU {_fmt(t('ko-vi', 'bleu'))} on the organisers' samples)."),
    }

    # ---------------------------------------------------------------- 3.1 / 3.2 / 3.3 / 3.4
    pkg = f"mindbridge-offline-{VERSION}-aarch64.tar.gz"
    package_contents = (
        f"{pkg} unpacks to: install_offline.sh (installer, entry point); app/ (source code, UI, config/, "
        "scripts/run.sh launcher, docker/Dockerfile, README.md, docs/, bench/ benchmark tool, tests/); wheels/ "
        "(every Python dependency for aarch64 / Python 3.12, including onnxruntime-qnn with the HTP v68 libraries, "
        "plus pip itself); models/ (Whisper large-v3-turbo and small w8a16 QNN context binaries for QCS6490, "
        "Whisper-small CPU fallback, envit5 and NLLB-200 1.3B translators, Silero VAD, Piper and Supertonic voices, "
        "manifest.json with sha256 of every file); app/samples/ (four short test recordings for "
        "`python -m mindbridge file`, no microphone needed).")

    impl = (
        "One Python process on the board. Push-to-talk audio is high-pass filtered and trimmed by Silero VAD, which "
        "also ends the turn on silence. Whisper large-v3-turbo (Qualcomm AI Hub w8a16 build: 8-bit weights, 16-bit "
        "activations) runs as QNN context binaries on the Hexagon NPU through ONNX Runtime's QNN execution provider, "
        "with CPU fallback disabled so nothing silently leaves the NPU; MindBridge drives the decoder token by token "
        "with the speaker's language forced from the button pressed. The text goes to the translator for the pair "
        "(envit5 int8 for English ⇄ Vietnamese, NLLB-200 1.3B int8 for Korean/Chinese, both on CTranslate2 on the "
        "Kryo CPU), then to Piper/Supertonic speech synthesis. The English pivot of each turn feeds the rule-based "
        "operational memory (SQLite). The UI is served on 127.0.0.1 only; an offline guard blocks every non-loopback "
        "connection at run time and the benchmark logs the network state before and after each run.\n\n"
        "Fallback: if the NPU or QNN runtime is unavailable, speech recognition switches to Whisper-small int8 on "
        "the CPU and the screen says so. Qualcomm AI Hub was used only during development (to download the QCS6490 "
        "Whisper builds and profile them on hosted RB3 Gen 2 devices); the submitted runtime needs no account, key "
        "or network.")

    requirements = {
        "Processor / accelerator": (
            "Qualcomm QCS6490 (RB3 Gen 2) with Hexagon HTP v68 for NPU speech recognition: NPU models tested on "
            "hosted RB3 Gen 2 devices (Qualcomm AI Hub) [TO FILL: and on our own board]. Without the NPU, any 64-bit "
            "CPU with 4+ cores runs everything on the CPU: tested on x86-64; other aarch64 boards estimated."),
        "Memory and storage": (
            f"RAM: 6 GB (the RB3 Gen 2's). {b_mem} CPU-only run on x86-64 for comparison: "
            f"{_fmt(V.get('peak_ram_mb'), 0)} MB peak, tested.\n\n"
            "Storage: about 8 GB free for the unpacked package, Python environment and models; estimated."),
        "OS and software": (
            "Ubuntu 24.04 LTS aarch64 (Qualcomm IoT image) with Python 3.12 and the FastRPC/CDSP driver "
            "(libcdsprpc.so, part of the image). Bundled: onnxruntime 1.31.0 + onnxruntime-qnn 2.7.0 (QAIRT 2.51, "
            "HTP v68 libraries included), CTranslate2 4.8.3, sherpa-onnx 1.13.8, numpy 2.5.4, FastAPI 0.159.1, "
            "uvicorn 0.54.0; every version pinned in app/requirements-aarch64.lock. No GPU driver or internet "
            "needed."),
        "Audio and peripherals": (
            "USB microphone, USB headset or USB speakerphone (or the kit's onboard mic); speaker or headphones (USB, "
            "3.5 mm or HDMI audio); HDMI display, touch optional; USB keyboard or presenter clicker as push-to-talk "
            "(keys 1 / 2 or Page Up / Page Down)."),
    }

    steps = {
        "Prepare:": (
            f"On a connected computer download {pkg} and its .sha256 from the link in 3.1 (≈ [TO FILL] GB) and copy "
            "both to the board's home folder (USB drive or scp). Nothing else needs downloading."),
        "Install:": (
            f"`sha256sum -c {pkg}.sha256 && tar -xzf {pkg} && cd mindbridge-offline-{VERSION}-aarch64 && "
            "bash install_offline.sh`. The installer builds a Python environment from the bundled wheels, checks "
            "every model's sha256 and runs a self-test (`doctor`) that reports whether the NPU is usable."),
        "Disconnect and launch:": (
            "Turn off Wi-Fi and unplug Ethernet (`nmcli radio wifi off`). Run `cd app && bash scripts/run.sh`. "
            "The UI opens full screen; it is ready when the chips at the top read \"Speech on NPU\" and \"Offline: no "
            "network\". Run details (top right) shows each model, where it runs, sizes and memory."),
        "Run the scenario:": (
            "Pick the pair in the top bar (Tiếng Việt ⇄ English, ⇄ 한국어 or ⇄ 中文). Each person taps their own button (or "
            "presses 1 / 2), speaks one or two sentences and stops; recording also ends after 0.9 s of silence. "
            "The translation appears in large type on the listener's side and is spoken aloud; the original stays "
            "small on the speaker's side. Follow docs/demo_scenario.md for the 30-minute script."),
        "Reset or troubleshoot:": (
            "Restart: close the window and run scripts/run.sh again; \"Clear\" under Remembered resets the memory. "
            "No sound in or out: `python -m mindbridge doctor` lists the audio devices; set "
            "MINDBRIDGE_AUDIO_INPUT_DEVICE / MINDBRIDGE_AUDIO_OUTPUT_DEVICE to the right one (if no microphone works, "
            "the UI records through the browser instead). \"Speech on CPU\" means the NPU runtime did not load; the "
            "reason is shown in Run details. Logs: app/data/mindbridge.log. No microphone at all: "
            "`python -m mindbridge file samples/*.wav --src vi --tgt en`."),
    }

    # ---------------------------------------------------------------- 4. results
    n_ve, n_vk = t("vi-en", "n"), t("vi-ko", "n")
    quality = (
        "Metric: sacreBLEU corpus BLEU (13a tokenizer; character tokens for Korean) and chrF++, on the organisers' "
        "sample set. Same models and settings as the device, run offline on an x86-64 CPU (accuracy does not depend "
        "on the processor).\n\n"
        f"Text in: VI→EN BLEU {_fmt(t('vi-en', 'bleu'))} / chrF++ {_fmt(t('vi-en', 'chrf++'))} (n={n_ve}); "
        f"VI→KO {_fmt(t('vi-ko', 'bleu'))} / {_fmt(t('vi-ko', 'chrf++'))} (n={n_vk}); "
        f"KO→VI {_fmt(t('ko-vi', 'bleu'))} / {_fmt(t('ko-vi', 'chrf++'))} (n={t('ko-vi', 'n')}).\n\n"
        f"Voice in (organisers' recordings → speech recognition → translation): VI→EN BLEU {_fmt(v('vi-en', 'bleu'))}, "
        f"Vietnamese word error rate {_fmt(v('vi-en', 'asr_wer'), 1, '%')} (n={v('vi-en', 'n')}); "
        f"KO→VI BLEU {_fmt(v('ko-vi', 'bleu'))}, Korean character error rate {_fmt(v('ko-vi', 'asr_cer'), 1, '%')} "
        f"(n={v('ko-vi', 'n')}); VI→KO BLEU {_fmt(v('vi-ko', 'bleu'))} (n={v('vi-ko', 'n')}). The 100 EN→VI "
        "recordings came without reference texts (the folder holds the VI→EN sheet), so EN→VI is not scored.\n\n"
        "Examples: \"Tôi muốn thuê xe đạp khoảng hai tiếng.\" → \"I'd like to rent a bicycle for two hours.\" "
        "Failure: \"Anh cần thêm dây không?\" → \"You need more rope?\" (reference: \"an extra cable\"): \"dây\" is "
        "ambiguous without context.")
    q_ev = (f"{tree}/bench/results/published/onevoice_sample_text/ and onevoice_sample_voice/ (results.jsonl: every "
            "sentence with source, reference, output and timing; run.log)")

    latency = (
        f"Speech recognition on the RB3 Gen 2 NPU (Qualcomm AI Hub profile on a hosted RB3 Gen 2, the exact binaries "
        f"we ship): encoder {_fmt(enc.get('inference_ms'), 0)} ms per utterance + {_fmt(dec.get('inference_ms'), 1)} ms "
        f"per output token, so about 1.8 s for a 20-token sentence; Whisper-small (fast mode) "
        f"{_fmt(small.get('encoder.bin', {}).get('inference_ms'), 0)} ms + "
        f"{_fmt(small.get('decoder.bin', {}).get('inference_ms'), 1)} ms/token.\n\n"
        f"{b_lat}\n\n"
        "Timing points: speech→translation runs from the end of recording (button released or silence detected) to "
        "the translated text being ready; total adds speech synthesis. Per-turn timings are shown on screen.")
    lat_ev = f"{tree}/bench/results/published/README.md (AI Hub job links); {b_dev}"

    MS = _json("model_sizes.json") or {"models_mb": {}, "loaded_per_configuration_mb": {}}
    m = MS["models_mb"]
    cfgs = {k: x["total"] for k, x in MS["loaded_per_configuration_mb"].items()}
    size_text = (
        f"Model files loaded for the VI ⇄ EN demo: {_fmt(cfgs.get('VI ⇄ EN demo (NPU)'), 0)} MB = Whisper "
        f"large-v3-turbo w8a16 QNN binaries {_fmt(m.get('asr/whisper-large-v3-turbo-quantized-qcs6490'), 0)} MB + "
        f"envit5 int8 {_fmt(m.get('mt/envit5-translation-ct2-int8'), 0)} MB + Piper voices "
        f"{_fmt(m.get('tts/vits-piper-vi_VN-vais1000-medium'), 0)} + {_fmt(m.get('tts/vits-piper-en_US-amy-low'), 0)} MB "
        f"+ Silero VAD {_fmt(m.get('vad/silero_vad.onnx'))} MB. VI ⇄ KO: {_fmt(cfgs.get('VI ⇄ KO demo (NPU)'), 0)} MB "
        f"(adds NLLB-200 1.3B int8 {_fmt(m.get('mt/nllb-200-distilled-1.3B-ct2-int8'), 0)} MB and Supertonic-3 "
        f"{_fmt(m.get('tts/sherpa-onnx-supertonic-3-tts-int8-2026-05-11'), 0)} MB).\n\n"
        f"All models in the package, including the Whisper-small CPU fallback and fast-mode NPU build: "
        f"{_fmt(MS.get('all_shipped_models_mb'), 0)} MB. Installed size including the Python environment: "
        "[TO FILL from the board: du -sh of the installed folder].")
    size_ev = f"{tree}/bench/results/published/model_sizes.json (bench/model_sizes.py); models/manifest.json in the package"

    mem = (f"{b_mem}\n\nFor reference, CPU-only run of the whole pipeline on x86-64 (Whisper turbo on the CPU instead "
           f"of the NPU): {_fmt(V.get('peak_ram_mb'), 0)} MB peak RSS. NPU memory for Whisper turbo per AI Hub "
           f"profile: {_fmt(enc.get('peak_memory_mb'))} MB encoder, {_fmt(dec.get('peak_memory_mb'))} MB decoder.")
    mem_ev = "summary.json → peak_ram_mb in each benchmark folder; run.log"

    ux = ("[TO FILL after recording: whether the 30-minute scenario completed, actual duration, any repeated turns "
          "or restarts.] Controls: one large push-to-talk button per speaker (keys 1 / 2 or a clicker), automatic "
          "stop on silence, language pair switch, Ask about the line, Shift handover, Clear memory; safety light and "
          "check questions answered by voice.")
    ux_ev = "[TO FILL: video timestamps]"

    limitations = (
        "Korean → Vietnamese is the weakest direction (BLEU about 20 on the samples); the NLLB translator still runs "
        "on the CPU, so long sentences in VI ⇄ KO/ZH take longer than VI ⇄ EN. Recognition of overlapping speech is "
        "not supported (push-to-talk, one speaker at a time). The memory layer understands common factory phrasing "
        "in English, Vietnamese, Korean and Chinese but not every paraphrase. The wearable badge from Phase 2 is "
        "shown on screen rather than built. [TO FILL: differences between the demonstrated and packaged build, "
        "if any]")
    next_steps = (
        "1) Run the full benchmark on our RB3 Gen 2 and tune NPU performance mode and CPU threads; check: speech→"
        "translation p50 below 2.5 s for VI→EN in the board log. 2) Improve Korean ⇄ Vietnamese with a larger or "
        "fine-tuned translator; check: BLEU on the organisers' VK samples and a held-out factory phrase list. "
        "3) Noise robustness for the factory floor (close-talk headset, VAD threshold); check: word error rate on "
        "our recordings with factory noise at 70 dB.")

    return {
        "summary": summary,
        "video_link": "[TO FILL: YouTube/Drive link, viewable by anyone with the link]",
        "video_duration": "[TO FILL: mm:ss]",
        "video_timestamps": "[TO FILL: network disconnected — mm:ss; first complete voice-to-voice exchange — mm:ss; "
                            "conflict alert — mm:ss; answer from memory — mm:ss; shift handover — mm:ss]",
        "package_url": f"[TO FILL: download URL]; {pkg}; v{VERSION}",
        "package_format": "Packaged source + models (Python app, all models, dependency wheels and an offline "
                          "installer); Dockerfile included as an alternative.",
        "source_repo": f"{REPO} (branch {BRANCH}, commit {sha})",
        "package_contents": package_contents,
        "implementation_notes": impl,
        "requirements": requirements,
        "steps": steps,
        "test_record": (
            "[TO FILL: date of the board run]. Accuracy: organisers' sample set (VI→EN 100 sentences with "
            f"recordings; VI ⇄ KO {n_vk} sentence pairs with recordings on both sides), MindBridge v{VERSION}, run "
            "offline on x86-64 (CPU) with the same models; on-device NPU timing: Qualcomm AI Hub profiles on hosted "
            "RB3 Gen 2 (Oct 2026); end-to-end timing and memory: [TO FILL: our RB3 Gen 2 run]. Recordings played "
            "from files, no added noise.\n"),
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
