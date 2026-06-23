import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz


class NewsMonitor:
    """ForexFactory ekonomik takvimini takip eder."""

    def __init__(self, high_impact_only: bool = True):
        self.high_impact_only = high_impact_only
        self.utc = pytz.UTC

    def get_today_events(self) -> list:
        """ForexFactory'den bugünün haberlerini çek."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
            url = "https://www.forexfactory.com/calendar"
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")

            events = []
            rows = soup.find_all("tr", class_=lambda x: x and "calendar__row" in x)
            current_date = None

            for row in rows:
                # Tarih
                date_cell = row.find("td", class_="calendar__date")
                if date_cell and date_cell.text.strip():
                    current_date = date_cell.text.strip()

                # Saat
                time_cell = row.find("td", class_="calendar__time")
                # Para birimi
                currency_cell = row.find("td", class_="calendar__currency")
                # Etki
                impact_cell = row.find("td", class_="calendar__impact")
                # Event adı
                event_cell = row.find("td", class_="calendar__event")

                if not (time_cell and currency_cell and impact_cell and event_cell):
                    continue

                impact_span = impact_cell.find("span")
                impact = ""
                if impact_span:
                    cls = impact_span.get("class", [])
                    if "high" in " ".join(cls):
                        impact = "HIGH"
                    elif "medium" in " ".join(cls):
                        impact = "MEDIUM"
                    else:
                        impact = "LOW"

                if self.high_impact_only and impact != "HIGH":
                    continue

                events.append({
                    "date": current_date,
                    "time": time_cell.text.strip(),
                    "currency": currency_cell.text.strip(),
                    "impact": impact,
                    "event": event_cell.text.strip(),
                })

            return events

        except Exception as e:
            print(f"[NEWS] ForexFactory çekilemedi: {e}")
            return self._fallback_major_events()

    def _fallback_major_events(self) -> list:
        """API başarısız olursa bilinen major event saatlerini döndür."""
        now_utc = datetime.utcnow()
        return [
            {"date": now_utc.strftime("%a %b %d"),
             "time": "Bilinmiyor", "currency": "USD",
             "impact": "HIGH", "event": "Takvim çekilemedi - dikkatli ol"},
        ]

    def is_news_window(self, minutes_before: int = 30, minutes_after: int = 30) -> tuple:
        """
        Şu an bir haber penceresinde miyiz?
        Returns: (bool, event_name)
        """
        events = self.get_today_events()
        now_utc = datetime.utcnow().replace(tzinfo=self.utc)

        for event in events:
            time_str = event.get("time", "").strip()
            if not time_str or time_str.lower() in ("all day", "tentative", ""):
                continue
            try:
                # ForexFactory saatleri ET (Eastern Time)
                et = pytz.timezone("America/New_York")
                today = datetime.now(et).date()
                hour, minute = self._parse_time(time_str)
                event_et = et.localize(datetime(today.year, today.month, today.day, hour, minute))
                event_utc = event_et.astimezone(self.utc)

                window_start = event_utc - timedelta(minutes=minutes_before)
                window_end   = event_utc + timedelta(minutes=minutes_after)

                if window_start <= now_utc <= window_end:
                    return True, f"{event['currency']} - {event['event']}"
            except Exception:
                continue

        return False, ""

    def _parse_time(self, time_str: str) -> tuple:
        """'8:30am' → (8, 30)"""
        time_str = time_str.lower().strip()
        am_pm = "am" if "am" in time_str else "pm"
        time_str = time_str.replace("am", "").replace("pm", "").strip()
        h, m = (time_str.split(":") + ["0"])[:2]
        hour = int(h)
        minute = int(m)
        if am_pm == "pm" and hour != 12:
            hour += 12
        if am_pm == "am" and hour == 12:
            hour = 0
        return hour, minute

    def get_upcoming_events(self, hours: int = 4) -> list:
        """Önümüzdeki N saat içindeki olayları döndür."""
        events = self.get_today_events()
        upcoming = []
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)

        for event in events:
            time_str = event.get("time", "").strip()
            if not time_str or time_str.lower() in ("all day", "tentative"):
                continue
            try:
                hour, minute = self._parse_time(time_str)
                event_et = et.localize(datetime(now_et.year, now_et.month, now_et.day, hour, minute))
                if now_et <= event_et <= now_et + timedelta(hours=hours):
                    event["minutes_away"] = int((event_et - now_et).total_seconds() / 60)
                    upcoming.append(event)
            except Exception:
                continue

        return upcoming
