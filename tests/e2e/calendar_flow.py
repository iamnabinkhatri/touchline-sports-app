"""Browser end-to-end test for the calendar: browse, claim, add, delete and mobile layout.

Needs Playwright:  pip install playwright && python3 -m playwright install chromium
Run:               python3 tests/e2e/calendar_flow.py
"""
import os
import tempfile
import subprocess, time, os, sys
from playwright.sync_api import sync_playwright
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
env=dict(os.environ, TOUCHLINE_DB=os.path.join(tempfile.gettempdir(), 'cal_e2e.db'), PORT='4190', PYTHONDONTWRITEBYTECODE='1')
for f in (os.path.join(tempfile.gettempdir(), 'cal_e2e.db'),os.path.join(tempfile.gettempdir(), 'cal_e2e.db-wal'),os.path.join(tempfile.gettempdir(), 'cal_e2e.db-shm')):
    if os.path.exists(f): os.remove(f)
srv=subprocess.Popen(['python3','-m','backend.server'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(2)
results=[]
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail)); print(("PASS " if ok else "FAIL ")+name+(" — "+detail if detail and not ok else ""))
errors=[]
try:
    with sync_playwright() as p:
        b=p.chromium.launch()
        pg=b.new_page(viewport={'width':1360,'height':900})
        pg.on('console', lambda m: errors.append(m.text) if m.type=='error' else None)
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto('http://127.0.0.1:4190/#/calendar'); pg.wait_for_selector('.cal-grid', timeout=8000); pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'cal_desktop.png'), full_page=False)
        check('calendar route renders grid of 42 days', pg.locator('.cal-day').count()==42, str(pg.locator('.cal-day').count()))
        check('sidebar links to calendar', pg.locator('.side-link[href="#/calendar"], a[href="#/calendar"]').count()>0)
        # month navigation
        title0=pg.inner_text('.cal-head h2')
        pg.click('[data-action=calendar-next]'); pg.wait_for_timeout(300)
        check('next month changes title', pg.inner_text('.cal-head h2')!=title0)
        pg.click('[data-action=calendar-today]'); pg.wait_for_timeout(300)
        check('today button returns to current month', pg.inner_text('.cal-head h2')==title0)
        # open the Needs-cover list and claim the donuts duty from the day panel
        open_cover=pg.locator('.cal-open__list li').count()
        check('help-wanted list shows unclaimed duties', open_cover>=1, str(open_cover))
        before_open=pg.locator('.cal-count').inner_text()
        claim=pg.locator('[data-action=claim-duty]').first
        if claim.count():
            claim.click(); pg.wait_for_timeout(900)
            toast=pg.locator('.toast, [role=status]').first
            after_open=pg.locator('.cal-count').inner_text()
            check('claiming a duty reduces the open count', after_open!=before_open, f"{before_open} -> {after_open}")
            check('claimed duty now shows "Give it back"', pg.locator('[data-action=release-duty]').count()>0)
            pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'cal_claimed.png'))
            pg.locator('[data-action=release-duty]').first.click(); pg.wait_for_timeout(900)
            check('giving a duty back restores the open count', pg.locator('.cal-count').inner_text()==before_open)
        else:
            check('a claimable duty exists', False, 'no claim button found')
        # add a duty through the modal
        pg.click('.page--calendar .page-head [data-action=new-duty]'); pg.wait_for_selector('dialog[open] form[data-form=new-duty]', timeout=4000)
        pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'cal_modal.png'))
        pg.select_option('dialog[open] select[name=kind]', 'drinks')
        pg.fill('dialog[open] input[name=title]', 'Sports drinks for the bench')
        pg.fill('dialog[open] textarea[name=note]', 'Two cases, no sugar-free')
        pg.click('dialog[open] form[data-form=new-duty] button[type=submit]'); pg.wait_for_timeout(1200)
        check('modal closes after adding a duty', pg.locator('dialog[open]').count()==0)
        check('new duty appears in the day panel', pg.locator('.cal-item__body strong', has_text='Sports drinks for the bench').count()>0)
        check('new duty is visible on the grid', pg.locator('.cal-chip', has_text='Drinks').count()>0)
        pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'cal_added.png'))
        # delete it
        pg.on('dialog', lambda d: d.accept())
        pg.locator('.cal-delete').first.click(); pg.wait_for_timeout(900)
        check('deleting removes the duty', pg.locator('.cal-item__body strong', has_text='Sports drinks for the bench').count()==0)
        # empty-day state
        pg.click('[data-action=calendar-day][data-date$="-28"] >> nth=0'); pg.wait_for_timeout(400)
        # mobile
        m=b.new_page(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
        m.on('pageerror', lambda e: errors.append(str(e)))
        m.goto('http://127.0.0.1:4190/#/calendar'); m.wait_for_selector('.cal-grid', timeout=8000); m.wait_for_timeout(500)
        m.screenshot(path=os.path.join(tempfile.gettempdir(), 'cal_mobile.png'), full_page=True)
        check('mobile nav includes Calendar', m.locator('.mobile-nav a[href="#/calendar"]').count()>0)
        tops=m.evaluate("[...document.querySelectorAll('.mobile-nav__item')].map(a=>Math.round(a.getBoundingClientRect().top))")
        check('all 7 mobile nav items sit on one row', len(set(tops))==1 and len(tops)==7, str(tops))
        overflow=m.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
        check('no horizontal scroll on phone', overflow<=1, f"overflow {overflow}px")
        b.close()
finally:
    srv.terminate()
real=[e for e in errors if 'favicon' not in e.lower()]
check('no JavaScript errors during the flow', not real, '; '.join(real[:3]))
failed=[r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
