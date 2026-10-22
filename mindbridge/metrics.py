"""Performance evidence: peak memory, model sizes, device and network snapshot."""

from __future__ import annotations

import os
import platform
import resource
import subprocess
import threading
import time
from pathlib import Path

import psutil


class PeakMemory:
    """Samples process RSS in the background; ``peak_mb`` is the high-water mark."""

    def __init__(self, interval_s: float = 0.05):
        self.interval = interval_s
        self.proc = psutil.Process(os.getpid())
        self.peak = 0
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def _run(self):
        while not self._stop.is_set():
            try:
                rss = self.proc.memory_info().rss
                for child in self.proc.children(recursive=True):
                    rss += child.memory_info().rss
                self.peak = max(self.peak, rss)
            except psutil.Error:
                pass
            time.sleep(self.interval)

    def __enter__(self):
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join()

    @property
    def peak_mb(self) -> float:
        # ru_maxrss (KiB on Linux) also catches spikes between samples.
        kernel_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        return max(self.peak, kernel_peak) / 2**20


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 2**20


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def files_size_mb(paths: list[str]) -> float:
    total = 0
    seen: set[str] = set()
    for p in paths:
        rp = os.path.realpath(p)
        if rp in seen or not os.path.isfile(rp):
            continue
        seen.add(rp)
        total += os.path.getsize(rp)
    return total / 2**20


def _cmd(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""


def device_info() -> dict:
    soc = ""
    for p in ("/sys/devices/soc0/machine", "/proc/device-tree/model"):
        try:
            soc = Path(p).read_text().strip("\x00\n ")
            if soc:
                break
        except OSError:
            continue
    return {
        "hostname": platform.node(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "soc": soc,
        "cpu_count": os.cpu_count(),
        "total_ram_mb": round(psutil.virtual_memory().total / 2**20),
    }


def _proc_default_route() -> str:
    """Default route from the kernel tables (works without iproute2)."""
    found = []
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if len(f) > 2 and f[1] == "00000000":
                found.append(f"default via {f[0]} (IPv4)")
    except OSError:
        pass
    try:
        for line in Path("/proc/net/ipv6_route").read_text().splitlines():
            f = line.split()
            if len(f) > 9 and f[0] == "0" * 32 and f[1] == "00" and f[9] != "lo":
                found.append(f"default via {f[9]} (IPv6)")
    except OSError:
        pass
    return "; ".join(found)


def network_snapshot() -> dict:
    """Evidence that the device is offline: interfaces, default route, radios."""
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    ifaces = {}
    for name, st in stats.items():
        if name == "lo":
            continue
        ipv4 = [a.address for a in addrs.get(name, []) if a.family == 2]
        ifaces[name] = {"up": st.isup, "ipv4": ipv4}
    route = _cmd(["ip", "route", "show", "default"]) or _proc_default_route()
    return {
        "interfaces": ifaces,
        "default_route": route or None,
        "rfkill": _cmd(["rfkill", "list"]) or None,
        "nmcli_radio": _cmd(["nmcli", "radio", "all"]) or None,
        "has_default_route": bool(route),
        "any_external_ip": any(i["up"] and i["ipv4"] for i in ifaces.values()),
    }
