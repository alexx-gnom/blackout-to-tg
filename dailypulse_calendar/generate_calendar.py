#!/usr/bin/env python3
"""DailyPulse: build date-specific calendar (std lib only)."""
from datetime import date,timedelta
from pathlib import Path
import calendar, argparse
ROOT=Path(__file__).resolve().parent

def read_rows(path):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            yield line.split('|')

def movable_date(year, month, weekday, nth):
    first=date(year,month,1)
    if nth>0:
        day=1+(weekday-first.weekday())%7+(nth-1)*7
    else:
        last=date(year,month,calendar.monthrange(year,month)[1])
        day=last.day-(last.weekday()-weekday)%7
    return date(year,month,day)

def build(year):
    items={date(year,m,d):[] for m in range(1,13) for d in range(1,calendar.monthrange(year,m)[1]+1)}
    for mmdd,typ,name in read_rows(ROOT/'holidays_fixed.txt'):
        day,month=map(int,mmdd.split('.'))
        if month==2 and day==29 and not calendar.isleap(year):continue
        items[date(year,month,day)].append((typ,name))
    for mm,wd,nth,typ,name in read_rows(ROOT/'holidays_movable.txt'):
        target=movable_date(year,int(mm),int(wd),int(nth))
        items[target].insert(0,(typ,name))
    return items

def main():
    p=argparse.ArgumentParser();p.add_argument('--year',type=int,default=date.today().year)
    p.add_argument('--include-memory',action='store_true',help='Include remembrance observances (M) in output')
    args=p.parse_args()
    rows=build(args.year)
    target=ROOT/f'calendar_{args.year}.txt'
    with target.open('w',encoding='utf-8') as out:
        out.write('# YYYY-MM-DD|TYPE|НАЗВА ; several lines possible per date\n')
        for day,events in rows.items():
            for t,n in events:
                if t=='M' and not args.include_memory:continue
                out.write(f'{day.isoformat()}|{t}|{n}\n')
    print(f'{target.name}: {len(rows)} dates, {sum(len(x) for x in rows.values())} entries; remembrance excluded unless requested')
if __name__=='__main__': main()
