"""The Edit Room — a local review UI for grading the cut shot by shot.

`/usr/bin/python3 -m pipeline.cli editroom <slug>` starts a localhost server
and prints the URL. The page is a review desk: a sidebar lists every shot
with its status dot, the main pane plays ONE shot at a time — approve or
flag it and the desk auto-advances to the next unreviewed shot, so a full
pass never requires scrolling a wall of cards. Decisions land in
work/<slug>/review.json, which the shot-fixer agent consumes: it patches
exactly the flagged beats, re-proxies them, and resets their status to
"reworked" for re-review. Approved beats are never touched.

Saving: every decision POSTs immediately; notes autosave ~1s after typing
stops and flush on blur/navigate/close (sendBeacon). The header shows the
live save state plus a Save button that flushes anything pending — the
button is reassurance, the autosave is the mechanism.

Serving video correctly matters: the proxy endpoint honors HTTP Range
requests (206) — browsers require ranges to seek, and Safari refuses to
play without them — and sends Cache-Control: no-store so a proxy fetched
mid-render (the BT103 incident) can never stick in the browser cache.

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
            # mtime in the URL busts any stale browser-cached copy of a
            # proxy that was later re-rendered under the same name
            proxies[p.name.split(".")[0]] = "%s?v=%d" % (p.name, p.stat().st_mtime)

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
    # a note-only autosave sends status:null — that must never erase a
    # decision already on file
    if payload.get("status") in ("approved", "flagged", "reworked"):
        entry["status"] = payload["status"]
    if "note" in payload:
        entry["note"] = payload["note"]
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
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_video(self, p: Path):
            size = p.stat().st_size
            start, end, partial = 0, size - 1, False
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                spec = rng[6:].split(",")[0].strip()
                s, _, e = spec.partition("-")
                try:
                    if s:
                        start = int(s)
                        if e:
                            end = int(e)
                    elif e:  # suffix form: the last N bytes
                        start = max(size - int(e), 0)
                    partial = True
                except ValueError:
                    start, end, partial = 0, size - 1, False
                end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            with open(p, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206 if partial else 200)
            if partial:
                self.send_header("Content-Range",
                                 "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the player aborts range reads constantly; that's normal

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._send(200, _state(slug))
            elif self.path.startswith("/proxies/"):
                name = os.path.basename(self.path.split("?")[0])
                p = (work / "proxies" / name).resolve()
                if p.exists() and p.suffix == ".mp4":
                    self._send_video(p)
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
--text:#FCFCFA;--muted:#9A9A94;--hair:#26262A;--flag:#E5484D;--rework:#E8A33D}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--ink);color:var(--text);display:flex;flex-direction:column;
font-family:Manrope,'Helvetica Neue',sans-serif;font-size:15px;line-height:1.5;
overflow:hidden}
header{background:var(--ink);border-bottom:1px solid var(--hair);
padding:12px 20px;display:flex;align-items:center;gap:16px;flex:none}
h1{font-family:Gabarito,sans-serif;font-size:19px;letter-spacing:-.02em}
.tally{margin-left:auto;display:flex;gap:14px;font-size:13px;color:var(--muted);
white-space:nowrap}
.tally b{color:var(--text);font-variant-numeric:tabular-nums}
.tally .ok b{color:var(--accent)} .tally .fl b{color:var(--flag)}
.save{display:flex;align-items:center;gap:10px}
#saveState{font-size:12.5px;color:var(--muted);white-space:nowrap}
#saveState.err{color:var(--flag)} #saveState.busy{color:var(--rework)}
#saveBtn{font:inherit;font-size:13px;font-weight:700;padding:7px 16px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
#saveBtn:hover{border-color:var(--accent)}
.bar{height:4px;background:var(--panel2);flex:none}
.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
.wrap{flex:1;display:grid;grid-template-columns:290px 1fr;min-height:0}
aside{overflow-y:auto;border-right:1px solid var(--hair);padding-bottom:30px}
.chh{position:sticky;top:0;background:var(--ink);z-index:2;
font-family:Gabarito,sans-serif;font-size:12px;letter-spacing:.07em;
text-transform:uppercase;color:var(--muted);padding:12px 14px 6px;
border-bottom:1px solid var(--hair)}
.brow{display:grid;grid-template-columns:12px 50px 1fr auto;gap:9px;
align-items:center;padding:6px 14px 6px 11px;cursor:pointer;
border-left:3px solid transparent;font-size:13px}
.brow:hover{background:var(--panel)}
.brow.cur{background:var(--panel2);border-left-color:var(--accent)}
.dot{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--hair)}
.dot.approved{background:var(--accent);border-color:var(--accent)}
.dot.flagged{background:var(--flag);border-color:var(--flag)}
.dot.reworked{background:var(--rework);border-color:var(--rework)}
.brow .bid{font-family:Gabarito,sans-serif;font-weight:800}
.brow .pu{color:var(--muted);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;font-size:12px}
.brow .du{color:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums}
.stage{overflow-y:auto;padding:20px 26px 60px}
.focus{max-width:940px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.crumb{font-size:13px;color:var(--muted)}
.crumb b{color:var(--text);font-family:Gabarito,sans-serif}
video{width:100%;aspect-ratio:16/9;background:#000;border-radius:12px;
display:block;outline:none}
.noproxy{display:flex;align-items:center;justify-content:center;
aspect-ratio:16/9;background:#000;border-radius:12px;color:var(--muted);
font-size:13px;text-align:center;padding:20px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
background:var(--panel2);border-radius:4px;padding:3px 8px;color:var(--muted)}
.chip.acc{color:var(--accent)}
.cap{font-size:14px;color:var(--muted);border-left:2px solid var(--hair);
padding-left:12px}
.note{width:100%;background:var(--panel);border:1px solid var(--hair);
border-radius:9px;color:var(--text);padding:10px 12px;font:inherit;
font-size:14px;resize:vertical;min-height:64px}
.note:focus{border-color:var(--accent);outline:none}
.acts{display:flex;gap:10px}
.acts button{flex:1;font:inherit;font-size:15px;font-weight:800;padding:13px 0;
border-radius:9px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer;font-family:Gabarito,sans-serif}
.acts button kbd{font-family:inherit;font-size:11px;opacity:.55;font-weight:400;
border:1px solid currentColor;border-radius:4px;padding:0 5px;margin-left:8px}
.acts .ok.on{background:var(--accent);border-color:var(--accent);color:#06110B}
.acts .fl.on{background:var(--flag);border-color:var(--flag)}
.nav{display:flex;gap:10px;align-items:center}
.nav button{font:inherit;font-size:13px;font-weight:700;padding:9px 16px;
border-radius:7px;border:1px solid var(--hair);background:transparent;
color:var(--muted);cursor:pointer}
.nav button:hover{color:var(--text);border-color:var(--muted)}
.nav .nu{margin-left:auto;color:var(--accent);border-color:rgba(18,183,106,.4)}
.nav .nu:hover{border-color:var(--accent);color:var(--accent)}
.done{background:var(--panel);border:1px solid rgba(18,183,106,.5);
border-radius:12px;padding:26px;text-align:center;
font-family:Gabarito,sans-serif;font-size:17px}
.hint{font-size:12px;color:var(--muted);text-align:center}
.hint kbd{border:1px solid var(--hair);border-radius:4px;padding:0 5px;
font-family:inherit}
</style></head><body>
<header><h1>Edit Room · __SLUG__</h1>
<div class="tally"><span class="ok">approved <b id="tA">0</b></span>
<span class="fl">flagged <b id="tF">0</b></span>
<span>left <b id="tL">0</b></span></div>
<div class="save"><span id="saveState">All changes saved</span>
<button id="saveBtn">Save</button></div></header>
<div class="bar"><i id="prog" style="width:0"></i></div>
<div class="wrap"><aside id="side"></aside>
<section class="stage"><div class="focus" id="focus">loading…</div></section></div>
<script>
const SLUG='__SLUG__', LS='editroom.'+SLUG+'.current';
let S=null, order=[], rows={}, idx=0, dirty={}, timers={};

function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmt(s){return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');}
function cur(){return order[idx];}
function needsReview(b){const st=b.review.status;return !st||st==='reworked';}

async function boot(){
  S=await (await fetch('/api/state')).json();
  order=[];
  for(const ch of S.chapters)for(const b of ch.beats){b.chapter=ch.title;order.push(b);}
  buildSide();
  const remembered=localStorage.getItem(LS);
  let start=order.findIndex(b=>b.id===remembered);
  if(start<0)start=order.findIndex(needsReview);
  if(start<0)start=0;
  select(start,true);
  counts();
}

function buildSide(){
  const side=document.getElementById('side');side.innerHTML='';
  let i=0;
  for(const ch of S.chapters){
    const h=document.createElement('div');h.className='chh';
    h.textContent=ch.title;side.appendChild(h);
    for(const b of ch.beats){
      const j=i++;
      const r=document.createElement('div');r.className='brow';
      r.innerHTML='<span class="dot"></span><span class="bid">'+b.id+'</span>'+
        '<span class="pu">'+esc(b.purpose)+'</span>'+
        '<span class="du">'+b.dur+'s</span>';
      r.onclick=()=>select(j);
      rows[b.id]=r;side.appendChild(r);patchRow(b);
    }
  }
}

function patchRow(b){
  const d=rows[b.id].querySelector('.dot');
  d.className='dot '+(b.review.status||'');
}

function select(i,first){
  if(!first)flushNote(cur().id);
  idx=i;localStorage.setItem(LS,cur().id);
  renderFocus();
  for(const id in rows)rows[id].classList.toggle('cur',id===cur().id);
  rows[cur().id].scrollIntoView({block:'nearest'});
}

function renderFocus(){
  const b=cur(), f=document.getElementById('focus');
  const st=b.review.status||'';
  const pos=idx+1, T=order.length;
  const vid=b.proxy
    ?'<video id="vid" controls autoplay playsinline src="/proxies/'+b.proxy+'"></video>'
    :'<div class="noproxy">no proxy yet — run:<br>pipeline.cli proxy '+SLUG+' --beat '+b.id+'</div>';
  const cards=b.cards.map(c=>'<span class="chip acc">'+esc(c.kit)+': '+esc(String(c.copy).slice(0,26))+'</span>').join('');
  f.innerHTML=
    '<div class="crumb"><b>'+b.id+'</b> · '+esc(b.chapter)+' · shot '+pos+' of '+T+'</div>'+
    vid+
    '<div class="row"><span class="chip">'+esc(b.purpose)+'</span>'+
    '<span class="chip">'+b.dur+'s @ '+fmt(b.record_s)+'</span>'+
    (b.take?'<span class="chip">'+esc(b.take)+'</span>':'')+
    (b.broll.length?'<span class="chip">b-roll ×'+b.broll.length+'</span>':'')+
    cards+'</div>'+
    (b.caption?'<div class="cap">'+esc(b.caption)+'</div>':'')+
    '<textarea class="note" id="note" placeholder="note for the shot-fixer…">'+
      esc(dirty[b.id]!==undefined?dirty[b.id]:(b.review.note||''))+'</textarea>'+
    '<div class="acts">'+
    '<button class="ok '+(st==='approved'?'on':'')+'" id="bOk">Approve<kbd>A</kbd></button>'+
    '<button class="fl '+(st==='flagged'?'on':'')+'" id="bFl">Flag<kbd>F</kbd></button></div>'+
    '<div class="nav"><button id="bPrev">‹ Prev</button>'+
    '<button id="bNext">Next ›</button>'+
    '<button class="nu" id="bNu">Next unreviewed ↵</button></div>'+
    '<div class="hint"><kbd>A</kbd> approve · <kbd>F</kbd> flag · '+
    '<kbd>←</kbd><kbd>→</kbd> prev/next · <kbd>↵</kbd> next unreviewed · '+
    '<kbd>space</kbd> play/pause</div>';
  const note=document.getElementById('note');
  note.addEventListener('input',()=>queueNote(b.id,note.value));
  note.addEventListener('blur',()=>flushNote(b.id));
  document.getElementById('bOk').onclick=()=>decide('approved');
  document.getElementById('bFl').onclick=()=>decide('flagged');
  document.getElementById('bPrev').onclick=()=>select((idx-1+order.length)%order.length);
  document.getElementById('bNext').onclick=()=>select((idx+1)%order.length);
  document.getElementById('bNu').onclick=gotoUnreviewed;
}

function gotoUnreviewed(){
  const T=order.length;
  for(let k=1;k<=T;k++){
    const j=(idx+k)%T;
    if(needsReview(order[j])){select(j);return;}
  }
  const f=document.getElementById('focus');
  const d=document.createElement('div');d.className='done';
  d.textContent='Every shot is reviewed. Tell Claude to run the shot-fixer on the flags.';
  f.prepend(d);
}

function counts(){
  let A=0,F=0;
  for(const b of order){
    if(b.review.status==='approved')A++;
    else if(b.review.status==='flagged')F++;
  }
  const T=order.length;
  document.getElementById('tA').textContent=A;
  document.getElementById('tF').textContent=F;
  document.getElementById('tL').textContent=T-A-F;
  document.getElementById('prog').style.width=(T?100*(A+F)/T:0)+'%';
}

function setState(txt,cls){
  const el=document.getElementById('saveState');
  el.textContent=txt;el.className=cls||'';
}

async function post(body){
  const r=await fetch('/api/review',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok)throw new Error('save failed');
}

function queueNote(id,val){
  dirty[id]=val;
  setState('Unsaved changes…','busy');
  clearTimeout(timers[id]);
  timers[id]=setTimeout(()=>flushNote(id),900);
}

async function flushNote(id){
  if(dirty[id]===undefined)return;
  const b=order.find(x=>x.id===id), note=dirty[id];
  clearTimeout(timers[id]);
  try{
    await post({beat_id:id,status:b.review.status||null,note:note});
    b.review.note=note;
    if(dirty[id]===note)delete dirty[id];
    if(!Object.keys(dirty).length)setSaved();
  }catch(e){
    setState('Save failed — retrying…','err');
    timers[id]=setTimeout(()=>flushNote(id),3000);
  }
}

function setSaved(){
  const t=new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
  setState('All changes saved · '+t);
}

async function decide(status){
  const b=cur(), note=document.getElementById('note').value;
  clearTimeout(timers[b.id]);delete dirty[b.id];
  setState('Saving…','busy');
  try{
    await post({beat_id:b.id,status:status,note:note});
    b.review={status:status,note:note};
    patchRow(b);counts();setSaved();
    setTimeout(gotoUnreviewed,150);
  }catch(e){setState('Save failed — click Save to retry','err');}
}

document.getElementById('saveBtn').onclick=async()=>{
  const ids=Object.keys(dirty);
  if(!ids.length){setSaved();return;}
  setState('Saving…','busy');
  for(const id of ids)await flushNote(id);
};

document.addEventListener('keydown',e=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='textarea'||tag==='input'){
    if(e.key==='Escape')e.target.blur();
    return;
  }
  if(e.key==='a'||e.key==='A')decide('approved');
  else if(e.key==='f'||e.key==='F')decide('flagged');
  else if(e.key==='ArrowLeft')select((idx-1+order.length)%order.length);
  else if(e.key==='ArrowRight')select((idx+1)%order.length);
  else if(e.key==='Enter')gotoUnreviewed();
  else if(e.key===' '){
    e.preventDefault();
    const v=document.getElementById('vid');
    if(v)v.paused?v.play():v.pause();
  }
});

window.addEventListener('beforeunload',()=>{
  for(const id in dirty){
    const b=order.find(x=>x.id===id);
    navigator.sendBeacon('/api/review',
      JSON.stringify({beat_id:id,status:(b&&b.review.status)||null,note:dirty[id]}));
  }
});

boot();
</script></body></html>
"""
