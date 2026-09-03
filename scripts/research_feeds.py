"""Public, timestamped research inputs. No LLM verdict or synthetic market data."""
from __future__ import annotations

import csv
import io
import html
import json
import math
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

UTC = timezone.utc
FRED_IDS = {"real10y": "DFII10", "nominal10y": "DGS10", "nominal2y": "DGS2", "fed_upper": "DFEDTARU", "cpi": "CPIAUCSL"}
FED_NEWS = "https://www.federalreserve.gov/feeds/speeches.xml"
FED_POLICY = "https://www.federalreserve.gov/feeds/press_monetary.xml"
CFTC_URL = "https://www.cftc.gov/dea/futures/other_sf.htm"
CALENDAR_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
H15_URL = "https://www.federalreserve.gov/releases/h15/"


def h15_parse(text, now):
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, re.S | re.I)
    dates, section, result = [], "", {}
    for row in rows:
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in cells]
        if not cells:
            continue
        if cells[0] == "Instruments":
            dates = [datetime.strptime(c, "%Y %b %d").replace(tzinfo=UTC) for c in cells[1:]]
            continue
        label = cells[0]
        if label.startswith("Nominal"):
            section = "nominal"
        elif label.startswith("Inflation indexed"):
            section = "real"
        key = "fed_effective" if label.startswith("Federal funds (effective)") else "nominal2y" if section == "nominal" and label == "2-year" else "nominal10y" if section == "nominal" and label == "10-year" else "real10y" if section == "real" and label == "10-year" else None
        if not key or len(cells)-1 != len(dates):
            continue
        obs = []
        for d, v in zip(dates, cells[1:]):
            try:
                dated(stamp(d), now)
                obs.append((d, number(v)))
            except ValueError:
                continue
        if obs:
            d, v = obs[-1]
            prev = obs[-2][1] if len(obs) > 1 else None
            result[key] = {"value": v, "previous": prev, "change": round(v-prev, 4) if prev is not None else None,
                           "observed_at": stamp(d), "date_only": True, "unit": "%", "status": "available" if (now-d).days <= 7 else "stale",
                           "source": "Federal Reserve H.15", "source_url": H15_URL, "checked_at": stamp(now)}
    if not result:
        raise ValueError("H.15 table could not be validated")
    return result


