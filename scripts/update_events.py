"""Import the public connpass Atom feed and render static, escaped event HTML."""

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

try:
    from update_projects import fetch_site_image, safe_site_url
except ModuleNotFoundError:
    from scripts.update_projects import fetch_site_image, safe_site_url

ROOT = Path(__file__).resolve().parent.parent
FEED_URL = "https://codefortoyama.connpass.com/ja.atom"
CACHE = ROOT / "data/events.json"
JST = timezone(timedelta(hours=9))
START = "<!-- CONNPASS_EVENTS_START -->"
END = "<!-- CONNPASS_EVENTS_END -->"
NS = {"a": "http://www.w3.org/2005/Atom"}


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "h1", "h2", "td", "tr", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "h1", "h2", "td", "tr", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(html):
    parser = Text()
    parser.feed(html)
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def parse_feed(xml):
    root = ET.fromstring(xml)
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise ValueError("Response is not an Atom feed")
    events = []
    for entry in root.findall("a:entry", NS):
        link = entry.find("a:link[@rel='alternate']", NS)
        if link is None:
            continue
        url = urlsplit(link.get("href", ""))
        if url.scheme != "https" or url.netloc != "codefortoyama.connpass.com":
            raise ValueError("Unexpected event host")
        if not re.fullmatch(r"/event/\d+/", url.path):
            continue
        summary = plain_text(entry.findtext("a:summary", "", NS))
        schedule = re.search(r"開催日時:\s*(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s*[～〜]\s*(?:(\d{4}/\d{2}/\d{2})\s+)?(\d{2}:\d{2})", summary)
        if not schedule:
            raise ValueError("Event schedule could not be parsed")
        date, begin, end_date, end = schedule.groups()
        started_at = datetime.strptime(date + " " + begin, "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        ended_at = datetime.strptime((end_date or date) + " " + end, "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        if ended_at < started_at and not end_date:
            ended_at += timedelta(days=1)
        if ended_at < started_at:
            raise ValueError("Event ends before it starts")
        place = re.search(r"開催場所:\s*([^\n]+)", summary)
        raw_summary = entry.findtext("a:summary", "", NS)
        paragraph = re.search(r"<p\b[^>]*>(.*?)</p>", raw_summary, re.S)
        description = plain_text(paragraph.group(1)).replace("\n", " ") if paragraph else "詳しい内容と参加条件は、connpassのイベント案内をご確認ください。"
        events.append({
            "title": entry.findtext("a:title", "", NS),
            "url": urlunsplit((url.scheme, url.netloc, url.path, "", "")),
            "start": started_at.isoformat(), "end": ended_at.isoformat(),
            "place": place.group(1) if place else "会場はイベント案内をご確認ください",
            "description": description[:140] + ("…" if len(description) > 140 else ""),
        })
    # An explicitly empty Atom feed is valid; malformed entries are not silently discarded.
    return list({event["url"]: event for event in events}.values())


def render_events(data, now, stale=False):
    upcoming = sorted((e for e in data["events"] if datetime.fromisoformat(e["end"]) > now), key=lambda e: e["start"])
    past = sorted((e for e in data["events"] if datetime.fromisoformat(e["end"]) <= now), key=lambda e: e["start"], reverse=True)
    blocks = ['<h3 class="event-group-heading">connpassの開催予定</h3>', '<div class="connpass-events">']
    for event in upcoming[:3]:
        start = datetime.fromisoformat(event["start"]).astimezone(JST)
        end = datetime.fromisoformat(event["end"]).astimezone(JST)
        e = {key: escape(value, quote=True) for key, value in event.items() if isinstance(value, str)}
        image_url = safe_site_url(event.get("image_url"))
        image = f'<a class="event-eyecatch-link" href="{e["url"]}" aria-label="{e["title"]}：connpassの案内を見る"><img class="event-eyecatch" src="{escape(image_url, quote=True)}" alt="" width="1200" height="630" loading="lazy" decoding="async" data-fallback="assets/event-placeholder.svg"></a>' if image_url else ''
        weekday = "月火水木金土日"[start.weekday()]
        hours = start.strftime("%H:%M") + "–" + (end.strftime("%m/%d ") if end.date() != start.date() else "") + end.strftime("%H:%M")
        blocks.append(f'''<article class="event-feature event-feature-connpass" data-event-end="{e['end']}">
  {image}
  <div class="event-content">
  <div class="event-date"><span>{start:%Y / %m}</span><strong>{start:%d}</strong><span>{weekday}曜日</span></div>
  <div class="event-body">
    <div class="tags"><span class="tag" data-event-status>開催予定</span><span class="tag tag-outline">connpass</span></div>
    <h3>{e['title']}</h3>
    <p>{e['description']}</p>
    <div class="event-meta"><span>{hours}</span><span>{e['place']}</span></div>
  </div>
  <a class="event-link" href="{e['url']}">詳細・申し込み<br><span>connpassへ ↗</span></a>
  </div>
</article>''')
    if not upcoming:
        blocks.append('<p class="event-empty">取り込み済みの情報には開催予定がありません。最新の募集情報は<a class="text-link" href="https://codefortoyama.connpass.com/">connpassで確認する ↗</a></p>')
    blocks.append('</div>')
    fetched = datetime.fromisoformat(data["fetched_at"]).astimezone(JST)
    blocks.append(f'<p class="section-note">connpass情報取得：<time datetime="{escape(data["fetched_at"])}">{fetched:%Y/%m/%d %H:%M}（日本時間）</time>。募集状況は各イベントの案内をご確認ください。</p>')
    if stale:
        blocks.append('<p class="section-note feed-warning">最新情報の取得に失敗したため、前回取得した情報を表示しています。最新の募集情報はconnpassをご確認ください。</p>')
    if past:
        blocks.append('<details class="event-history"><summary>最近開催したイベント</summary><ul>')
        for event in past[:3]:
            date = datetime.fromisoformat(event["start"]).astimezone(JST)
            image_url = safe_site_url(event.get("image_url"))
            image = f'<img class="event-history-image" src="{escape(image_url, quote=True)}" alt="" width="120" height="63" loading="lazy" decoding="async" data-fallback="assets/event-placeholder.svg">' if image_url else ''
            blocks.append(f'<li><a href="{escape(event["url"], quote=True)}">{image}<time datetime="{date:%Y-%m-%d}">{date:%Y/%m/%d}</time><span>{escape(event["title"])}</span><span aria-hidden="true">↗</span></a></li>')
        blocks.append('</ul></details>')
    return "\n".join(blocks)


def replace_events(page, html):
    if page.count(START) != 1 or page.count(END) != 1:
        raise ValueError("Expected exactly one event block")
    before, remaining = page.split(START)
    _, after = remaining.split(END)
    return before + START + "\n" + html + "\n        " + END + after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed-file", type=Path, help="Read a downloaded Atom feed instead of using the network")
    parser.add_argument("--offline", action="store_true", help="Render the last successfully fetched data")
    parser.add_argument("--require-fresh", action="store_true", help="Fail instead of publishing cached events when fetching fails")
    parser.add_argument("--output", type=Path, help="Prepare only public files in a GitHub Pages artifact directory")
    args = parser.parse_args()
    now = datetime.now(JST)
    stale = False
    if args.offline:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        try:
            if args.feed_file:
                xml = args.feed_file.read_bytes()
            else:
                request = Request(FEED_URL, headers={"User-Agent": "CodeForToyamaWebsite/1.0"})
                with urlopen(request, timeout=30) as response:
                    xml = response.read(2_000_001)
                if len(xml) > 2_000_000:
                    raise ValueError("Feed exceeds the size limit")
            data = {"source": FEED_URL, "fetched_at": now.isoformat(timespec="seconds"), "events": parse_feed(xml)}
            cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"events": []}
            previous_images = {event["url"]: event.get("image_url") for event in cached["events"]}
            for event in data["events"]:
                # Image failures must not stop fresh event dates and registration links.
                event["image_url"] = fetch_site_image(event["url"]) or safe_site_url(previous_images.get(event["url"]))
        except Exception as error:
            if args.require_fresh or not CACHE.exists():
                raise
            print(f"Warning: connpass fetch failed ({type(error).__name__}); using cached events", file=sys.stderr)
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            stale = True
    page = replace_events((ROOT / "index.html").read_text(encoding="utf-8"), render_events(data, now, stale))
    if not stale and not args.offline:
        CACHE.parent.mkdir(exist_ok=True)
        temporary = CACHE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(CACHE)
    if args.output:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text(page, encoding="utf-8")
        for name in ("css", "js", "assets"):
            shutil.copytree(ROOT / name, output / name, dirs_exist_ok=True)
        for name in (".nojekyll", "sitemap.xml"):
            shutil.copy2(ROOT / name, output / name)
    else:
        (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"Rendered {len(data['events'])} connpass events" + (" (cached)" if stale else ""))


if __name__ == "__main__":
    main()
