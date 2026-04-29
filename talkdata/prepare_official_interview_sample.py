from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from db_utils import compute_content_hash


OUTPUT_DIR = SCRIPT_DIR / "import_ready"
OUTPUT_FILE = "official_interview_expansion_import.csv"
DB_FILE = PROJECT_DIR / "corpus.db"
FIELDS = (
    "title",
    "content",
    "source",
    "year",
    "category",
    "dataset_name",
    "source_url",
    "crawl_source",
    "crawl_date",
    "license_note",
)

SOURCE = "访谈语料"
MAX_CONTENT_LEN = 1200
MIN_CONTENT_LEN = 60
REQUEST_TIMEOUT = 20
DEFAULT_LICENSE_NOTE = "公开网页文字片段，仅用于语料检索展示；上线展示短片段，并提供原文链接，版权归原网站及相关权利人所有。"
SOURCE_METADATA = {
    "china_interview": {
        "crawl_source": "中国网《中国访谈》",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "china_live": {
        "crawl_source": "中国网网上直播/文字实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "scio_press": {
        "crawl_source": "中国网网上直播/国新办发布会文字实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "state_council_briefing": {
        "crawl_source": "中国网网上直播/国务院政策例行吹风会文字实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "ministry_press": {
        "crawl_source": "中国网网上直播/部委公开发布会文字实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "taiwan_affairs_press": {
        "crawl_source": "中国网网上直播/国台办新闻发布会文字实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
    "mfa_press": {
        "crawl_source": "外交部例行记者会实录",
        "license_note": DEFAULT_LICENSE_NOTE,
    },
}

LIST_SOURCES = [
    {
        "category": "中国访谈",
        "dataset_name": "china_interview",
        "list_urls": [
            "http://fangtan.china.com.cn/node_7069383.htm",
            "http://fangtan.china.com.cn/node_7069386.htm",
            "http://fangtan.china.com.cn/node_7069387.htm",
            "http://www.china.com.cn/fangtan/node_7021614.htm",
        ],
        "include": ("fangtan.china.com.cn", "www.china.com.cn"),
        "href_tokens": ("content_",),
        "title_tokens": (),
    },
    {
        "category": "发布会实录",
        "dataset_name": "china_live",
        "list_urls": [
            "http://www.china.com.cn/zhibo/node_7030498.htm",
            "http://www.china.com.cn/zhibo/node_7223481.htm",
            "http://www.china.com.cn/zhibo/node_9018201.htm",
            "http://www.china.com.cn/zhibo/node_9014450.htm",
            "http://www.china.com.cn/zhibo/node_9005547.htm",
            "http://www.china.com.cn/zhibo/node_9000243.htm",
            "http://www.china.com.cn/zhibo/node_8027706.htm",
            "http://www.china.com.cn/zhibo/node_8021488.htm",
            "http://www.china.com.cn/zhibo/node_8016075.htm",
            "http://www.china.com.cn/zhibo/node_8009517.htm",
            "http://www.china.com.cn/zhibo/node_8002461.htm",
            "http://www.china.com.cn/zhibo/node_7245314.htm",
            "http://www.china.com.cn/zhibo/node_7244037.htm",
            "http://www.china.com.cn/zhibo/node_7243161.htm",
            "http://www.china.com.cn/zhibo/node_7243162.htm",
            "http://www.china.com.cn/zhibo/node_7243165.htm",
            "http://www.china.com.cn/zhibo/node_7243166.htm",
            "http://www.china.com.cn/zhibo/node_9000156.htm",
            "http://www.china.com.cn/zhibo/node_8011140.htm",
        ],
        "include": ("www.china.com.cn",),
        "href_tokens": ("zhibo/content_", "content_"),
        "title_tokens": ("文字实录", "发布会", "直播", "吹风会", "记者会"),
    },
    {
        "category": "外交部记者会",
        "dataset_name": "mfa_press",
        "list_urls": [
            "https://www.mfa.gov.cn/fyrbt_673021/jzhsl_673025/index.shtml",
            *[
                f"https://www.mfa.gov.cn/fyrbt_673021/jzhsl_673025/index_{index}.shtml"
                for index in range(1, 31)
            ],
        ],
        "include": ("www.mfa.gov.cn",),
        "href_tokens": (".shtml",),
        "title_tokens": ("例行记者会", "记者会"),
    },
]

SEED_ARTICLES = [
    {
        "title": "对话杨澜（上）：爱是我生命的最大动力",
        "url": "http://fangtan.china.com.cn/2017-05/10/content_40781973.htm",
        "category": "中国访谈",
        "dataset_name": "china_interview",
    },
    {
        "title": "对话杨澜（中）：访谈节目的黄金时代落幕了吗？",
        "url": "http://fangtan.china.com.cn/2017-05/10/content_40781981.htm",
        "category": "中国访谈",
        "dataset_name": "china_interview",
    },
    {
        "title": "对话杨澜（下）：“年轻人千万不能混！”",
        "url": "http://fangtan.china.com.cn/2017-05/10/content_40781986.htm",
        "category": "中国访谈",
        "dataset_name": "china_interview",
    },
]

YEAR_RE = re.compile(r"(20\d{2}|19\d{2})")
SPACE_RE = re.compile(r"[ \t\r\f\v]+")
TIME_MARK_RE = re.compile(r"\[[0-9]{1,2}[-:月日0-9\s]{3,20}\]")
SPEAKER_RE = re.compile(r"^[\s\[]?([\u4e00-\u9fffA-Za-z0-9·•（）()、]{1,34})[\]】）)]?[：:]\s*(.*)$")
QUESTION_SPEAKER_RE = re.compile(r"(主持人|记者|中国网|网友|问|提问|主持)")
BOILERPLATE_TOKENS = (
    "版权所有",
    "责任编辑",
    "分享到",
    "字号：",
    "打印本页",
    "关闭窗口",
    "网站地图",
    "ICP备案",
    "copyright",
    "本期人员",
    "阅读全文",
    "收起",
)
METADATA_SPEAKERS = {"嘉宾", "时间", "地点", "来源", "责任编辑", "图为", "图片"}
CHINA_LIVE_CHARACTERS_RE = re.compile(r"ciic_webcast\['characters'\]\s*=\s*(\[.*?\]);", re.S)


@dataclass(frozen=True)
class ArticleRef:
    title: str
    url: str
    category: str
    dataset_name: str


@dataclass
class ParsedArticle:
    ref: ArticleRef
    title: str
    year: str
    utterances: list[tuple[str, str]]


def clean_text(value: str | None) -> str:
    text = unescape(value or "")
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def is_boilerplate(line: str) -> bool:
    lower = line.lower()
    return any(token in lower for token in BOILERPLATE_TOKENS)


def make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        }
    )
    return session


