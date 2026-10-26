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

IS_MAC = platform.system() == "Darwin"


def _ru_maxrss_bytes() -> int:
    """Kernel high-water mark of this process: ru_maxrss is in bytes on macOS, KiB on Linux."""
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return v if IS_MAC else v * 1024


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
        # The kernel's high-water mark also catches spikes between samples.
        return max(self.peak, _ru_maxrss_bytes()) / 2**20


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 2**20


def peak_rss_mb() -> float:
    return _ru_maxrss_bytes() / 2**20


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
    model = ""
    if IS_MAC:
        soc = _cmd(["sysctl", "-n", "machdep.cpu.brand_string"])  # e.g. "Apple M5"
        model = _cmd(["sysctl", "-n", "hw.model"])  # e.g. "Mac16,12"
    for p in ("/sys/devices/soc0/machine", "/proc/device-tree/model"):
        if soc:
            break
        try:
            soc = Path(p).read_text().strip("\x00\n ")
        except OSError:
            continue
    return {
        "hostname": platform.node(),
        "model": model,
        "os": f"macOS {platform.mac_ver()[0]}" if IS_MAC else platform.platform(),
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


def parse_darwin_route(out_v4: str, out_v6: str = "") -> str:
    """Default route from macOS `route -n get default` output ("not in table" when offline)."""
    found = []
    for out, fam in ((out_v4, "IPv4"), (out_v6, "IPv6")):
        fields = dict(
            (k.strip(), v.strip()) for k, _, v in (line.partition(":") for line in out.splitlines()) if v
        )
        iface = fields.get("interface", "")
        if not iface or iface.startswith("lo"):
            continue
        # macOS keeps IPv6 link-local defaults on system tunnels (utunN) even with Wi-Fi off; they lead nowhere.
        # An IPv4 default via utun is a VPN, i.e. real connectivity.
        if fam == "IPv6" and iface.startswith("utun"):
            continue
        found.append(f"default via {iface} gateway {fields.get('gateway', '?')} ({fam})")
    return "; ".join(found)


def _darwin_wifi_power() -> str:
    """'Wi-Fi Power (en0): Off' — what the System Settings / Control Center switch did."""
    ports = _cmd(["networksetup", "-listallhardwareports"]).splitlines()
    for i, line in enumerate(ports):
        if line.strip() in ("Hardware Port: Wi-Fi", "Hardware Port: AirPort") and i + 1 < len(ports):
            dev = ports[i + 1].split(":", 1)[-1].strip()
            return _cmd(["networksetup", "-getairportpower", dev])
    return ""


def network_snapshot() -> dict:
    """Evidence that the device is offline: interfaces, default route, radios."""
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    ifaces = {}
    for name, st in stats.items():
        if name.startswith("lo"):
            continue
        ipv4 = [a.address for a in addrs.get(name, []) if a.family == 2 and not a.address.startswith("169.254.")]
        ifaces[name] = {"up": st.isup, "ipv4": ipv4}
    if IS_MAC:
        route = parse_darwin_route(_cmd(["route", "-n", "get", "default"]),
                                   _cmd(["route", "-n", "get", "-inet6", "default"]))
        radios = {"wifi_power": _darwin_wifi_power() or None}
    else:
        route = _cmd(["ip", "route", "show", "default"]) or _proc_default_route()
        radios = {"rfkill": _cmd(["rfkill", "list"]) or None, "nmcli_radio": _cmd(["nmcli", "radio", "all"]) or None}
    return {
        "interfaces": ifaces,
        "default_route": route or None,
        **radios,
        "has_default_route": bool(route),
        "any_external_ip": any(i["up"] and i["ipv4"] for i in ifaces.values()),
    }
