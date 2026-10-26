"""Printable demo script (A4 PDF) from docs/demo_scenario.md: every turn, who speaks, which key to press."""

import asyncio
import html
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
rows = []
for line in (ROOT / "docs" / "demo_scenario.md").read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\| (\d+) \|(.*)\|\s*$", line)
    if not m:
        continue
    cells = [c.strip() for c in m.group(2).split("|")]
    n = int(m.group(1))
    if n <= 35:   # Part A: | time | who | says | expected |
        _time, who, says, expect = cells[:4]
    else:         # Part B: | who | says | expected |
        who, says, expect = cells[:3]
    rows.append((n, who.replace("**", ""), says.replace("**", ""), expect.replace("**", "")))


def key_for(who: str, says: str) -> str:
    w = who.lower()
    if "(hỏi" in w or "hỏi về" in w:
        return "Hỏi về dây chuyền"
    if "trả lời" in w:
        return "Trả lời"
    if "operator" in w:
        return "2 / yellow"
    if "either" in w or "(" in who and "tap" in says.lower():
        return "screen"
    return "1 / blue"


def role_class(who: str) -> str:
    w = who.lower()
    return "op" if "operator" in w else "ko" if "(ko)" in w else "sup"


trs = "\n".join(
    f'<tr class="{role_class(w)}"><td class="n">{n}</td><td class="who">{html.escape(w)}</td>'
    f'<td class="key">{html.escape(key_for(w, s))}</td><td class="says">{html.escape(s)}</td>'
    f'<td class="exp">{html.escape(e)}</td></tr>'
    + ('<tr class="part"><td colspan="5">Part B — switch the top bar to Tiếng Việt ⇄ 한국어</td></tr>' if n == 35 else "")
    for n, w, s, e in rows)
page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 12mm; }}
body {{ font-family: Arial, "Noto Sans", "Noto Sans CJK KR", sans-serif; font-size: 10.5pt; color: #1a1a2e; }}
h1 {{ font-size: 15pt; margin: 0 0 2mm; color: #0a2357; }}
p {{ margin: 0 0 3mm; font-size: 9.5pt; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border-bottom: 0.3mm solid #d5dae3; padding: 1.6mm 1.5mm; vertical-align: top; text-align: left; }}
th {{ background: #0a2357; color: #fff; font-size: 9pt; }}
td.n {{ width: 6mm; color: #6b7280; }} td.who {{ width: 30mm; font-weight: 700; }} td.key {{ width: 22mm; font-size: 9pt; }}
td.says {{ font-size: 11.5pt; }} td.exp {{ width: 42mm; font-size: 8.5pt; color: #6b7280; }}
tr.op td.who {{ color: #8a6d00; }} tr.op {{ background: #fff8db; }} tr.ko {{ background: #eef4ff; }}
tr.part td {{ background: #0a2357; color: #fff; font-weight: 700; }}
tr {{ page-break-inside: avoid; }}
</style></head><body>
<h1>MindBridge demo script (about 30 minutes)</h1>
<p>Supervisor: key <b>1</b> or the blue button. Operator: key <b>2</b> or the yellow button (highlighted rows).
Speak one or two sentences at normal pace, 20–40 cm from the laptop, then wait for the translation to finish
speaking. If a line is misrecognised, say it once more; if it fails twice, type it and say so on camera.</p>
<table><tr><th>#</th><th>Who</th><th>Press</th><th>Says</th><th>MindBridge should</th></tr>
{trs}</table></body></html>"""


async def main(out: Path):
    tmp = out.with_suffix(".html")
    tmp.write_text(page, encoding="utf-8")
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium") if Path(
            "/opt/pw-browsers/chromium").exists() else await p.chromium.launch()
        pg = await br.new_page()
        await pg.goto(tmp.as_uri())
        await pg.pdf(path=str(out), format="A4", print_background=True)
        await br.close()
    tmp.unlink()
    print("wrote", out, len(rows), "turns")


asyncio.run(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "print" / "demo_script.pdf"))
