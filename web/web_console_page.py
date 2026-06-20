"""Web 控制台的内嵌前端(单页 HTML/CSS/JS,无外部资源、无构建)。

拆成独立文件只为让 web_console.py 聚焦后端逻辑。这里是纯字符串。

设计:精灵球主题亮色(上红下白、黑带、黄电),卡片化、留白克制、信息层次清晰;
响应式,窄屏自动堆叠。日志区不是纯文本,而是结构化行卡片(时间/类型/状态分列)。
token 由页面从自身 url 的 ?token= 读出,后续所有 fetch 自动带上(同 token 同源)。

后端 API 契约未变(/api/status、/api/config、/api/tasks、/api/memory、
/api/logs/*),本文件只重做呈现层。
"""

DENIED_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>皮卡丘控制台</title><style>
*{box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC",sans-serif;
  background:linear-gradient(180deg,#ee1515 0 46%,#fff 46% 100%);
  color:#2b2b2b;display:flex;align-items:center;justify-content:center;
  height:100vh;margin:0;text-align:center}
.box{background:#fff;padding:36px 44px;border-radius:22px;border:4px solid #2b2b2b;
  box-shadow:0 16px 44px rgba(0,0,0,.28);max-width:360px}
.bolt{font-size:46px}
h1{margin:10px 0 8px;font-size:22px;color:#ee1515}
p{color:#555;margin:0;line-height:1.65;font-size:14px}
</style></head><body><div class="box"><div class="bolt">⚡</div>
<h1>访问被拒</h1>
<p>缺少或错误的 token。每次启动 token 都会变,请用桌宠终端<b>最新打印</b>的那条完整链接打开。</p></div></body></html>"""


PAGE_HTML = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ 皮卡丘控制台</title>
<style>
  :root{
    /* 精灵球主题 */
    --red:#ee1515; --red-dk:#c40d0d; --red-soft:#ffe3e3;
    --black:#2b2b2b; --ink:#3a3a3a;
    --yellow:#ffcb05; --yellow-dk:#e0a800; --yellow-soft:#fff7d6;
    --blue:#2f6fed; --blue-soft:#e7efff;
    --green:#2f9e44; --green-soft:#e6f6ea;
    --orange:#e8590c; --orange-soft:#fff0e6;
    /* 中性 */
    --bg:#f3f4f6; --bg-2:#fafbfc; --card:#ffffff;
    --line:#e6e8ec; --line-2:#eef0f3;
    --fg:#2b2b2b; --fg-dim:#6b7280; --fg-mute:#9aa1ab;
    --radius:16px; --radius-sm:11px;
    --shadow:0 4px 18px rgba(43,43,43,.07);
    --shadow-lg:0 10px 30px rgba(43,43,43,.10);
  }
  *{box-sizing:border-box}
  ::selection{background:rgba(255,203,5,.45)}
  html,body{height:100%}
  body{margin:0;font-family:-apple-system,"PingFang SC","Hiragino Sans GB",
       "Segoe UI",sans-serif;color:var(--fg);font-size:14px;line-height:1.5;
       background:var(--bg);-webkit-font-smoothing:antialiased}

  /* ── 顶栏:精灵球红顶黑带 ── */
  header{position:sticky;top:0;z-index:20;
    background:linear-gradient(180deg,var(--red),var(--red-dk));
    border-bottom:4px solid var(--black);
    display:flex;align-items:center;gap:13px;padding:13px 22px;color:#fff;
    box-shadow:0 3px 14px rgba(238,21,21,.25)}
  .logo{display:flex;align-items:center;gap:12px}
  .ball{width:32px;height:32px;border-radius:50%;flex:none;position:relative;
    background:linear-gradient(180deg,#fff 0 48%,#fff 48% 100%);
    border:3px solid var(--black);overflow:hidden;
    box-shadow:0 2px 7px rgba(0,0,0,.25)}
  .ball:before{content:"";position:absolute;inset:0 0 50% 0;background:#fff}
  .ball:after{content:"";position:absolute;left:50%;top:50%;width:9px;height:9px;
    transform:translate(-50%,-50%);background:#fff;border:3px solid var(--black);
    border-radius:50%;z-index:2}
  /* 用一条黑带模拟精灵球中线 */
  .ball{background:
      radial-gradient(circle at 50% 50%,#fff 0 5px,var(--black) 5px 7px,transparent 7px),
      linear-gradient(180deg,var(--red) 0 calc(50% - 2px),var(--black) calc(50% - 2px) calc(50% + 2px),#fff calc(50% + 2px) 100%)}
  .ball:before,.ball:after{display:none}
  .logo h1{font-size:16.5px;margin:0;letter-spacing:.3px;font-weight:800;
    text-shadow:0 1px 2px rgba(0,0,0,.18)}
  .logo .sub{font-size:11px;color:rgba(255,255,255,.82);margin-top:1px}
  .conn{margin-left:auto;display:flex;align-items:center;gap:7px;font-size:12.5px;
    color:#fff;padding:5px 13px;border-radius:20px;
    background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);font-weight:600}
  .conn .led{width:8px;height:8px;border-radius:50%;background:#fff;opacity:.6;flex:none}
  .conn.ok .led{background:#b9f6ca;opacity:1;box-shadow:0 0 8px #69db7c}
  .conn.bad .led{background:#ffd0d0;opacity:1;box-shadow:0 0 8px #ff8787}
  .conn .meta{color:rgba(255,255,255,.7);font-variant-numeric:tabular-nums}

  /* ── 选项卡:黑带 ── */
  nav{display:flex;gap:2px;padding:0 14px;background:var(--black);
    position:sticky;top:58px;z-index:19;overflow-x:auto;scrollbar-width:none}
  nav::-webkit-scrollbar{display:none}
  nav button{appearance:none;background:none;border:none;color:#c9ccd2;
    padding:13px 16px 11px;cursor:pointer;font-size:13.5px;font-weight:600;
    border-bottom:3px solid transparent;white-space:nowrap;transition:color .15s}
  nav button .ico{margin-right:6px}
  nav button:hover{color:#fff}
  nav button.on{color:var(--yellow);border-bottom-color:var(--yellow)}

  main{max-width:1080px;margin:0 auto;padding:22px 18px 60px}
  .tab{display:none;animation:fade .25s ease}
  .tab.on{display:block}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  /* ── 卡片 ── */
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:18px 18px 16px;margin-bottom:16px;box-shadow:var(--shadow)}
  .card>h2{margin:0 0 14px;font-size:13px;font-weight:700;letter-spacing:.3px;
    color:var(--ink);display:flex;align-items:center;gap:8px}
  .card>h2 .bar{width:4px;height:15px;border-radius:3px;background:var(--red)}
  .card>h2 small{font-weight:500;letter-spacing:0;color:var(--fg-mute);font-size:12px}
  .col2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:720px){.col2{grid-template-columns:1fr}}

  /* ── 统计格 ── */
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(135px,1fr));gap:11px}
  .stat{background:var(--bg-2);border:1px solid var(--line-2);border-radius:var(--radius-sm);
    padding:12px 13px;transition:border-color .15s,transform .15s,box-shadow .15s}
  .stat:hover{border-color:#dfe2e7;transform:translateY(-1px);box-shadow:var(--shadow)}
  .stat .k{font-size:11.5px;color:var(--fg-mute);display:flex;align-items:center;gap:5px}
  .stat .v{font-size:18px;font-weight:700;margin-top:5px;font-variant-numeric:tabular-nums;color:var(--ink)}
  .stat.hl{border-color:rgba(255,203,5,.5);background:var(--yellow-soft)}
  .stat.hl .v{color:var(--yellow-dk)}

  /* ── 英雄区:固定高度,不随文字行数跳动 ── */
  .hero{display:flex;align-items:center;gap:16px;height:92px;overflow:hidden;
    background:linear-gradient(110deg,var(--yellow-soft),#fffdf3 70%);
    border:1px solid rgba(255,203,5,.5);border-radius:14px;padding:0 20px;margin-bottom:14px;
    box-shadow:var(--shadow)}
  .hero .face{font-size:40px;line-height:1;width:52px;text-align:center;flex:none;
    filter:drop-shadow(0 2px 4px rgba(224,168,0,.35))}
  .hero .who{flex:1;min-width:0}
  .hero .who .now{font-size:23px;font-weight:800;letter-spacing:.3px;color:var(--black);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .hero .who .desc{color:#8a7320;font-size:12.5px;margin-top:3px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .hero .pill-row{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end;
    max-width:46%;flex:none}
  @media(max-width:560px){.hero .pill-row{display:none}}

  /* ── 徽章 ── */
  .badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;
    font-size:11.5px;font-weight:600;border:1px solid transparent;white-space:nowrap}
  .badge:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
  .badge.on{background:var(--green-soft);color:var(--green);border-color:rgba(47,158,68,.28)}
  .badge.off{background:#f1f2f4;color:var(--fg-dim);border-color:var(--line)}
  .badge.off:before{opacity:.45}
  .badge.busy{background:var(--orange-soft);color:var(--orange);border-color:rgba(232,89,12,.3)}
  .badge.warn{background:var(--red-soft);color:var(--red);border-color:rgba(238,21,21,.3)}

  /* ── 警示框 ── */
  .alert{display:none;margin-top:12px;padding:12px 14px;border-radius:10px;
    background:var(--orange-soft);border:1px solid rgba(232,89,12,.4);
    color:var(--orange);font-size:13px}

  /* ── 配置表单 ── */
  .grp-title{font-size:12px;font-weight:700;letter-spacing:.3px;color:var(--red-dk);
    margin:20px 0 4px;padding-bottom:6px;border-bottom:1px dashed var(--line);
    display:flex;align-items:center;gap:7px}
  .grp-title:first-child{margin-top:2px}
  .grp-title .bar{width:4px;height:13px;border-radius:2px;background:var(--yellow)}
  .row{display:flex;align-items:center;gap:12px;padding:11px 2px;
    border-bottom:1px solid var(--line-2)}
  .row:last-child{border-bottom:none}
  .row .lbl{flex:1;min-width:0}
  .row .lbl b{font-weight:600}
  .row .lbl small{color:var(--fg-mute);display:block;font-size:11.5px;margin-top:3px;line-height:1.45}
  .ctrl{flex:none}

  input[type=number],input[type=text],select,textarea{
    font:inherit;color:var(--fg);background:#fff;
    border:1.5px solid var(--line);border-radius:9px;padding:7px 10px;
    transition:border-color .15s,box-shadow .15s}
  input:focus,select:focus,textarea:focus{outline:none;border-color:var(--yellow-dk);
    box-shadow:0 0 0 3px rgba(255,203,5,.2)}
  input[type=number]{width:120px;font-variant-numeric:tabular-nums}
  select{min-width:170px;cursor:pointer}
  textarea{width:100%;min-height:170px;resize:vertical;line-height:1.6;
    font-family:ui-monospace,Menlo,monospace;font-size:13px}
  .field-text{display:block;padding:12px 2px;border-bottom:1px solid var(--line-2)}
  .field-text .lbl{margin-bottom:8px}

  /* 开关 */
  .switch{position:relative;width:46px;height:26px;flex:none}
  .switch input{opacity:0;width:0;height:0}
  .slider{position:absolute;inset:0;background:#cfd3da;border-radius:26px;transition:.22s;cursor:pointer}
  .slider:before{content:"";position:absolute;height:20px;width:20px;left:3px;top:3px;
    background:#fff;border-radius:50%;transition:.22s;box-shadow:0 1px 3px rgba(0,0,0,.2)}
  .switch input:checked+.slider{background:var(--green)}
  .switch input:checked+.slider:before{transform:translateX(20px)}

  /* 按钮 */
  button.btn{appearance:none;font:inherit;font-weight:700;cursor:pointer;
    border-radius:9px;padding:8px 16px;border:1.5px solid transparent;transition:.15s}
  button.btn:active{transform:translateY(1px)}
  button.primary{background:linear-gradient(180deg,var(--yellow),var(--yellow-dk));
    color:#4a3a00;box-shadow:0 2px 10px rgba(255,203,5,.35)}
  button.primary:hover{filter:brightness(1.05)}
  button.ghost{background:#fff;color:var(--ink);border-color:var(--line)}
  button.ghost:hover{border-color:#cdd1d8;background:var(--bg-2)}
  button.danger{background:#fff;color:var(--red);border-color:rgba(238,21,21,.35)}
  button.danger:hover{background:var(--red-soft)}
  button.tiny{padding:5px 11px;font-size:12px;border-radius:7px}
  .actbar{margin-top:18px;display:flex;gap:10px;flex-wrap:wrap}

  .tag{display:inline-flex;align-items:center;font-size:11px;font-weight:600;
    padding:2px 8px;border-radius:6px;background:var(--blue-soft);
    color:var(--blue);border:1px solid rgba(47,111,237,.22)}
  .tag.y{background:var(--yellow-soft);color:var(--yellow-dk);border-color:rgba(224,168,0,.3)}
  .pin{font-size:10.5px;font-weight:700;margin-left:7px;padding:1px 7px;border-radius:6px;
    vertical-align:middle}
  .pin.restart{background:var(--orange-soft);color:var(--orange)}
  .pin.ov{background:var(--blue-soft);color:var(--blue)}

  /* 表格 */
  table{width:100%;border-collapse:collapse;font-size:13px}
  thead th{text-align:left;padding:9px 10px;color:var(--fg-mute);font-weight:600;
    font-size:11.5px;letter-spacing:.3px;border-bottom:1.5px solid var(--line)}
  tbody td{padding:10px;border-bottom:1px solid var(--line-2);vertical-align:middle}
  tbody tr:last-child td{border-bottom:none}
  tbody tr:hover{background:var(--bg-2)}
  td .memtext{width:100%}

  /* ── 日志:结构化行卡片(非纯文本)── */
  .logwrap{display:flex;flex-direction:column;gap:7px;max-height:420px;overflow:auto;
    padding-right:4px}
  .logwrap::-webkit-scrollbar{width:9px}
  .logwrap::-webkit-scrollbar-thumb{background:#dadde2;border-radius:6px}
  .logwrap::-webkit-scrollbar-track{background:transparent}
  .li{display:flex;align-items:center;gap:11px;padding:9px 12px;border-radius:10px;
    background:var(--bg-2);border:1px solid var(--line-2);font-size:13px}
  .li:hover{border-color:#dfe2e7}
  .li .ic{width:26px;height:26px;border-radius:8px;flex:none;display:flex;
    align-items:center;justify-content:center;font-size:14px}
  .li .ts{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--fg-mute);
    flex:none;font-variant-numeric:tabular-nums}
  .li .main{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .li .main.wrap{white-space:normal;word-break:break-word}
  .li .meta{flex:none;display:flex;gap:8px;align-items:center;color:var(--fg-dim);font-size:12px}
  .li .num{font-variant-numeric:tabular-nums}
  /* 调用日志图标底色 */
  .li.ok .ic{background:var(--green-soft)} .li.ok{border-left:3px solid var(--green)}
  .li.fail .ic{background:var(--red-soft)} .li.fail{border-left:3px solid var(--red)}
  /* 危险操作 */
  .li.allow .ic{background:var(--green-soft)} .li.allow{border-left:3px solid var(--green)}
  .li.deny .ic{background:var(--red-soft)} .li.deny{border-left:3px solid var(--red)}
  .li.pending .ic{background:var(--orange-soft)} .li.pending{border-left:3px solid var(--orange)}
  .li.deny .cmd,.li.allow .cmd,.li.pending .cmd{
    font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--ink)}
  /* 对话气泡式 */
  .li.user{background:var(--blue-soft);border-color:rgba(47,111,237,.18);border-left:3px solid var(--blue)}
  .li.pika{background:var(--yellow-soft);border-color:rgba(224,168,0,.22);border-left:3px solid var(--yellow)}
  .li.user .ic{background:rgba(47,111,237,.16)} .li.pika .ic{background:rgba(255,203,5,.3)}
  .li.convo .main{white-space:normal;word-break:break-word;line-height:1.55}
  .li .who{font-weight:700;font-size:12px;margin-right:6px}
  .li.user .who{color:var(--blue)} .li.pika .who{color:var(--yellow-dk)}

  /* 空 / 静 */
  .empty{text-align:center;color:var(--fg-mute);padding:28px 0;font-size:13px;line-height:1.7}
  .empty .e{font-size:32px;display:block;margin-bottom:8px;opacity:.55}
  .muted{color:var(--fg-mute);font-size:12.5px}
  .skl{color:var(--fg-mute);font-size:13px;padding:8px 0}
  .mono{font-family:ui-monospace,Menlo,monospace;font-size:12px;word-break:break-all}

  /* lastcall 行 */
  .lastcall{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:13px}
  .lastcall .sep{color:var(--line);}

  /* toast */
  .toast{position:fixed;bottom:26px;left:50%;transform:translate(-50%,16px);
    background:#fff;color:var(--fg);padding:12px 20px;border-radius:12px;
    border:1.5px solid var(--line);box-shadow:var(--shadow-lg);
    font-size:13.5px;opacity:0;transition:.28s cubic-bezier(.2,.8,.2,1);
    pointer-events:none;z-index:99;display:flex;align-items:center;gap:9px}
  .toast.show{opacity:1;transform:translate(-50%,0)}
  .toast.ok{border-color:rgba(47,158,68,.5)}
  .toast.err{border-color:rgba(238,21,21,.5)}
</style>
</head>
<body>
<header>
  <div class="logo">
    <span class="ball"></span>
    <div>
      <h1>皮卡丘控制台</h1>
      <div class="sub">Pikachu Pet · local console</div>
    </div>
  </div>
  <div class="conn" id="conn"><span class="led"></span><span id="conn-txt">连接中…</span>
    <span class="meta" id="conn-meta"></span></div>
</header>

<nav>
  <button data-tab="status" class="on"><span class="ico">📊</span>实时状态</button>
  <button data-tab="config"><span class="ico">⚙️</span>配置</button>
  <button data-tab="tasks"><span class="ico">⏰</span>定时任务</button>
  <button data-tab="memory"><span class="ico">🧠</span>记忆</button>
  <button data-tab="logs"><span class="ico">📜</span>日志</button>
</nav>

<main>
  <!-- ── 实时状态 ── -->
  <section class="tab on" id="tab-status">
    <div class="hero" id="hero">
      <div class="face" id="hero-face">⚡</div>
      <div class="who">
        <div class="now" id="hero-now">—</div>
        <div class="desc" id="hero-desc">读取中…</div>
      </div>
      <div class="pill-row" id="hero-pills"></div>
    </div>
    <div class="alert" id="active-cmd"></div>

    <div class="col2">
      <div class="card"><h2><span class="bar"></span>运行态</h2>
        <div class="grid" id="rt"></div></div>
      <div class="card"><h2><span class="bar"></span>概览</h2>
        <div class="grid" id="ov"></div></div>
    </div>

    <div class="card"><h2><span class="bar"></span>最近一次调用</h2>
      <div id="lastcall" class="lastcall"><span class="muted">—</span></div></div>
  </section>

  <!-- ── 配置 ── -->
  <section class="tab" id="tab-config">
    <div class="card">
      <h2><span class="bar"></span>配置 <small>改完点保存,大多数立即生效;标「需重启」的下次启动生效</small></h2>
      <div id="cfg"><div class="skl">加载中…</div></div>
      <div class="actbar">
        <button class="btn primary" onclick="saveConfig()">💾 保存改动</button>
        <button class="btn ghost" onclick="loadConfig()">↺ 撤销未保存</button>
      </div>
    </div>
  </section>

  <!-- ── 定时任务 ── -->
  <section class="tab" id="tab-tasks">
    <div class="card"><h2><span class="bar"></span>定时任务</h2>
      <div id="tasks"><div class="skl">加载中…</div></div></div>
  </section>

  <!-- ── 记忆 ── -->
  <section class="tab" id="tab-memory">
    <div class="card"><h2><span class="bar"></span>教皮卡丘记住一件事</h2>
      <div class="row" style="border:none;padding:4px 0">
        <select id="m-type" class="ctrl"></select>
        <input type="text" id="m-text" placeholder="皮卡丘要记住的事…" style="flex:1"
          onkeydown="if(event.key==='Enter')addMem()">
        <button class="btn primary ctrl" onclick="addMem()">＋ 记下</button>
      </div>
    </div>
    <div class="card"><h2><span class="bar"></span>记忆库 <small id="mem-count"></small></h2>
      <div id="mem"><div class="skl">加载中…</div></div></div>
  </section>

  <!-- ── 日志 ── -->
  <section class="tab" id="tab-logs">
    <div class="card"><h2><span class="bar"></span>调用日志 <small>最近 100 条 · 新→旧</small></h2>
      <div class="logwrap" id="log-calls"><div class="skl">—</div></div></div>
    <div class="card"><h2><span class="bar"></span>危险操作流水 <small>三层确认留痕</small></h2>
      <div class="logwrap" id="log-danger"><div class="skl">—</div></div></div>
    <div class="card"><h2><span class="bar"></span>对话流水 <small>最近 100 条 · 新→旧</small></h2>
      <div class="logwrap" id="log-convo"><div class="skl">—</div></div></div>
  </section>
</main>

<div class="toast" id="toast"></div>

<script>
const TOKEN = new URLSearchParams(location.search).get("token") || "";
const Q = (s)=>document.querySelector(s);
function api(path, opts={}){
  opts.headers = Object.assign({"X-Token":TOKEN,"Content-Type":"application/json"}, opts.headers||{});
  return fetch(path, opts).then(async r=>{
    const d = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(d.error || ("HTTP "+r.status));
    return d;
  });
}
let _toastTimer;
function toast(msg,kind){ const t=Q("#toast"); t.textContent=msg;
  t.className="toast show"+(kind?(" "+kind):"");
  clearTimeout(_toastTimer);
  _toastTimer=setTimeout(()=>t.classList.remove("show"),2000); }
function esc(s){ return String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function jsAttr(s){ return JSON.stringify(String(s==null?"":s))
  .replace(/&/g,"&amp;").replace(/'/g,"&#39;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
// epoch 秒 → 本地时间字符串(危险/对话流水用)
function fmtTs(ts){ if(!ts) return ""; try{ const d=new Date(ts*1000);
  const p=n=>String(n).padStart(2,"0");
  return `${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}catch(e){ return ""; } }

// ── 选项卡切换 ──
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("nav button").forEach(x=>x.classList.remove("on"));
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
  b.classList.add("on"); Q("#tab-"+b.dataset.tab).classList.add("on");
  if(b.dataset.tab==="config") loadConfig();
  if(b.dataset.tab==="tasks") loadTasks();
  if(b.dataset.tab==="memory") loadMem();
  if(b.dataset.tab==="logs") loadLogs();
});

// ── 实时状态(轮询)──
const STATE_CN = {idle:"待机",walk_right:"散步",walk_left:"散步",walk:"散步",sleep:"睡觉",
  think:"思考中",happy:"开心",cheer:"欢呼",sad:"沮丧",eat:"吃东西",look:"东张西望",
  jump:"跳跃",sing:"哼歌",yawn:"打哈欠",surprise:"惊讶",struggle:"挣扎",dust:"待机",
  glow:"放电",particles:"待机"};
const STATE_FACE = {idle:"⚡",walk:"🐾",walk_left:"🐾",walk_right:"🐾",sleep:"😴",
  think:"💭",happy:"😄",cheer:"🎉",sad:"☁️",eat:"😋",look:"👀",jump:"⤴️",
  sing:"🎵",yawn:"🥱",surprise:"😮",struggle:"😣"};
const STATE_DESC = {idle:"安安静静待着",walk:"溜达中",sleep:"趴下睡着啦",
  think:"正在调用 Claude 想事情",cheer:"任务搞定,放电庆祝",sad:"任务失败,头顶乌云",
  eat:"啃果子",look:"东张西望找乐子",jump:"蹦跶",sing:"哼着小曲",yawn:"困了",
  surprise:"被戳了一下",struggle:"被拖着乱蹬"};

function bdg(on,t){return `<span class="badge ${on?'on':'off'}">${esc(t||(on?'是':'否'))}</span>`;}

async function poll(){
  const conn=Q("#conn");
  try{
    const s = await api("/api/status");
    conn.className="conn ok"; Q("#conn-txt").textContent="已连接";
    const r = s.runtime||{};
    const st = r.state||"idle";

    Q("#hero-face").textContent = STATE_FACE[st] || "⚡";
    Q("#hero-now").textContent = STATE_CN[st] || st || "—";
    Q("#hero-desc").textContent = (r.thinking?"💭 ":"")+(STATE_DESC[st]||"");
    Q("#conn-meta").textContent = "up "+fmtDur(r.uptime_ms);
    const pills=[];
    pills.push(r.chat_open ? '<span class="badge on">聊天窗开</span>' : '<span class="badge off">聊天窗关</span>');
    if(r.chat_busy) pills.push('<span class="badge busy">回复中</span>');
    else if(r.thinking) pills.push('<span class="badge busy">思考中</span>');
    if(r.in_quiet_hours) pills.push('<span class="badge off">静默</span>');
    Q("#hero-pills").innerHTML = pills.join("");

    Q("#rt").innerHTML = [
      ["💬","聊天窗", bdg(r.chat_open,r.chat_open?"开":"关")],
      ["✍️","聊天状态", r.chat_busy?'<span class="badge busy">回复中</span>':bdg(false,"空闲")],
      ["⏰","定时执行中", (r.sched_workers||0)+" 个"],
      ["🧠","后台整理/搭话", (r.memory_workers||0)+" 个"],
      ["⚠️","待确认危险", r.active_confirm?'<span class="badge warn">等你确认</span>':((r.pending_confirms||0)+" 个")],
      ["📋","确认队列", (r.confirm_queue||0)+" 个"],
      ["💡","常驻气泡", bdg(r.bubble_sticky,r.bubble_sticky?"有":"无")],
      ["📦","待发结果", (r.pending_results||0)+" 个"],
      ["🗨️","未读搭话", (r.proactive_topics||0)+" 个"],
      ["🔔","提醒队列", (r.sticky_queue||0)+" 个"],
      ["🌙","静默时段", bdg(r.in_quiet_hours,r.in_quiet_hours?"是":"否")],
      ["💤","空闲时长", fmtDur(r.idle_ms)],
    ].map(([i,k,v])=>`<div class="stat"><div class="k">${i} ${k}</div><div class="v" style="font-size:15px">${v}</div></div>`).join("");

    const acEl=Q("#active-cmd");
    if(r.active_confirm && r.active_confirm_cmd){ acEl.style.display="block";
      acEl.innerHTML='⚠️ <b>正在等你在桌宠上确认</b>:<span class="mono">'+esc(r.active_confirm_cmd)+'</span>'; }
    else { acEl.style.display="none"; }

    Q("#ov").innerHTML = [
      ["🧬","模型", esc(s.model), true],
      ["🔐","权限模式", esc(s.permission_mode)],
      ["⏰","定时任务", (s.tasks_active||0)+" / "+(s.tasks_total||0)],
      ["🧠","记忆条数", s.memory_count||0, true],
      ["🗨️","今日主动搭话", s.proactive_today||0],
      ["📞","调用日志", s.log_counts?.calls||0],
      ["⚠️","危险留痕", s.log_counts?.danger||0],
      ["💬","对话流水", s.log_counts?.convo||0],
    ].map(([i,k,v,hl])=>`<div class="stat ${hl?'hl':''}"><div class="k">${i} ${k}</div><div class="v" style="font-size:${String(v).length>8?'14':'17'}px">${v}</div></div>`).join("");

    if(s.last_call){const c=s.last_call;
      Q("#lastcall").innerHTML =
        `<span class="muted mono">${esc(c.ts||"")}</span>`+
        `<span class="tag y">${esc(c.kind||"")}</span>`+
        `<span class="num">${esc(c.elapsed)}s</span>`+
        `${c.ok?'<span class="badge on">成功</span>':'<span class="badge warn">失败</span>'}`+
        `<span class="muted">入 ${esc(c.prompt_chars)} 字 · 出 ${esc(c.reply_chars)} 字</span>`;
    } else { Q("#lastcall").innerHTML='<span class="muted">还没有调用记录</span>'; }
  }catch(e){
    conn.className="conn bad"; Q("#conn-meta").textContent="";
    Q("#conn-txt").textContent = /fetch|network|Failed/i.test(e.message) ? "桌宠未运行" : ("断开:"+e.message);
  }
}
function fmtDur(ms){ if(!ms&&ms!==0) return "—"; const s=Math.floor(ms/1000);
  if(s<60) return s+"s"; const m=Math.floor(s/60); if(m<60) return m+"m"+(s%60)+"s";
  const h=Math.floor(m/60); return h+"h"+(m%60)+"m"; }

// ── 配置 ──
let CFG_ITEMS = [];
async function loadConfig(){
  try{
    const d = await api("/api/config"); CFG_ITEMS = d.items;
    const groups = {};
    d.items.forEach(it=>{ (groups[it.group]=groups[it.group]||[]).push(it); });
    let html = "";
    for(const g in groups){
      html += `<div class="grp-title"><span class="bar"></span>${esc(g)}</div>`;
      groups[g].forEach(it=>{ html += renderItem(it); });
    }
    Q("#cfg").innerHTML = html || '<div class="empty">无可编辑项</div>';
  }catch(e){ Q("#cfg").innerHTML='<div class="empty"><span class="e">⚠️</span>加载失败:'+esc(e.message)+'</div>'; }
}
function pins(it){
  return (it.needs_restart?`<span class="pin restart">需重启</span>`:"")+
         (it.overridden?`<span class="pin ov">已改</span>`:"");
}
function renderItem(it){
  const help = it.help?`<small>${esc(it.help)}</small>`:"";
  const id="f_"+it.key;
  const lbl = `<b>${esc(it.label)}</b>${pins(it)}${help}`;
  let ctrl="";
  if(it.type==="bool"){
    ctrl=`<label class="switch"><input type="checkbox" id="${id}" ${it.value?"checked":""}><span class="slider"></span></label>`;
  }else if(it.type==="enum"){
    ctrl=`<select id="${id}">`+it.choices.map(c=>`<option value="${esc(c)}" ${c===it.value?"selected":""}>${esc(c||"(默认)")}</option>`).join("")+`</select>`;
  }else if(it.type==="int"||it.type==="float"){
    ctrl=`<input type="number" id="${id}" value="${esc(it.value)}" ${it.min!=null?`min="${it.min}"`:""} ${it.max!=null?`max="${it.max}"`:""} ${it.type==="float"?'step="0.01"':""}>`;
  }else if(it.type==="hours_range"){
    const v=Array.isArray(it.value)?it.value:[0,0];
    ctrl=`<input type="number" id="${id}_a" value="${esc(v[0])}" min="0" max="23" style="width:62px"> <span class="muted">→</span> `+
         `<input type="number" id="${id}_b" value="${esc(v[1])}" min="0" max="23" style="width:62px"> <span class="muted">点</span>`;
  }else if(it.type==="text"){
    const resetBtn = it.overridden
      ? `<button class="btn ghost tiny" style="margin-top:8px" onclick='resetKey(${jsAttr(it.key)})'>恢复默认(重启生效)</button>`
      : "";
    return `<div class="field-text"><div class="lbl">${lbl}</div>
      <textarea id="${id}">${esc(it.value)}</textarea>${resetBtn}</div>`;
  }
  return `<div class="row"><div class="lbl">${lbl}</div><div class="ctrl">${ctrl}</div>
    ${it.overridden?`<button class="btn ghost tiny" onclick='resetKey(${jsAttr(it.key)})'>默认</button>`:""}</div>`;
}
function readItemValue(it){
  if(it.type==="hours_range"){
    const a=Q("#f_"+it.key+"_a"), b=Q("#f_"+it.key+"_b");
    if(!a||!b) return undefined;
    const av=parseInt(a.value,10), bv=parseInt(b.value,10);
    if(isNaN(av)||isNaN(bv)) return undefined;
    return [av, bv];
  }
  const el=Q("#f_"+it.key); if(!el) return undefined;
  if(it.type==="bool") return el.checked;
  if(it.type==="int") return parseInt(el.value,10);
  if(it.type==="float") return parseFloat(el.value);
  return el.value;
}
async function saveConfig(){
  const payload={};
  CFG_ITEMS.forEach(it=>{ const v=readItemValue(it); if(v!==undefined && !(typeof v==="number"&&isNaN(v))) payload[it.key]=v; });
  try{
    const r = await api("/api/config",{method:"POST",body:JSON.stringify(payload)});
    let msg="已保存 ✓";
    if(r.needs_restart && r.needs_restart.length) msg+=`(${r.needs_restart.length} 项重启后生效)`;
    toast(msg,"ok"); loadConfig();
  }catch(e){ toast("保存失败:"+e.message,"err"); }
}
async function resetKey(key){
  try{ await api("/api/config/reset",{method:"POST",body:JSON.stringify({keys:[key]})});
    toast("已标记恢复默认,重启后生效","ok"); loadConfig(); }
  catch(e){ toast("失败:"+e.message,"err"); }
}

// ── 定时任务 ──
async function loadTasks(){
  try{
    const d = await api("/api/tasks"); const ts=d.tasks||[];
    if(!ts.length){ Q("#tasks").innerHTML='<div class="empty"><span class="e">⏰</span>暂无定时任务<br><span class="muted">跟皮卡丘说「3 分钟后提醒我喝水」就会出现在这</span></div>'; return; }
    Q("#tasks").innerHTML = `<table><thead><tr><th>描述</th><th>类型</th><th>状态</th><th></th></tr></thead><tbody>`+
      ts.map(t=>`<tr><td>${esc(t.desc||t.prompt||"")}</td>
        <td><span class="tag">${esc(t.mode||"")} · ${esc(t.kind||"")}</span></td>
        <td>${t.done?'<span class="badge off">已完成</span>':'<span class="badge on">待触发</span>'}</td>
        <td style="text-align:right"><button class="btn danger tiny" onclick='delTask(${jsAttr(t.id)})'>删除</button></td></tr>`).join("")+`</tbody></table>`;
  }catch(e){ Q("#tasks").innerHTML='<div class="empty"><span class="e">⚠️</span>加载失败:'+esc(e.message)+'</div>'; }
}
async function delTask(id){
  if(!confirm("删除这个定时任务?")) return;
  try{ await api("/api/tasks/"+encodeURIComponent(id),{method:"DELETE"}); toast("已删除","ok"); loadTasks(); }
  catch(e){ toast("失败:"+e.message,"err"); }
}

// ── 记忆 ──
let MEM_TYPES=[];
const TYPE_CN={fact:"事实",preference:"喜好",todo:"待办",routine:"作息",topic:"话题"};
async function loadMem(){
  try{
    const d = await api("/api/memory"); MEM_TYPES=d.types||[];
    Q("#m-type").innerHTML = MEM_TYPES.map(t=>`<option value="${esc(t)}">${esc(TYPE_CN[t]||t)}</option>`).join("");
    const ms=d.memories||[];
    Q("#mem-count").textContent = ms.length ? `共 ${ms.length} 条` : "";
    if(!ms.length){ Q("#mem").innerHTML='<div class="empty"><span class="e">🧠</span>还没有记忆<br><span class="muted">聊久了皮卡丘会自己记;也可以在上面手动教它</span></div>'; return; }
    Q("#mem").innerHTML = `<table><thead><tr><th style="width:64px">类型</th><th>内容</th><th style="width:60px">权重</th><th style="width:120px"></th></tr></thead><tbody>`+
      ms.map(m=>`<tr>
        <td><span class="tag y">${esc(TYPE_CN[m.type]||m.type)}</span></td>
        <td><input type="text" class="memtext" value="${esc(m.text)}"></td>
        <td class="mono" style="text-align:center">${(typeof m.weight==="number")?m.weight.toFixed(2):esc(m.weight)}</td>
        <td style="text-align:right;white-space:nowrap">
          <button class="btn ghost tiny" onclick='saveMem(${jsAttr(m.id)},this)'>存</button>
          <button class="btn danger tiny" onclick='delMem(${jsAttr(m.id)})'>删</button></td></tr>`).join("")+`</tbody></table>`;
  }catch(e){ Q("#mem").innerHTML='<div class="empty"><span class="e">⚠️</span>加载失败:'+esc(e.message)+'</div>'; }
}
async function addMem(){
  const text=Q("#m-text").value.trim(); if(!text){toast("先写点内容","err");return;}
  try{ await api("/api/memory",{method:"POST",body:JSON.stringify({type:Q("#m-type").value,text})});
    Q("#m-text").value=""; toast("已记住 ✓","ok"); loadMem(); }
  catch(e){ toast("失败:"+e.message,"err"); }
}
async function saveMem(id,btn){
  const inp=btn.closest("tr").querySelector(".memtext");
  const text=inp.value.trim(); if(!text){toast("内容不能为空","err");return;}
  try{ await api("/api/memory",{method:"PUT",body:JSON.stringify({id,text})});
    toast("已更新 ✓","ok"); loadMem(); }
  catch(e){ toast("失败:"+e.message,"err"); }
}
async function delMem(id){
  if(!confirm("删除这条记忆?")) return;
  try{ await api("/api/memory",{method:"DELETE",body:JSON.stringify({id})}); toast("已删除","ok"); loadMem(); }
  catch(e){ toast("失败:"+e.message,"err"); }
}

// ── 日志(结构化行卡片)──
function liEmpty(icon,txt){ return `<div class="empty"><span class="e">${icon}</span>${txt}</div>`; }
// 调用日志:图标 / 类型 / 耗时 / 字数 / 成败
function renderCall(l){
  const ok = !!l.ok;
  return `<div class="li ${ok?'ok':'fail'}">
    <div class="ic">${ok?'✅':'❌'}</div>
    <div class="ts">${esc(l.ts||'')}</div>
    <div class="main"><span class="tag y">${esc(l.kind||'')}</span></div>
    <div class="meta">
      <span class="num">${esc(l.elapsed)}s</span>
      <span class="muted">入${esc(l.prompt_chars)}/出${esc(l.reply_chars)}</span>
    </div></div>`;
}
// 危险操作:决策色条 + 命令 mono
const DEC_CN={allow:"已放行",deny:"已拒绝",pending:"待确认"};
const DEC_IC={allow:"✓",deny:"✕",pending:"⏳"};
function renderDanger(l){
  const d=(l.decision||"pending");
  return `<div class="li ${esc(d)}">
    <div class="ic">${DEC_IC[d]||'•'}</div>
    <div class="ts">${esc(fmtTs(l.ts))}</div>
    <div class="main cmd">${esc(l.command||'')}</div>
    <div class="meta"><span class="badge ${d==='allow'?'on':(d==='deny'?'warn':'busy')}">${DEC_CN[d]||esc(d)}</span></div>
  </div>`;
}
// 对话:气泡式
function renderConvo(l){
  const isU = l.role==="user";
  const txt = String(l.text||"").replace(/\s+/g," ").trim();
  return `<div class="li convo ${isU?'user':'pika'}">
    <div class="ic">${isU?'🧑':'⚡'}</div>
    <div class="main"><span class="who">${isU?'你':'皮卡'}</span>${esc(txt)}</div>
    <div class="ts">${esc(fmtTs(l.ts))}</div>
  </div>`;
}
async function loadLogs(){
  const fill=(sel,lines,render,icon,emptyTxt)=>{
    const arr=(lines||[]).slice().reverse();
    Q(sel).innerHTML = arr.length ? arr.map(render).join("") : liEmpty(icon,emptyTxt);
  };
  try{ const c=await api("/api/logs/calls"); fill("#log-calls",c.lines,renderCall,"📞","还没有调用记录"); }
  catch(e){ Q("#log-calls").innerHTML=liEmpty("⚠️","加载失败"); }
  try{ const d=await api("/api/logs/danger"); fill("#log-danger",d.lines,renderDanger,"🛡️","还没有危险操作记录"); }
  catch(e){ Q("#log-danger").innerHTML=liEmpty("⚠️","加载失败"); }
  try{ const v=await api("/api/logs/convo"); fill("#log-convo",v.lines,renderConvo,"💬","还没有对话记录"); }
  catch(e){ Q("#log-convo").innerHTML=liEmpty("⚠️","加载失败"); }
}

poll(); setInterval(poll, 1500);
</script>
</body>
</html>"""
