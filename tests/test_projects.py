from datetime import datetime
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("projects", Path(__file__).resolve().parents[1] / "scripts/update_projects.py")
projects = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projects)


def repo(name, **kwargs):
    return {"name": name, "owner": {"login": "codefortoyama"}, "private": False, "default_branch": "main", **kwargs}


def project(name, date="2026-10-10T00:00:00+00:00", **kwargs):
    return {"name": name, "url": "https://github.com/codefortoyama/" + name, "last_commit": date, "description": "説明", "archived": False, "fork": False, **kwargs}


class ProjectTests(unittest.TestCase):
    def test_reviewed_descriptions_survive_refreshed_github_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/project_descriptions.json").write_text(json.dumps({
                "projects": {"example": {"description": "調査した説明文 <地図>", "sources": []}}
            }))
            item = project("example", description="", pages_url="https://codefortoyama.github.io/example/")
            data = {"projects": [item], "fetched_at": "2026-10-11T09:00:00+09:00"}
            with patch.object(projects, "ROOT", root):
                for html in [projects.render_list(data), projects.render_featured(data)]:
                    self.assertIn("調査した説明文 &lt;地図&gt;", html)
                    self.assertIn('href="https://codefortoyama.github.io/example/"', html)
                    self.assertIn('href="https://github.com/codefortoyama/example"', html)
            self.assertEqual(item["description"], "")

    def test_pagination_and_commit_dates_override_push_order(self):
        calls = []
        def api(url):
            calls.append(url)
            if url.endswith("page=2"):
                return [repo("newer", pushed_at="2020-01-01T00:00:00Z"), repo("secret", private=True)], ""
            if "/orgs/" in url:
                return [repo("older", pushed_at="2026-10-11T00:00:00Z")], '<https://api.github.com/orgs/codefortoyama/repos?page=2>; rel="next"'
            date = "2026-10-10T00:00:00Z" if "/newer/" in url else "2026-10-01T00:00:00Z"
            return [{"commit": {"committer": {"date": date}}}], ""
        result = projects.collect_projects(api)
        self.assertEqual([item["name"] for item in result], ["newer", "older"])
        self.assertEqual(len(calls), 4)

    def test_empty_repo_is_excluded_from_collection_and_both_pages(self):
        def api(url):
            if "/orgs/" in url:
                return [repo("empty")], ""
            raise HTTPError(url, 409, "Empty repository", None, None)
        data = {"projects": projects.collect_projects(api), "fetched_at": "2026-10-11T09:00:00+09:00"}
        self.assertEqual(data["projects"], [])
        data["projects"] = [project("empty", date=None)]
        self.assertNotIn("empty", projects.render_list(data))
        self.assertIn("公開リポジトリ 0件", projects.render_list(data))
        self.assertNotIn('class="project-card"', projects.render_featured(data))

    def test_api_failure_is_not_treated_as_empty_repo(self):
        def api(url):
            if "/orgs/" in url:
                return [repo("example")], ""
            raise HTTPError(url, 403, "Rate limit", None, None)
        with self.assertRaises(HTTPError):
            projects.collect_projects(api)

    def test_featured_exactly_three_and_full_list_keeps_all(self):
        data = {"projects": [project(str(n), f"2026-10-0{n}T00:00:00+00:00") for n in range(1, 6)], "fetched_at": "2026-10-11T09:00:00+09:00"}
        class Links(HTMLParser):
            def __init__(self):
                super().__init__(); self.links = []
            def handle_starttag(self, tag, attrs):
                if tag == "a": self.links.append(dict(attrs)["href"])
        parser = Links(); parser.feed(projects.render_featured(data))
        self.assertEqual([url.rsplit("/", 1)[1] for url in parser.links], ["5", "4", "3"])
        parser = Links(); parser.feed(projects.render_list(data))
        self.assertEqual(len(parser.links), 5)

    def test_timezone_aware_order_and_display(self):
        older = project("older", "2026-10-11T08:00:00+09:00")
        newer = project("newer", "2026-10-11T00:00:00+00:00")
        self.assertEqual(projects.sort_projects([older, newer])[0]["name"], "newer")
        self.assertIn("2026/10/11", projects.commit_label(newer))

    def test_pages_api_url_takes_priority_over_homepage(self):
        def api(url):
            if "/orgs/" in url:
                return [repo("example", has_pages=True, homepage="https://unrelated.example/")], ""
            if url.endswith("/pages"):
                return {"html_url": "https://project.example/", "public": True}, ""
            return [{"commit": {"committer": {"date": "2026-10-10T00:00:00Z"}}}], ""
        item = projects.collect_projects(api, fetch_image=lambda url: "https://project.example/cover.png")[0]
        self.assertEqual(item["pages_url"], "https://project.example/")
        self.assertEqual(item["image_url"], "https://project.example/cover.png")
        data = {"projects": [item], "fetched_at": "2026-10-11T09:00:00+09:00"}
        for html in [projects.render_list(data), projects.render_featured(data)]:
            self.assertIn('href="https://project.example/"', html)
            self.assertIn('href="https://github.com/codefortoyama/example"', html)
            self.assertIn("公開サイトを見る", html)

    def test_pages_not_found_falls_back_and_permission_error_does_not(self):
        def api(url):
            if "/orgs/" in url:
                return [repo("example", has_pages=True)], ""
            if url.endswith("/pages"):
                raise HTTPError(url, 404, "No Pages site", None, None)
            return [{"commit": {"committer": {"date": "2026-10-10T00:00:00Z"}}}], ""
        item = projects.collect_projects(api, lambda url: None)[0]
        self.assertIsNone(item["pages_url"])
        self.assertEqual(projects.project_destination(item)[0], item["url"])
        def forbidden(url):
            if "/orgs/" in url:
                return [repo("example", has_pages=True)], ""
            raise HTTPError(url, 403, "Rate limit", None, None)
        with self.assertRaises(HTTPError):
            projects.collect_projects(forbidden)

    def test_public_pages_fallback_verifies_url_and_follows_custom_domain(self):
        def missing_api(url):
            raise HTTPError(url, 404, "Pages metadata unavailable", None, None)
        urls = []
        def verify(url):
            urls.append(url)
            return "https://actual-project.example/"
        item = repo("example", has_pages=True, homepage="https://upstream.example/")
        self.assertEqual(projects.resolve_pages_url(item, missing_api, verify), "https://actual-project.example/")
        self.assertEqual(urls, ["https://codefortoyama.github.io/example/"])
        self.assertIsNone(projects.resolve_pages_url(item, missing_api, lambda url: None))

    def test_project_subdirectory_and_user_site_urls(self):
        def missing_api(url):
            raise HTTPError(url, 404, "Pages metadata unavailable", None, None)
        urls = []
        def verify(url):
            urls.append(url)
            return url
        self.assertEqual(projects.resolve_pages_url(repo("example", has_pages=True, homepage="https://codefortoyama.github.io/example/v1/"), missing_api, verify), "https://codefortoyama.github.io/example/v1/")
        self.assertEqual(projects.resolve_pages_url(repo("codefortoyama.github.io", has_pages=True), missing_api, verify), "https://codefortoyama.github.io/")

    def test_unreachable_site_is_not_linked(self):
        with patch.object(projects, "urlopen", side_effect=URLError("DNS lookup failed")):
            self.assertIsNone(projects.check_published_site("https://codefortoyama.github.io/example/"))

    def test_site_image_metadata_priority_relative_paths_and_safe_urls(self):
        base = "https://codefortoyama.github.io/example/"
        self.assertEqual(projects.parse_site_image('<meta name="twitter:image" content="twitter.png"><meta content="images/cover.png?a=1&amp;b=2" property="og:image">', base), base + "images/cover.png?a=1&b=2")
        self.assertEqual(projects.parse_site_image('<meta property="og:image" content="javascript:bad"><meta name="twitter:image" content="/cover.png">', base), "https://codefortoyama.github.io/cover.png")
        self.assertIsNone(projects.parse_site_image('<meta property="og:image" content="data:image/png;base64,abc">', base))
        with patch.object(projects, "urlopen", side_effect=URLError("offline")):
            self.assertIsNone(projects.fetch_site_image(base))

    def test_eyecatch_only_for_public_site_and_fallback_when_missing(self):
        data = {"projects": [project("with-image", pages_url="https://codefortoyama.github.io/", image_url="https://codefortoyama.github.io/cover.png"), project("no-image", pages_url="https://example.com/"), project("repository-only", image_url="https://example.com/ignore.png")], "fetched_at": "2026-10-11T09:00:00+09:00"}
        html = projects.render_featured(data)
        self.assertEqual(html.count('class="project-eyecatch"'), 2)
        self.assertIn('src="https://codefortoyama.github.io/cover.png"', html)
        self.assertIn('src="assets/project-placeholder.svg"', html)
        self.assertNotIn("ignore.png", html)

    def test_broken_metadata_image_uses_verified_hero_image(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.read.return_value = b'<meta property="og:image" content="missing.png"><img class="hero-photo" src="img/main.jpg"><img src="icon.png">'
        response.headers.get_content_charset.return_value = "utf-8"
        response.geturl.return_value = "https://codefortoyama.github.io/project/"
        response.__enter__.return_value = response
        with patch.object(projects, "urlopen", return_value=response), patch.object(projects, "check_published_site", side_effect=[None, "https://codefortoyama.github.io/project/img/main.jpg"]) as verify:
            self.assertEqual(projects.fetch_site_image("https://codefortoyama.github.io/project/"), "https://codefortoyama.github.io/project/img/main.jpg")
            self.assertEqual(verify.call_count, 2)

    def test_unreviewed_page_is_not_fetched_and_cached_image_uses_placeholder(self):
        for url in ["http://127.0.0.1/", "https://unreviewed.example/", "http://toyama.5374.jp/"]:
            with self.subTest(url=url), patch.object(projects, "urlopen") as fetch:
                self.assertIsNone(projects.fetch_site_image(url))
                self.assertIsNone(projects.check_published_site(url))
                fetch.assert_not_called()
        data = {"projects": [project("example", pages_url="https://project.example/", image_url="https://unreviewed.example/cover.png")], "fetched_at": "2026-10-11T09:00:00+09:00"}
        html = projects.render_featured(data)
        self.assertIn('href="https://project.example/"', html)
        self.assertIn('src="assets/project-placeholder.svg"', html)
        self.assertNotIn("unreviewed.example", html)

    def test_unreviewed_metadata_image_skipped_for_local_hero(self):
        html = '<meta property="og:image" content="https://unreviewed.example/cover.png"><img class="hero" src="cover.png">'
        self.assertEqual(projects.parse_site_images(html, "https://codefortoyama.github.io/project/"), ["https://codefortoyama.github.io/project/cover.png"])

    def test_unsafe_site_url_falls_back(self):
        for url in ["javascript:alert(1)", "//example.com", "https://user:password@example.com/", "http://toyama.5374.jp/"]:
            item = project("example", pages_url=url)
            self.assertEqual(projects.project_destination(item)[0], item["url"])
        self.assertEqual(projects.safe_site_url("https://codefortoyama.github.io/example/"), "https://codefortoyama.github.io/example/")

    def test_published_site_links_are_separate_from_source_links(self):
        class Anchors(HTMLParser):
            def __init__(self):
                super().__init__(); self.depth = 0; self.nested = False; self.links = []
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.nested |= self.depth > 0
                    self.depth += 1
                    self.links.append(dict(attrs)["href"])
            def handle_endtag(self, tag):
                if tag == "a": self.depth -= 1
        data = {"projects": [project("example", pages_url="https://codefortoyama.github.io/example/")], "fetched_at": "2026-10-11T09:00:00+09:00"}
        for html in [projects.render_list(data), projects.render_featured(data)]:
            parser = Anchors(); parser.feed(html)
            self.assertFalse(parser.nested)
            self.assertEqual(parser.depth, 0)
            self.assertEqual(parser.links, ["https://codefortoyama.github.io/example/", "https://github.com/codefortoyama/example"])

    def test_escaped_metadata_and_archive_fork_labels(self):
        data = {"projects": [project("example", description='<script>alert("x")</script>', archived=True, fork=True)], "fetched_at": "2026-10-11T09:00:00+09:00"}
        for html in [projects.render_list(data), projects.render_featured(data)]:
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
        self.assertIn("アーカイブ", projects.render_list(data))
        self.assertIn("フォーク", projects.render_list(data))

    def test_network_failure_keeps_data_and_strict_publish_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "projects.json"
            data = {"projects": [project("example")], "fetched_at": "2026-10-11T09:00:00+09:00"}
            cache.write_text(json.dumps(data))
            original = cache.read_bytes()
            (root / "index.html").write_text("<!-- GITHUB_FEATURED_START --><!-- GITHUB_FEATURED_END -->")
            (root / "projects.html").write_text("<!-- GITHUB_REPOSITORIES_START --><!-- GITHUB_REPOSITORIES_END -->")
            with patch.object(projects, "ROOT", root), patch.object(projects, "CACHE", cache), patch.object(projects, "collect_projects", side_effect=OSError("offline")):
                with patch("sys.argv", ["update_projects.py"]): projects.main()
                self.assertEqual(cache.read_bytes(), original)
                self.assertIn("前回取得した情報", (root / "projects.html").read_text())
                with patch("sys.argv", ["update_projects.py", "--require-fresh"]):
                    with self.assertRaises(OSError): projects.main()

    def test_build_keeps_fresh_event_html_and_adds_sitemap_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "_site"; output.mkdir()
            (root / "projects.html").write_text("<!-- GITHUB_REPOSITORIES_START --><!-- GITHUB_REPOSITORIES_END -->")
            (output / "index.html").write_text("fresh events<!-- GITHUB_FEATURED_START --><!-- GITHUB_FEATURED_END -->")
            (output / "sitemap.xml").write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://codefortoyama.github.io/</loc></url></urlset>')
            cache = root / "projects.json"
            cache.write_text(json.dumps({"projects": [project("example")], "fetched_at": "2026-10-11T09:00:00+09:00"}))
            with patch.object(projects, "ROOT", root), patch.object(projects, "CACHE", cache), patch("sys.argv", ["update_projects.py", "--offline", "--output", str(output)]):
                projects.main()
            self.assertTrue((output / "index.html").read_text().startswith("fresh events"))
            self.assertIn("projects.html", (output / "sitemap.xml").read_text())
            self.assertIn("example", (output / "projects.html").read_text())


if __name__ == "__main__":
    unittest.main()