def classify_live_ref(title: str, default_category: str, default_dataset_name: str) -> tuple[str, str]:
    if "国新办" in title or "国务院新闻办公室" in title:
        return "国新办发布会", "scio_press"
    if "国务院政策例行吹风会" in title or "吹风会" in title:
        return "政策吹风会", "state_council_briefing"
    if "国台办" in title or "国务院台湾事务办公室" in title:
        return "国台办发布会", "taiwan_affairs_press"
    ministry_tokens = (
        "商务部",
        "交通运输部",
        "中国气象局",
        "国家中医药管理局",
        "中国贸促会",
        "最高法",
        "最高人民法院",
        "最高检",
        "国家统计局",
        "农业农村部",
        "工业和信息化",
        "市场监管",
        "国家发展改革委",
    )
    if any(token in title for token in ministry_tokens):
        return "部委发布会", "ministry_press"
    return default_category, default_dataset_name


def fetch_html(session: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT, verify=False, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            return response.text
        except Exception as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError(f"failed to fetch {url}")


def collect_article_refs(session: requests.Session, max_per_source: int) -> list[ArticleRef]:
    refs: list[ArticleRef] = []
    seen: set[str] = set()

    for seed in SEED_ARTICLES:
        url = seed["url"]
        seen.add(url)
        refs.append(
            ArticleRef(
                title=seed["title"],
                url=url,
                category=seed["category"],
                dataset_name=seed["dataset_name"],
            )
        )

    for source in LIST_SOURCES:
        count = 0
        for list_url in source["list_urls"]:
            if count >= max_per_source:
                break
            try:
                soup = BeautifulSoup(fetch_html(session, list_url), "html.parser")
            except Exception:
                continue
            for anchor in soup.select("a[href]"):
                if count >= max_per_source:
                    break
                title = clean_text(anchor.get_text(" ", strip=True))
                href = anchor.get("href") or ""
                if not title or not href:
                    continue
                url = urljoin(list_url, href)
                host = urlparse(url).netloc
                if source["include"] and not any(item in host for item in source["include"]):
                    continue
                if not any(token in url for token in source["href_tokens"]):
                    continue
                if source["title_tokens"] and not any(token in title for token in source["title_tokens"]):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                count += 1
                category = source["category"]
                dataset_name = source["dataset_name"]
                if dataset_name == "china_live":
                    category, dataset_name = classify_live_ref(title, category, dataset_name)
                refs.append(
                    ArticleRef(
                        title=title,
                        url=url,
                        category=category,
                        dataset_name=dataset_name,
                    )
                )
    return refs


def extract_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ("h1", ".title", ".article-title", "#p_title"):
        node = soup.select_one(selector)
        if node:
            title = clean_text(node.get_text(" ", strip=True))
            if title and len(title) > 4:
                return title
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    if title:
        return title.split("_")[0].split("-")[0].split("--")[0].strip() or fallback
    return fallback


def extract_year(text: str, url: str) -> str:
    match = YEAR_RE.search(url) or YEAR_RE.search(text[:1200])
    return match.group(1) if match else ""


def normalize_lines(text: str) -> list[str]:
    text = TIME_MARK_RE.sub("", text)
    text = re.sub(r"\[([^\]\[]{1,34})\]", r"\1：", text)
    text = re.sub(r"(\S{1,34})\s+[:：]\s+", r"\1：", text)
    lines = []
    for raw in text.splitlines():
        line = clean_text(raw)
        if not line or is_boilerplate(line):
            continue
        if len(line) <= 1:
            continue
        lines.append(line)
    return lines


def append_utterance(utterances: list[tuple[str, str]], speaker: str, parts: list[str]) -> None:
    body = clean_text(" ".join(parts))
    if not speaker or not body:
        return
    if len(body) < 8 or not re.search(r"[\u4e00-\u9fff]", body):
        return
    utterances.append((speaker, body))


def extract_utterances(text: str) -> list[tuple[str, str]]:
    utterances: list[tuple[str, str]] = []
    current_speaker = ""
    current_parts: list[str] = []

    for line in normalize_lines(text):
        match = SPEAKER_RE.match(line)
        if match:
            speaker = clean_text(match.group(1))
            body = clean_text(match.group(2))
            if len(speaker) <= 34 and not is_boilerplate(speaker):
                append_utterance(utterances, current_speaker, current_parts)
                current_speaker = speaker
                current_parts = [body] if body else []
                continue
        if current_speaker:
            current_parts.append(line)

    append_utterance(utterances, current_speaker, current_parts)

    cleaned: list[tuple[str, str]] = []
    for speaker, body in utterances:
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) > 900:
            body = body[:900].rstrip("，。；、 ") + "。"
        if len(body) >= 8:
            cleaned.append((speaker, body))
    return cleaned


