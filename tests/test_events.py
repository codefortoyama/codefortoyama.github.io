from datetime import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("events", Path(__file__).resolve().parents[1] / "scripts/update_events.py")
events = importlib.util.module_from_spec(spec)
spec.loader.exec_module(events)


def feed(title="AI開発をやってみよう", date="2026/10/15 19:00 ～ 20:30", url="https://codefortoyama.connpass.com/event/409117/?utm_source=feed", paragraph="&lt;p&gt;初めての方向けの体験会。&lt;/p&gt;"):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>{title}</title><link rel="alternate" href="{url}"/>
      <summary type="html">開催日時: {date}&lt;br /&gt;開催場所: オンライン&lt;br /&gt;{paragraph}</summary>
    </entry></feed>'''


class EventTests(unittest.TestCase):
    def test_real_format_and_tracking_removal(self):
        event = events.parse_feed(feed())[0]
        self.assertEqual(event["start"], "2026-10-15T19:00:00+09:00")
        self.assertEqual(event["end"], "2026-10-15T20:30:00+09:00")
        self.assertEqual(event["url"], "https://codefortoyama.connpass.com/event/409117/")
        self.assertEqual(event["place"], "オンライン")
        self.assertEqual(event["description"], "初めての方向けの体験会。")

    def test_malformed_response_does_not_erase_cache(self):
        with self.assertRaises(ValueError):
            events.parse_feed("<html>challenge page</html>")
        with self.assertRaises(ValueError):
            events.parse_feed(feed(date="日時未定"))

    def test_only_group_urls_are_allowed(self):
        with self.assertRaises(ValueError):
            events.parse_feed(feed(url="https://example.com/event/409117/"))

    def test_cross_midnight_and_multiday(self):
        event = events.parse_feed(feed(date="2026/12/31 23:00 ～ 01:00"))[0]
        self.assertEqual(event["end"], "2027-01-01T01:00:00+09:00")
        event = events.parse_feed(feed(date="2026/10/15 19:00 ～ 2026/10/17 20:30"))[0]
        self.assertEqual(event["end"], "2026-10-17T20:30:00+09:00")

    def test_markup_is_escaped(self):
        event = events.parse_feed(feed(title="&lt;img src=x onerror=alert(1)&gt;"))[0]
        data = {"events": [event], "fetched_at": "2026-10-11T12:00:00+09:00"}
        html = events.render_events(data, datetime.fromisoformat("2026-10-11T12:00:00+09:00"))
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_finished_events_move_to_history_at_end_boundary(self):
        data = {"events": events.parse_feed(feed()), "fetched_at": "2026-10-11T12:00:00+09:00"}
        upcoming = events.render_events(data, datetime.fromisoformat("2026-10-15T20:29:59+09:00"))
        self.assertIn('class="event-feature event-feature-connpass"', upcoming)
        finished = events.render_events(data, datetime.fromisoformat("2026-10-15T20:30:00+09:00"))
        self.assertNotIn('class="event-feature event-feature-connpass"', finished)
        self.assertIn("最近開催したイベント", finished)
        self.assertIn("開催予定がありません", finished)

    def test_upcoming_sorted_by_start_not_publication(self):
        first = events.parse_feed(feed())[0]
        later = dict(first, title="Later", start="2026-11-01T19:00:00+09:00", end="2026-11-01T20:30:00+09:00")
        data = {"events": [later, first], "fetched_at": "2026-10-11T12:00:00+09:00"}
        html = events.render_events(data, datetime.fromisoformat("2026-10-11T12:00:00+09:00"))
        self.assertLess(html.index(first["title"]), html.index("Later"))

    def test_images_in_upcoming_and_history_and_unsafe_images_omitted(self):
        event = events.parse_feed(feed())[0]
        event["image_url"] = "https://media.connpass.com/cover.png?a=1&b=2"
        data = {"events": [event], "fetched_at": "2026-10-11T12:00:00+09:00"}
        upcoming = events.render_events(data, datetime.fromisoformat("2026-10-11T12:00:00+09:00"))
        self.assertIn('class="event-eyecatch"', upcoming)
        self.assertIn('src="https://media.connpass.com/cover.png?a=1&amp;b=2"', upcoming)
        history = events.render_events(data, datetime.fromisoformat("2026-10-16T12:00:00+09:00"))
        self.assertIn('class="event-history-image"', history)
        for invalid in [None, "javascript:alert(1)", "https://user:password@example.com/image.png"]:
            event["image_url"] = invalid
            self.assertNotIn('<img', events.render_events(data, datetime.fromisoformat("2026-10-11T12:00:00+09:00")))

    def test_replaces_only_generated_block_and_is_idempotent(self):
        page = "before" + events.START + "old" + events.END + "after"
        result = events.replace_events(page, "new")
        self.assertEqual(result, events.replace_events(result, "new"))
        self.assertTrue(result.startswith("before"))
        self.assertTrue(result.endswith("after"))

    def test_fetch_failure_preserves_cache_and_strict_mode_fails(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "events.json"
            data = {"events": events.parse_feed(feed()), "fetched_at": "2026-10-11T12:00:00+09:00"}
            cache.write_text(json.dumps(data))
            original = cache.read_bytes()
            (root / "index.html").write_text(events.START + events.END)
            with patch.object(events, "ROOT", root), patch.object(events, "CACHE", cache), patch.object(events, "urlopen", side_effect=OSError("offline")):
                with patch("sys.argv", ["update_events.py"]):
                    events.main()
                self.assertEqual(cache.read_bytes(), original)
                self.assertIn("前回取得した情報", (root / "index.html").read_text())
                with patch("sys.argv", ["update_events.py", "--require-fresh"]):
                    with self.assertRaises(OSError):
                        events.main()

    def test_image_failure_keeps_previous_image_and_updates_event(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "events.json"
            event = events.parse_feed(feed())[0]
            event["image_url"] = "https://media.connpass.com/previous.png"
            cache.write_text(json.dumps({"events": [event], "fetched_at": "2026-10-10T12:00:00+09:00"}))
            source = root / "feed.xml"
            source.write_text(feed(title="Updated event"))
            (root / "index.html").write_text(events.START + events.END)
            with patch.object(events, "ROOT", root), patch.object(events, "CACHE", cache), patch.object(events, "fetch_site_image", return_value=None), patch("sys.argv", ["update_events.py", "--require-fresh", "--feed-file", str(source)]):
                events.main()
            updated = json.loads(cache.read_text())["events"][0]
            self.assertEqual(updated["title"], "Updated event")
            self.assertEqual(updated["image_url"], event["image_url"])


if __name__ == "__main__":
    unittest.main()
