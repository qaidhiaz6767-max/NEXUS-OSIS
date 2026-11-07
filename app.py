"""Local-only HTTP and CLI entry point for NEXUS OSIS.
Start: python3 app.py
"""

from __future__ import annotations

import argparse
import json
import logging
import importlib.util
import re
import math
import ssl
import socket
import os
import sys
import threading
import tempfile
import time
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, HTTPRedirectHandler, build_opener

from core import Coordinator as CoreCoordinator, Store, HELP
from nexus.commands import offline_command
from nexus.intents import classify as classify_intent, handle as handle_intent
from nexus.briefing import build_briefing
from nexus.providers import OpenAIResponsesProvider
from nexus.validation import configured_timezone, clean_text, today_local, iso_day, now
from nexus.backend_api import get_data
from nexus.workspaces import WorkspaceRegistry
from nexus.web_security import csp_for

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get("NEXUS_DB", str(ROOT / "data" / "nexus.sqlite3")))
STATIC = {
    "/": ("web/index.html", "text/html; charset=utf-8"),
    "/index.html": ("web/index.html", "text/html; charset=utf-8"),
    "/style.css": ("web/style.css", "text/css; charset=utf-8"),
    "/app.js": ("web/app.js", "text/javascript; charset=utf-8"),
}
for module in ("state", "api", "domain", "ui", "views", "forms", "voice"):
    STATIC[f"/{module}.js"] = (f"web/{module}.js", "text/javascript; charset=utf-8")


WORLD_SOURCES = {
    "coingecko": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true&include_last_updated_at=true",
    "exchange": "https://open.er-api.com/v6/latest/USD",
    "bbc": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "coinbase_btc": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
    "coinbase_eth": "https://api.coinbase.com/v2/prices/ETH-USD/spot",
}
WORLD_LIMIT = 300_000


class _FeedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        allowed_hosts = {urlsplit(url).netloc for url in WORLD_SOURCES.values()}
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc not in allowed_hosts:
            raise ValueError("Feed redirect is outside the approved sources")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch_url(url: str) -> bytes:
    """Fixed public feeds only; never a URL supplied by the browser or AI."""
    if url not in WORLD_SOURCES.values():
        raise ValueError("Unknown public feed")
    request = Request(url, headers={"User-Agent": "NEXUS-Local/0.5 public-feed-reader"})
    with build_opener(_FeedRedirect()).open(request, timeout=6) as response:
        data = response.read(WORLD_LIMIT + 1)
    if len(data) > WORLD_LIMIT:
        raise ValueError("Public feed exceeds the 300 KB limit")
    return data


def _feed_number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid feed number")
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError("Invalid feed number")
    return value


def _parse_world_source(source: str, raw: bytes):
    if len(raw) > WORLD_LIMIT:
        raise ValueError("Oversized feed")
    if source == "bbc":
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Feed document declarations are not supported")
        root = ET.fromstring(raw)
        titles = [
            " ".join("".join(node.itertext()).split())[:300]
            for node in root.findall(".//item/title")
        ]
        titles = [title for title in titles if title][:6]
        if not titles:
            raise ValueError("No RSS headlines found")
        return titles
    data = json.loads(raw)
    if source.startswith("coinbase_"):
        coin, expected = (
            ("bitcoin", "BTC") if source == "coinbase_btc" else ("ethereum", "ETH")
        )
        quote = data["data"]
        if (
            quote.get("base") != expected
            or quote.get("currency") != "USD"
            or not isinstance(quote.get("amount"), str)
        ):
            raise ValueError("Unexpected spot quote")
        return {
            coin: {
                "usd": _feed_number(float(quote["amount"]), positive=True),
                "change_24h": None,
                "source_updated_at": None,
            }
        }
    if source == "exchange":
        if data.get("result") != "success" or data.get("base_code") != "USD":
            raise ValueError("Unexpected exchange-rate response")
        return {
            "usd_idr": _feed_number(data["rates"]["IDR"], positive=True),
            "source_updated_at": (
                data.get("time_last_update_utc")
                if isinstance(data.get("time_last_update_utc"), str)
                else None
            ),
        }
    return {
        coin: {
            "usd": _feed_number(data[coin]["usd"], positive=True),
            "change_24h": _feed_number(data[coin]["usd_24h_change"]),
            "source_updated_at": (
                datetime.fromtimestamp(
                    data[coin]["last_updated_at"], timezone.utc
                ).isoformat()
                if isinstance(data[coin].get("last_updated_at"), (int, float))
                and not isinstance(data[coin].get("last_updated_at"), bool)
                else None
            ),
        }
        for coin in ("bitcoin", "ethereum")
    }


def _feed_error(exc):
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return {
            "code": "certificate_error",
            "message": "Python could not verify the HTTPS certificate. Check the Python certificate installation; TLS verification stays enabled.",
        }, 60
    if isinstance(exc, HTTPError):
        if exc.code == 429:
            try:
                delay = max(30, min(300, int(exc.headers.get("Retry-After", "60"))))
            except (ValueError, TypeError):
                delay = 60
            return {
                "code": "rate_limited",
                "message": "The source is rate-limiting requests. A fallback will be used where available.",
            }, delay
        return {
            "code": "source_http_error",
            "message": f"The source returned HTTP {exc.code}.",
        }, 30
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return {"code": "timeout", "message": "The source did not respond in time."}, 30
    if isinstance(exc, URLError):
        return {
            "code": "connection_error",
            "message": "The server could not connect. Check its internet, proxy and Python certificate settings.",
        }, 30
    return {
        "code": "invalid_data",
        "message": "The source did not return usable data.",
    }, 30


