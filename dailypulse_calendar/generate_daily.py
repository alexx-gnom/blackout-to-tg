#!/usr/bin/env python3
"""DailyPulse: prepares one date's Telegram content from repo .txt lists (stdlib only)."""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import random
import sys
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
try:
    LOCAL_ZONE = ZoneInfo('Europe/Kyiv')
except ZoneInfoNotFoundError:  # Windows Python may have no tz database
    LOCAL_ZONE = None
GITHUB_RAW = 'https://raw.githubusercontent.com/alexx-gnom/blackout-to-tg/main/'
CAPTION_SAFE_LIMIT = 950  # Telegram max 1024; leave margin
PRIORITY = {'U': 0, 'I': 1, 'F': 2, 'A': 3}


def lines(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f'Missing input: {path.relative_to(ROOT)}')
    return [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def seeded_shuffle(values: list, *parts: object) -> list:
    seed = int.from_bytes(hashlib.sha256('|'.join(map(str, parts)).encode()).digest()[:8], 'big')
    output = list(values)
    random.Random(seed).shuffle(output)
    return output


def season_for(day: date) -> str:
    return ('winter' if day.month in (12, 1, 2) else
            'spring' if day.month in (3, 4, 5) else
            'summer' if day.month in (6, 7, 8) else 'autumn')


def dates_in_year(year: int) -> list[date]:
    return [date(year, 1, 1) + timedelta(days=i)
            for i in range(366 if calendar.isleap(year) else 365)]


def morning_text_plan(year: int) -> dict[date, str]:
    """Use all 365 phrases once/year; respect four seasonal ranges in accompanying map."""
    content = lines(ROOT / 'morning' / 'DailyPulse_morning.txt')
    pool_map = ROOT / 'dailypulse_calendar' / 'morning_ranges.txt'
    pools: dict[str, list[str]] = {}
    taken: set[int] = set()
    for record in lines(pool_map):
        section, start, end = record.split('|', 2)
        if section in pools or section not in ('general', 'winter', 'spring', 'summer', 'autumn'):
            raise ValueError(f'Invalid/duplicate range {record!r}')
        lo, hi = int(start), int(end)
        if lo < 1 or hi > len(content) or hi < lo:
            raise ValueError(f'Out of bounds range {record!r}; phrases={len(content)}')
        for index in range(lo, hi + 1):
            if index in taken:
                raise ValueError(f'Overlapping phrase index {index}')
            taken.add(index)
        pools[section] = content[lo - 1:hi]
    if set(pools) != {'general', 'winter', 'spring', 'summer', 'autumn'}:
        raise ValueError('Expected general/winter/spring/summer/autumn in morning_ranges.txt')
    if len(taken) != len(content):
        raise ValueError('Not all morning phrases are covered by morning_ranges.txt')

    all_days = dates_in_year(year)
    result: dict[date, str] = {}
    for season in ('winter', 'spring', 'summer', 'autumn'):
        season_days = [d for d in all_days if season_for(d) == season]
        chosen = seeded_shuffle(season_days, 'morning-season-dates', year, season)[:len(pools[season])]
        if len(chosen) < len(pools[season]):
            raise ValueError(f'Too many {season} phrases for {year}')
        phrases = seeded_shuffle(pools[season], 'morning-season-phrases', year, season)
        result.update(zip(chosen, phrases))
    remainder = [d for d in all_days if d not in result]
    general = seeded_shuffle(pools['general'], 'morning-general', year)
    if len(remainder) < len(general):
        raise ValueError('Too many general phrases for calendar dates')
    # Leap year adds 1 date; only that extra date reuses a general phrase.
    while len(general) < len(remainder):
        general.extend(seeded_shuffle(pools['general'], 'leap-overflow', year))
    result.update(zip(remainder, general))
    return result


def evening_text_for(day: date) -> str:
    content = lines(ROOT / 'evening' / 'DailyPulse_evening.txt')
    if not content:
        raise ValueError('Empty evening list')
    shuffled = seeded_shuffle(content, 'evening-phrases', day.year)
    return shuffled[(day - date(day.year, 1, 1)).days % len(shuffled)]


def photo_index(day: date, *, morning: bool) -> int:
    if morning:
        season = season_for(day)
        start_year = day.year - 1 if season == 'winter' and day.month in (1, 2) else day.year
        start_month = {'winter': 12, 'spring': 3, 'summer': 6, 'autumn': 9}[season]
        start = date(start_year, start_month, 1)
        cycle_day = (day - start).days
        parts = ('morning-photo', season, start_year)
    else:
        cycle_day = (day - date(day.year, 1, 1)).days
        parts = ('evening-photo', day.year)
    cycle, offset = divmod(cycle_day, 80)
    order = seeded_shuffle(list(range(1, 81)), *parts, cycle)
    # Prevent adjacent duplicates at cycle boundaries.
    if cycle and offset == 0:
        previous = seeded_shuffle(list(range(1, 81)), *parts, cycle - 1)[-1]
        if order[0] == previous:
            order[0], order[1] = order[1], order[0]
    return order[offset]


def image_path(day: date, morning: bool) -> Path:
    name = f'{photo_index(day, morning=morning):02d}.jpg'
    if morning:
        return Path('morning') / 'pict' / season_for(day) / name
    return Path('evening') / 'pict' / name


def moving_day(year: int, month: int, weekday: int, nth: int) -> date:
    if not 1 <= month <= 12 or not 0 <= weekday <= 6 or nth not in (-1, 1, 2, 3, 4, 5):
        raise ValueError(f'Invalid moving holiday: {month}|{weekday}|{nth}')
    first = date(year, month, 1)
    if nth == -1:
        last = date(year, month, calendar.monthrange(year, month)[1])
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    result = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    if result.month != month:
        raise ValueError(f'Nonexistent nth weekday: {month}|{weekday}|{nth}')
    return result


def read_holidays(day: date) -> list[dict[str, str]]:
    events: list[tuple[str, str]] = []
    for record in lines(ROOT / 'holidays' / 'holidays_fixed.txt'):
        fields = record.split('|', 2)
        if len(fields) != 3:
            raise ValueError(f'Invalid fixed holiday: {record}')
        ddmm, kind, title = fields
        if ddmm == day.strftime('%d.%m') and kind in PRIORITY:
            events.append((kind, title))
    for record in lines(ROOT / 'holidays' / 'holidays_movable.txt'):
        fields = record.split('|', 4)
        if len(fields) != 5:
            raise ValueError(f'Invalid movable holiday: {record}')
        month, weekday, nth, kind, title = fields
        if kind in PRIORITY and moving_day(day.year, int(month), int(weekday), int(nth)) == day:
            events.append((kind, title))
    unique: list[tuple[str, str]] = []
    seen = set()
    for kind, title in sorted(events, key=lambda e: PRIORITY[e[0]]):
        if title.casefold() not in seen:
            unique.append((kind, title))
            seen.add(title.casefold())
    return [{'type': k, 'name': n} for k, n in unique]


def read_birthdays(day: date) -> list[str]:
    people = []
    for record in lines(ROOT / 'holidays' / 'birthdays.txt'):
        parts = record.split('|', 1)
        if len(parts) != 2:
            raise ValueError(f'Invalid birthday: {record}')
        if parts[0] == day.strftime('%d.%m') and parts[1].strip():
            # Put one person on one line. Duplicate dates are supported.
            people.append(parts[1].strip())
    return list(dict.fromkeys(people))


def make_morning_caption(phrase: str, holidays: list, birthdays: list[str]) -> tuple[str, str]:
    core = f'Доброго ранку! ☀️\n\n{phrase}'
    extra_blocks = []
    if holidays:
        extra_blocks.append('🎉 Сьогодні відзначаємо:\n' + '\n'.join(
            ('🇺🇦 ' if h['type'] == 'U' else '🌍 ' if h['type'] == 'I' else '🎈 ') + h['name']
            for h in holidays))
    if birthdays:
        extra_blocks.append('🎂 Сьогодні день народження:\n' + '\n'.join('🎁 ' + p for p in birthdays))
    if not extra_blocks:
        return core, ''
    full = core + '\n\n' + '\n\n'.join(extra_blocks)
    if len(full) <= CAPTION_SAFE_LIMIT:
        return full, ''
    return core, '\n\n'.join(extra_blocks)


def create(day: date, check_images: bool) -> dict:
    morning_phrase = morning_text_plan(day.year)[day]
    evening_phrase = evening_text_for(day)
    holidays = read_holidays(day)
    birthdays = read_birthdays(day)
    am_path, pm_path = image_path(day, True), image_path(day, False)
    if check_images:
        # Check the complete 400-photo library; fail early instead of breaking on a random date.
        expected = [ROOT / 'evening' / 'pict' / f'{i:02d}.jpg' for i in range(1, 81)]
        expected += [ROOT / 'morning' / 'pict' / season / f'{i:02d}.jpg'
                     for season in ('winter', 'spring', 'summer', 'autumn')
                     for i in range(1, 81)]
        absent = [str(p.relative_to(ROOT)) for p in expected if not p.is_file()]
        if absent:
            raise FileNotFoundError(f'Missing {len(absent)} JPG of 400; examples: {absent[:10]}')
    caption, extra = make_morning_caption(morning_phrase, holidays, birthdays)
    if len(caption) > CAPTION_SAFE_LIMIT:
        raise ValueError('Morning phrase alone is too long for a photo caption')
    if len(evening_phrase) > CAPTION_SAFE_LIMIT:
        raise ValueError('Evening phrase too long')
    make_url = lambda p: GITHUB_RAW + quote(p.as_posix(), safe='/')
    return {
        'version': 1,
        'date': day.isoformat(),
        'timezone': 'Europe/Kyiv',
        'morning': {'time': '07:00', 'caption': caption, 'extra_text': extra,
                    'image_url': make_url(am_path), 'image_file': am_path.as_posix()},
        'evening': {'time': '21:55', 'caption': evening_phrase,
                    'image_url': make_url(pm_path), 'image_file': pm_path.as_posix()},
        'holidays': holidays,
        'birthdays': birthdays,
    }


def main() -> None:
    p = argparse.ArgumentParser(description='Prepare DailyPulse JSON for the selected Kyiv day.')
    p.add_argument('--date', help='YYYY-MM-DD; default: current date in Europe/Kyiv')
    p.add_argument('--check-images', action='store_true', help='Verify selected files exist locally')
    p.add_argument('--output', default='dailypulse_calendar/daily.json', help='Output JSON relative to repo root')
    args = p.parse_args()
    today = date.fromisoformat(args.date) if args.date else datetime.now(LOCAL_ZONE).date()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    result = create(today, args.check_images)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'[OK] {today} {season_for(today)} | holidays={len(result["holidays"])} '
          f'birthdays={len(result["birthdays"])}')
    print(f'[AM] {result["morning"]["image_file"]}')
    print(f'[PM] {result["evening"]["image_file"]}')
    print(f'[JSON] {output}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        raise SystemExit(1)
