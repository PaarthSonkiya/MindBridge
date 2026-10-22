"""Render docs/img/*.html diagrams to PNG with headless Chromium (Playwright)."""

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent


async def main(names):
    async with async_playwright() as p:
        exe = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")
        br = await p.chromium.launch(**({"executable_path": exe} if Path(exe).exists() else {}))
        pg = await br.new_page(viewport={"width": 1200, "height": 600}, device_scale_factor=2)
        for name in names:
            await pg.goto((HERE / f"{name}.html").as_uri())
            await pg.wait_for_timeout(300)
            await pg.locator("body").screenshot(path=str(HERE / f"{name}.png"))
            print("wrote", HERE / f"{name}.png")
        await br.close()


asyncio.run(main(sys.argv[1:] or ["architecture"]))
