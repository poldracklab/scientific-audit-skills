"""HTTP(S) transport confined to public addresses, including every redirect."""
import http.client
import ipaddress
import socket
import urllib.request
from functools import partial
from urllib.parse import urlsplit


def validate_url(url: str):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("unsafe URL: only HTTP(S) sources are supported")
    if parts.username is not None or parts.password is not None:
        raise ValueError("unsafe URL: embedded credentials are not supported")
    if "%" in parts.hostname or any(ord(c) <= 32 for c in url):
        raise ValueError("unsafe URL: invalid host or whitespace")
    if parts.port not in (None, 80, 443):
        raise ValueError("unsafe URL: only web ports 80 and 443 are supported")
    return parts


def public_addresses(host: str, port: int) -> list:
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("unsafe destination: no public address")
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        mapped = getattr(ip, "ipv4_mapped", None)
        if not ip.is_global or ip.is_multicast or (mapped and not mapped.is_global):
            raise ValueError("unsafe destination: every resolved address must be public")
    return addresses


def _connect(address, timeout=60, source_address=None):
    """Connect directly to a validated sockaddr; never resolve the host a second time."""
    error = None
    for family, kind, proto, _, sockaddr in public_addresses(*address):
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            error = exc
            sock.close()
    raise error


def _connection(cls, *args, **kwargs):
    connection = cls(*args, **kwargs)
    # HTTPConnection exposes this hook for connection creation; HTTPS retains normal
    # certificate validation and wraps the pinned socket with the original hostname.
    connection._create_connection = _connect
    return connection


class PublicHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        validate_url(req.full_url)
        return self.do_open(partial(_connection, http.client.HTTPConnection), req)


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        validate_url(req.full_url)
        return self.do_open(partial(_connection, http.client.HTTPSConnection), req, context=self._context)


class PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_bytes(req: urllib.request.Request) -> bytes:
    validate_url(req.full_url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicHTTPHandler(),
                                        PublicHTTPSHandler(), PublicRedirectHandler())
    with opener.open(req, timeout=60) as response:
        return response.read()
