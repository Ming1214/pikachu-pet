"""Web 控制台的内嵌前端(单页 HTML/CSS/JS,无外部资源、无构建)。

拆成独立文件只为让 web_console.py 聚焦后端逻辑。这里是纯字符串。
精灵球配色致敬桌宠主题(上红下白、黑带、黄电)。token 由页面从自身 url 的
?token= 读出,后续所有 fetch 自动带上(同 token 同源)。
"""

DENIED_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>皮卡丘控制台</title><style>
body{font-family:-apple-system,"PingFang SC",sans-serif;background:#2b2b2b;color:#fff;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
.box{background:#fff;color:#2b2b2b;padding:32px 40px;border-radius:18px;border:3px solid #2b2b2b}
h1{color:#ee1515;margin:0 0 8px}
</style></head><body><div class="box"><h1>⚡ 访问被拒</h1>
<p>缺少或错误的 token。请用桌宠启动时打印的完整链接打开本页。</p></div></body></html>"""


PAGE_HTML = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ 皮卡丘控制台</title>
<style>
  :root{
    --red:#ee1515; --red-dk:#c81010; --black:#2b2b2b; --yellow:#ffcb05;
    --yellow-soft:#fff4c2; --blue:#3b5bdb; --bg:#f4f4f4; --card:#fff;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,"PingFang SC","Hiragino Sans GB",sans-serif;
       background:var(--bg);color:var(--black)}
  header{background:linear-gradient(var(--red),var(--red-dk));color:#fff;padding:14px 20px;
         border-bottom:5px solid var(--black);display:flex;align-items:center;gap:12px}
  header h1{font-size:19px;margin:0}
  header .dot{margin-left:auto;font-size:13px;opacity:.9}
  nav{display:flex;gap:4px;background:var(--black);padding:0 12px;flex-wrap:wrap}
  nav button{background:none;border:none;color:#ccc;padding:11px 16px;cursor:pointer;
             font-size:14px;border-bottom:3px solid transparent}
  nav button.on{color:var(--yellow);border-bottom-color:var(--yellow);font-weight:bold}
  main{padding:18px;max-width:920px;margin:0 auto}
  .tab{display:none} .tab.on{display:block}
  .card{background:var(--card);border:2px solid var(--black);border-radius:14px;
        padding:16px;margin-bottom:14px}
  .card h2{margin:0 0 12px;font-size:15px;color:var(--red)}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  .stat{background:var(--bg);border-radius:10px;padding:10px 12px}
  .stat .k{font-size:12px;color:#888} .stat .v{font-size:20px;font-weight:bold;margin-top:2px}
  .badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:bold}
  .badge.on{background:#d3f9d8;color:#2b8a3e} .badge.off{background:#ffe3e3;color:#c92a2a}
  .badge.busy{background:var(--yellow-soft);color:#a8870a}
  .row{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #eee}
  .row:last-child{border-bottom:none}
  .row .lbl{flex:1} .row .lbl small{color:#999;display:block;font-size:11px;margin-top:2px}
  .grp-title{font-weight:bold;color:var(--black);margin:16px 0 4px;font-size:13px}
  input[type=number],input[type=text],select{font:inherit;padding:6px 9px;border:1.5px solid #ccc;
        border-radius:8px;background:#fff}
  input[type=number]{width:120px} select{min-width:160px}
  textarea{width:100%;font:inherit;padding:10px;border:1.5px solid #ccc;border-radius:10px;
           min-height:160px;resize:vertical}
  .switch{position:relative;width:46px;height:26px;flex:none}
  .switch input{opacity:0;width:0;height:0}
  .slider{position:absolute;inset:0;background:#ccc;border-radius:26px;transition:.2s;cursor:pointer}
  .slider:before{content:"";position:absolute;height:20px;width:20px;left:3px;top:3px;
                 background:#fff;border-radius:50%;transition:.2s}
  .switch input:checked+.slider{background:#2b8a3e}
  .switch input:checked+.slider:before{transform:translateX(20px)}
  button.act{background:var(--blue);color:#fff;border:none;padding:8px 16px;border-radius:9px;
             cursor:pointer;font:inherit;font-weight:bold}
  button.act:hover{filter:brightness(1.08)}
  button.ghost{background:#fff;color:var(--black);border:1.5px solid #ccc}
  button.danger{background:#fa5252}
  .restart{font-size:11px;color:#e8590c;margin-left:6px}
  .ov{font-size:11px;color:var(--blue);margin-left:6px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #eee;vertical-align:top}
  th{color:#888;font-weight:600}
  .mono{font-family:ui-monospace,Menlo,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--black);
         color:#fff;padding:11px 20px;border-radius:24px;font-size:14px;opacity:0;
         transition:opacity .25s;pointer-events:none;z-index:99}
  .toast.show{opacity:1}
  .tag{font-size:11px;padding:1px 7px;border-radius:6px;background:var(--yellow-soft);color:#a8870a}
  .muted{color:#999;font-size:13px}
</style>
</head>
<body>
<header>
  <span style="font-size:24px">⚡</span>
  <h1>皮卡丘控制台</h1>
  <span class="dot" id="conn">连接中…</span>
</header>
<nav>
  <button data-tab="status" class="on">实时状态</button>
  <button data-tab="config">配置</button>
  <button data-tab="tasks">定时任务</button>
  <button data-tab="memory">记忆</button>
  <button data-tab="logs">日志</button>
</nav>
<main>
  <!-- 实时状态 -->
  <section class="tab on" id="tab-status">
    <div class="card"><h2>运行态</h2><div class="grid" id="rt"></div>
      <div id="active-cmd" class="mono" style="display:none;margin-top:10px;padding:10px;
           background:#fff4c2;border:1.5px solid #f2c200;border-radius:8px;color:#a8870a"></div></div>
    <div class="card"><h2>概览</h2><div class="grid" id="ov"></div></div>
    <div class="card"><h2>最近一次调用</h2><div id="lastcall" class="mono muted">—</div></div>
  </section>

  <!-- 配置 -->
  <section class="tab" id="tab-config">
    <div class="card"><h2>配置(改完点保存,大多数立即生效)</h2>
      <div id="cfg"></div>
      <div style="margin-top:14px;display:flex;gap:10px">
        <button class="act" onclick="saveConfig()">💾 保存改动</button>
        <button class="act ghost" onclick="loadConfig()">↺ 撤销未保存</button>
      </div>
    </div>
  </section>

  <!-- 定时任务 -->
  <section class="tab" id="tab-tasks">
    <div class="card"><h2>定时任务</h2><div id="tasks"><p class="muted">加载中…</p></div></div>
  </section>

  <!-- 记忆 -->
  <section class="tab" id="tab-memory">
    <div class="card"><h2>新增记忆</h2>
      <div class="row">
        <select id="m-type"></select>
        <input type="text" id="m-text" placeholder="皮卡丘要记住的事…" style="flex:1">
        <button class="act" onclick="addMem()">＋ 加</button>
      </div>
    </div>
    <div class="card"><h2>记忆库</h2><div id="mem"><p class="muted">加载中…</p></div></div>
  </section>

  <!-- 日志 -->
  <section class="tab" id="tab-logs">
    <div class="card"><h2>调用日志(最近 100)</h2><div id="log-calls" class="mono">—</div></div>
    <div class="card"><h2>危险操作流水</h2><div id="log-danger" class="mono">—</div></div>
    <div class="card"><h2>对话流水(最近 100)</h2><div id="log-convo" class="mono">—</div></div>
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
function toast(msg){ const t=Q("#toast"); t.textContent=msg; t.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer=setTimeout(()=>t.classList.remove("show"),1800); }
function esc(s){ return String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
// 给【单引号 HTML 属性】里内嵌的 JS 字符串字面量做安全编码:JSON.stringify 得到带双引号
// 的 JS 字符串,再把会破坏单引号属性/标签的字符转成 HTML 实体。用于 onclick='fn(...)'。
function jsAttr(s){ return JSON.stringify(String(s==null?"":s))
  .replace(/&/g,"&amp;").replace(/'/g,"&#39;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// ---- 页签切换 ----
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("nav button").forEach(x=>x.classList.remove("on"));
  document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
  b.classList.add("on"); Q("#tab-"+b.dataset.tab).classList.add("on");
  if(b.dataset.tab==="config") loadConfig();
  if(b.dataset.tab==="tasks") loadTasks();
  if(b.dataset.tab==="memory") loadMem();
  if(b.dataset.tab==="logs") loadLogs();
});

// ---- 实时状态(轮询)----
const STATE_CN = {idle:"待机",walk_right:"散步→",walk_left:"←散步",sleep:"睡觉",think:"思考中",
  happy:"开心",cheer:"欢呼",sad:"沮丧",eat:"吃东西",look:"东张西望",jump:"跳跃",sing:"哼歌",
  yawn:"打哈欠",surprise:"惊讶"};
function bdg(on,t){return `<span class="badge ${on?'on':'off'}">${t||(on?'是':'否')}</span>`;}
async function poll(){
  try{
    const s = await api("/api/status");
    Q("#conn").textContent = "● 已连接";
    const r = s.runtime||{};
    Q("#rt").innerHTML = [
      ["当前动作", STATE_CN[r.state]||r.state||"—"],
      ["思考中", bdg(r.thinking,r.thinking?"是":"否")],
      ["聊天窗", bdg(r.chat_open,r.chat_open?"开":"关")],
      ["聊天忙", r.chat_busy?'<span class="badge busy">回复中</span>':bdg(false,"空闲")],
      ["定时任务执行", (r.sched_workers||0)+" 个"],
      ["后台整理/搭话", (r.memory_workers||0)+" 个"],
      ["待确认危险操作", r.active_confirm?'<span class="badge busy">等你确认</span>':((r.pending_confirms||0)+" 个")],
      ["确认队列", (r.confirm_queue||0)+" 个"],
      ["常驻气泡", bdg(r.bubble_sticky,r.bubble_sticky?"有":"无")],
      ["待发结果暂存", (r.pending_results||0)+" 个"],
      ["未读搭话话题", (r.proactive_topics||0)+" 个"],
      ["提醒队列", (r.sticky_queue||0)+" 个"],
      ["静默时段", bdg(r.in_quiet_hours,r.in_quiet_hours?"是":"否")],
      ["空闲", fmtDur(r.idle_ms)],
      ["运行时长", fmtDur(r.uptime_ms)],
    ].map(([k,v])=>`<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
    // 当前正在等确认的危险命令(若有),单独醒目显示
    const acEl=Q("#active-cmd");
    if(r.active_confirm && r.active_confirm_cmd){ acEl.style.display="block";
      acEl.textContent="⚠️ 正在等你确认:"+r.active_confirm_cmd; }
    else { acEl.style.display="none"; }
    Q("#ov").innerHTML = [
      ["模型", s.model],
      ["权限模式", s.permission_mode],
      ["定时任务", (s.tasks_active||0)+" / "+(s.tasks_total||0)],
      ["记忆条数", s.memory_count||0],
      ["今日主动搭话", s.proactive_today||0],
      ["调用日志行", s.log_counts?.calls||0],
      ["危险操作留痕", s.log_counts?.danger||0],
      ["对话流水行", s.log_counts?.convo||0],
      ["待确认信令", s.log_counts?.guardian_pending||0],
      ["工具事件流", s.log_counts?.tool_events||0],
    ].map(([k,v])=>`<div class="stat"><div class="k">${k}</div><div class="v" style="font-size:16px">${esc(v)}</div></div>`).join("");
    if(s.last_call){const c=s.last_call;
      Q("#lastcall").textContent = `${c.ts} · ${c.kind} · ${c.elapsed}s · ${c.ok?"成功":"失败"} · 入${c.prompt_chars}字/出${c.reply_chars}字`;}
  }catch(e){
    const msg = /fetch|network/i.test(e.message) ? "桌宠没在跑或网络不通" : e.message;
    Q("#conn").textContent = "○ 断开:" + msg;
  }
}
function fmtDur(ms){ if(!ms&&ms!==0) return "—"; const s=Math.floor(ms/1000);
  if(s<60) return s+"s"; const m=Math.floor(s/60); if(m<60) return m+"m"+(s%60)+"s";
  const h=Math.floor(m/60); return h+"h"+(m%60)+"m"; }

// ---- 配置 ----
let CFG_ITEMS = [];
async function loadConfig(){
  const d = await api("/api/config"); CFG_ITEMS = d.items;
  const groups = {};
  d.items.forEach(it=>{ (groups[it.group]=groups[it.group]||[]).push(it); });
  let html = "";
  for(const g in groups){
    html += `<div class="grp-title">${esc(g)}</div>`;
    groups[g].forEach(it=>{ html += renderItem(it); });
  }
  Q("#cfg").innerHTML = html;
}
function renderItem(it){
  const rs = it.needs_restart?`<span class="restart">需重启</span>`:"";
  const ov = it.overridden?`<span class="ov">●已改</span>`:"";
  const help = it.help?`<small>${esc(it.help)}</small>`:"";
  let ctrl="";
  const id="f_"+it.key;
  if(it.type==="bool"){
    ctrl=`<label class="switch"><input type="checkbox" id="${id}" ${it.value?"checked":""}><span class="slider"></span></label>`;
  }else if(it.type==="enum"){
    ctrl=`<select id="${id}">`+it.choices.map(c=>`<option value="${esc(c)}" ${c===it.value?"selected":""}>${esc(c||"(默认)")}</option>`).join("")+`</select>`;
  }else if(it.type==="int"||it.type==="float"){
    ctrl=`<input type="number" id="${id}" value="${esc(it.value)}" ${it.min!=null?`min="${it.min}"`:""} ${it.max!=null?`max="${it.max}"`:""} ${it.type==="float"?'step="0.01"':""}>`;
  }else if(it.type==="hours_range"){
    const v=Array.isArray(it.value)?it.value:[0,0];
    ctrl=`<input type="number" id="${id}_a" value="${esc(v[0])}" min="0" max="23" style="width:64px"> → `+
         `<input type="number" id="${id}_b" value="${esc(v[1])}" min="0" max="23" style="width:64px"> 点`;
  }else if(it.type==="text"){
    const resetBtn = it.overridden
      ? `<button class="act ghost" style="margin-top:6px" onclick='resetKey(${jsAttr(it.key)})'>恢复默认(重启后生效)</button>`
      : "";
    return `<div style="padding:9px 0;border-bottom:1px solid #eee"><div class="lbl"><b>${esc(it.label)}</b>${rs}${ov}${help}</div>
      <textarea id="${id}">${esc(it.value)}</textarea>${resetBtn}</div>`;
  }
  return `<div class="row"><div class="lbl">${esc(it.label)}${rs}${ov}${help}</div>${ctrl}
    ${it.overridden?`<button class="act ghost" onclick='resetKey(${jsAttr(it.key)})'>默认</button>`:""}</div>`;
}
function readItemValue(it){
  if(it.type==="hours_range"){
    const a=Q("#f_"+it.key+"_a"), b=Q("#f_"+it.key+"_b");
    if(!a||!b) return undefined;
    const av=parseInt(a.value,10), bv=parseInt(b.value,10);
    if(isNaN(av)||isNaN(bv)) return undefined;  // 任一框空着就跳过(别发 [NaN,..] 脏数据)
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
    let msg="已保存";
    if(r.needs_restart && r.needs_restart.length) msg+=`(${r.needs_restart.length} 项需重启生效)`;
    toast(msg); loadConfig();
  }catch(e){ toast("保存失败:"+e.message); }
}
async function resetKey(key){
  try{ await api("/api/config/reset",{method:"POST",body:JSON.stringify({keys:[key]})});
    toast("已标记恢复默认,重启后生效"); loadConfig(); }
  catch(e){ toast("失败:"+e.message); }
}

// ---- 定时任务 ----
async function loadTasks(){
  try{
    const d = await api("/api/tasks"); const ts=d.tasks||[];
    if(!ts.length){ Q("#tasks").innerHTML='<p class="muted">暂无定时任务</p>'; return; }
    Q("#tasks").innerHTML = `<table><tr><th>描述</th><th>类型</th><th>状态</th><th></th></tr>`+
      ts.map(t=>`<tr><td>${esc(t.desc||t.prompt||"")}</td>
        <td><span class="tag">${esc(t.mode||"")}/${esc(t.kind||"")}</span></td>
        <td>${t.done?'<span class="badge off">已完成</span>':'<span class="badge on">待触发</span>'}</td>
        <td><button class="act danger" onclick='delTask(${jsAttr(t.id)})'>删</button></td></tr>`).join("")+`</table>`;
  }catch(e){ Q("#tasks").innerHTML='<p class="muted">加载失败:'+esc(e.message)+'</p>'; }
}
async function delTask(id){
  if(!confirm("删除这个定时任务?")) return;
  try{ await api("/api/tasks/"+encodeURIComponent(id),{method:"DELETE"}); toast("已删除"); loadTasks(); }
  catch(e){ toast("失败:"+e.message); }
}

// ---- 记忆 ----
let MEM_TYPES=[];
const TYPE_CN={fact:"事实",preference:"喜好",todo:"待办",routine:"作息",topic:"话题"};
async function loadMem(){
  try{
    const d = await api("/api/memory"); MEM_TYPES=d.types||[];
    Q("#m-type").innerHTML = MEM_TYPES.map(t=>`<option value="${t}">${TYPE_CN[t]||t}</option>`).join("");
    const ms=d.memories||[];
    if(!ms.length){ Q("#mem").innerHTML='<p class="muted">还没有记忆</p>'; return; }
    Q("#mem").innerHTML = `<table><tr><th>类型</th><th>内容</th><th>权重</th><th></th></tr>`+
      ms.map(m=>`<tr>
        <td><span class="tag">${TYPE_CN[m.type]||esc(m.type)}</span></td>
        <td><input type="text" class="memtext" style="width:100%" value="${esc(m.text)}"></td>
        <td>${(typeof m.weight==="number")?m.weight.toFixed(2):esc(m.weight)}</td>
        <td><button class="act" onclick='saveMem(${jsAttr(m.id)},this)'>存</button>
            <button class="act danger" onclick='delMem(${jsAttr(m.id)})'>删</button></td></tr>`).join("")+`</table>
      <p class="muted" style="margin-top:8px">提示:在内容框里改文字,改完点「存」。</p>`;
  }catch(e){ Q("#mem").innerHTML='<p class="muted">加载失败:'+esc(e.message)+'</p>'; }
}
async function addMem(){
  const text=Q("#m-text").value.trim(); if(!text){toast("先写点内容");return;}
  try{ await api("/api/memory",{method:"POST",body:JSON.stringify({type:Q("#m-type").value,text})});
    Q("#m-text").value=""; toast("已记住"); loadMem(); }
  catch(e){ toast("失败:"+e.message); }
}
async function saveMem(id,btn){
  const inp=btn.closest("tr").querySelector(".memtext");
  const text=inp.value.trim(); if(!text){toast("内容不能为空");return;}
  try{ await api("/api/memory",{method:"PUT",body:JSON.stringify({id,text})});
    toast("已更新"); loadMem(); }   // 刷新:确认服务端实际存了什么,且失效条目会消失
  catch(e){ toast("失败:"+e.message); }
}
async function delMem(id){
  if(!confirm("删除这条记忆?")) return;
  try{ await api("/api/memory",{method:"DELETE",body:JSON.stringify({id})}); toast("已删除"); loadMem(); }
  catch(e){ toast("失败:"+e.message); }
}

// ---- 日志 ----
async function loadLogs(){
  const fmtCall=l=>`${l.ts} · ${l.kind} · ${l.elapsed}s · ${l.ok?"✓":"✗"} · 入${l.prompt_chars}/出${l.reply_chars}`;
  const fmtDanger=l=>`${l.ts||""} · ${l.decision||""} · ${l.command||""}`;
  const fmtConvo=l=>`[${l.role==="user"?"你":"皮卡"}] ${l.text||""}`;
  try{ const c=await api("/api/logs/calls"); Q("#log-calls").textContent=(c.lines||[]).map(fmtCall).reverse().join("\n")||"(空)"; }catch(e){}
  try{ const d=await api("/api/logs/danger"); Q("#log-danger").textContent=(d.lines||[]).map(fmtDanger).reverse().join("\n")||"(空)"; }catch(e){}
  try{ const v=await api("/api/logs/convo"); Q("#log-convo").textContent=(v.lines||[]).map(fmtConvo).reverse().join("\n")||"(空)"; }catch(e){}
}

poll(); setInterval(poll, 1500);
</script>
</body>
</html>"""