class WorldFeedCache:
    """Public prices refresh independently of daily FX and slower news feeds."""

    TTL = {
        "coingecko": 15,
        "exchange": 3600,
        "bbc": 300,
        "coinbase_btc": 15,
        "coinbase_eth": 15,
    }

    def __init__(self, fetcher=None, clock=None):
        self.fetcher = fetcher
        self.clock = clock or time.monotonic
        self.lock = threading.Lock()
        self.records = {
            name: {
                "value": None,
                "error": None,
                "fetched_at": None,
                "checked_at": None,
                "last_success": None,
                "next_refresh": 0,
            }
            for name in WORLD_SOURCES
        }

    def _refresh(self, names):
        if not names:
            return
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                name: executor.submit(self.fetcher or fetch_url, WORLD_SOURCES[name])
                for name in names
            }
            for name, future in futures.items():
                record = self.records[name]
                record["checked_at"] = now()
                try:
                    record["value"] = _parse_world_source(name, future.result())
                    record.update(
                        error=None,
                        fetched_at=now(),
                        last_success=self.clock(),
                        next_refresh=self.clock() + self.TTL[name],
                    )
                except Exception as exc:
                    error, retry = _feed_error(exc)
                    record.update(error=error, next_refresh=self.clock() + retry)

    def _stale(self, name):
        record = self.records[name]
        return bool(
            record["error"]
            or record["last_success"] is None
            or self.clock() - record["last_success"] > self.TTL[name] * 2
        )

    def get(self):
        with self.lock:
            current = self.clock()
            self._refresh(
                [
                    name
                    for name in ("coingecko", "exchange", "bbc")
                    if current >= self.records[name]["next_refresh"]
                ]
            )
            if not self.records["coingecko"]["value"] or self._stale("coingecko"):
                self._refresh(
                    [
                        name
                        for name in ("coinbase_btc", "coinbase_eth")
                        if self.clock() >= self.records[name]["next_refresh"]
                    ]
                )
            prices = {}
            for coin, fallback in [
                ("bitcoin", "coinbase_btc"),
                ("ethereum", "coinbase_eth"),
            ]:
                primary = self.records["coingecko"]
                record_name = (
                    "coingecko"
                    if primary["value"] and not self._stale("coingecko")
                    else (
                        fallback
                        if self.records[fallback]["value"] and not self._stale(fallback)
                        else "coingecko" if primary["value"] else fallback
                    )
                )
                record = self.records[record_name]
                value = (record["value"] or {}).get(coin)
                if value:
                    quote = dict(value)
                    quote.update(
                        source=(
                            "CoinGecko" if record_name == "coingecko" else "Coinbase"
                        ),
                        fetched_at=record["fetched_at"],
                        stale=self._stale(record_name),
                    )
                    stamp = quote.get("source_updated_at")
                    if stamp:
                        try:
                            quote["stale"] = (
                                quote["stale"]
                                or (
                                    datetime.now(timezone.utc)
                                    - datetime.fromisoformat(stamp)
                                ).total_seconds()
                                > 180
                            )
                        except ValueError:
                            quote["stale"] = True
                    prices[coin] = quote
            exchange_record = self.records["exchange"]
            exchange = (
                dict(exchange_record["value"]) if exchange_record["value"] else None
            )
            if exchange:
                exchange.update(
                    source="ExchangeRate-API",
                    fetched_at=exchange_record["fetched_at"],
                    stale=self._stale("exchange"),
                    kind="daily_reference",
                )
                try:
                    stamp = parsedate_to_datetime(exchange["source_updated_at"])
                    exchange["stale"] = (
                        exchange["stale"]
                        or (datetime.now(timezone.utc) - stamp).total_seconds() > 172800
                    )
                except (ValueError, TypeError, KeyError):
                    exchange["source_updated_at"] = None
            news = self.records["bbc"]
            groups = [
                len(prices) == 2
                and all(not quote["stale"] for quote in prices.values()),
                bool(exchange and not exchange["stale"]),
                bool(news["value"] and not self._stale("bbc")),
            ]
            has_data = bool(prices or exchange or news["value"])
            sources = {}
            errors = []
            for name, record in self.records.items():
                if record["checked_at"] is None:
                    continue
                sources[name] = {
                    "status": (
                        "stale"
                        if record["value"] and self._stale(name)
                        else "available" if record["value"] else "unavailable"
                    ),
                    "checked_at": record["checked_at"],
                    "fetched_at": record["fetched_at"],
                    "refresh_seconds": self.TTL[name],
                }
                if record["error"]:
                    errors.append({"source": name, **record["error"]})
            return {
                "prices": prices or None,
                "exchange": exchange,
                "headlines": list(news["value"] or []),
                "sources": sources,
                "errors": errors,
                "status": (
                    "LIVE"
                    if all(groups)
                    else (
                        "PARTIAL" if any(groups) else "STALE" if has_data else "OFFLINE"
                    )
                ),
                "fetched_at": now(),
                "cache_seconds": 15 if prices else 30,
                "news_stale": bool(news["value"] and self._stale("bbc")),
            }


def fetch_world():
    return WorldFeedCache().get()


class _ConversationTone:
    def __init__(self, provider):
        self.provider = provider

    def respond(self, **request):
        request["instructions"] += (
            "\nSpeak naturally, like a capable colleague. Answer the actual question first. "
            "Use ordinary sentences and contractions. Match the user’s language and level of detail. "
            "Do not demand slash commands, recite tool names, start with canned disclaimers, or print raw JSON. "
            "Small talk is welcome. Never invent records, access, emotions, approvals or completed actions. "
            "Keep confirmations for changes requiring human review. Use the approved tool schemas when needed."
        )
        return self.provider.respond(**request)


