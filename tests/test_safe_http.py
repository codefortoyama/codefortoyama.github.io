from email.message import Message
from io import BytesIO
import socket
import ssl
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, Request
from urllib.response import addinfourl

from scripts import safe_http


HOST = "codefortoyama.github.io"
URL = f"https://{HOST}/"


def address(ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sockaddr = (ip, 443, 0, 0) if family == socket.AF_INET6 else (ip, 443)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


class SafeHTTPTests(unittest.TestCase):
    def test_rejected_urls_never_open_connection(self):
        urls = [
            "http://codefortoyama.github.io/", "https://127.0.0.1/",
            "https://169.254.169.254/", "https://10.0.0.1/", "https://[::1]/",
            "https://localhost/", "https://unreviewed.example/",
            "https://codefortoyama.github.io.evil.example/",
            "https://evil-codefortoyama.github.io/", "https://codefortoyama.github.io./",
            "https://user:password@codefortoyama.github.io/",
            "https://@codefortoyama.github.io/", "https://codefortoyama.github.io:8080/",
            "https://codefortoyama.github.io:/", "https://codefortoyama.github.io:bad/",
            "https://codefortoyama.github.io/\n", "https://codefortoyama.github.io\\@evil.example/",
            "file:///etc/passwd", "//codefortoyama.github.io/", None,
        ]
        for url in urls:
            with self.subTest(url=url), patch.object(safe_http, "build_opener") as opener:
                with self.assertRaises((ValueError, AttributeError)):
                    safe_http.secure_urlopen(url, allowed_hosts=safe_http.PAGE_HOSTS)
                opener.assert_not_called()

    def test_public_dns_checks_all_answers_before_any_socket(self):
        ips = ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254",
               "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "::", "fe80::1", "fc00::1",
               "ff02::1", "::ffff:127.0.0.1", "2002:7f00:1::"]
        for ip in ips:
            for addresses in [[address(ip)], [address("185.199.108.153"), address(ip)]]:
                with self.subTest(ip=ip, mixed=len(addresses) > 1):
                    connection = safe_http.PublicHTTPSConnection(HOST, timeout=10)
                    with patch.object(safe_http.socket, "getaddrinfo", return_value=addresses), patch.object(safe_http.socket, "socket") as create_socket:
                        with self.assertRaises(ValueError):
                            connection.connect()
                        create_socket.assert_not_called()

    def test_pinned_sockaddr_and_original_tls_hostname(self):
        for ip in ["185.199.108.153", "2606:50c0:8000::153"]:
            connection = safe_http.PublicHTTPSConnection(HOST, timeout=10)
            context = MagicMock()
            connection._context = context
            sock = MagicMock()
            record = address(ip)
            with patch.object(safe_http.socket, "getaddrinfo", return_value=[record]) as dns, patch.object(safe_http.socket, "socket", return_value=sock):
                connection.connect()
            dns.assert_called_once_with(HOST, 443, type=socket.SOCK_STREAM)
            sock.connect.assert_called_once_with(record[4])
            context.wrap_socket.assert_called_once_with(sock, server_hostname=HOST)
            self.assertIs(connection.sock, context.wrap_socket.return_value)

    def test_default_context_verifies_certificate_and_tls_failure_closes_socket(self):
        connection = safe_http.PublicHTTPSConnection(HOST, timeout=10)
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)
        connection._context = MagicMock()
        connection._context.wrap_socket.side_effect = ssl.SSLCertVerificationError("invalid certificate")
        sock = MagicMock()
        with patch.object(safe_http.socket, "getaddrinfo", return_value=[address("185.199.108.153")]), patch.object(safe_http.socket, "socket", return_value=sock):
            with self.assertRaises(ssl.SSLCertVerificationError):
                connection.connect()
        sock.close.assert_called_once()

    def fake_handler(self, responses, calls):
        class FakeHTTPSHandler(HTTPSHandler):
            def https_open(self, request):
                calls.append(request)
                code, location = responses[len(calls) - 1]
                headers = Message()
                if location is not None:
                    headers["Location"] = location
                response = addinfourl(BytesIO(b"ok"), headers, request.full_url, code)
                response.msg = "test response"
                return response
        return FakeHTTPSHandler

    def test_redirect_to_internal_unreviewed_or_http_destination_is_not_followed(self):
        for location in ["https://127.0.0.1/", "https://169.254.169.254/", "https://unreviewed.example/", "http://codefortoyama.github.io/", "https://codefortoyama.github.io:8080/"]:
            calls = []
            handler = self.fake_handler([(302, location)], calls)
            with self.subTest(location=location), patch.object(safe_http, "PublicHTTPSHandler", handler):
                with self.assertRaises(ValueError):
                    safe_http.secure_urlopen(URL, allowed_hosts=safe_http.PAGE_HOSTS)
            self.assertEqual(len(calls), 1)

    def test_allowed_relative_redirect_preserves_head_and_ignores_environment_proxy(self):
        calls = []
        handler = self.fake_handler([(302, "/cover.png"), (200, None)], calls)
        with patch.object(safe_http, "PublicHTTPSHandler", handler), patch.dict("os.environ", {"HTTPS_PROXY": "http://127.0.0.1:8080"}):
            with safe_http.secure_urlopen(Request(URL, method="HEAD"), allowed_hosts=safe_http.PAGE_HOSTS) as response:
                self.assertEqual(response.status, 200)
        self.assertEqual([r.full_url for r in calls], [URL, URL + "cover.png"])
        self.assertEqual([r.get_method() for r in calls], ["HEAD", "HEAD"])

    def test_redirect_limit(self):
        calls = []
        handler = self.fake_handler([(302, "/loop")] * 6, calls)
        with patch.object(safe_http, "PublicHTTPSHandler", handler):
            with self.assertRaises(ValueError):
                safe_http.secure_urlopen(URL, allowed_hosts=safe_http.PAGE_HOSTS)
        self.assertEqual(len(calls), 6)

    def test_api_token_cannot_follow_redirect_to_other_host(self):
        calls = []
        handler = self.fake_handler([(302, URL)], calls)
        request = Request("https://api.github.com/repos/codefortoyama/example", headers={"Authorization": "Bearer test-token"})
        with patch.object(safe_http, "PublicHTTPSHandler", handler):
            with self.assertRaises(ValueError):
                safe_http.secure_urlopen(request, allowed_hosts=safe_http.API_HOSTS)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(ValueError):
            safe_http.secure_urlopen(Request(URL, headers={"Authorization": "Bearer test-token"}), allowed_hosts=safe_http.PAGE_HOSTS)

    def test_http_error_preserved_for_head_fallback(self):
        calls = []
        handler = self.fake_handler([(405, None)], calls)
        with patch.object(safe_http, "PublicHTTPSHandler", handler):
            with self.assertRaises(HTTPError) as error:
                safe_http.secure_urlopen(URL, allowed_hosts=safe_http.PAGE_HOSTS)
            self.assertEqual(error.exception.code, 405)
            error.exception.close()


if __name__ == "__main__":
    unittest.main()
