#!/usr/bin/env python3
"""
build_site.py — regenerate website/index.html from the SQLreader_job source files.
Run from any directory:  python website/build_site.py
"""
import os
import html as _h

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FILES = [
    ("main.py",      "Entry Point"),
    ("constants.py", "Constants"),
    ("db_helper.py", "DB Layer"),
    ("settings.py",  "Settings"),
    ("dialogs.py",   "Dialogs"),
    ("widgets.py",   "Widgets"),
    ("viewer.py",    "Viewer (UI)"),
]

# ── Read & escape source files ────────────────────────────────────────────────
sources = {}
for fname, _ in FILES:
    with open(os.path.join(ROOT, fname), encoding="utf-8") as f:
        sources[fname] = _h.escape(f.read())

# ── Build tab nav buttons ─────────────────────────────────────────────────────
tab_nav_parts = []
for i, (fname, label) in enumerate(FILES):
    active = " active" if i == 0 else ""
    tab_nav_parts.append(
        f'<button class="tab-btn{active}" onclick="showTab(\'{fname}\')" id="btn-{fname}">'
        f'<span class="tab-label">{label}</span>'
        f'<span class="tab-fname">{fname}</span></button>'
    )
tab_nav = "\n      ".join(tab_nav_parts)

# ── Build tab panels ──────────────────────────────────────────────────────────
tab_panel_parts = []
for i, (fname, label) in enumerate(FILES):
    active = " active" if i == 0 else ""
    tab_panel_parts.append(
        f'<div class="tab-panel{active}" id="panel-{fname}">'
        f'<pre><code class="language-python">{sources[fname]}</code></pre></div>'
    )
tab_panels = "\n      ".join(tab_panel_parts)

# ── Feature cards ─────────────────────────────────────────────────────────────
FEATURES = [
    ("📂", "Open .pspc files",       "File dialog — supports all SQLite-based formats"),
    ("📋", "Browse all tables",      "Left panel lists every table in the database"),
    ("🔍", "Real-time search",       "Instant row filtering inside any table"),
    ("📊", "Export to Excel",        "All tables → one .xlsx workbook (Ctrl+E)"),
    ("🔌", "Port Connections",       "Auto-join S1 (EngineeringItems) and S2–S4 (Port table)"),
    ("👁️", "Column management",      "Hide / show / reorder columns; settings persist per table"),
    ("↕️", "Sorting",                "Click any column header to sort ascending / descending"),
    ("💾", "Persistent settings",    "Window size, last file, column preferences saved across restarts"),
]
feature_cards = "\n      ".join(
    f'<div class="feature-card">'
    f'<span class="feature-icon">{icon}</span>'
    f'<strong>{title}</strong>'
    f'<p>{desc}</p></div>'
    for icon, title, desc in FEATURES
)

