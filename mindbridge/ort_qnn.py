"""Create ONNX Runtime sessions on the Qualcomm Hexagon NPU (QNN HTP backend).

Supports the ``onnxruntime-qnn`` 2.x plugin EP (Linux aarch64 / Windows on ARM)
and the older monolithic QNN EP build. Falls back to CPU only when asked to.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("mindbridge.qnn")

_EP = "QNNExecutionProvider"
_registered = False


def _htp_options(qnn_mod=None) -> dict[str, str]:
    opts = {
        "htp_performance_mode": os.environ.get("MINDBRIDGE_HTP_PERF_MODE", "burst"),
        "htp_graph_finalization_optimization_mode": "3",
    }
    if qnn_mod is not None:
        opts["backend_path"] = qnn_mod.get_qnn_htp_path()
    else:
        opts["backend_path"] = "QnnHtp.dll" if os.name == "nt" else "libQnnHtp.so"
    return opts


def qnn_available() -> tuple[bool, str]:
    """Return (available, reason)."""
    try:
        import onnxruntime as ort
    except ImportError:
        return False, "onnxruntime not installed"
    try:
        import onnxruntime_qnn as qnn  # plugin EP package

        _register(ort, qnn)
        devs = [d for d in ort.get_ep_devices() if d.ep_name == _EP]
        if devs:
            return True, f"onnxruntime-qnn plugin {getattr(qnn, '__version__', '?')} ({len(devs)} device(s))"
        return False, "QNN plugin registered but no NPU device found (is /dev/fastrpc-* accessible?)"
    except ImportError:
        pass
    if _EP in ort.get_available_providers():
        return True, "built-in QNN EP"
    return False, "onnxruntime-qnn not installed"


def _register(ort, qnn) -> None:
    global _registered
    if not _registered:
        try:
            ort.register_execution_provider_library(_EP, qnn.get_library_path())
        except Exception as exc:  # already registered in this process
            log.debug("register_execution_provider_library: %s", exc)
        _registered = True


def make_session(model_path: Path | str, backend: str = "qnn", threads: int = 4):
    """backend: 'qnn' (NPU, no silent CPU fallback) or 'cpu'."""
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.intra_op_num_threads = threads
    if backend == "cpu":
        return ort.InferenceSession(str(model_path), sess_options=so, providers=["CPUExecutionProvider"])

    so.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    try:
        import onnxruntime_qnn as qnn

        _register(ort, qnn)
        devs = [d for d in ort.get_ep_devices() if d.ep_name == _EP]
        if not devs:
            raise RuntimeError("no QNN device")
        so.add_provider_for_devices(devs, _htp_options(qnn))
        return ort.InferenceSession(str(model_path), sess_options=so)
    except ImportError:
        return ort.InferenceSession(
            str(model_path), sess_options=so, providers=[_EP], provider_options=[_htp_options()]
        )