def extract_china_live_utterances(session: requests.Session, soup: BeautifulSoup, page_url: str) -> list[tuple[str, str]]:
    data_node = soup.select_one("#content_data[src]")
    if not data_node:
        return []
    src = data_node.get("src") or ""
    if not src:
        return []
    try:
        js_text = fetch_html(session, urljoin(page_url, src))
    except Exception:
        return []
    match = CHINA_LIVE_CHARACTERS_RE.search(js_text)
    if not match:
        return []
    try:
        items = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    items.sort(key=lambda item: item.get("date") or "")
    utterances: list[tuple[str, str]] = []
    for item in items:
        speaker = clean_text(item.get("speaker"))
        content_html = item.get("content") or ""
        body = clean_text(BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True))
        if speaker and body:
            utterances.append((speaker, body))
    return utterances


def parse_article(session: requests.Session, ref: ArticleRef) -> ParsedArticle | None:
    try:
        html = fetch_html(session, ref.url)
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    utterances = extract_china_live_utterances(session, soup, ref.url)
    if not utterances:
        utterances = extract_utterances(text)
    if len(utterances) < 2:
        return None
    return ParsedArticle(
        ref=ref,
        title=extract_title(soup, ref.title),
        year=extract_year(f"{ref.title}\n{text}", ref.url),
        utterances=utterances,
    )


