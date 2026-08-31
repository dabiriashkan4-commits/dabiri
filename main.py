from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from engine.analysis import build_analysis
from engine.config import SETTINGS


def strict_json(payload: dict[str, Any]) -> str:
    """Serialize valid JSON and neutralize HTML-significant characters."""
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return encoded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render_dashboard(payload: dict[str, Any]) -> str:
    data = strict_json(payload)
    instrument = escape(str(payload["metadata"]["instrument"]))
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.plot.ly; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>داشبورد آزمایشی هوشمندی طلا | {instrument}</title>
  <meta name="description" content="داشبورد فارسی داده‌های کاملاً شبیه‌سازی‌شده؛ فاقد داده زنده و اجرای معامله">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" defer></script>
  <style>
    :root{{--navy:#07162a;--blue:#2864f0;--ink:#142033;--muted:#65748a;--line:#dfe6ef;--bg:#f4f7fb;--amber:#bd7414;--red:#bf3345;--teal:#087f75}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Vazirmatn,Tahoma,sans-serif}}header{{background:linear-gradient(135deg,var(--navy),#102d50);color:#fff;padding:24px}}.wrap{{max-width:1180px;margin:auto}}h1{{margin:0;font-size:clamp(1.35rem,3vw,2.1rem)}}.sub{{color:#aebed3;margin:6px 0 0}}.demo{{display:inline-flex;margin-top:16px;border:1px solid #f2c166;border-radius:999px;background:#f2c16622;color:#ffd98e;padding:7px 12px;font-weight:800}}main{{padding:22px}}.grid{{display:grid;gap:14px;grid-template-columns:repeat(4,minmax(0,1fr))}}.card{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 8px 28px #1024400c}}.card span{{display:block;color:var(--muted);font-size:.78rem}}.card strong{{display:block;margin-top:7px;font-size:1.25rem}}.wide{{grid-column:span 4}}.half{{grid-column:span 2}}.warn{{border-color:#f0cf91;background:#fffaf0}}.risk{{color:var(--red)}}#chart{{height:380px;direction:ltr}}table{{width:100%;border-collapse:collapse;margin-top:10px}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:right;font-size:.83rem}}th{{color:var(--muted)}}footer{{padding:22px;color:var(--muted);font-size:.78rem}}code{{direction:ltr;unicode-bidi:embed}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}.wide,.half{{grid-column:span 2}}}}@media(max-width:480px){{.grid{{grid-template-columns:1fr}}.wide,.half{{grid-column:span 1}}}}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>مرکز آزمایشی تحلیل طلا — {instrument}</h1><p class="sub">نمای پژوهشی مستقل برای آزمون فنی، احساسات و ریسک</p><span class="demo">داده کاملاً شبیه‌سازی‌شده · SYNTHETIC / DEMO</span></div></header>
  <main class="wrap">
    <section class="grid" aria-label="خلاصه تحلیل">
      <article class="card"><span>تصمیم</span><strong id="decision">—</strong></article>
      <article class="card"><span>قیمت نمایشی</span><strong id="close">—</strong></article>
      <article class="card"><span>روند مصنوعی</span><strong id="trend">—</strong></article>
      <article class="card"><span>دروازه ریسک</span><strong id="risk" class="risk">—</strong></article>
      <article class="card wide warn"><strong>هشدار داده</strong><p>تمام اعداد این صفحه ساختگی و صرفاً برای نمایش نرم‌افزار هستند. این صفحه به بازار، کارگزار یا سامانه اجرای سفارش متصل نیست.</p></article>
      <article class="card wide"><h2>مسیر قیمت شبیه‌سازی‌شده</h2><div id="chart" role="img" aria-label="نمودار قیمت ساختگی"></div><noscript>برای نمایش نمودار آزمایشی JavaScript لازم است.</noscript></article>
      <article class="card half"><h2>رویدادهای نمایشی</h2><table><thead><tr><th>زمان</th><th>رویداد</th><th>اهمیت</th></tr></thead><tbody id="events"></tbody></table></article>
      <article class="card half"><h2>کنترل ریسک</h2><p id="risk-reasons"></p><p><strong>اجرای معامله: غیرفعال</strong></p></article>
    </section>
  </main>
  <footer class="wrap">خروجی محلی و مستقل · provider=<code>synthetic</code> · mode=<code>demo</code></footer>
  <script type="application/json" id="dashboard-data">{data}</script>
  <script>
    'use strict';
    const payload = JSON.parse(document.getElementById('dashboard-data').textContent);
    const setText = (id, value) => document.getElementById(id).textContent = String(value);
    setText('decision', payload.decision.decision);
    setText('close', payload.market.last_close.toLocaleString('fa-IR'));
    setText('trend', payload.market.trend);
    setText('risk', payload.risk.verdict);
    setText('risk-reasons', payload.risk.reasons.join(' · '));
    const tbody = document.getElementById('events');
    payload.events.forEach((event) => {{
      const row = document.createElement('tr');
      [event.date, event.event, event.importance].forEach((value) => {{const cell=document.createElement('td');cell.textContent=String(value);row.appendChild(cell);}});
      tbody.appendChild(row);
    }});
    window.addEventListener('load', () => {{
      if (!window.Plotly) return;
      const x = payload.candles.map((row) => row.date);
      const y = payload.candles.map((row) => row.close);
      Plotly.newPlot('chart', [{{x,y,type:'scatter',mode:'lines',line:{{color:'#2864f0',width:3}},name:'Synthetic close'}}], {{paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{{family:'Vazirmatn'}},margin:{{t:20,r:20,b:45,l:55}},xaxis:{{gridcolor:'#edf1f6'}},yaxis:{{gridcolor:'#edf1f6',title:'Demo USD/oz'}}}}, {{responsive:true,displaylogo:false}});
    }});
  </script>
</body>
</html>
"""


def generate_outputs() -> dict[str, Path]:
    payload = build_analysis()
    SETTINGS.output_dir.mkdir(parents=True, exist_ok=True)
    SETTINGS.static_dir.mkdir(parents=True, exist_ok=True)
    results_path = SETTINGS.output_dir / "results.json"
    dashboard_path = SETTINGS.output_dir / "dashboard.html"
    static_path = SETTINGS.static_dir / "index.html"
    results_path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    html = render_dashboard(payload)
    dashboard_path.write_text(html, encoding="utf-8")
    static_path.write_text(html, encoding="utf-8")
    return {"results": results_path, "dashboard": dashboard_path, "static": static_path}


def ensure_outputs() -> dict[str, Path]:
    expected = {
        "results": SETTINGS.output_dir / "results.json",
        "dashboard": SETTINGS.output_dir / "dashboard.html",
        "static": SETTINGS.static_dir / "index.html",
    }
    return expected if all(path.exists() for path in expected.values()) else generate_outputs()


if __name__ == "__main__":
    for name, path in generate_outputs().items():
        print(f"{name}: {path.name}")
