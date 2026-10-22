"""Hard guarantee that MindBridge never touches the network at run time.

``install()`` patches the socket layer so any connection to a non-loopback
address raises immediately and is logged. The UI shows the blocked-attempt
count (always 0 in practice) next to the live network snapshot.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading

log = logging.getLogger("mindbridge.offline")

_lock = threading.Lock()
_installed = False
blocked_attempts: list[str] = []


class NetworkBlocked(ConnectionError):
    pass


def _is_local(address) -> bool:
    if isinstance(address, tuple) and address:
        host = address[0]
    else:  # AF_UNIX path etc.
        return True
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a hostname means a DNS lookup → not local


def install() -> None:
    global _installed
    with _lock:
        if _installed:
            return
        orig_connect = socket.socket.connect
        orig_connect_ex = socket.socket.connect_ex
        orig_getaddrinfo = socket.getaddrinfo

        def guard(address):
            if not _is_local(address):
                blocked_attempts.append(str(address))
                log.error("Blocked outbound connection to %s (strict offline mode)", address)
                raise NetworkBlocked(f"MindBridge is offline-only; blocked {address}")

        def connect(self, address):
            if self.family in (socket.AF_INET, socket.AF_INET6):
                guard(address)
            return orig_connect(self, address)

        def connect_ex(self, address):
            if self.family in (socket.AF_INET, socket.AF_INET6):
                guard(address)
            return orig_connect_ex(self, address)

        def getaddrinfo(host, *args, **kwargs):
            if host not in (None, "localhost", "127.0.0.1", "::1", "0.0.0.0"):
                guard((host, 0))
            return orig_getaddrinfo(host, *args, **kwargs)

        socket.socket.connect = connect  # type: ignore[method-assign]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
        socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
        _installed = True
        log.info("Strict offline mode: outbound network disabled for this process")


def is_installed() -> bool:
    return _installed
