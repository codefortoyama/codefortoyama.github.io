"""HTTPS fetches restricted to reviewed hosts and pinned public DNS addresses."""

from http.client import HTTPSConnection
from ipaddress import ip_address
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

API_HOSTS = frozenset({"api.github.com"})
FEED_HOSTS = frozenset({"codefortoyama.connpass.com"})
PAGE_HOSTS = frozenset({"codefortoyama.github.io", "codefortoyama.connpass.com"})
IMAGE_HOSTS = PAGE_HOSTS | {"media.connpass.com"}
MAX_REDIRECTS = 5


def validate_url(url, allowed_hosts):
    """Check URL syntax without doing DNS or sending a request."""
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Invalid fetch URL")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in allowed_hosts
            or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443)
            or parts.netloc.lower() not in {parts.hostname, f"{parts.hostname}:443"}):
        raise ValueError("Fetch URL must use a reviewed HTTPS host on port 443")
    return url


def public_addresses(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise URLError("No DNS addresses")
    for family, _, _, _, address in addresses:
        ip = ip_address(address[0])
        # Reject mapped and transition addresses as well as local/reserved ranges.
        if (family not in (socket.AF_INET, socket.AF_INET6) or not ip.is_global
                or ip.is_multicast
                or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo))):
            raise ValueError("DNS returned a non-public address")
    return addresses


class PublicHTTPSConnection(HTTPSConnection):
    def connect(self):
        if self._tunnel_host or self.port != 443:
            raise ValueError("Proxy tunnels and non-standard ports are disabled")
        addresses = public_addresses(self.host, self.port)
        last_error = None
        for family, kind, protocol, _, address in addresses:
            sock = socket.socket(family, kind, protocol)
            try:
                sock.settimeout(self.timeout)
                # Use the validated sockaddr; never resolve the hostname again.
                sock.connect(address)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as error:
                sock.close()
                last_error = error
            except Exception:
                sock.close()
                raise
        raise last_error


class PublicHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(PublicHTTPSConnection, request, context=self._context)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def secure_urlopen(request, *, timeout=20, allowed_hosts):
    """Validate each redirect before connecting, with no environment proxies."""
    if isinstance(request, str):
        validate_url(request, allowed_hosts)
        request = Request(request)
    validate_url(request.full_url, allowed_hosts)
    method = request.get_method()
    if method not in {"GET", "HEAD"} or request.data is not None:
        raise ValueError("Only bodyless GET and HEAD fetches are supported")
    headers = dict(request.header_items())
    # Authentication belongs only to the API, never to pages or images.
    if any(key.lower() == "authorization" for key in headers) and allowed_hosts != API_HOSTS:
        raise ValueError("Authorization is restricted to GitHub API requests")
    opener = build_opener(ProxyHandler({}), NoRedirects(), PublicHTTPSHandler())
    url = request.full_url
    for redirects in range(MAX_REDIRECTS + 1):
        validate_url(url, allowed_hosts)
        current = Request(url, headers=headers, method=method)
        try:
            return opener.open(current, timeout=timeout)
        except HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                raise
            try:
                location = error.headers.get("Location")
                if not location or redirects == MAX_REDIRECTS:
                    raise ValueError("Missing redirect destination or too many redirects")
                if any(ord(c) <= 32 or ord(c) == 127 for c in location) or "\\" in location:
                    raise ValueError("Invalid redirect destination")
                url = urljoin(url, location)
                validate_url(url, allowed_hosts)
            finally:
                error.close()
