"""
News Monitor — ForexFactory JSON API kullanır (Cloudflare bypass).
Bu hafta + gelecek hafta verisi çekilir, HIGH impact olaylar filtrelenir.
"""
import requests
from datetime import datetime, timedelta
import pytz


FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

# Gold için kritik para birimleri
GOLD_CURRENCIES = {"USD", "XAU", "CNY", "EUR", "GBP", "JPY"}


class NewsMonitor:
    """ForexFactory JSON API ile ekonomik takvim takibi."""

    def __init__(self, high_impact_only: bool = True):
        self.high_impact_only = high_impact_only
        self._cache: list = []
        self._cache_time = None
        self._cache_ttl = 3600  # 1 saat cache

    def get_today_events(self) -> list:
        """Bu haftanın HIGH impact olaylarını döndür (cache'li)."""
        now = datetime.utcnow()

        # Cache geçerliyse tekrar çekme
        if self._cache and self._cache_time:
            age = (now - self._cache_time).total_seconds()
            if age < self._cache_ttl:
                return self._filter(self._cache)

        events = []
        for url in FF_URLS:
            try:
                r = requests.get(url, timeout=10,
                                 headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    events.extend(r.json())
            except Exception as e:
                print(f"[NEWS] {url} cekilemedi: {e}")

        if events:
            self._cache = events
            self._cache_time = now
        elif not self._cache:
            return self._fallback_major_events()

        return self._filter(self._cache)

    def _filter(self, events: list) -> list:
        if not self.high_impact_only:
            return events
        return [e for e in events if e.get("impact", "").lower() == "high"]

    def _parse_event_time(self, event: dict):
        """Event tarih/saatini UTC datetime'a cevir."""
        raw = event.get("date", "")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                et = pytz.timezone("America/New_York")
                dt = et.localize(dt)
            return dt.astimezone(pytz.UTC)
        except Exception:
            return None

    def is_news_window(self, minutes_before: int = 30,
                       minutes_after: int = 30) -> tuple:
        """
        Su an haber penceresi icinde miyiz?
        Returns: (bool, event_name)
        """
        events = self.get_today_events()
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)

        for event in events:
            ev_utc = self._parse_event_time(event)
            if ev_utc is None:
                continue
            window_start = ev_utc - timedelta(minutes=minutes_before)
            window_end   = ev_utc + timedelta(minutes=minutes_after)
            if window_start <= now_utc <= window_end:
                name = f"{event.get('country', '?')} - {event.get('title', '?')}"
                return True, name

        return False, ""

    def get_upcoming_events(self, hours: int = 4) -> list:
        """Onumuzdeki N saat icindeki HIGH impact olaylari dondur."""
        events = self.get_today_events()
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
        upcoming = []

        for event in events:
            ev_utc = self._parse_event_time(event)
            if ev_utc is None:
                continue
            diff = (ev_utc - now_utc).total_seconds()
            if 0 < diff <= hours * 3600:
                e = dict(event)
                e["minutes_away"] = int(diff / 60)
                e["currency"]     = event.get("country", "")
                e["event"]        = event.get("title", "")
                upcoming.append(e)

        return sorted(upcoming, key=lambda x: x["minutes_away"])

    def is_gold_news_window(self, minutes_before: int = 30,
                             minutes_after: int = 30) -> tuple:
        """
        Gold'u etkileyen haber penceresi (USD + major currencies).
        """
        events = self.get_today_events()
        now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)

        for event in events:
            currency = event.get("country", "").upper()
            if currency not in GOLD_CURRENCIES:
                continue
            ev_utc = self._parse_event_time(event)
            if ev_utc is None:
                continue
            window_start = ev_utc - timedelta(minutes=minutes_before)
            window_end   = ev_utc + timedelta(minutes=minutes_after)
            if window_start <= now_utc <= window_end:
                name = f"{currency} - {event.get('title', '?')}"
                return True, name

        return False, ""

    def _fallback_major_events(self) -> list:
        """API basarisiz olursa guvenli fallback."""
        print("[NEWS] Takvim API hatasi — fallback aktif, islem acilmiyor")
        now_utc = datetime.utcnow()
        return [{
            "date":     now_utc.isoformat(),
            "country":  "USD",
            "impact":   "High",
            "title":    "Takvim API hatasi — dikkatli ol",
            "forecast": "",
            "previous": "",
        }]