def content_candidates(article: ParsedArticle) -> list[str]:
    candidates: list[str] = []
    utterances = article.utterances
    for index, (speaker, body) in enumerate(utterances):
        if index + 1 >= len(utterances):
            continue
        next_speaker, next_body = utterances[index + 1]
        if speaker in METADATA_SPEAKERS:
            continue
        is_question = bool(QUESTION_SPEAKER_RE.search(speaker)) or "？" in body or "?" in body
        if not is_question or speaker == next_speaker:
            continue
        content = f"{speaker}：{body}\n{next_speaker}：{next_body}"
        if MIN_CONTENT_LEN <= len(content) <= MAX_CONTENT_LEN:
            candidates.append(content)
    return candidates


def load_existing_hashes(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT content_hash FROM corpus_entries WHERE content_hash IS NOT NULL AND TRIM(content_hash) != ''"
            ).fetchall()
        }
    finally:
        conn.close()


def build_rows(
    articles: list[ParsedArticle],
    db_path: Path,
    limit: int,
    include_existing: bool = False,
) -> list[dict[str, str]]:
    existing_hashes = load_existing_hashes(db_path)
    seen_hashes: set[str] = set()
    rows: list[dict[str, str]] = []
    crawl_date = date.today().isoformat()

    for article in articles:
        for offset, content in enumerate(content_candidates(article), start=1):
            if len(rows) >= limit:
                return rows
            content_hash = compute_content_hash(content)
            if (not include_existing and content_hash in existing_hashes) or content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            rows.append(
                {
                    "title": f"{article.title} 片段 {offset}",
                    "content": content,
                    "source": SOURCE,
                    "year": article.year,
                    "category": article.ref.category,
                    "dataset_name": article.ref.dataset_name,
                    "source_url": article.ref.url,
                    "crawl_source": SOURCE_METADATA.get(article.ref.dataset_name, {}).get(
                        "crawl_source",
                        article.ref.dataset_name,
                    ),
                    "crawl_date": crawl_date,
                    "license_note": SOURCE_METADATA.get(article.ref.dataset_name, {}).get(
                        "license_note",
                        DEFAULT_LICENSE_NOTE,
                    ),
                }
            )
    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for row in rows:
        key = f"{row['dataset_name']}|{row['category']}"
        stats[key] = stats.get(key, 0) + 1
    return stats


def source_priority(article: ParsedArticle) -> tuple[int, str]:
    priorities = {
        "mfa_press": 0,
        "scio_press": 1,
        "state_council_briefing": 2,
        "ministry_press": 3,
        "taiwan_affairs_press": 4,
        "china_live": 5,
        "china_interview": 6,
    }
    return (priorities.get(article.ref.dataset_name, 99), article.title)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a small official interview/Q&A sample CSV.")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / OUTPUT_FILE)
    parser.add_argument("--db", type=Path, default=DB_FILE)
    parser.add_argument("--limit", type=int, default=800)
    parser.add_argument("--max-per-source", type=int, default=35)
    parser.add_argument("--include-existing", action="store_true", help="输出已在数据库中的重复片段，用于元数据回填")
    args = parser.parse_args()

    session = make_session()
    refs = collect_article_refs(session, args.max_per_source)
    articles = [article for ref in refs if (article := parse_article(session, ref))]
    articles.sort(key=source_priority)
    rows = build_rows(articles, args.db, args.limit, include_existing=args.include_existing)
    write_csv(rows, args.output)

    print("official interview sample preparation complete")
    print(f"- candidate article links: {len(refs)}")
    print(f"- parsed articles: {len(articles)}")
    print(f"- output rows: {len(rows)}")
    for key, count in sorted(summarize(rows).items()):
        dataset_name, category = key.split("|", 1)
        print(f"- {dataset_name} / {category}: {count}")
    print(f"- output file: {args.output}")


if __name__ == "__main__":
    main()
