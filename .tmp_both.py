import asyncio, subprocess
from playwright.async_api import async_playwright

BASE = "http://localhost:8001"
INIT_B03 = "55c8092a-4cec-402d-86c0-0499557e4c29"
MDS_IV = "63552bed-6ddc-4b8b-9ec3-601eb7f97eea"

def db_mds(iid):
    code = f"import sqlite3;c=sqlite3.connect('/app/data/innovatiepijplijn.db');print(c.execute('SELECT mds_id FROM initiatives WHERE id=?',(iid,)).fetchone()[0]);c.close()"
    out = subprocess.run(["docker","compose","exec","-T","innovatiepijplijn","python3","-c",code],capture_output=True,text=True,cwd="/Users/erouw/Documents/Development/innovatie_pijplijn")
    return out.stdout.strip()

async def edit_mds(page, mds_value):
    await page.locator("button:has-text('Bewerken')").first.click()
    await page.wait_for_timeout(400)
    sel = page.locator("#modal-edit-initiative select[name='mds_id']")
    await sel.select_option(value=mds_value)
    async with page.expect_response(lambda r: r.request.method == "PUT" and "/api/initiatieven/" in r.url, timeout=15000) as info:
        await page.locator("#modal-edit-initiative button[type='submit']").click()
    resp = await info.value
    await page.wait_for_timeout(800)
    return resp.status

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.request.post(BASE + "/api/auth/login", data={"username": "admin", "password": "admin123"})
        await page.goto(f"{BASE}/api/initiatieven/detail/{INIT_B03}")
        await page.wait_for_load_state("domcontentloaded")
        print(f"Start mds_id: {db_mds(INIT_B03)!r}")

        s1 = await edit_mds(page, MDS_IV)
        print(f"1) Koppelen → PUT {s1}, DB mds_id: {db_mds(INIT_B03)!r}")

        s2 = await edit_mds(page, "")
        print(f"2) Ontkoppelen → PUT {s2}, DB mds_id: {db_mds(INIT_B03)!r}")

        await browser.close()

asyncio.run(main())