def conversation_setup(allow_ai, store, demo=False):
    enabled = bool(allow_ai and "ai" in store.capabilities and not demo)
    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    try:
        installed = (
            "openai" in sys.modules or importlib.util.find_spec("openai") is not None
        )
    except (ImportError, ValueError):
        installed = False
    reason = (
        "demo"
        if demo
        else (
            "disabled"
            if not enabled
            else (
                "missing_key"
                if not key_present
                else "missing_package" if not installed else "configured"
            )
        )
    )
    return {
        "enabled": enabled,
        "key_present": key_present,
        "package_installed": installed,
        "provider": "OpenAI",
        "model": os.getenv("NEXUS_MODEL", "gpt-4.1-mini"),
        "reason": reason,
        "ready_to_try": reason == "configured",
    }


def _plain_request(message):
    text = message.strip()
    text = re.sub(r"^(?:hey\s+|hi\s+)?nexus\b[,!:]?\s*", "", text, flags=re.I)
    text = re.sub(
        r"^(?:can you|could you|would you|please|tolong|bisa kamu)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"^(?:hey|hi|hello|yo)(?:\s+bro)?[,\s]+(?=(?:show|list|add|create|what|when|how|remind|find|search|mark|start)\b)",
        "",
        text,
        flags=re.I,
    )
    return text.strip().rstrip(".!?").strip()


