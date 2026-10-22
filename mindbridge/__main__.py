"""MindBridge command line.

    python -m mindbridge serve        # device UI on http://127.0.0.1:8765
    python -m mindbridge talk         # terminal push-to-talk (no screen needed)
    python -m mindbridge doctor       # check models, NPU, audio, network
    python -m mindbridge translate "Do not restart Machine 4" --src en --tgt vi
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from mindbridge import __version__, offline_guard
from mindbridge.config import load_config


def _setup_logging(verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_serve(args, cfg):
    import uvicorn

    from mindbridge.pipeline import MindBridge
    from mindbridge.server import create_app, warmup

    if cfg.strict_offline:
        offline_guard.install()
    print(f"MindBridge {__version__}: loading models…", flush=True)
    t = time.perf_counter()
    bridge = MindBridge(cfg)
    warmup(bridge)
    print(f"Ready in {time.perf_counter() - t:.1f}s. ASR: {bridge.asr.name}. Open http://{cfg.host}:{cfg.port}", flush=True)
    app = create_app(cfg, bridge)
    uvicorn.run(app, host=cfg.host, port=args.port or cfg.port, log_level="warning")


def cmd_talk(args, cfg):
    """Terminal mode: Enter to start, Enter to stop (or stop on silence)."""
    from mindbridge.audio.io import Player, Recorder
    from mindbridge.pipeline import MindBridge

    if cfg.strict_offline:
        offline_guard.install()
    a, b = (args.pair or cfg.default_pair).split("-")
    sides = {"1": (b, a, "Supervisor"), "2": (a, b, "Operator")}  # (speaker, listener, role)
    bridge = MindBridge(cfg)
    rec, player = Recorder(cfg.audio.input_device, cfg.audio.max_utterance_s), Player(cfg.audio.output_device)
    print(f"Pair {a}-{b}. Press 1 + Enter for {sides['1'][0]} speaker, 2 + Enter for {sides['2'][0]}, q to quit.")
    while True:
        k = input("> ").strip().lower()
        if k == "q":
            break
        if k not in sides:
            continue
        spk, lst, role = sides[k]
        endpoint = bridge.vad.streaming() if bridge.vad else None
        done = {"flag": False}
        rec.start(endpoint, cfg.audio.vad_endpoint_silence_s, on_auto_stop=lambda d=done: d.update(flag=True))
        print("  listening… (stops on silence, or press Enter)")
        import select

        while not done["flag"]:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                sys.stdin.readline()
                break
        audio = rec.stop()
        turn = bridge.talk(audio, 16000, spk, lst, role)
        print(f"  [{spk}] {turn.source_text}\n  [{lst}] {turn.translation}")
        print("  " + ", ".join(f"{k} {v:.0f} ms" for k, v in turn.timings_ms.items() if "." not in k))
        for al in turn.alerts:
            print(f"  ! {al['level'].upper()}: {al['text_en']}")
        if turn.verification:
            print(f"  ? {turn.verification['question']}")
        if turn.tts_audio is not None:
            player.play(turn.tts_audio, turn.tts_sample_rate, block=True)


def cmd_file(args, cfg):
    """Run recorded files through the full pipeline (no microphone needed): transcript, translation, timings."""
    import soundfile as sf

    from mindbridge.metrics import network_snapshot, peak_rss_mb
    from mindbridge.pipeline import MindBridge

    if cfg.strict_offline:
        offline_guard.install()
    bridge = MindBridge(cfg, load_memory=False)
    bridge.preload_pair(f"{args.src}-{args.tgt}")
    print(f"ASR: {bridge.asr.name} | MT: {bridge.mt.name} | network default route: "
          f"{network_snapshot()['has_default_route']}")
    for path in args.wav:
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        turn = bridge.talk(audio, sr, args.src, args.tgt, "file", remember=False)
        print(f"\n{path} ({turn.audio_seconds:.1f} s)\n  [{turn.speaker_lang}] {turn.source_text}\n"
              f"  [{args.tgt}] {turn.translation}")
        print("  " + ", ".join(f"{k} {v:.0f} ms" for k, v in turn.timings_ms.items() if "." not in k))
        if args.play and turn.tts_audio is not None:
            from mindbridge.audio.io import Player

            Player(cfg.audio.output_device).play(turn.tts_audio, turn.tts_sample_rate, block=True)
    print(f"\npeak RAM {peak_rss_mb():.0f} MB")


def cmd_translate(args, cfg):
    from mindbridge.config import REPO_ROOT
    from mindbridge.mt import MtRouter

    if cfg.strict_offline:
        offline_guard.install()
    mt = MtRouter(cfg.models_path, cfg.mt, phrasebook=REPO_ROOT / "config" / "phrasebook.json")
    if args.file:  # one sentence per line in, one translation per line out
        src_lines = Path(args.file).read_text(encoding="utf-8-sig").splitlines()
        out = sys.stdout
        if args.output:
            out = open(args.output, "w", encoding="utf-8")  # noqa: SIM115
        t0 = time.perf_counter()
        for line in src_lines:
            out.write((mt.translate(line, args.src, args.tgt).text if line.strip() else "") + "\n")
        if args.output:
            out.close()
        print(f"{len(src_lines)} lines in {time.perf_counter() - t0:.1f} s", file=sys.stderr)
        return
    r = mt.translate(args.text, args.src, args.tgt)
    print(r.text)
    print(f"({r.timings_ms['mt']:.0f} ms)", file=sys.stderr)


def cmd_doctor(args, cfg):
    """Check everything a judge needs, without loading the UI."""
    from mindbridge.metrics import device_info, network_snapshot
    from mindbridge.ort_qnn import qnn_available

    ok = True
    report: dict = {"version": __version__, "device": device_info(), "network": network_snapshot()}
    mp = cfg.models_path
    checks = {
        "vad": mp / "vad" / "silero_vad.onnx",
        "asr_npu": mp / cfg.asr.qnn_model_dir,
        "asr_cpu": mp / cfg.asr.cpu_model_dir,
        "mt": mp / cfg.mt.model_dir,
    }
    if cfg.mt.en_vi_model_dir:
        checks["mt_en_vi"] = mp / cfg.mt.en_vi_model_dir
    from mindbridge import languages as L

    for lang in L.LANGUAGES.values():
        checks[f"tts_{lang.code}"] = mp / "tts" / lang.tts_voice
    report["models"] = {k: p.exists() for k, p in checks.items()}
    report["qnn"] = dict(zip(("available", "detail"), qnn_available(), strict=True))
    try:
        from mindbridge.audio.io import list_devices

        report["audio_devices"] = list_devices()
    except Exception as exc:  # noqa: BLE001
        report["audio_devices"] = str(exc)
    if args.run:
        from mindbridge.pipeline import MindBridge

        offline_guard.install()
        bridge = MindBridge(cfg)
        a, b = cfg.default_pair.split("-")
        out = bridge.talk(None, 16000, b, a, "Supervisor", text="Do not restart machine 4 until the pressure valve is replaced.")
        report["smoke_test"] = {"translation": out.translation, "timings_ms": out.timings_ms, "asr": bridge.asr.name}
    for k in ("mt", "asr_cpu", "vad"):
        ok &= report["models"][k]
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print("\nOK" if ok else "\nMISSING MODELS — run scripts/fetch_models.py (online) or install the offline bundle.")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="mindbridge", description="Offline on-device voice translation + operational memory")
    p.add_argument("--config", help="path to mindbridge.toml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the device UI")
    s.add_argument("--port", type=int, default=0)
    t = sub.add_parser("talk", help="terminal push-to-talk")
    t.add_argument("--pair", default="")
    f = sub.add_parser("file", help="translate recorded .wav files end to end (no microphone needed)")
    f.add_argument("wav", nargs="+")
    f.add_argument("--src", default="en")
    f.add_argument("--tgt", default="vi")
    f.add_argument("--play", action="store_true", help="also play the spoken translation")
    tr = sub.add_parser("translate", help="translate a line of text, or a file with one sentence per line")
    tr.add_argument("text", nargs="?", default="")
    tr.add_argument("--file", help="input text file, one sentence per line")
    tr.add_argument("--output", help="write translations here (default: stdout)")
    tr.add_argument("--src", default="en")
    tr.add_argument("--tgt", default="vi")
    d = sub.add_parser("doctor", help="check models, NPU, audio and network")
    d.add_argument("--run", action="store_true", help="also load the pipeline and translate one sentence")
    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    cfg = load_config(args.config)
    if args.cmd == "serve":  # keep a log next to the memory database for troubleshooting
        fh = logging.FileHandler(cfg.data_path / "mindbridge.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(fh)
    cmds = {"serve": cmd_serve, "talk": cmd_talk, "file": cmd_file, "translate": cmd_translate, "doctor": cmd_doctor}
    return cmds[args.cmd](args, cfg)


if __name__ == "__main__":
    sys.exit(main() or 0)
