"""Refresh public GitHub repository links, ranked by default-branch commit date."""

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib.request import Request
import xml.etree.ElementTree as ET

try:
    from safe_http import API_HOSTS, PAGE_HOSTS, IMAGE_HOSTS, secure_urlopen as urlopen, validate_url
except ModuleNotFoundError:
    from scripts.safe_http import API_HOSTS, PAGE_HOSTS, IMAGE_HOSTS, secure_urlopen as urlopen, validate_url

ROOT = Path(__file__).resolve().parent.parent
OWNER = "codefortoyama"
API = "https://api.github.com"
CACHE = ROOT / "data/projects.json"
JST = timezone(timedelta(hours=9))


def api_get(url):
    if urlsplit(url).netloc != "api.github.com" or urlsplit(url).scheme != "https":
        raise ValueError("Unexpected GitHub API URL")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CodeForToyamaWebsite/1.0"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=30, allowed_hosts=API_HOSTS) as response:
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError("GitHub response exceeds the size limit")
        return json.loads(raw), response.headers.get("Link", "")


def check_published_site(url, allowed_hosts=PAGE_HOSTS):
    headers = {"User-Agent": "CodeForToyamaWebsite/1.0"}
    try:
        validate_url(url, allowed_hosts)
        with urlopen(Request(url, headers=headers, method="HEAD"), timeout=20, allowed_hosts=allowed_hosts) as response:
            return safe_site_url(response.geturl()) if response.status == 200 else None
    except HTTPError as error:
        if error.code != 405:
            return None
    except (URLError, TimeoutError, ValueError):
        return None
    try:
        with urlopen(Request(url, headers=headers), timeout=20, allowed_hosts=allowed_hosts) as response:
            return safe_site_url(response.geturl()) if response.status == 200 else None
    except (URLError, TimeoutError, ValueError):
        return None


def resolve_pages_url(repo, get=api_get, verify=check_published_site):
    if not repo.get("has_pages"):
        return None
    name = repo["name"]
    try:
        pages, _ = get(f"{API}/repos/{OWNER}/{quote(name, safe='')}/pages")
    except HTTPError as error:
        if error.code != 404:
            raise
    else:
        if not pages.get("public", True):
            return None
        if safe_site_url(pages.get("html_url")):
            return safe_site_url(pages["html_url"])
    # Public Pages metadata is not always available without a repository-scoped token.
    # Verify the actual project URL; redirects also reveal a configured custom domain.
    host = f"{OWNER}.github.io"
    path = "/" if name.lower() == host else f"/{quote(name, safe='')}/"
    candidates = []
    homepage = safe_site_url(repo.get("homepage"))
    if homepage:
        parsed = urlsplit(homepage)
        if parsed.hostname == host and (parsed.path == path.rstrip("/") or parsed.path.startswith(path)):
            candidates.append(homepage)
    candidates.append(f"https://{host}{path}")
    for url in dict.fromkeys(candidates):
        published = verify(url)
        if published:
            return published
    return None