# ── HTML template (uses __PLACEHOLDER__ so CSS/JS braces are safe) ─────────────
TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PSPC Viewer — Autodesk Plant 3D .pspc Reader</title>
<link rel="stylesheet"
  href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         background: #f0f4f8; color: #1e293b; line-height: 1.6; }

  /* ── Header ─────────────────────────────────────── */
  header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    color: white; padding: 0 2rem;
    display: flex; align-items: center; justify-content: space-between;
    height: 64px; position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 14px rgba(0,0,0,.5);
  }
  .logo { display: flex; align-items: center; gap: .7rem; }
  .logo-icon { font-size: 1.6rem; }
  .logo-text { font-size: 1.1rem; font-weight: 700; letter-spacing: .03em; }
  .logo-ver {
    font-size: .7rem; background: #2563eb; padding: 2px 7px;
    border-radius: 4px; margin-left: .4rem; vertical-align: middle;
  }
  .btn-dl-hdr {
    background: #2563eb; color: white;
    padding: .45rem 1.1rem; border-radius: 6px;
    text-decoration: none; font-weight: 600; font-size: .85rem;
    display: flex; align-items: center; gap: .4rem;
    transition: background .2s;
  }
  .btn-dl-hdr:hover { background: #1d4ed8; }

  /* ── Hero ────────────────────────────────────────── */
  .hero {
    background: linear-gradient(160deg, #0f172a 0%, #1e3a5f 55%, #1e40af 100%);
    color: white; padding: 4.5rem 2rem 4rem; text-align: center;
  }
  .hero h1 {
    font-size: 2.8rem; font-weight: 800; letter-spacing: -.03em;
    margin-bottom: .4rem;
  }
  .hero h1 span { color: #60a5fa; }
  .hero .sub {
    font-size: 1.1rem; color: #94a3b8; max-width: 540px;
    margin: 0 auto 1.8rem;
  }
  .hero .sub code { background: rgba(255,255,255,.1); padding: 1px 5px; border-radius: 4px; }
  .badges { display: flex; gap: .5rem; justify-content: center; flex-wrap: wrap; margin-bottom: 2rem; }
  .badge {
    background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.18);
    padding: .25rem .75rem; border-radius: 20px; font-size: .8rem;
  }
  .dl-btns { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
  .btn-dl {
    display: inline-flex; align-items: center; gap: .6rem;
    background: #2563eb; color: white;
    padding: .9rem 2.2rem; border-radius: 8px;
    text-decoration: none; font-weight: 700; font-size: 1rem;
    box-shadow: 0 4px 18px rgba(37,99,235,.5);
    transition: background .2s, transform .15s;
  }
  .btn-dl:hover { background: #1d4ed8; transform: translateY(-2px); }
  .btn-dl.btn-setup {
    background: #059669;
    box-shadow: 0 4px 18px rgba(5,150,105,.4);
  }
  .btn-dl.btn-setup:hover { background: #047857; }
  .btn-dl .ico { font-size: 1.3rem; }
  .btn-dl .sub-lbl { font-size: .72rem; font-weight: 400; opacity: .8; display: block; margin-top: .1rem; }
  .dl-note { font-size: .8rem; color: #64748b; margin-top: .8rem; }
  .dl-warn {
    display: inline-block; margin-top: .55rem;
    background: rgba(251,191,36,.12); border: 1px solid rgba(251,191,36,.4);
    color: #fbbf24; border-radius: 6px; padding: .35rem .8rem;
    font-size: .78rem; line-height: 1.5;
  }
  .dl-warn strong { color: #fcd34d; }

  /* ── Troubleshooting ─────────────────────────────────────── */
  .trouble-box {
    background: white; border-radius: 10px; padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.06); border: 1px solid #e2e8f0;
    margin-bottom: 2.5rem;
  }
  .trouble-box details { margin-bottom: .6rem; }
  .trouble-box summary {
    cursor: pointer; font-weight: 600; font-size: .93rem;
    padding: .4rem .2rem; list-style: none; display: flex; align-items: center; gap: .5rem;
  }
  .trouble-box summary::before { content: "▶"; font-size: .7rem; color: #94a3b8; transition: transform .2s; }
  .trouble-box details[open] summary::before { transform: rotate(90deg); }
  .trouble-box .detail-body { padding: .5rem .2rem .2rem 1.4rem; color: #475569; font-size: .88rem; line-height: 1.7; }
  .trouble-box .detail-body ol { padding-left: 1.2rem; }
  .trouble-box .detail-body code { background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-size: .82rem; }

  /* ── How to run from source ──────────────────────── */
  .run-box {
    background: #1e293b; color: #e2e8f0;
    border-radius: 8px; padding: 1rem 1.4rem; margin-top: 2rem;
    font-family: monospace; font-size: .87rem; text-align: left;
    max-width: 480px; margin-left: auto; margin-right: auto;
  }
  .run-box .cmt { color: #64748b; }
  .run-box .cmd { color: #86efac; }

  /* ── Main ────────────────────────────────────────── */
  main { max-width: 1200px; margin: 0 auto; padding: 2.5rem 1.5rem; }

  /* ── Section title ───────────────────────────────── */
  .sec-title {
    font-size: 1.35rem; font-weight: 700;
    margin-bottom: 1.2rem; padding-bottom: .5rem;
    border-bottom: 2px solid #e2e8f0;
  }

  /* ── Features ────────────────────────────────────── */
  .features { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }
  .feature-card {
    background: white; border-radius: 10px; padding: 1.2rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.06); border: 1px solid #e2e8f0;
  }
  .feature-icon { font-size: 1.5rem; display: block; margin-bottom: .45rem; }
  .feature-card strong { display: block; margin-bottom: .2rem; font-size: .93rem; }
  .feature-card p { color: #64748b; font-size: .84rem; }

  /* ── Shortcuts ───────────────────────────────────── */
  .shortcuts {
    background: white; border-radius: 10px; padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.06); border: 1px solid #e2e8f0;
    margin-bottom: 2.5rem; overflow-x: auto;
  }
  .shortcuts table { border-collapse: collapse; width: 100%; }
  .shortcuts tr { border-bottom: 1px solid #f1f5f9; }
  .shortcuts tr:last-child { border-bottom: none; }
  .shortcuts td { padding: .45rem .75rem; font-size: .9rem; }
  .shortcuts td:first-child {
    font-family: "Cascadia Code", "Fira Code", monospace;
    color: #374151; font-weight: 600; white-space: nowrap;
    background: #f8fafc; border-radius: 4px;
  }

  /* ── Project structure ───────────────────────────── */
  .struct-box {
    background: #1e293b; color: #e2e8f0;
    border-radius: 10px; padding: 1.25rem 1.5rem;
    font-family: "Cascadia Code", "Fira Code", monospace; font-size: .86rem;
    line-height: 1.8; margin-bottom: 2.5rem; overflow-x: auto;
  }
  .struct-box .dim { color: #64748b; }
  .struct-box .hl  { color: #60a5fa; font-weight: 600; }

  /* ── Source tabs ─────────────────────────────────── */
  .source-section { margin-bottom: 3rem; }
  .tab-nav {
    display: flex; flex-wrap: wrap; gap: 0;
    border-bottom: 2px solid #e2e8f0;
  }
  .tab-btn {
    background: none; border: none; cursor: pointer;
    padding: .55rem .9rem; border-radius: 6px 6px 0 0;
    font-family: inherit; font-size: .82rem; color: #64748b;
    display: flex; flex-direction: column; align-items: flex-start; gap: .05rem;
    border-bottom: 2px solid transparent; margin-bottom: -2px;
    transition: color .15s, background .15s;
  }
  .tab-btn:hover { background: #f1f5f9; color: #1e293b; }
  .tab-btn.active { color: #2563eb; border-bottom-color: #2563eb; background: #eff6ff; }
  .tab-label { font-weight: 600; }
  .tab-fname { font-family: "Cascadia Code", monospace; font-size: .73rem; opacity: .7; }
  .tab-panel {
    display: none; background: #0d1117;
    border-radius: 0 0 10px 10px; overflow: auto; max-height: 72vh;
  }
  .tab-panel.active { display: block; }
  .tab-panel pre { margin: 0; }
  .tab-panel code { font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", monospace !important; font-size: .8rem !important; line-height: 1.65 !important; }

  /* ── Footer ──────────────────────────────────────── */
  footer {
    text-align: center; padding: 2rem; color: #94a3b8; font-size: .85rem;
    border-top: 1px solid #e2e8f0; background: white; margin-top: 1rem;
  }
  footer code { background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-size: .8rem; }
</style>
</head>
<body>

<!-- ── Header ──────────────────────────────────────────────────── -->
<header>
  <div class="logo">
    <span class="logo-icon">🔌</span>
    <span class="logo-text">PSPC Viewer <span class="logo-ver">v1.3</span></span>
  </div>
  <div style="display:flex;gap:.5rem;">
    <a href="/download/PSPCViewer_Setup.exe" class="btn-dl-hdr" style="background:#059669;">&#11015; Setup .exe</a>
    <a href="/download/PSPCViewer.exe" class="btn-dl-hdr">&#11015; Portable .exe</a>
  </div>
</header>

<!-- ── Hero ────────────────────────────────────────────────────── -->
<div class="hero">
  <h1>PSPC <span>Viewer</span></h1>
  <p class="sub">
    Open, browse, search, and export Autodesk Plant&nbsp;3D
    <code>.pspc</code> files — SQLite databases with piping &amp; instrumentation data.
  </p>
  <div class="badges">
    <span class="badge">Python 3.10+</span>
    <span class="badge">tkinter</span>
    <span class="badge">SQLite</span>
    <span class="badge">Windows .exe</span>
    <span class="badge">Open Source</span>
  </div>
  <div class="dl-btns">
    <a href="/download/PSPCViewer_Setup.exe" class="btn-dl btn-setup">
      <span class="ico">&#11015;</span>
      <span>Download Setup<span class="sub-lbl">PSPCViewer_Setup.exe &nbsp;·&nbsp; Installer</span></span>
    </a>
    <a href="/download/PSPCViewer.exe" class="btn-dl">
      <span class="ico">&#11015;</span>
      <span>Download Portable<span class="sub-lbl">PSPCViewer.exe &nbsp;·&nbsp; Single file, no install</span></span>
    </a>
  </div>
  <p class="dl-note">Windows &nbsp;·&nbsp; No Python required</p>
  <p class="dl-warn">
    ⚠ Chrome may save the file as <strong>PSPCViewer.exe.crdownload</strong> — see
    <a href="#troubleshooting" style="color:#fcd34d;">Troubleshooting</a> below.
  </p>

  <div class="run-box">
    <span class="cmt"># Or run from source (Python 3.10+)</span><br>
    <span class="cmd">pip install pandas openpyxl</span><br>
    <span class="cmd">python main.py</span>
  </div>
</div>

<!-- ── Main content ─────────────────────────────────────────────── -->
<main>

  <!-- Features -->
  <h2 class="sec-title">Features</h2>
  <div class="features">
    __FEATURES__
  </div>

  <!-- Keyboard shortcuts -->
  <h2 class="sec-title">Keyboard Shortcuts</h2>
  <div class="shortcuts">
    <table>
      <tr><td>Ctrl+O</td><td>Open .pspc / SQLite file</td></tr>
      <tr><td>Ctrl+E</td><td>Export all tables to Excel (.xlsx)</td></tr>
      <tr><td>F5</td><td>Reload current table</td></tr>
      <tr><td>Double-click cell</td><td>Edit cell inline</td></tr>
      <tr><td>Click header</td><td>Sort column ascending / descending (&#9650;&#9660;)</td></tr>
      <tr><td>Drag header L / R</td><td>Reorder column</td></tr>
      <tr><td>Right-click header</td><td>Hide column &nbsp;/&nbsp; open column manager</td></tr>
    </table>
  </div>

  <!-- Project structure -->
  <h2 class="sec-title">Project Structure</h2>
  <div class="struct-box">
SQLreader_job/<br>
&#9474;<br>
&#9500;&#9472;&#9472; <span class="hl">main.py</span>       <span class="dim">&larr; entry point; starts the app</span><br>
&#9474;<br>
&#9500;&#9472;&#9472; <span class="hl">constants.py</span>  <span class="dim">&larr; shared constants (EI_VIEW_COLS, HIDDEN_COLS, …)</span><br>
&#9500;&#9472;&#9472; <span class="hl">settings.py</span>   <span class="dim">&larr; Settings (JSON) + SettingsDialog</span><br>
&#9500;&#9472;&#9472; <span class="hl">dialogs.py</span>    <span class="dim">&larr; ColumnDialog (show / hide / reorder columns)</span><br>
&#9500;&#9472;&#9472; <span class="hl">widgets.py</span>    <span class="dim">&larr; CellEditor (inline cell editing)</span><br>
&#9474;<br>
&#9500;&#9472;&#9472; <span class="hl">db_helper.py</span>  <span class="dim">&larr; DbHelper — all SQL here, no tkinter</span><br>
&#9500;&#9472;&#9472; <span class="hl">viewer.py</span>     <span class="dim">&larr; PSPCViewer — all tkinter here, no SQL</span><br>
&#9474;<br>
&#9492;&#9472;&#9472; dist/<br>
&nbsp;&nbsp;&nbsp;&nbsp;&#9492;&#9472;&#9472; PSPCViewer.exe  <span class="dim">&larr; standalone Windows executable (PyInstaller)</span>
  </div>

  <!-- Source code tabs -->
  <div class="source-section">
    <h2 class="sec-title">Source Code</h2>
    <div class="tab-nav">
      __TAB_NAV__
    </div>
    __TAB_PANELS__
  </div>

  <!-- Troubleshooting -->
  <h2 class="sec-title" id="troubleshooting">Troubleshooting</h2>
  <div class="trouble-box">

    <details open>
      <summary>⚠️ Chrome downloads the file as <code>PSPCViewer.exe.crdownload</code> instead of <code>.exe</code></summary>
      <div class="detail-body">
        <p>Chrome adds a <code>.crdownload</code> suffix while the download is in progress.
        The file is <strong>not usable yet</strong> — it is incomplete.</p>
        <p style="margin-top:.5rem"><strong>Solutions:</strong></p>
        <ol>
          <li><strong>Wait for the download to finish.</strong> Chrome will automatically rename it to <code>PSPCViewer.exe</code> when done. Check progress in Chrome's download bar (<code>Ctrl+J</code>).</li>
          <li><strong>If Chrome shows "Failed" or the file stayed as <code>.crdownload</code></strong> — the download was interrupted. Click <em>Resume</em> or restart the download.</li>
          <li><strong>Use a different browser.</strong> Firefox and Edge do not use <code>.crdownload</code> — the file lands directly as <code>PSPCViewer.exe</code>.</li>
          <li><strong>Allow the file in Windows Security / SmartScreen.</strong> Sometimes Windows blocks the download mid-way; click <em>Keep anyway</em> in the Chrome warning bar, then re-download.</li>
        </ol>
      </div>
    </details>

  </div>

</main>

<footer>
  PSPC Viewer &nbsp;&middot;&nbsp; Autodesk Plant&nbsp;3D .pspc reader &nbsp;&middot;&nbsp;
  Build exe: <code>build_exe.bat</code> &nbsp;&middot;&nbsp;
  Requirements: <code>pip install pandas openpyxl</code>
</footer>

<script>
hljs.highlightAll();

function showTab(fname) {
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById('btn-' + fname).classList.add('active');
  document.getElementById('panel-' + fname).classList.add('active');
}
</script>
</body>
</html>
"""

html_out = (TEMPLATE
    .replace("__FEATURES__",  feature_cards)
    .replace("__TAB_NAV__",   tab_nav)
    .replace("__TAB_PANELS__", tab_panels))

out_path = os.path.join(HERE, "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_out)
print(f"Generated: {out_path}")
