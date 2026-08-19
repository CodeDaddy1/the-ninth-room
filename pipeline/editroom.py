"""The Edit Room — a local review UI for grading the cut shot by shot.

`/usr/bin/python3 -m pipeline.cli editroom <slug>` starts a localhost server
and prints the URL. The page shows every beat as a card: its 480p proxy, its
transcript, its overlays, grouped by chapter — with Approve / Flag+note on
each. Decisions land in work/<slug>/review.json, which the shot-fixer agent
consumes: it patches exactly the flagged beats, re-proxies them, and resets
their status to "reworked" for re-review. Approved beats are never touched.

Everything is local and $0: stdlib http.server, no build step, no cloud.
The page is written fresh on every start, so UI changes ship by restarting.

What breaks if this is wrong: review decisions get lost (the one file that
matters is review.json — it is written atomically via replace) or the page
shows stale proxies (the state endpoint re-reads the proxy dir every call,
so a re-render shows up on refresh).
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ingest import work_path, analysis_dir

PORT = 8765


def _state(slug: str) -> "dict":
    work = work_path(slug)
    out = analysis_dir(slug)
    tl = json.loads((out / "timeline_map.json").read_text())
    plan = json.loads((work / "edit_plan.json").read_text())
    caps = {}
    if (work / "captions.json").exists():
        caps = {c["beat_id"]: c["text"]
                for c in json.loads((work / "captions.json").read_text())["beats"]}
    cards_by_beat: "dict[str, list]" = {}
    if (work / "graphics_plan.json").exists():
        for c in json.loads((work / "graphics_plan.json").read_text())["cards"]:
            cards_by_beat.setdefault(c["beat_id"], []).append(
                {"id": c["id"], "kit": c.get("kit_type", c.get("type")),
                 "copy": c.get("text") or c.get("stat") or c.get("kicker") or ""})
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
    proxies = {}
    pdir = work / "proxies"
    if pdir.is_dir():
        for p in pdir.glob("BT*.mp4"):
            proxies[p.name.split(".")[0]] = p.name

    plan_by_id = {b["id"]: b for b in plan["beats"]}
    chapters = [{"id": c["id"], "title": c["title"], "beats": []}
                for c in plan.get("chapters", [])]
    ch_index = {c["id"]: c for c in chapters}
    for beat in tl["beats"]:
        pb = plan_by_id.get(beat["id"], {})
        entry = {
            "id": beat["id"],
            "dur": round(beat["record_e"] - beat["record_s"], 1),
            "record_s": round(beat["record_s"], 1),
            "purpose": pb.get("purpose", ""),
            "take": pb.get("take_id", ""),
            "caption": caps.get(beat["id"], ""),
            "cards": cards_by_beat.get(beat["id"], []),
            "broll": [br["clip_id"] for br in pb.get("broll", [])],
            "proxy": proxies.get(beat["id"]),
            "review": review.get(beat["id"], {}),
        }
        ch = ch_index.get(pb.get("chapter_id"))
        (ch["beats"] if ch else chapters[0]["beats"] if chapters else []).append(entry)
    total = len(tl["beats"])
    approved = sum(1 for r in review.values() if r.get("status") == "approved")
    flagged = sum(1 for r in review.values() if r.get("status") == "flagged")
    return {"slug": slug, "chapters": chapters,
            "counts": {"total": total, "approved": approved, "flagged": flagged}}


def _save_review(slug: str, beat_id: str, payload: "dict") -> None:
    work = work_path(slug)
    path = work / "review.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    entry = data.get(beat_id, {})
    entry.update({k: v for k, v in payload.items() if k in ("status", "note")})
    import time
    entry["ts"] = int(time.time())
    data[beat_id] = entry
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def serve(slug: str, port: int = PORT, log=print) -> None:
    work = work_path(slug)
    page = PAGE.replace("__SLUG__", slug)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._send(200, _state(slug))
            elif self.path.startswith("/proxies/"):
                p = (work / "proxies" / os.path.basename(self.path)).resolve()
                if p.exists() and p.suffix == ".mp4":
                    data = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send(404, {"error": "no proxy"})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/api/review":
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if not body.get("beat_id"):
                    self._send(400, {"error": "beat_id required"})
                    return
                _save_review(slug, body["beat_id"], body)
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log("[editroom] http://127.0.0.1:%d  (Ctrl-C to stop)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit Room — __SLUG__</title>
<style>
:root{--accent:#12B76A;--ink:#09090B;--panel:#141416;--panel2:#1C1C1F;
--text:#FCFCFA;--muted:#9A9A94;--hair:#26262A;--flag:#E5484D}
*{box-sizing:border-box;margin:0}
body{background:var(--ink);color:var(--text);
font-family:Manrope,'Helvetica Neue',sans-serif;font-size:15px;line-height:1.5}
header{position:sticky;top:0;z-index:9;background:var(--ink);
border-bottom:1px solid var(--hair);padding:14px 22px;display:flex;
align-items:center;gap:18px}
h1{font-family:Gabarito,sans-serif;font-size:20px;letter-spacing:-.02em}
.tally{margin-left:auto;display:flex;gap:14px;font-size:13px;color:var(--muted)}
.tally b{color:var(--text)}
.tally .ok b{color:var(--accent)} .tally .fl b{color:var(--flag)}
.bar{height:5px;background:var(--panel2)}
.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
main{max-width:1500px;margin:0 auto;padding:20px 22px 80px}
h2{font-family:Gabarito,sans-serif;font-size:17px;margin:30px 0 12px;
color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
h2 b{color:var(--text)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}
.beat{background:var(--panel);border:1px solid var(--hair);border-radius:12px;
overflow:hidden;display:flex;flex-direction:column}
.beat.approved{border-color:rgba(18,183,106,.55)}
.beat.flagged{border-color:rgba(229,72,77,.6)}
.beat.reworked{border-color:#E8A33D88}
video{width:100%;aspect-ratio:16/9;background:#000;display:block}
.body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:8px;flex:1}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.bid{font-family:Gabarito,sans-serif;font-weight:800}
.chip{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
background:var(--panel2);border-radius:4px;padding:2px 7px;color:var(--muted)}
.chip.acc{color:var(--accent)}
.cap{font-size:13px;color:var(--muted);max-height:56px;overflow:hidden}
.note{width:100%;background:var(--panel2);border:1px solid var(--hair);
border-radius:7px;color:var(--text);padding:7px 9px;font:inherit;font-size:13px;
resize:vertical;min-height:34px}
.acts{display:flex;gap:8px;margin-top:auto}
button{flex:1;font:inherit;font-size:13px;font-weight:700;padding:8px 0;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
button.ok.on{background:var(--accent);border-color:var(--accent);color:#06110B}
button.fl.on{background:var(--flag);border-color:var(--flag)}
.noproxy{display:flex;align-items:center;justify-content:center;
aspect-ratio:16/9;background:#000;color:var(--muted);font-size:13px}
</style></head><body>
<header><h1>Edit Room · __SLUG__</h1>
<div class="tally"><span class="ok">approved <b id="tA">0</b></span>
<span class="fl">flagged <b id="tF">0</b></span>
<span>total <b id="tT">0</b></span></div></header>
<div class="bar"><i id="prog" style="width:0"></i></div>
<main id="main">loading…</main>
<script>
let S=null;
async function load(){S=await (await fetch('/api/state')).json();render();}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function render(){
  const m=document.getElementById('main');m.innerHTML='';
  let A=0,F=0,T=0;
  for(const ch of S.chapters){
    const h=document.createElement('h2');
    h.innerHTML='<b>'+esc(ch.title)+'</b> · '+ch.beats.length+' shots';
    m.appendChild(h);
    const g=document.createElement('div');g.className='grid';m.appendChild(g);
    for(const b of ch.beats){
      T++;const st=b.review.status||'';
      if(st==='approved')A++;if(st==='flagged')F++;
      const el=document.createElement('div');el.className='beat '+st;
      const vid=b.proxy?'<video preload="metadata" controls src="/proxies/'+b.proxy+'"></video>'
        :'<div class="noproxy">no proxy — run: pipeline.cli proxy __SLUG__ --beat '+b.id+'</div>';
      const cards=b.cards.map(c=>'<span class="chip acc">'+esc(c.kit)+': '+esc(String(c.copy).slice(0,22))+'</span>').join('');
      el.innerHTML=vid+'<div class="body">'+
        '<div class="row"><span class="bid">'+b.id+'</span>'+
        '<span class="chip">'+esc(b.purpose)+'</span>'+
        '<span class="chip">'+b.dur+'s @ '+fmt(b.record_s)+'</span>'+
        (b.broll.length?'<span class="chip">b-roll ×'+b.broll.length+'</span>':'')+'</div>'+
        (cards?'<div class="row">'+cards+'</div>':'')+
        '<div class="cap">'+esc(b.caption)+'</div>'+
        '<textarea class="note" placeholder="note for the shot-fixer…">'+esc(b.review.note||'')+'</textarea>'+
        '<div class="acts"><button class="ok '+(st==='approved'?'on':'')+'">Approve</button>'+
        '<button class="fl '+(st==='flagged'?'on':'')+'">Flag</button></div></div>';
      const note=el.querySelector('.note');
      el.querySelector('.ok').onclick=()=>save(b.id,'approved',note.value);
      el.querySelector('.fl').onclick=()=>save(b.id,'flagged',note.value);
      note.addEventListener('change',()=>save(b.id,st||null,note.value,true));
      g.appendChild(el);
    }
  }
  document.getElementById('tA').textContent=A;
  document.getElementById('tF').textContent=F;
  document.getElementById('tT').textContent=T;
  document.getElementById('prog').style.width=(T?100*A/T:0)+'%';
}
function fmt(s){return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');}
async function save(id,status,note,quiet){
  await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({beat_id:id,status:status,note:note})});
  if(!quiet)load();
}
load();
</script></body></html>
"""
