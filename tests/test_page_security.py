"""Keep HTML security policies intact across pages and generated builds."""

from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


class PageSecurityTests(unittest.TestCase):
    def test_security_policy_precedes_all_resource_loading_on_each_page(self):
        policies = []
        for name in ("index.html", "projects.html", "privacy.html"):
            with self.subTest(page=name):
                page = Page((ROOT / name).read_text(encoding="utf-8"))
                index, meta = next((i, attrs) for i, (tag, attrs) in enumerate(page.tags)
                                   if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy")
                self.assertTrue(all(tag not in {"script", "link", "img", "iframe"}
                                    for tag, _ in page.tags[:index]))
                policies.append(meta["content"])
                directives = dict((parts[0], parts[1:]) for directive in meta["content"].split(";")
                                  if (parts := directive.split()))
                for directive in ("default-src", "base-uri", "object-src", "form-action"):
                    self.assertEqual(directives[directive], ["'none'"])
                self.assertNotIn("'unsafe-inline'", meta["content"])
                self.assertNotIn("'unsafe-eval'", meta["content"])
                self.assertNotIn("frame-ancestors", directives)  # Ineffective in a meta policy.
                self.assertTrue(any(tag == "meta" and attrs.get("name") == "referrer"
                                    and attrs.get("content") == "strict-origin-when-cross-origin"
                                    for tag, attrs in page.tags))
        self.assertEqual(len(set(policies)), 1)

    def test_no_inline_scripts_handlers_or_http_resource_urls(self):
        for name in ("index.html", "projects.html", "privacy.html"):
            with self.subTest(page=name):
                page = Page((ROOT / name).read_text(encoding="utf-8"))
                for tag, attrs in page.tags:
                    if tag == "script":
                        self.assertTrue(attrs.get("src"))
                    self.assertFalse(any(key.startswith("on") for key in attrs))
                    for key in ("href", "src"):
                        self.assertFalse(attrs.get(key, "").startswith("http://"))


if __name__ == "__main__":
    unittest.main()