def stamp(value=None):
    return (value or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_text(url):
    last = None
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": "AshkanGoldDesk/3.0", "Accept": "*/*"})
            with urlopen(req, timeout=12) as response:
                return response.read(8_000_000).decode("utf-8-sig", errors="replace")
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.5)
    raise RuntimeError("Source unavailable or request timed out") from last


def number(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a market value")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite value")
    return result


def dated(value, now):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if parsed > now + timedelta(minutes=2):
        raise ValueError("future observation")
    return parsed


def fred_parse(text, series, now):
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            day = row.get("observation_date") or row.get("DATE")
            observed = dated(day, now)
            rows.append((observed, number(row[series])))
        except (TypeError, KeyError, ValueError):
            continue
    rows.sort()
    if not rows:
        raise ValueError("No dated FRED observations")
    observed, value = rows[-1]
    previous = rows[-2][1] if len(rows) > 1 else None
    result = {"value": value, "previous": previous, "change": round(value-previous, 4) if previous is not None else None,
              "observed_at": stamp(observed), "unit": "%", "date_only": True}
    if series == "CPIAUCSL":
        prior = next((v for d, v in reversed(rows) if d.year == observed.year-1 and d.month == observed.month), None)
        if prior is None or prior <= 0:
            raise ValueError("CPI year comparison unavailable")
        result.update(value=round((value/prior-1)*100, 2), previous=None, change=None, unit="% YoY")
    return result


def fred(series, now):
    start = (now-timedelta(days=450 if series == "CPIAUCSL" else 45)).date().isoformat()
    result = fred_parse(fetch_text(f"https://fred.stlouisfed.org/graph/graph.csv?id={series}&cosd={start}"), series, now)
    result.update(source="FRED / Federal Reserve" if series != "CPIAUCSL" else "FRED / BLS", source_url=f"https://fred.stlouisfed.org/series/{series}")
    age = (now-dated(result["observed_at"], now)).total_seconds()/86400
    result["status"] = "stale" if age > (65 if series == "CPIAUCSL" else 7) else "available"
    return result


def yahoo_result(symbol, interval="1d", period="1mo"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?interval={interval}&range={period}"
    data = json.loads(fetch_text(url))
    result = data["chart"]["result"][0]
    if result["meta"]["symbol"] != symbol:
        raise ValueError("Unexpected market symbol")
    return result


def market_metric(symbol, now):
    result = yahoo_result(symbol)
    meta = result["meta"]
    value = number(meta["regularMarketPrice"])
    if value <= 0:
        raise ValueError("Invalid index price")
    observed = datetime.fromtimestamp(number(meta["regularMarketTime"]), UTC)
    dated(stamp(observed), now)
    # Compare with the previous completed daily close, not chartPreviousClose (range start).
    q = result["indicators"]["quote"][0]["close"]
    exchange_zone = ZoneInfo(meta.get("exchangeTimezoneName", "America/New_York"))
    session_day = observed.astimezone(exchange_zone).date()
    closes = sorted((ts, number(v)) for ts, v in zip(result.get("timestamp", []), q)
                    if v is not None and datetime.fromtimestamp(ts, exchange_zone).date() < session_day)
    prev = closes[-1][1] if closes else None
    return {"value": value, "previous": prev, "change": round(value-prev, 4) if prev is not None else None,
            "unit": "index", "observed_at": stamp(observed), "source": "Yahoo Finance", "source_url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/",
            "status": "available" if (now-observed).total_seconds() < 96*3600 else "stale"}


def cftc_parse(text, now):
    match = re.search(r"(?m)^GOLD - COMMODITY EXCHANGE INC\.", text)
    if not match:
        raise ValueError("Gold contract not found")
    header = text[max(0, match.start()-2000):match.start()]
    dates = re.findall(r"Positions as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", header)
    if not dates:
        raise ValueError("Position date unavailable")
    observed = datetime.strptime(dates[-1], "%B %d, %Y").replace(tzinfo=UTC)
    dated(stamp(observed), now)
    part = text[match.start():match.start()+1800]
    if "CFTC Code #088691" not in part:
        raise ValueError("Wrong futures contract")
    positions = re.search(r": Positions[^\n]*\n([^\n]+)", part)
    values = [int(v.replace(",", "")) for v in re.findall(r"\d[\d,]*", positions.group(1))] if positions else []
    if len(values) != 11:
        raise ValueError("Unexpected CFTC category layout")
    oi = re.search(r"Open Interest is\s+([\d,]+)", part)
    if not oi:
        raise ValueError("Open interest missing")
    long, short = values[5], values[6]
    return {"long": long, "short": short, "net": long-short, "open_interest": int(oi.group(1).replace(",", "")),
            "observed_at": stamp(observed), "date_only": True, "status": "stale" if (now-observed).days > 10 else "lagged",
            "source": "CFTC · COMEX Gold futures only", "source_url": CFTC_URL}


def news_parse(text, now):
    root = ET.fromstring(text.lstrip("\ufeff"))
    rows = []
    for item in root.findall("./channel/item"):
        try:
            title, link = item.findtext("title"), item.findtext("link")
            dt = parsedate_to_datetime(item.findtext("pubDate")).astimezone(UTC)
            dated(stamp(dt), now)
            if not title or urlparse(link).hostname != "www.federalreserve.gov" or (now-dt).days > 30:
                continue
            rows.append({"title": title, "url": link, "published_at": stamp(dt), "source": "Federal Reserve"})
        except (ValueError, TypeError, AttributeError):
            continue
    return sorted(rows, key=lambda x: x["published_at"], reverse=True)[:6]


def calendar_parse(text, now):
    text = re.sub(r"\r?\n[ \t]", "", text)
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Invalid calendar")
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        start = re.search(r"(?m)^DTSTART([^:]*):([^\r\n]+)", block)
        title = re.search(r"(?m)^SUMMARY:([^\r\n]+)", block)
        if not start or not title:
            continue
        try:
            timezone_match = re.search(r'TZID=([^;]+)', start[1])
            if not start[2].endswith("Z") and not timezone_match:
                continue  # A floating time has no verifiable timezone.
            zone = UTC if start[2].endswith("Z") else ZoneInfo(timezone_match[1].strip('"'))
            dt = datetime.strptime(start[2].rstrip("Z"), "%Y%m%dT%H%M%S").replace(tzinfo=zone).astimezone(UTC)
            if not now-timedelta(hours=24) <= dt <= now+timedelta(days=14):
                continue
            label = title[1].replace("\\,", ",")
            if not any(w in label.lower() for w in ["employment situation", "consumer price", "producer price", "job openings", "productivity"]):
                continue
            events.append({"title": label, "scheduled_at": stamp(dt), "source": "BLS", "url": "https://www.bls.gov/schedule/", "impact": "high"})
        except (ValueError, KeyError):
            continue
    return sorted(events, key=lambda x: x["scheduled_at"])


def safe_job(key, job, now):
    try:
        value = job()
        if isinstance(value, list):
            value = {"items": value, "status": "available" if value else "empty"}
        return key, {**value, "checked_at": stamp(now)}
    except Exception:
        return key, {"status": "unavailable", "checked_at": stamp(now), "reason": "Source unavailable or response failed validation"}


def collect(now):
    jobs = [(key, lambda s=series: fred(s, now)) for key, series in FRED_IDS.items()]
    jobs += [(key, lambda s=symbol: market_metric(s, now)) for key, symbol in [("dxy", "DX-Y.NYB"), ("vix", "^VIX"), ("sp500", "^GSPC")]]
    jobs += [("positioning", lambda: cftc_parse(fetch_text(CFTC_URL), now)),
             ("h15", lambda: h15_parse(fetch_text(H15_URL), now)),
             ("news", lambda: news_parse(fetch_text(FED_NEWS), now)),
             ("policy_news", lambda: news_parse(fetch_text(FED_POLICY), now)),
             ("calendar", lambda: calendar_parse(fetch_text(CALENDAR_URL), now))]
    with ThreadPoolExecutor(max_workers=8) as pool:
        result = dict(pool.map(lambda job: safe_job(job[0], job[1], now), jobs))
    h15 = result.pop("h15", {})
    for key in ["nominal10y", "nominal2y", "real10y", "fed_effective"]:
        if key in h15 and result.get(key, {}).get("status") != "available":
            result[key] = h15[key]
    for key, series in FRED_IDS.items():
        result[key].setdefault("source", "FRED")
        result[key].setdefault("source_url", f"https://fred.stlouisfed.org/series/{series}")
    for key, url in [("news", FED_NEWS), ("policy_news", FED_POLICY), ("calendar", CALENDAR_URL), ("positioning", CFTC_URL)]:
        result[key].setdefault("source_url", url)
    result["coverage"] = {"news": "Federal Reserve only; not a comprehensive geopolitical news feed", "positioning": "Weekly futures positions, not current spot order flow", "etf_flows": "unavailable", "options": "unavailable", "fed_probabilities": "unavailable"}
    return result