class SiteImages(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = {}
        self.hero_images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "img" and ("hero" in attrs.get("class", "").lower() or attrs.get("fetchpriority") == "high"):
            self.hero_images.append(attrs.get("src", ""))
        if tag.lower() != "meta":
            return
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        content = attrs.get("content", "").strip()
        if key in {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"} and content:
            self.images.setdefault(key, content)


def parse_site_images(html, site_url):
    parser = SiteImages()
    parser.feed(html)
    candidates = [parser.images.get(key) for key in ["og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"]] + parser.hero_images
    images = []
    for image in candidates:
        if image:
            resolved = safe_image_url(urljoin(site_url, image))
            if resolved and resolved not in images:
                images.append(resolved)
    return images


def parse_site_image(html, site_url):
    images = parse_site_images(html, site_url)
    return images[0] if images else None


def fetch_site_image(site_url):
    if not safe_site_url(site_url):
        return None
    try:
        validate_url(site_url, PAGE_HOSTS)
        request = Request(site_url, headers={"User-Agent": "CodeForToyamaWebsite/1.0"})
        with urlopen(request, timeout=20, allowed_hosts=PAGE_HOSTS) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                return None
            charset = response.headers.get_content_charset() or "utf-8"
            candidates = parse_site_images(raw.decode(charset, errors="replace"), response.geturl())
        for image in candidates:
            published = check_published_site(image, allowed_hosts=IMAGE_HOSTS)
            if published:
                return published
        return None
    except (URLError, TimeoutError, ValueError, LookupError):
        return None


def collect_projects(get=api_get, verify=check_published_site, fetch_image=fetch_site_image):
    url = f"{API}/orgs/{OWNER}/repos?type=public&per_page=100"
    repositories = []
    visited = set()
    while url:
        if url in visited:
            raise ValueError("Repeated GitHub pagination URL")
        visited.add(url)
        page, links = get(url)
        if not isinstance(page, list):
            raise ValueError("Expected a repository list")
        repositories.extend(page)
        match = re.search(r'<([^>]+)>;\s*rel="next"', links)
        url = match.group(1) if match else None

    projects = {}
    for repo in repositories:
        if repo.get("private", True):
            continue
        name = repo["name"]
        if repo.get("owner", {}).get("login", "").lower() != OWNER:
            raise ValueError("Unexpected repository owner")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError("Unexpected repository name")
        last_commit = None
        branch = repo.get("default_branch")
        if branch and not repo.get("disabled", False):
            params = urlencode({"sha": branch, "per_page": 1})
            try:
                commits, _ = get(f"{API}/repos/{OWNER}/{quote(name, safe='')}/commits?{params}")
            except HTTPError as error:
                if error.code != 409:  # GitHub returns 409 for an empty repository.
                    raise
                commits = []
            if not isinstance(commits, list):
                raise ValueError("Expected a commit list")
            if commits:
                last_commit = commits[0]["commit"]["committer"]["date"]
                date = datetime.fromisoformat(last_commit.replace("Z", "+00:00"))
                if date.tzinfo is None:
                    raise ValueError("Commit timestamp must include timezone")
                last_commit = date.isoformat()
        if not last_commit:
            continue
        pages_url = resolve_pages_url(repo, get, verify)
        projects[name] = {
            "name": name,
            "url": f"https://github.com/{OWNER}/{name}",
            "pages_url": pages_url,
            "image_url": fetch_image(pages_url) if pages_url else None,
            "description": repo.get("description") or "",
            "last_commit": last_commit,
            "archived": bool(repo.get("archived")),
            "fork": bool(repo.get("fork")),
        }
    return sort_projects(projects.values())


def safe_site_url(url):
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url)
        parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return url


def safe_image_url(url):
    try:
        return validate_url(url, IMAGE_HOSTS)
    except ValueError:
        return None


def project_destination(project):
    site = safe_site_url(project.get("pages_url"))
    return (site, "公開サイトを見る") if site else (project["url"], "GitHubで見る")


def sort_projects(projects):
    def key(project):
        timestamp = datetime.fromisoformat(project["last_commit"]).timestamp() if project["last_commit"] else float("-inf")
        return (-timestamp, project["name"].casefold())
    return sorted(projects, key=key)


def commit_label(project):
    if not project["last_commit"]:
        return '<span>コミットなし</span>'
    date = datetime.fromisoformat(project["last_commit"]).astimezone(JST)
    return f'<time datetime="{escape(project["last_commit"], quote=True)}">最終コミット {date:%Y/%m/%d}</time>'


def badges(project):
    labels = []
    if project["archived"]:
        labels.append("アーカイブ")
    if project["fork"]:
        labels.append("フォーク")
    return '<span class="repository-badges">' + ''.join(f'<span class="tag tag-outline">{label}</span>' for label in labels) + '</span>' if labels else ''


def source_note(data, stale):
    date = datetime.fromisoformat(data["fetched_at"]).astimezone(JST)
    note = f'<p class="section-note">GitHub情報取得：<time datetime="{escape(data["fetched_at"], quote=True)}">{date:%Y/%m/%d %H:%M}（日本時間）</time></p>'
    if stale:
        note += '<p class="section-note feed-warning">最新情報を取得できなかったため、前回取得した情報を表示しています。最新の情報はGitHubをご確認ください。</p>'
    return note


def load_descriptions():
    path = ROOT / "data/project_descriptions.json"
    return json.loads(path.read_text(encoding="utf-8"))["projects"] if path.exists() else {}


def project_description(project, descriptions):
    reviewed = descriptions.get(project["name"], {}).get("description", "").strip()
    return reviewed or project["description"].strip() or "Code for Toyamaの公開リポジトリです。内容はGitHubのREADMEをご覧ください。"


def render_featured(data, stale=False):
    projects = [project for project in sort_projects(data["projects"]) if project["last_commit"]][:3]
    descriptions = load_descriptions()
    cards = ['<div class="project-grid">']
    for index, project in enumerate(projects, 1):
        destination, label = project_destination(project)
        name, url = escape(project["name"]), escape(destination, quote=True)
        description = project_description(project, descriptions)
        source_link = f'<a class="project-source-link" href="{escape(project["url"], quote=True)}">ソースコードを見る（GitHub） ↗</a>' if destination != project["url"] else ''
        image = ''
        if safe_site_url(project.get("pages_url")):
            image_url = safe_image_url(project.get("image_url")) or "assets/project-placeholder.svg"
            image = f'<img class="project-eyecatch" src="{escape(image_url, quote=True)}" alt="" width="1200" height="630" loading="lazy" decoding="async" data-fallback="assets/project-placeholder.svg">'
        cards.append(f'''<article class="project-card">
  <a class="project-main-link" href="{url}">
  {image}
  <span class="project-card-number">PROJECT {index:02}</span>
  <h3>{name}</h3>
  <p>{escape(description)}</p>
  <div class="project-card-bottom">{commit_label(project)}<span>{label} ↗</span></div>
  </a>
  {source_link}
</article>''')
    cards.append('</div>')
    if not projects:
        cards.append('<p>コミットのある公開プロジェクトはまだありません。<a class="text-link" href="projects.html">リポジトリ一覧を見る →</a></p>')
    cards.append(source_note(data, stale))
    return '\n'.join(cards)


def render_list(data, stale=False):
    projects = sort_projects(project for project in data["projects"] if project["last_commit"])
    descriptions = load_descriptions()
    lines = [f'<p class="projects-intro">公開リポジトリ {len(projects)}件</p>', '<ul class="repository-list">']
    for project in projects:
        destination, label = project_destination(project)
        description = f'<span class="repository-description">{escape(project_description(project, descriptions))}</span>'
        source_link = f'<a class="repository-source-link" href="{escape(project["url"], quote=True)}">ソースコードを見る（GitHub） ↗</a>' if destination != project["url"] else ''
        lines.append(f'''<li><a class="repository-link" href="{escape(destination, quote=True)}">
  <span><span class="repository-name">{escape(project['name'])}</span>{description}{badges(project)}</span>
  <span class="repository-meta">{commit_label(project)}<span class="repository-destination">{label} ↗</span></span>
</a>{source_link}</li>''')
    lines.append('</ul>')
    if not projects:
        lines.append('<p>公開リポジトリはまだありません。<a href="https://github.com/codefortoyama">GitHubの団体ページを見る ↗</a></p>')
    lines.append(source_note(data, stale))
    return '\n'.join(lines)


def replace_block(page, marker, html):
    start, end = f"<!-- {marker}_START -->", f"<!-- {marker}_END -->"
    if page.count(start) != 1 or page.count(end) != 1:
        raise ValueError("Expected exactly one project block: " + marker)
    before, rest = page.split(start)
    _, after = rest.split(end)
    return before + start + "\n" + html + "\n        " + end + after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--require-fresh", action="store_true")
    parser.add_argument("--output", type=Path, help="Update an artifact already prepared by update_events.py")
    args = parser.parse_args()
    stale = False
    if args.offline:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        try:
            data = {"source": f"https://github.com/{OWNER}", "fetched_at": datetime.now(JST).isoformat(timespec="seconds"), "projects": collect_projects()}
        except Exception as error:
            if args.require_fresh or not CACHE.exists():
                raise
            print(f"Warning: GitHub fetch failed ({type(error).__name__}); using cached projects")
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            stale = True
    destination = args.output.resolve() if args.output else ROOT
    # Keep the event block that was freshly rendered in the preceding build step.
    homepage = destination / "index.html"
    page = replace_block(homepage.read_text(encoding="utf-8"), "GITHUB_FEATURED", render_featured(data, stale))
    listing = replace_block((ROOT / "projects.html").read_text(encoding="utf-8"), "GITHUB_REPOSITORIES", render_list(data, stale))
    if not stale and not args.offline:
        CACHE.parent.mkdir(exist_ok=True)
        temporary = CACHE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(CACHE)
    homepage.write_text(page, encoding="utf-8")
    (destination / "projects.html").write_text(listing, encoding="utf-8")
    if args.output:
        namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
        ET.register_namespace("", namespace)
        sitemap = destination / "sitemap.xml"
        tree = ET.parse(sitemap)
        url = "https://codefortoyama.github.io/projects.html"
        if url not in [element.text for element in tree.findall(f".//{{{namespace}}}loc")]:
            entry = ET.SubElement(tree.getroot(), f"{{{namespace}}}url")
            ET.SubElement(entry, f"{{{namespace}}}loc").text = url
        tree.write(sitemap, encoding="utf-8", xml_declaration=True)
    print(f"Rendered {len(data['projects'])} public GitHub repositories")


if __name__ == "__main__":
    main()
