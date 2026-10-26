"""Local device server: serves the touchscreen UI on 127.0.0.1 and runs the pipeline.

Nothing here listens on an external interface or calls out: the UI is opened in
a kiosk browser on the RB3 Gen 2's own display.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from mindbridge import __version__, offline_guard
from mindbridge import languages as L
from mindbridge.audio import dsp
from mindbridge.config import AppConfig
from mindbridge.metrics import device_info, network_snapshot, peak_rss_mb, rss_mb
from mindbridge.pipeline import MindBridge, Turn

log = logging.getLogger("mindbridge.server")
UI_DIR = Path(__file__).parent / "ui"

ROLES = {"a": "Supervisor", "b": "Operator"}


class Hub:
    """Owns the pipeline, the mic, a single worker thread and the websocket clients."""

    def __init__(self, cfg: AppConfig, bridge: MindBridge):
        self.cfg = cfg
        self.bridge = bridge
        self.pair = cfg.default_pair
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.turns: dict[str, Turn] = {}
        self.jobs: queue.Queue = queue.Queue()
        self.state = "idle"
        self.listening: dict | None = None
        self.recorder = None
        self.mic_error = ""
        self._mic_lock = threading.Lock()
        self._init_mic()
        threading.Thread(target=self._worker, daemon=True).start()

    # -------------------------------------------------------------- languages
    def sides(self) -> dict[str, str]:
        other, vi = self.pair.split("-")[1], "vi"
        return {"a": other, "b": vi}

    def side_info(self) -> dict:
        s = self.sides()
        return {
            k: {"lang": v, "name": L.get(v).name, "native": L.get(v).native, "role": ROLES[k]}
            for k, v in s.items()
        }

    # -------------------------------------------------------------- mic
    def _init_mic(self):
        try:
            import sounddevice as sd

            from mindbridge.audio.io import Recorder

            sd.query_devices(kind="input")
            self.recorder = Recorder(self.cfg.audio.input_device, self.cfg.audio.max_utterance_s)
        except Exception as exc:  # no PortAudio / no input device
            self.recorder = None
            self.mic_error = str(exc)

    def start_listening(self, side: str, mode: str, memory_id: int | None = None) -> dict:
        if self.recorder is None:
            return {"ok": False, "error": f"No microphone on the device ({self.mic_error}). Using browser mic."}
        with self._mic_lock:
            if self.recorder.active:
                return self._stop_locked()
            endpoint = self.bridge.vad.streaming() if self.bridge.vad is not None else None
            self.listening = {"side": side, "mode": mode, "memory_id": memory_id, "t0": time.time()}
            self.recorder.start(endpoint, self.cfg.audio.vad_endpoint_silence_s, on_auto_stop=self.stop_listening)
        self._set_state("listening", side=side, mode=mode)
        threading.Thread(target=self._level_meter, daemon=True).start()
        return {"ok": True}

    def stop_listening(self) -> dict:
        with self._mic_lock:
            return self._stop_locked()

    def _stop_locked(self) -> dict:
        if self.recorder is None or not self.recorder.active or self.listening is None:
            return {"ok": False}
        audio = self.recorder.stop()
        job, self.listening = self.listening, None
        if self.recorder.last_was_digital_silence:
            self._set_state("idle")
            msg = ("The microphone is blocked: it only returns silence. On a Mac: System Settings → Privacy & "
                   "Security → Microphone → turn on Terminal, then restart MindBridge (Ctrl+C, bash scripts/run.sh).")
            self.emit({"type": "error", "message": msg})
            return {"ok": False, "error": msg}
        self.jobs.put({**job, "audio": audio, "sr": dsp.TARGET_SR, "t_end": time.time()})
        self._set_state("processing", side=job["side"], mode=job["mode"])
        return {"ok": True, "seconds": round(len(audio) / dsp.TARGET_SR, 2)}

    def _level_meter(self):
        while self.recorder is not None and self.recorder.active:
            self.emit({"type": "level", "dbfs": round(self.recorder.level_dbfs, 1)})
            time.sleep(0.1)

    # -------------------------------------------------------------- jobs
    def submit(self, job: dict):
        self.jobs.put(job)
        self._set_state("processing", side=job["side"], mode=job["mode"])

    def _worker(self):
        while True:
            job = self.jobs.get()
            try:
                self._run(job)
            except Exception as exc:  # keep the device alive whatever happens
                log.exception("job failed")
                self.emit({"type": "error", "message": str(exc)})
            finally:
                recording = self.recorder is not None and self.recorder.active
                if self.jobs.empty() and not recording:
                    self._set_state("idle")

    def _run(self, job: dict):
        sides = self.sides()
        side, mode = job["side"], job["mode"]
        lang = sides[side]
        other = sides["b" if side == "a" else "a"]
        audio, sr, text = job.get("audio"), job.get("sr", dsp.TARGET_SR), job.get("text")
        if text is None and (audio is None or len(audio) < sr * 0.25):
            self.emit({"type": "error", "message": "Didn't catch that — tap and speak a little longer."})
            return
        b = self.bridge
        if mode == "ask":
            turn = b.ask(audio, sr, lang, text=text)
        elif mode == "verify":
            turn = b.verify(audio, sr, lang, int(job["memory_id"]), text=text)
        else:
            turn = b.talk(audio, sr, lang, other, ROLES[side], text=text, remember=False)
            self._publish(turn, side)
            if turn.source_text:
                b.remember(turn)
                self.emit({"type": "turn_update", "turn": turn.public(), "side": side})
                self._push_memory()
            return
        self._publish(turn, side)
        self._push_memory()

    def _publish(self, turn: Turn, side: str):
        self.turns[turn.id] = turn
        if len(self.turns) > 200:
            self.turns.pop(next(iter(self.turns)))
        self.emit({"type": "turn", "turn": turn.public(), "side": side, "has_audio": turn.tts_audio is not None})

    def _push_memory(self):
        m = self.bridge.memory
        self.emit({
            "type": "memory",
            "items": [x.to_dict() for x in m.store.all(60)],
            "light": m.safety_light(),
        })

    # -------------------------------------------------------------- events
    def _set_state(self, state: str, **extra):
        self.state = state
        self.emit({"type": "state", "state": state, **extra})

    def emit(self, event: dict):
        if self.loop is None:
            return
        data = json.dumps(event, ensure_ascii=False, default=str)
        for ws in list(self.clients):
            asyncio.run_coroutine_threadsafe(_safe_send(ws, data, self.clients), self.loop)

    def status(self) -> dict:
        b = self.bridge
        return {
            "version": __version__,
            "pair": self.pair,
            "pairs": [f"{a}-{c}" for a, c in L.PAIRS],
            "sides": self.side_info(),
            "state": self.state,
            "mic": {"available": self.recorder is not None, "error": self.mic_error},
            "offline": {
                "strict_guard": offline_guard.is_installed(),
                "blocked_attempts": len(offline_guard.blocked_attempts),
                "network": network_snapshot(),
            },
            "device": device_info(),
            "models": b.inventory(),
            "load_ms": {k: round(v) for k, v in b.load_ms.items()},
            "memory_mb": {"rss": round(rss_mb()), "peak": round(peak_rss_mb())},
            "light": b.memory.safety_light(),
        }


async def _safe_send(ws: WebSocket, data: str, clients: set):
    try:
        await ws.send_text(data)
    except Exception:
        clients.discard(ws)


def create_app(cfg: AppConfig, bridge: MindBridge) -> FastAPI:
    hub = Hub(cfg, bridge)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.loop = asyncio.get_running_loop()
        yield

    app = FastAPI(title="MindBridge", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.hub = hub

    @app.get("/")
    async def index():
        return FileResponse(UI_DIR / "index.html")

    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    @app.get("/api/status")
    async def status():
        return hub.status()

    @app.post("/api/pair")
    async def set_pair(body: dict):
        pair = body.get("pair", "")
        if pair not in [f"{a}-{b}" for a, b in L.PAIRS]:
            return JSONResponse({"ok": False, "error": f"unknown pair {pair}"}, 400)
        hub.pair = pair
        threading.Thread(target=bridge.preload_pair, args=(pair,), daemon=True).start()
        return {"ok": True, "sides": hub.side_info()}

    @app.post("/api/listen/start")
    async def listen_start(body: dict):
        return hub.start_listening(body.get("side", "a"), body.get("mode", "talk"), body.get("memory_id"))

    @app.post("/api/listen/stop")
    async def listen_stop():
        return hub.stop_listening()

    @app.post("/api/upload")
    async def upload(
        file: UploadFile = File(...), side: str = Form("a"), mode: str = Form("talk"), memory_id: str = Form("")
    ):
        audio, sr = dsp.read_wav_bytes(await file.read())
        hub.submit({"side": side, "mode": mode, "memory_id": memory_id or None, "audio": audio, "sr": sr})
        return {"ok": True, "seconds": round(len(audio) / sr, 2)}

    @app.post("/api/text")
    async def text(body: dict):
        hub.submit({
            "side": body.get("side", "a"), "mode": body.get("mode", "talk"),
            "memory_id": body.get("memory_id"), "text": body.get("text", ""),
        })
        return {"ok": True}

    @app.get("/api/audio/{turn_id}.wav")
    async def audio(turn_id: str):
        t = hub.turns.get(turn_id)
        if t is None or t.tts_audio is None:
            return Response(status_code=404)
        return Response(dsp.wav_bytes(t.tts_audio, t.tts_sample_rate), media_type="audio/wav")

    @app.post("/api/say")
    async def say(body: dict):
        """Speak arbitrary text (verification question, alerts) in a language."""
        text, lang = body.get("text", ""), body.get("lang", "vi")
        out = await asyncio.to_thread(bridge.speak, text, lang)
        if out is None:
            return Response(status_code=204)
        return Response(dsp.wav_bytes(out.audio, out.sample_rate), media_type="audio/wav")

    @app.get("/api/memory")
    async def memory():
        m = bridge.memory
        return {"items": [x.to_dict() for x in m.store.all(200)], "light": m.safety_light()}

    @app.post("/api/memory/clear")
    async def memory_clear():
        bridge.memory.store.clear()
        hub._push_memory()
        return {"ok": True}

    @app.get("/api/handover")
    async def handover(lang: str = "vi"):
        return await asyncio.to_thread(bridge.handover, lang)

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        hub.clients.add(socket)
        await socket.send_text(json.dumps({"type": "hello", "status": hub.status()}, default=str, ensure_ascii=False))
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            hub.clients.discard(socket)

    return app


def warmup(bridge: MindBridge):
    """Run each model once so the first real utterance is not slowed by lazy init."""
    t = time.perf_counter()
    silence = np.zeros(dsp.TARGET_SR, dtype=np.float32)
    try:
        bridge.asr.transcribe(dsp.pad_tail(silence), "en", ["en"])
        a, b = bridge.cfg.default_pair.split("-")
        bridge.translate("Hello.", "en", b if b != "en" else a)
    except Exception as exc:  # pragma: no cover
        log.warning("warm-up failed: %s", exc)
    bridge.load_ms["warmup"] = (time.perf_counter() - t) * 1e3