def _number_word(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def _spoken_text(text):
    text = re.sub(
        r"```.*?```", "I’ve included the code in the chat.", str(text), flags=re.S
    )
    text = re.sub(r"[#*_`]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:1500]


class ConversationCoordinator(CoreCoordinator):
    """Conversational entry adapter; Core still validates every tool and approval."""

    def __init__(self, store, *, allow_ai=False, provider=None, world_service=None):
        super().__init__(store, allow_ai=allow_ai, provider=provider)
        self.world_service = world_service

    def _can_use_ai(self):
        return (
            self.allow_ai
            and "ai" in self.store.capabilities
            and bool(self.provider or os.environ.get("OPENAI_API_KEY"))
        )

    def _focus(self, task_id):
        # Operational conversation context, never a business-record mutation.
        with self.store._conn() as con:
            con.execute(
                "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
                (task_id,),
            )

    def _digest(self, mode="brief", owner=""):
        report = build_briefing(
            self.store, "week" if mode == "weekly" else "today", owner
        )
        counts = report["counts"]
        tasks = report["priorities"]
        if mode == "weekly":
            completed = report["completed_last_7_days"]
            text = (
                f"I found {_number_word(len(completed), 'task')} with recorded completion dates in the last seven days"
                + (" in this report (up to 30 shown)." if len(completed) == 30 else ".")
            )
            if report["completion_time_unknown"]:
                text += f" {_number_word(report['completion_time_unknown'], 'older completed task')} have no completion date, so I haven’t counted them."
            text += "".join("\n• " + task["title"] for task in completed[:5])
        elif mode == "tasks":
            text = (
                f"{owner + ' has' if owner else 'You have'} {_number_word(counts['open_tasks'], 'open task')}"
                + (f" in {self.store.workspace_id.upper()}." if not owner else ".")
            )
            text += "".join(
                f"\n• #{task['id']} {task['title']} — {task['owner']}"
                + (
                    f", due {task['due_date']}"
                    if task["due_date"]
                    else ", no deadline set"
                )
                for task in tasks[:6]
            )
            if not tasks:
                text += " Tell me what you want to get done, and I’ll prepare a task for review."
            self._focus(tasks[0]["id"] if len(tasks) == 1 else None)
        else:
            with self.store._conn() as con:
                events_today = con.execute(
                    "SELECT count(*) FROM events WHERE day=?",
                    (today_local().isoformat(),),
                ).fetchone()[0]
            text = f"You have {_number_word(counts['open_tasks'], 'open task')} and {_number_word(events_today, 'event')} today in {self.store.workspace_id.upper()}."
            if counts["overdue"]:
                text += f" {_number_word(counts['overdue'], 'task')} {'is' if counts['overdue'] == 1 else 'are'} past the deadline."
            if tasks:
                first = tasks[0]
                reason = (
                    "its deadline has passed"
                    if first["due_date"]
                    and first["due_date"] < today_local().isoformat()
                    else (
                        "it’s marked high priority"
                        if first["priority"] == "high"
                        else "it comes first in your current priority order"
                    )
                )
                text += f" I’d start with “{first['title']}” (#{first['id']}) because {reason}."
                self._focus(first["id"])
            elif not events_today:
                text += " Your schedule is clear in the saved records. What would you like to work on?"
            if report["upcoming_events"]:
                event = report["upcoming_events"][0]
                text += f"\nNext up: {event['title']} on {event['day']}" + (
                    f" at {event['time']}." if event["time"] else " — time not set."
                )
            if counts["pending_approvals"]:
                text += f"\n{_number_word(counts['pending_approvals'], 'proposed change')} {'needs' if counts['pending_approvals'] == 1 else 'need'} your review."
        return {
            "message": text,
            "kind": "verified_information",
            "authority_level": 0,
            "evidence": report,
        }

    def _local(self, message, history):
        if message.lstrip().startswith("/"):
            return None
        text = _plain_request(message)
        lower = text.casefold().replace("’", "'")
        if not lower or re.fullmatch(
            r"(?:hey|hi|hello|yo|halo|hai|hey bro|good morning|good afternoon|good evening|pagi|selamat pagi)(?:\s+(?:nexus|there|bro))?",
            lower,
        ):
            return {
                "message": "Hey. What are we working on?",
                "kind": "conversation",
                "suggestions": [
                    "What should I focus on today?",
                    "Show my tasks",
                    "What can you do?",
                ],
            }
        if re.fullmatch(
            r"(?:how are you|how'?s it going|what'?s up|apa kabar)(?:\s+(?:nexus|bro))?",
            lower,
        ):
            return {
                "message": "I’m here and ready to help. What’s on your mind?",
                "kind": "conversation",
            }
        if lower in {
            "thanks",
            "thank you",
            "thank you bro",
            "makasih",
            "terima kasih",
            "nice",
            "okay",
            "ok",
            "alright",
        }:
            return {
                "message": (
                    "You’re welcome."
                    if lower not in {"okay", "ok", "alright"}
                    else "All right. I’m here when you need me."
                ),
                "kind": "conversation",
            }
        if lower in {
            "what can you do",
            "help",
            "help me",
            "bisa apa",
            "what do you do",
        }:
            return {
                "message": "I can help you review your workload, find saved information, prepare tasks and meetings, and look up the current public market feeds. Changes go to your Approval inbox first. For open-ended conversation, connect OpenAI in Settings.",
                "kind": "conversation",
                "suggestions": [
                    "Show my tasks",
                    "What’s happening today?",
                    "What’s Bitcoin at?",
                ],
            }
        name = re.fullmatch(
            r"(?:my name is|call me|nama saya|namaku)\s+([\w .'-]{1,60})", text, re.I
        )
        if name:
            return {
                "message": f"Got it, {name[1].strip()}. What would you like to work on?",
                "kind": "conversation",
            }
        if lower in {"what is my name", "what's my name", "siapa nama saya"}:
            with self.store._conn() as con:
                fact = con.execute(
                    "SELECT m.value FROM memories m JOIN memory_details d ON d.key=m.key WHERE lower(m.key) IN ('preferred name','name','my name') AND (d.valid_until='' OR d.valid_until>=?) LIMIT 1",
                    (today_local().isoformat(),),
                ).fetchone()
            if fact:
                return {
                    "message": f"You’ve saved your name as {fact[0]}.",
                    "kind": "verified_information",
                }
            for item in reversed(history):
                match = (
                    re.fullmatch(
                        r"(?:my name is|call me|nama saya|namaku)\s+([\w .'-]{1,60})[.!]?",
                        item["content"].strip(),
                        re.I,
                    )
                    if item["role"] == "user"
                    else None
                )
                if match:
                    return {
                        "message": f"You told me {match[1].strip().rstrip('.')} in this conversation. I haven’t saved it as a permanent fact.",
                        "kind": "conversation",
                    }
            return {
                "message": "You haven’t told me your name in the recent conversation or saved it as a fact yet.",
                "kind": "conversation",
            }
        if lower in {
            "what's happening today",
            "what is happening today",
            "what's going on today",
            "what is going on today",
            "what should i focus on today",
            "what should i do today",
            "what do i need to do today",
            "what needs my attention",
            "give me a briefing",
            "give me my briefing",
            "status report",
            "morning briefing",
            "briefing",
            "apa aja hari ini",
            "ada apa hari ini",
            "apa kabar hari ini",
            "ringkasan hari ini",
        }:
            return self._digest()
        if lower in {"help plan my day", "plan my day"} and not self._can_use_ai():
            return self._digest()
        if (
            re.fullmatch(
                r"(?:show|list|check|lihat|tampilkan)?\s*(?:me\s+)?(?:(?:my|our|the|open|unfinished|pending|daftar)\s+)*(?:tasks|assignments|tugas)(?: saya|ku)?",
                lower,
            )
            or "belum selesai" in lower
        ):
            return self._digest("tasks")
        owner = re.fullmatch(r"what should (.+) prioritize", text, re.I)
        if owner:
            return self._digest("tasks", owner[1])
        if (
            "finished this week" in lower
            or "completed this week" in lower
            or "selesai minggu ini" in lower
        ):
            return self._digest("weekly")
        if lower in {
            "show my schedule",
            "what's on my calendar",
            "show my events",
            "upcoming events",
            "next events",
            "jadwal saya",
            "agenda saya",
            "show my calendar",
        }:
            report = build_briefing(self.store)
            rows = report["upcoming_events"]
            reply = (
                "Here’s what’s coming up in the next seven days:"
                + "".join(
                    f"\n• {row['title']} — {row['day']}"
                    + (f" at {row['time']}" if row["time"] else ", time not set")
                    for row in rows
                )
                if rows
                else "There are no events saved for the next seven days. Tell me what you’re planning and when."
            )
            return {
                "message": reply,
                "kind": "verified_information",
                "evidence": {"workspace": self.store.workspace_id, "events": rows},
            }
        if lower in {
            "show my projects",
            "what projects are active",
            "our projects",
            "my projects",
            "lihat proyek",
        }:
            rows = self.store.state()["projects"]
            return {
                "message": (
                    "Here are your saved projects:"
                    + "".join(
                        f"\n• #{row['id']} {row['title']} — {row['status']}"
                        for row in rows[:8]
                    )
                    if rows
                    else "No projects are saved in this workspace yet. What are you planning?"
                ),
                "kind": "verified_information",
                "evidence": {
                    "workspace": self.store.workspace_id,
                    "projects": rows[:8],
                },
            }
        if lower in {
            "what needs approval",
            "show pending approvals",
            "what is waiting for approval",
            "what's waiting for approval",
        }:
            rows = [
                row
                for row in self.store.state()["pending"]
                if row["expires_at"] > now()
            ]
            return {
                "message": (
                    "These changes are waiting for your review:"
                    + "".join("\n• " + row["description"] for row in rows[:5])
                    if rows
                    else "There are no Core changes waiting for approval."
                ),
                "kind": "verified_information",
            }
        if (
            self.world_service
            and re.search(
                r"\b(bitcoin|btc|ethereum|eth|usd.?idr|dollar.*rupiah|market update|market prices)\b",
                lower,
            )
            and (
                re.search(
                    r"\b(price|prices|rate|rates|worth|value|current|now|today|harga|kurs|berapa|market update)\b",
                    lower,
                )
                or lower in {"bitcoin", "btc", "ethereum", "eth", "usd/idr", "usdidr"}
                or re.fullmatch(
                    r"(?:what's|what is) (?:bitcoin|btc|ethereum|eth) at", lower
                )
            )
            and not re.search(r"\b(buy|sell|invest|trade|purchase)\b", lower)
        ):
            data = self.world_service.get()
            sentences = []
            for coin, label in [("bitcoin", "Bitcoin"), ("ethereum", "Ethereum")]:
                if (
                    coin in lower
                    or ("btc" if coin == "bitcoin" else "eth") in lower
                    or "market" in lower
                ):
                    quote = (data.get("prices") or {}).get(coin)
                    sentences.append(
                        f"{label} is ${quote['usd']:,.2f} from {quote.get('source','the public feed')}"
                        + (
                            " (last known price; refresh unavailable)."
                            if quote.get("stale")
                            else "."
                        )
                        if quote
                        else f"I couldn’t retrieve {label} right now. I haven’t substituted a price."
                    )
            if re.search(r"usd|idr|dollar|rupiah|market", lower):
                rate = data.get("exchange")
                sentences.append(
                    f"The published USD/IDR reference is {rate['usd_idr']:,.2f} rupiah per dollar. This is a reference rate, not a live trading quote."
                    if rate
                    else "The USD/IDR reference feed is unavailable right now."
                )
            return {
                "message": " ".join(sentences),
                "kind": "verified_information",
                "evidence": data,
            }
        addition = re.fullmatch(
            r"(?:add|create|make)(?: me)?(?: a)? task(?: called| named| to)?\s+(.+)|(?:remind me to|ingatkan saya untuk|tambah(?:kan)? tugas)\s+(.+)",
            text,
            re.I,
        )
        if addition:
            self._focus(None)
            title = addition[1] or addition[2]
            due = ""
            priority = "medium"
            match = re.search(
                r"\s+(?:(?:by|on|for)\s+)?(today|tomorrow|besok|hari ini|\d{4}-\d{2}-\d{2})$",
                title,
                re.I,
            )
            if match:
                value = match[1].casefold()
                due = (
                    (
                        today_local()
                        + timedelta(days=1 if value in {"tomorrow", "besok"} else 0)
                    ).isoformat()
                    if value in {"today", "tomorrow", "besok", "hari ini"}
                    else iso_day(value)
                )
                title = title[: match.start()].strip()
            match = re.search(
                r"\s+(?:(?:with|as)\s+)?(high|medium|low) priority$", title, re.I
            )
            if match:
                priority = match[1].lower()
                title = title[: match.start()].strip()
            return {
                "message": "",
                "pending": self.store.propose(
                    "create_task",
                    {"title": title, "due_date": due, "priority": priority},
                ),
            }
        if lower in {
            "mark it done",
            "mark that done",
            "complete that task",
            "selesaikan tugas itu",
        }:
            with self.store._conn() as con:
                row = con.execute(
                    "SELECT last_task_id FROM conversation_references WHERE singleton=1"
                ).fetchone()
            if not row or row[0] is None:
                return {
                    "message": "Which saved task do you mean? Give me its number so I prepare the right change.",
                    "kind": "clarification",
                }
            return {
                "message": "",
                "pending": self.store.propose(
                    "set_task_status", {"task_id": row[0], "status": "done"}
                ),
            }
        status = re.fullmatch(
            r"(?:mark|set) task\s+(\d+)\s+(?:as )?(done|complete|completed|doing|in progress|todo)|(?:complete|finish|start) task\s+(\d+)",
            lower,
        )
        if status:
            task_id = int(status[1] or status[3])
            with self.store._conn() as con:
                if not con.execute(
                    "SELECT id FROM tasks WHERE id=?", (task_id,)
                ).fetchone():
                    return {
                        "message": f"I can’t find task #{task_id} in this workspace.",
                        "kind": "clarification",
                    }
            state = (
                "doing"
                if lower.startswith("start ") or status[2] in {"doing", "in progress"}
                else "todo" if status[2] == "todo" else "done"
            )
            return {
                "message": "",
                "pending": self.store.propose(
                    "set_task_status", {"task_id": task_id, "status": state}
                ),
            }
        if lower in {
            "make it high priority",
            "make that high priority",
            "make it low priority",
            "set its deadline to tomorrow",
            "make it due tomorrow",
        }:
            with self.store._conn() as con:
                row = con.execute(
                    "SELECT t.*,d.description,d.project_id,d.milestone_id,d.follow_up_context FROM conversation_references r JOIN tasks t ON t.id=r.last_task_id LEFT JOIN task_details d ON d.task_id=t.id WHERE r.singleton=1"
                ).fetchone()
            if row is None:
                return {
                    "message": "Which task do you mean? Give me its number or open its task details first.",
                    "kind": "clarification",
                }
            args = {
                key: row[key]
                for key in (
                    "title",
                    "owner",
                    "due_date",
                    "priority",
                    "description",
                    "project_id",
                    "milestone_id",
                    "follow_up_context",
                )
            }
            args["task_id"] = row["id"]
            if "priority" in lower:
                args["priority"] = "low" if "low priority" in lower else "high"
            else:
                args["due_date"] = (today_local() + timedelta(days=1)).isoformat()
            return {"message": "", "pending": self.store.propose("update_task", args)}
        note = re.fullmatch(r"(?:add|save|create)(?: a)? note\s+(.+)", text, re.I)
        if note:
            return {
                "message": "",
                "pending": self.store.propose(
                    "create_note", {"title": "Quick note", "body": note[1]}
                ),
            }
        search = re.fullmatch(r"(?:search for|find|look for|cari)\s+(.+)", text, re.I)
        if search:
            data = self.store.search(search[1])
            rows = data["facts"][:3] + data["projects"][:3] + data["notes"][:3]
            reply = (
                "Here’s what I found:"
                + "".join(
                    "\n• "
                    + (row.get("key") or row.get("title"))
                    + ": "
                    + (row.get("value") or row.get("goal") or row.get("body") or "")[
                        :250
                    ]
                    for row in rows
                )
                if rows
                else "I couldn’t find that in your saved facts, projects or notes. What else should I look for?"
            )
            return {"message": reply, "kind": "verified_information", "evidence": data}
        return None

    def report(self, result):
        item = result.get("pending")
        if item:
            name, args = item["name"], item["args"]
            if name == "create_task":
                result["message"] = (
                    f"I’ve drafted “{args['title']}”"
                    + (f" for {args['due_date']}" if args.get("due_date") else "")
                    + ". Review it in the Approval inbox before it’s saved."
                )
            elif name == "execute_plan":
                result["message"] = (
                    f"I’ve prepared a plan with {_number_word(len(args['steps']), 'change')}. Review the whole plan in the Approval inbox."
                )
            else:
                result["message"] = (
                    "I’ve prepared that change for your review. Check the Approval inbox; it hasn’t been applied yet."
                )
        elif result.get("kind") == "draft":
            result["message"] = result["message"].removeprefix(
                "AI draft — no actions executed.\n\n"
            )
        if result.get("message", "").startswith(
            "Verified local tool results:"
        ) and result.get("evidence"):
            summaries = []
            for evidence in result["evidence"]:
                tool, data = evidence["tool"], evidence["result"]
                if tool == "read_tasks":
                    summaries.append(
                        "Here are the matching tasks:"
                        + "".join(
                            f"\n• #{row['id']} {row['title']} — {row['status']}"
                            for row in data[:8]
                        )
                        if data
                        else "No tasks match that request."
                    )
                elif tool == "generate_briefing":
                    summaries.append(
                        f"You have {_number_word(data['counts']['open_tasks'], 'open task')} and {_number_word(data['counts']['overdue'], 'overdue task')}."
                    )
                elif tool == "get_project":
                    summaries.append(
                        f"{data['project']['title']}: {data['project']['goal']}\nStatus: {data['project']['status']}. {_number_word(len(data['tasks']), 'linked task')} returned."
                    )
                elif tool == "review_events":
                    summaries.append(
                        "Your matching events:"
                        + "".join(
                            f"\n• {row['title']} — {row['day']}" for row in data[:6]
                        )
                        if data
                        else "There are no events in that date range."
                    )
                else:
                    summaries.append(
                        "I found matching saved information."
                        + "".join(
                            "\n• " + row["key"] + ": " + row["value"][:250]
                            for row in data.get("facts", [])[:5]
                        )
                    )
            result["message"] = "\n\n".join(summaries)
        if result.get("message", "").startswith("The AI service is unavailable"):
            result["message"] = (
                "I couldn’t reach OpenAI for that reply. Your local tasks and schedule are still available. Check the conversation setup in Settings, then try again."
            )
        result.setdefault("voice_message", _spoken_text(result.get("message", "")))
        return super().report(result)

    def _ai(self, message, history):
        original = self.provider
        self.provider = _ConversationTone(original or OpenAIResponsesProvider())
        try:
            return super()._ai(message, history)
        finally:
            self.provider = original

    def chat(self, message):
        self.store.require("propose")
        message = clean_text(message, "Message", 3000)
        history = self.store.recent_messages(limit=8)
        command_id = self.store.start_command(
            message, "local_command" if message.startswith("/") else "conversation"
        )
        self.store.record("user", message)
        try:
            result = self._local(message, history)
            if result is None:
                result = handle_intent(self.store, message, classify_intent(message))
            if result is None:
                result = offline_command(self.store, message)
            if result is None and self._can_use_ai():
                result = self._ai(message, history)
            if result is None:
                result = {
                    "message": "I can help with your saved tasks, schedule, projects and notes right now. For a free-form conversation about anything else, connect OpenAI in Settings. What would you like to work on?",
                    "kind": "unavailable",
                    "reason": conversation_setup(self.allow_ai, self.store)["reason"],
                    "suggestions": ["What should I focus on today?", "Show my tasks"],
                }
        except ValueError as exc:
            self.store.log_event("validation_error", type(exc).__name__)
            result = {
                "message": f"I couldn’t prepare that: {exc}",
                "status": "error",
                "kind": "clarification",
            }
        except Exception as exc:
            self.store.log_event("service_error", type(exc).__name__)
            result = {
                "message": "I couldn’t complete that request. Your saved information is still available; try again or open Settings to check the AI connection.",
                "status": "error",
                "kind": "unavailable",
            }
        result["message"] = result["message"][:6000]
        result = self.report(result)
        self.store.record("assistant", result["message"])
        self.store.finish_command(command_id, result)
        result["command_id"] = command_id
        result["lifecycle"] = self.store.command(command_id)
        return result


# Preserve the entry point name used by the HTTP server and CLI.
Coordinator = ConversationCoordinator


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def make_ics(events: list[dict], workspace_id="osis") -> bytes:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NEXUS OSIS//Local Event Export//EN",
        "CALSCALE:GREGORIAN",
    ]
    for e in events:
        day = e["day"].replace("-", "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:nexus-{workspace_id}-{e['id']}@localhost",
                f"DTSTAMP:{dtstamp}",
            ]
        )
        if e["time"]:
            lines.append(f"DTSTART:{day}T{e['time'].replace(':', '')}00")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{day}")
        lines.extend(
            [
                f"SUMMARY:{ics_escape(e['title'])}",
                f"LOCATION:{ics_escape(e['location'])}",
                f"DESCRIPTION:{ics_escape(e['details'])}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def handler_factory(
    base_store: Store, port: int, *, registry=None, allow_ai=False, demo=False
):
    provider_observations = {}
    observations_lock = threading.Lock()
    world_service = WorldFeedCache()

    def cached_world():
        return world_service.get()

    class Handler(BaseHTTPRequestHandler):
        server_version = "NEXUS/0.5"

        def log_message(self, format, *args):
            # Avoid logging sensitive commands or meeting-note content.
            pass

        def send_bytes(self, data: bytes, content_type: str, filename: str = ""):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                csp_for(data, content_type),
            )
            if filename:
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
            self.end_headers()
            self.wfile.write(data)

        def host_is_local(self) -> bool:
            # HTTP Host check limits DNS-rebinding style requests. This is not user authentication.
            actual_port = self.server.server_port
            return self.headers.get("Host", "") in (
                f"127.0.0.1:{actual_port}",
                f"localhost:{actual_port}",
            )

        def json_response(self, obj: dict, code=200):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def scoped_store(self):
            values = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get(
                "workspace", [base_store.workspace_id]
            )
            if len(values) != 1:
                raise ValueError("Choose one workspace")
            if registry is not None:
                return registry.store(values[0])
            if values[0] != base_store.workspace_id:
                raise ValueError("Unknown workspace")
            return base_store

        def do_GET(self):
            try:
                self.get_request()
            except Exception as exc:
                logging.error("NEXUS read failed: %s", type(exc).__name__)
                self.json_response(
                    {"error": "Internal error. Refresh your workspace."}, code=500
                )

        def get_request(self):
            if not self.host_is_local():
                self.json_response({"error": "Untrusted host"}, code=403)
                return
            route = urlsplit(self.path).path
            if route in STATIC:
                location, content_type = STATIC[route]
                self.send_bytes((ROOT / location).read_bytes(), content_type)
                return
            try:
                store = self.scoped_store()
            except PermissionError as exc:
                self.json_response({"error": str(exc)}, code=403)
                return
            except ValueError as exc:
                self.json_response({"error": str(exc)}, code=400)
                return
            if route == "/api/world":
                store.require("read")
                self.json_response(cached_world())
                return
            try:
                extended = get_data(
                    store,
                    route,
                    parse_qs(urlsplit(self.path).query, keep_blank_values=True),
                )
            except LookupError as exc:
                self.json_response({"error": str(exc)}, code=404)
                return
            except ValueError as exc:
                self.json_response({"error": str(exc)}, code=400)
                return
            if extended is not None:
                self.json_response(extended)
                return
            if route == "/api/workspaces":
                self.json_response(
                    {
                        "workspaces": (
                            registry.list()
                            if registry
                            else [
                                {
                                    "id": store.workspace_id,
                                    "label": store.workspace_id.upper(),
                                    "domain": "school",
                                    "capabilities": sorted(store.capabilities),
                                }
                            ]
                        )
                    }
                )
                return
            if route == "/api/search":
                try:
                    query = parse_qs(urlsplit(self.path).query).get("q", [""])[0]
                    self.json_response(store.search(query))
                except ValueError as exc:
                    self.json_response({"error": str(exc)}, code=400)
                return
            if route == "/api/state":
                state = store.state()
                state["timezone"] = configured_timezone()
                state["demo"] = demo
                state["capabilities"] = sorted(store.capabilities)
                with store._conn() as con:
                    state["summary"]["task_status"] = {
                        row["status"]: row["total"]
                        for row in con.execute(
                            "SELECT status,count(*) AS total FROM tasks GROUP BY status"
                        )
                    }
                configured = bool(
                    allow_ai
                    and "ai" in store.capabilities
                    and os.environ.get("OPENAI_API_KEY")
                )
                with observations_lock:
                    observation = dict(
                        provider_observations.get(store.workspace_id, {})
                    )
                state["system"] = {
                    "version": "0.5 development",
                    "local": "online",
                    "ai": (
                        observation.get("status", "configured")
                        if configured
                        else "disabled"
                    ),
                    "ai_checked_at": observation.get("at"),
                    "model": (
                        os.getenv("NEXUS_MODEL", "gpt-4.1-mini") if configured else None
                    ),
                }
                state["conversation_setup"] = conversation_setup(allow_ai, store, demo)
                state["mode"] = (
                    "Demo · temporary sample records"
                    if demo
                    else (
                        "AI + local commands"
                        if allow_ai
                        and "ai" in store.capabilities
                        and os.environ.get("OPENAI_API_KEY")
                        else "Private offline commands"
                    )
                )
                self.json_response(state)
                return
            if (
                route in {"/api/backup", "/api/calendar.ics"}
                and "export" not in store.capabilities
            ):
                self.json_response(
                    {"error": "Workspace permission required: export"}, code=403
                )
                return
            if route == "/api/backup":
                self.send_bytes(
                    json.dumps(store.export(), indent=2, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                    "application/json; charset=utf-8",
                    f"nexus-{store.workspace_id}-backup.json",
                )
                return
            if route == "/api/calendar.ics":
                self.send_bytes(
                    make_ics(store.state()["events"], store.workspace_id),
                    "text/calendar; charset=utf-8",
                    f"nexus-{store.workspace_id}-calendar.ics",
                )
                return
            if route == "/api/help":
                self.json_response({"message": HELP})
                return
            self.json_response({"error": "Not found"}, code=404)

        def do_POST(self):
            if not self.host_is_local():
                self.json_response({"error": "Untrusted host"}, code=403)
                return
            route = urlsplit(self.path).path
            # Defense against other web pages making requests to localhost.
            origin = self.headers.get("Origin")
            if origin and origin not in (
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            ):
                self.json_response({"error": "Origin blocked"}, code=403)
                return
            if (
                self.headers.get("X-NEXUS-Local") != "1"
                or self.headers.get("Content-Type", "").split(";")[0]
                != "application/json"
            ):
                self.json_response(
                    {"error": "Local UI JSON request required"}, code=403
                )
                return
            try:
                store = self.scoped_store()
                coordinator = Coordinator(
                    store, allow_ai=allow_ai, world_service=world_service
                )
                length = int(self.headers.get("Content-Length", "0"))
                if not (1 <= length <= (64000 if route == "/api/propose" else 16000)):
                    raise ValueError("Request too large or empty.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
                if route in {"/api/chat", "/api/commands"}:
                    result = coordinator.chat(data.get("message", ""))
                    if result.get("provider_status") in {
                        "verified",
                        "error",
                        "unavailable",
                    }:
                        with observations_lock:
                            provider_observations[store.workspace_id] = {
                                "status": (
                                    "verified"
                                    if result["provider_status"] == "verified"
                                    else "error"
                                ),
                                "at": datetime.now(timezone.utc).isoformat(
                                    timespec="seconds"
                                ),
                            }
                elif route == "/api/propose":
                    item = store.propose(data.get("name"), data.get("args"))
                    result = coordinator.report(
                        {
                            "message": "Proposal prepared. Review the exact values before approving.",
                            "pending": item,
                        }
                    )
                elif route == "/api/decide":
                    action_id = data.get("id")
                    if not isinstance(action_id, str) or len(action_id) > 128:
                        raise ValueError("Invalid action ID")
                    approve = data.get("approve")
                    if not isinstance(approve, bool):
                        raise ValueError("Approval must be true or false")
                    result_text = store.decide(action_id, approve)
                    if "propose" in store.capabilities:
                        store.record("assistant", result_text)
                    result = {
                        "message": result_text,
                        "outcome": store.approval_status(action_id),
                        "workspace": store.workspace_id,
                    }
                else:
                    self.json_response({"error": "Not found"}, code=404)
                    return
                self.json_response(result)
            except PermissionError as exc:
                self.json_response({"error": str(exc)}, code=403)
            except (ValueError, json.JSONDecodeError) as exc:
                self.json_response({"error": str(exc)}, code=400)
            except Exception as exc:
                logging.error("NEXUS request failed: %s", type(exc).__name__)
                self.json_response(
                    {
                        "error": "Internal error. No successful action is confirmed; refresh your workspace."
                    },
                    code=500,
                )

    return Handler


def cli(store: Store, *, allow_ai=False):
    assistant = Coordinator(store, allow_ai=allow_ai, world_service=WorldFeedCache())
    print("\nNEXUS Core v0.5 — private local command center")
    print(
        "Type /help for commands. Type /quit to exit. Approval is required for every change.\n"
    )
    while True:
        try:
            command = input("YOU > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNEXUS offline.")
            break
        if command.lower() in ("/quit", "/exit"):
            break
        if not command:
            continue
        if command.lower() == "/plan":
            print("Enter up to five write commands, then a blank line:")
            lines = []
            try:
                while len(lines) < 5:
                    line = input("STEP > ").strip()
                    if not line:
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                print("Plan entry cancelled.")
                continue
            command += "\n" + "\n".join(lines)
        result = assistant.chat(command)
        print("\nNEXUS >", result["message"])
        pending = result.get("pending")
        if pending:
            print("\nREQUIRES APPROVAL:", pending["description"])
            print(json.dumps(pending["args"], ensure_ascii=False, indent=2))
            answer = input("Approve? Type YES to confirm: ").strip()
            try:
                print("NEXUS >", store.decide(pending["id"], answer == "YES"))
            except ValueError as exc:
                print("NEXUS >", exc)
        print()


def main():
    parser = argparse.ArgumentParser(description="NEXUS — local personal AI core")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use invented temporary records; discarded on exit, AI disabled",
    )
    parser.add_argument(
        "--workspace",
        default="osis",
        choices=[
            "osis",
            "personal",
            "academic",
            "research",
            "coding",
            "finance",
            "atlas",
        ],
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Separate workspace database directory",
    )
    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help="Opt in to sending active-workspace context to OpenAI",
    )
    parser.add_argument("--cli", action="store_true", help="Text-only terminal mode")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open your browser automatically",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Local web port (default 8765)"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help="Path to SQLite database"
    )
    args = parser.parse_args()
    if not args.cli and not 1024 <= args.port <= 65535:
        parser.error("Port must be 1024..65535")
    if args.demo:
        if args.enable_ai:
            parser.error("Demo mode is offline; omit --enable-ai")
        with tempfile.TemporaryDirectory(prefix="nexus-demo-") as directory:
            args.db = Path(directory) / "osis.sqlite3"
            args.workspace_root = Path(directory) / "workspaces"
            print("DEMO: invented temporary records; changes are discarded on exit.")
            run(args)
    else:
        run(args)


def run(args):
    with WorkspaceRegistry(
        args.db,
        args.workspace_root or args.db.parent / "workspaces",
        runtime_locks=True,
    ) as registry:
        run_workspace(args, registry)


def run_workspace(args, registry):
    if args.demo:
        from nexus.demo import seed_demo

        seed_demo(registry)
    store = registry.store(args.workspace)
    if args.cli:
        cli(store, allow_ai=args.enable_ai)
        return
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", args.port),
            handler_factory(
                store,
                args.port,
                registry=registry,
                allow_ai=args.enable_ai,
                demo=args.demo,
            ),
        )
    except OSError as exc:
        sys.exit(f"Could not start NEXUS on port {args.port}: {exc}. Try --port 8766")
    url = f"http://127.0.0.1:{args.port}"
    print("\nNEXUS Core v0.5")
    print("Local dashboard:", url)
    print("Local records:", store.path)
    print(
        "Brain mode:",
        (
            "Optional AI enabled"
            if args.enable_ai and os.environ.get("OPENAI_API_KEY")
            else "Offline command mode"
        ),
    )
    print("To stop: press Control + C\n")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nNEXUS stopped. Data remains on disk.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
