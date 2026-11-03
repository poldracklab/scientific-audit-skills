"""Exercise the real urllib request path with an offline socket transport."""
import io
import ipaddress
import socket
import ssl
import urllib.request
from collections import deque
from types import SimpleNamespace

import pytest

from fetch_common import default_get_bytes, default_post_json


@pytest.fixture
def wire(monkeypatch):
    responses = deque()
    state = SimpleNamespace(dns={}, lookups=[], connections=[], sent=[], tls=[])
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setattr(urllib.request, "_opener", None)

    def resolve(host, port, *args, **kwargs):
        state.lookups.append(host)
        try:
            default = str(ipaddress.ip_address(host))
        except ValueError:
            default = "93.184.216.34"
        ips = state.dns.get(host, [default])
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "",
                 (ip, port, 0, 0) if ":" in ip else (ip, port)) for ip in ips]

    def make_socket(*args, **kwargs):
        return SimpleNamespace(
            connect=lambda address: state.connections.append(address),
            settimeout=lambda timeout: None, setsockopt=lambda *args: None,
            sendall=lambda data: state.sent.append(data), close=lambda: None,
            makefile=lambda *args, **kwargs: io.BytesIO(responses.popleft()),
        )

    def respond(body=b"ok", status="200 OK", headers=""):
        responses.append(f"HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\n{headers}\r\n".encode() + body)

    def wrap(context, sock, server_hostname=None, **kwargs):
        state.tls.append((server_hostname, context.verify_mode, context.check_hostname))
        return sock

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket, "socket", make_socket)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    state.respond = respond
    return state


@pytest.mark.parametrize("url", ["file:///tmp/secret", "ftp://public.test/a", "data:text/plain,secret"])
def test_retrieval_rejects_non_http_schemes(wire, tmp_path, url):
    secret = tmp_path / "secret"
    secret.write_text("private fixture")
    if url.startswith("file:"):
        url = secret.as_uri()
    with pytest.raises(ValueError, match="unsafe|HTTP|scheme"):
        default_get_bytes(url)
    assert wire.connections == []


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1",
                               "172.16.0.1", "0.0.0.0", "100.64.0.1", "224.0.0.1",
                               "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1"])
def test_private_or_special_dns_address_never_connects(wire, ip):
    wire.dns["repository.test"] = [ip]
    wire.respond()
    with pytest.raises(ValueError, match="public|unsafe"):
        default_get_bytes("http://repository.test/data")
    assert wire.connections == []


def test_mixed_public_and_private_dns_is_rejected(wire):
    wire.dns["repository.test"] = ["93.184.216.34", "127.0.0.1"]
    wire.respond()
    with pytest.raises(ValueError, match="public|unsafe"):
        default_get_bytes("http://repository.test/data")
    assert wire.connections == []


@pytest.mark.parametrize("target", ["http://127.0.0.1/private", "http://metadata.test/private",
                                   "file:///tmp/secret"])
def test_redirect_cannot_reach_local_destination(wire, target):
    wire.dns["metadata.test"] = ["169.254.169.254"]
    wire.respond(b"", "302 Found", f"Location: {target}\r\n")
    wire.respond(b"private")
    with pytest.raises((ValueError, urllib.error.HTTPError)):
        default_get_bytes("http://repository.test/data")
    assert [address[0] for address in wire.connections] == ["93.184.216.34"]


def test_public_redirect_preserves_tls_hostname_and_verification(wire):
    wire.respond(b"", "302 Found", "Location: https://cdn.test/file\r\n")
    wire.respond(b"data")
    assert default_get_bytes("https://repository.test/data") == b"data"
    assert wire.tls == [("repository.test", ssl.CERT_REQUIRED, True), ("cdn.test", ssl.CERT_REQUIRED, True)]


def test_connection_uses_validated_address_without_second_resolution(wire, monkeypatch):
    real = socket.getaddrinfo

    def rebinding(host, port, *args, **kwargs):
        if host in wire.lookups:
            wire.dns[host] = ["127.0.0.1"]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", rebinding)
    wire.respond()
    assert default_get_bytes("http://repository.test/data") == b"ok"
    assert wire.lookups == ["repository.test"]
    assert wire.connections == [("93.184.216.34", 80)]


def test_environment_proxy_cannot_bypass_destination_policy(wire, monkeypatch):
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:8123")
    wire.respond()
    assert default_get_bytes("http://repository.test/data") == b"ok"
    assert wire.connections == [("93.184.216.34", 80)]


def test_post_json_uses_same_public_connection_policy(wire):
    wire.dns["repository.test"] = ["10.0.0.1"]
    wire.respond(b"{}")
    with pytest.raises(ValueError, match="public|unsafe"):
        default_post_json("http://repository.test/api", {"query": "x"})
    assert wire.connections == []


def test_crossref_default_transport_rejects_local_file(wire, tmp_path):
    from crossref import default_get_json

    secret = tmp_path / "secret.json"
    secret.write_text('{}')
    with pytest.raises(ValueError, match="unsafe|HTTP|scheme"):
        default_get_json(secret.as_uri())


@pytest.mark.parametrize("url", ["http://user:password@repository.test/data", "http://repository.test:22/data",
                               "http://[fe80::1%25en0]/data"])
def test_ambiguous_or_non_web_urls_are_rejected(wire, url):
    wire.respond()
    with pytest.raises(ValueError, match="unsafe|port|credentials"):
        default_get_bytes(url)
    assert wire.connections == []
