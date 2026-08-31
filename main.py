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
    template = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.plot.ly; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>داشبورد داده واقعی طلا | __INSTRUMENT__</title>
  <meta name="description" content="قیمت مشاهده‌شده XAUUSD از منبع بازار واقعی، همراه با زمان منبع و کنترل تازگی؛ بدون fallback ساختگی">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" defer></script>
  <style>
    :root{--navy:#07162a;--blue:#2864f0;--ink:#142033;--muted:#65748a;--line:#dfe6ef;--bg:#f4f7fb;--amber:#a96106;--red:#bf3345;--teal:#087f75}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Vazirmatn,Tahoma,sans-serif}header{background:linear-gradient(135deg,var(--navy),#102d50);color:#fff;padding:24px}.wrap{max-width:1180px;margin:auto}h1{margin:0;font-size:clamp(1.35rem,3vw,2.1rem)}.sub{color:#aebed3;margin:6px 0 0}.status{display:inline-flex;margin-top:16px;border:1px solid #4ed6be;border-radius:999px;background:#0a8f7a22;color:#8ff3df;padding:7px 12px;font-weight:800}.status.offline{border-color:#f2c166;background:#f2c16622;color:#ffd98e}main{padding:22px}.grid{display:grid;gap:14px;grid-template-columns:repeat(4,minmax(0,1fr))}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 8px 28px #1024400c}.card span{display:block;color:var(--muted);font-size:.78rem}.card strong{display:block;margin-top:7px;font-size:1.25rem}.wide{grid-column:span 4}.half{grid-column:span 2}.notice{border-color:#b9d8d2;background:#f4fffd}.warn{border-color:#f0cf91;background:#fffaf0}.risk{color:var(--amber)}#chart{height:320px;direction:ltr}.empty{height:240px;display:grid;place-items:center;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:14px;padding:24px}dl{display:grid;grid-template-columns:max-content 1fr;gap:10px 16px;margin:12px 0 0}dt{color:var(--muted)}dd{margin:0;direction:ltr;unicode-bidi:embed;text-align:right;overflow-wrap:anywhere}a{color:var(--blue)}footer{padding:22px;color:var(--muted);font-size:.78rem}code{direction:ltr;unicode-bidi:embed}@media(max-width:760px){.grid{grid-template-columns:1fr 1fr}.wide,.half{grid-column:span 2}}@media(max-width:480px){.grid{grid-template-columns:1fr}.wide,.half{grid-column:span 1}dl{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>مرکز داده واقعی طلا — __INSTRUMENT__</h1><p class="sub">قیمت مشاهده‌شده بازار با مهر زمانی منبع و کنترل تازگی</p><span id="data-status" class="status">در حال بررسی منبع…</span></div></header>
  <main class="wrap">
    <section class="grid" aria-label="خلاصه داده بازار">
      <article class="card"><span>قیمت XAU/USD</span><strong id="price">—</strong></article>
      <article class="card"><span>ارز / واحد</span><strong>USD / اونس تروا</strong></article>
      <article class="card"><span>زمان مشاهده منبع</span><strong id="observed">—</strong></article>
      <article class="card"><span>دروازه ریسک</span><strong id="risk" class="risk">—</strong></article>
      <article class="card wide notice"><strong>سیاست صحت داده</strong><p>قیمت فقط از پاسخ اعتبارسنجی‌شده Gold API نمایش داده می‌شود. هیچ عدد شبیه‌سازی‌شده یا fallback ساختگی وجود ندارد. اگر منبع قطع، نامعتبر یا قدیمی باشد، قیمت «ناموجود» می‌شود.</p></article>
      <article class="card wide"><h2>تاریخچه قیمت</h2><div id="chart" class="empty">تاریخچه OHLC معتبر هنوز پیکربندی نشده است؛ بنابراین نمودار و اندیکاتور ساختگی نمایش داده نمی‌شود.</div></article>
      <article class="card half"><h2>ردیابی منبع</h2><dl><dt>ارائه‌دهنده</dt><dd>Gold API</dd><dt>زمان دریافت سرور</dt><dd id="fetched">—</dd><dt>سن داده هنگام دریافت</dt><dd id="age">—</dd><dt>Endpoint</dt><dd><a href="https://api.gold-api.com/price/XAU/USD" rel="noreferrer">api.gold-api.com/price/XAU/USD</a></dd></dl></article>
      <article class="card half warn"><h2>محدودیت تحلیل</h2><p>تا وقتی تاریخچه واقعی OHLC، اخبار، تقویم اقتصادی و موقعیت‌گیری معتبر متصل نشده‌اند، نتیجه تحلیل <strong>WAIT</strong> باقی می‌ماند.</p><p id="risk-reasons"></p><p><strong>اجرای معامله: غیرفعال</strong></p></article>
    </section>
  </main>
  <footer class="wrap">provider=<code>gold-api.com</code> · mode=<code>live_market_data</code> · synthetic_fallback=<code>false</code></footer>
  <script type="application/json" id="dashboard-data">__PAYLOAD__</script>
  <script>
    'use strict';
    const payload = JSON.parse(document.getElementById('dashboard-data').textContent);
    const setText = (id, value) => document.getElementById(id).textContent = String(value);
    const available = payload.metadata.data_available === true && Number.isFinite(payload.market.price);
    const status = document.getElementById('data-status');
    status.textContent = available ? 'داده بازار واقعی · LIVE / OBSERVED' : 'منبع واقعی در دسترس نیست · WAIT';
    if (!available) status.classList.add('offline');
    setText('price', available ? payload.market.price.toLocaleString('fa-IR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'ناموجود');
    setText('observed', payload.metadata.observed_at || 'ناموجود');
    setText('fetched', payload.quote?.fetched_at || 'ناموجود');
    setText('age', Number.isFinite(payload.market.quote_age_seconds) ? `${payload.market.quote_age_seconds.toLocaleString('fa-IR')} ثانیه` : 'ناموجود');
    setText('risk', payload.risk.verdict);
    setText('risk-reasons', payload.risk.reasons.join(' · '));
    if (Array.isArray(payload.candles) && payload.candles.length > 1 && window.Plotly) {
      const chart = document.getElementById('chart');
      chart.classList.remove('empty');
      const x = payload.candles.map((row) => row.date);
      const y = payload.candles.map((row) => row.close);
      Plotly.newPlot(chart, [{x,y,type:'scatter',mode:'lines',line:{color:'#2864f0',width:3},name:'Observed close'}], {paper_bgcolor:'#fff',plot_bgcolor:'#fff',font:{family:'Vazirmatn'},margin:{t:20,r:20,b:45,l:55},xaxis:{gridcolor:'#edf1f6'},yaxis:{gridcolor:'#edf1f6',title:'USD/oz'}}, {responsive:true,displaylogo:false});
    }
  </script>
</body>
</html>
"""
    return template.replace("__INSTRUMENT__", instrument).replace("__PAYLOAD__", data)


def generate_outputs(payload: dict[str, Any] | None = None) -> dict[str, Path]:
    snapshot = payload or build_analysis()
    SETTINGS.output_dir.mkdir(parents=True, exist_ok=True)
    SETTINGS.static_dir.mkdir(parents=True, exist_ok=True)
    results_path = SETTINGS.output_dir / "results.json"
    dashboard_path = SETTINGS.output_dir / "dashboard.html"
    static_path = SETTINGS.static_dir / "index.html"
    results_path.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    html = render_dashboard(snapshot)
    dashboard_path.write_text(html, encoding="utf-8")
    static_path.write_text(html, encoding="utf-8")
    return {"results": results_path, "dashboard": dashboard_path, "static": static_path}


if __name__ == "__main__":
    for name, path in generate_outputs().items():
        print(f"{name}: {path.name}")
