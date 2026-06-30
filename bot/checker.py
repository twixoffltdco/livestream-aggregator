#!/usr/bin/env python3
"""
LiveStream Aggregator Bot
==========================
Проверяет список каналов (YouTube / VK / Rutube / Twitch / любые сайты,
поддерживаемые yt-dlp), определяет кто сейчас стримит ВПРЯМУЮ ("в сети"),
достаёт реальную прямую ссылку на поток (HLS m3u8 / DASH) и собирает:

  - data/playlist.m3u8   -> готовый плейлист для VLC / IPTV-плееров
  - data/streams.json    -> метаданные для лендинга (название, платформа,
                             превью, статус, прямая ссылка, время обновления)

Скрипт идемпотентный и безопасный к ошибкам отдельных каналов:
если один канал упал/недоступен - бот не падает, а просто помечает
его как offline и идёт дальше.

Запускается вручную:
    python bot/checker.py

Либо по расписанию через GitHub Actions (см. .github/workflows/update.yml),
каждые 30 минут.
"""

import json
import os
import sys
import time
import datetime
import concurrent.futures
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("[!] yt-dlp не установлен. Выполните: pip install -r bot/requirements.txt")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parent.parent
CHANNELS_FILE = ROOT_DIR / "bot" / "channels.json"
DATA_DIR = ROOT_DIR / "data"
DOCS_DATA_DIR = ROOT_DIR / "docs"
PLAYLIST_FILE = DATA_DIR / "playlist.m3u8"
STREAMS_JSON_FILE = DATA_DIR / "streams.json"

# Базовый URL, по которому будет доступен этот репозиторий через GitHub Pages /
# raw.githubusercontent. Используется только для подсказок в выводе бота,
# на сам функционал не влияет.
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "OinkTechLLC/livestream-aggregator")

MAX_WORKERS = int(os.environ.get("BOT_MAX_WORKERS", "6"))
TIMEOUT_PER_CHANNEL = int(os.environ.get("BOT_TIMEOUT", "25"))

YDL_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "extract_flat": False,
    "socket_timeout": TIMEOUT_PER_CHANNEL,
    "ignoreerrors": True,
    "nocheckcertificate": True,
    # Часто помогает с гео/антибот-блокировками на YouTube/VK
    "extractor_args": {
        "youtube": {"player_client": ["android", "web"]}
    },
}


def log(msg: str):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def pick_best_stream_url(info: dict) -> str:
    """Достаёт лучшую прямую ссылку на HLS-поток из словаря yt-dlp."""
    if not info:
        return ""

    # Прямой top-level url (часто бывает для простых live-экстракторов)
    if info.get("url") and ".m3u8" in info.get("url", ""):
        return info["url"]

    formats = info.get("formats") or []
    if not formats:
        return info.get("url", "") or ""

    # Предпочитаем HLS (m3u8) с самым высоким разрешением
    hls_formats = [
        f for f in formats
        if f.get("protocol") in ("m3u8", "m3u8_native") and f.get("url")
    ]
    if hls_formats:
        hls_formats.sort(key=lambda f: (f.get("height") or 0), reverse=True)
        return hls_formats[0]["url"]

    # Фоллбэк: любой формат с прямым url
    direct_formats = [f for f in formats if f.get("url")]
    if direct_formats:
        direct_formats.sort(key=lambda f: (f.get("height") or 0), reverse=True)
        return direct_formats[0]["url"]

    return ""


def check_channel(channel: dict) -> dict:
    """Проверяет один канал. Возвращает словарь с результатом."""
    name = channel.get("name", "Без названия")
    url = channel.get("url")
    platform = channel.get("platform", "unknown")

    result = {
        "name": name,
        "platform": platform,
        "source_url": url,
        "logo": channel.get("logo", ""),
        "category": channel.get("category", "other"),
        "is_live": False,
        "stream_url": "",
        "title": "",
        "viewer_count": None,
        "thumbnail": "",
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        "error": None,
    }

    if not url:
        result["error"] = "no url"
        return result

    try:
        with yt_dlp.YoutubeDL(YDL_BASE_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        result["error"] = str(e)[:200]
        log(f"  ✗ {name} ({platform}): ошибка — {result['error']}")
        return result

    if not info:
        result["error"] = "empty info"
        return result

    is_live = bool(info.get("is_live") or info.get("live_status") == "is_live")
    result["is_live"] = is_live
    result["title"] = info.get("title", "") or ""
    result["thumbnail"] = info.get("thumbnail", "") or channel.get("logo", "")
    result["viewer_count"] = info.get("concurrent_view_count") or info.get("view_count")

    if is_live:
        stream_url = pick_best_stream_url(info)
        result["stream_url"] = stream_url
        if stream_url:
            log(f"  ✓ {name} ({platform}): В ЭФИРЕ — поток получен")
        else:
            log(f"  ~ {name} ({platform}): в эфире, но не удалось достать прямую ссылку")
            result["is_live"] = False
            result["error"] = "live but no stream url extracted"
    else:
        log(f"  · {name} ({platform}): офлайн")

    return result


def load_channels() -> list:
    if not CHANNELS_FILE.exists():
        log(f"[!] Файл со списком каналов не найден: {CHANNELS_FILE}")
        return []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_m3u(streams: list) -> str:
    lines = ["#EXTM3U"]
    for s in streams:
        if not s["is_live"] or not s["stream_url"]:
            continue
        title = s["title"] or s["name"]
        group = s.get("category", "other")
        logo = s.get("thumbnail") or s.get("logo") or ""
        lines.append(
            f'#EXTINF:-1 tvg-id="{s["name"]}" tvg-logo="{logo}" group-title="{group}",{s["name"]} — {title}'
        )
        lines.append(s["stream_url"])
    return "\n".join(lines) + "\n"


def main():
    log("=== LiveStream Aggregator Bot: старт проверки ===")
    channels = load_channels()
    if not channels:
        log("[!] Список каналов пуст, нечего проверять.")
        sys.exit(0)

    log(f"Каналов к проверке: {len(channels)} (потоков: {MAX_WORKERS})")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_channel, ch): ch for ch in channels}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    live_count = sum(1 for r in results if r["is_live"])
    log(f"Готово. В эфире сейчас: {live_count} из {len(results)}")

    # Сортировка: сначала живые, потом по имени
    results.sort(key=lambda r: (not r["is_live"], r["name"].lower()))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "total_channels": len(results),
        "live_now": live_count,
        "repo": GITHUB_REPO,
        "streams": results,
    }

    with open(STREAMS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    m3u_content = build_m3u(results)
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    # Дублируем данные в /docs, чтобы GitHub Pages лендинг мог их подхватить
    with open(DOCS_DATA_DIR / "streams.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(DOCS_DATA_DIR / "playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    log(f"Записано: {STREAMS_JSON_FILE}")
    log(f"Записано: {PLAYLIST_FILE}")
    log("=== Готово ===")


if __name__ == "__main__":
    main()
