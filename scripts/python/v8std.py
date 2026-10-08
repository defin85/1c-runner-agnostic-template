from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "https://its.1c.ru"


def cache_root() -> Path:
    return Path(os.environ.get("V8STD_CACHE_ROOT", PROJECT_ROOT / ".artifacts" / "v8std")).expanduser()


def read_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset()
    encodings = [charset] if charset else ["utf-8", "cp1251"]
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1251", errors="replace")


def normalize_input(value: str) -> str:
    if re.fullmatch(r"(?:#?std)?\d+", value, flags=re.IGNORECASE):
        number = re.sub(r"\D", "", value)
        return f"{DEFAULT_BASE_URL}/db/v8std/content/{number}/hdoc"
    if value.startswith("/"):
        return urllib.parse.urljoin(DEFAULT_BASE_URL, value)
    return value


def source_url(url: str, body: str) -> str:
    match = re.search(r'href="([^"]*/db/content/v8std/src/[^"]+?i\d+\.htm)"', body)
    if match:
        return urllib.parse.urljoin(url, html.unescape(match.group(1)))
    return url


def title_from(body: str, text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return clean_text(match.group(1)).split("::", 1)[0].strip()
    return text.splitlines()[0] if text.splitlines() else "v8std document"


def clean_text(body: str) -> str:
    body = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.IGNORECASE)
    body = re.sub(r"</(?:p|div|h[1-6]|li|tr|table|br)>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    lines = [re.sub(r"\s+", " ", line).strip() for line in body.splitlines()]
    return "\n".join(line for line in lines if line)


def document_id(url: str, body: str, text: str) -> str:
    for source in (text, body, url):
        match = re.search(r"#std(\d+)", source)
        if match:
            return f"std{match.group(1)}"
    match = re.search(r"/content/(\d+)/hdoc", url)
    if match:
        return f"std{match.group(1)}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"url-{digest}"


def write_cached(record: dict[str, str]) -> tuple[Path, Path]:
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    stem = record["id"]
    json_path = root / f"{stem}.json"
    text_path = root / f"{stem}.txt"
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(record["text"] + "\n", encoding="utf-8")
    return json_path, text_path


def fetch(args: argparse.Namespace) -> int:
    hdoc_url = normalize_input(args.value)
    hdoc_body = read_url(hdoc_url)
    src_url = source_url(hdoc_url, hdoc_body)
    src_body = hdoc_body if src_url == hdoc_url else read_url(src_url)
    text = clean_text(src_body)
    record = {
        "id": document_id(hdoc_url, src_body, text),
        "title": title_from(src_body, text),
        "hdoc_url": hdoc_url,
        "source_url": src_url,
        "text": text,
    }
    json_path, text_path = write_cached(record)
    print(f"{record['id']}: {record['title']}")
    print(record["source_url"])
    print(f"cache: {json_path}")
    print(f"text: {text_path}")
    return 0


def records() -> list[dict[str, str]]:
    root = cache_root()
    if not root.is_dir():
        return []
    result = []
    for path in sorted(root.glob("*.json")):
        result.append(json.loads(path.read_text(encoding="utf-8")))
    return result


def snippet(text: str, query: str, width: int) -> str:
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index < 0:
        index = compact_match_index(text, query)
    if index < 0:
        return ""
    start = max(0, index - width // 2)
    end = min(len(text), index + len(query) + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def normalize_search_text(value: str) -> str:
    return value.lower().replace("ё", "е")


def compact_match_index(text: str, query: str) -> int:
    compact_text = []
    original_indexes = []
    for index, char in enumerate(normalize_search_text(text)):
        if re.match(r"\w", char):
            compact_text.append(char)
            original_indexes.append(index)
    compact_query = re.sub(r"\W+", "", normalize_search_text(query))
    compact_index = "".join(compact_text).find(compact_query)
    if compact_index < 0:
        return -1
    return original_indexes[compact_index]


def search(args: argparse.Namespace) -> int:
    found = 0
    for record in records():
        hit = snippet(record["text"], args.query, args.width)
        if not hit:
            continue
        found += 1
        print(f"{record['id']}: {record['title']}")
        print(record["source_url"])
        print(hit)
        print()
        if found >= args.limit:
            break
    if found == 0:
        print(f"nothing found in {cache_root()}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="v8std")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("value", help="v8std URL, /db/... path, std id, or numeric id")
    fetch_parser.set_defaults(func=fetch)

    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--width", type=int, default=260)
    search_parser.set_defaults(func=search)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
