"""Word-synced render. Caption TEXT comes from the script (always correct);
TIMING comes from the Whisper transcript, aligned with difflib (handles mishears).
Footage cuts on sentence boundaries; ballot years pop on beat with red REJECTED stamps."""
import sys, os, glob, json, subprocess, difflib
sys.path.insert(0, '~/Projects/curated-curiosities')
from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
from worker import assemble, config

BASE = '~/Projects/curated-curiosities/work/houston-no-zoning'
ASSETS = BASE + '/assets/houston-has-no-zoning-laws'
TMP = BASE + '/tmp'
W, H, FPS = 1080, 1920, config.DEFAULT_FPS
NAVY=(14,27,44); CREAM=(244,239,230); AMBER=(232,163,61); RED=(214,40,40)
wm = str(config.PROJECT_ROOT/'brand'/'exports'/'watermark.png')
TOTAL, BRAND = 55.0, 2.0; CONTENT_END = TOTAL - BRAND

def sh(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode!=0: print('FAIL:',' '.join(map(str,cmd))[:120]); print(p.stderr[-600:]); raise SystemExit(1)
def font(sz):
    for f in ['/System/Library/Fonts/Supplemental/Arial Bold.ttf','/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Helvetica.ttc']:
        if os.path.exists(f):
            try: return ImageFont.truetype(f,sz)
            except Exception: pass
    return ImageFont.load_default()
def norm(s): return ''.join(c for c in s.lower() if c.isalnum())

# --- script lines (caption TEXT = these; index = beat) -------------------
LINES=[
 "America's fourth-largest city has no zoning laws. None.",
 "That means a high-rise can legally go up right next to a single-family home — a bar beside a school.",
 "Every other major American city decides what can be built where. Houston? Doesn't.",
 "And it's not an accident. Houstonians were asked to add zoning three times — 1948, 1962, and 1993 — and voted it down every single time.",
 "But here's the part people get wrong — it's not a free-for-all. The city still controls lot sizes, density, and parking, and private deed restrictions quietly shape about a quarter of it.",
 "So it's not no rules. It's no single rulebook — the biggest American experiment in just letting people build.",
 "would your city ever do this?",
]
script_words=[]
for li,ln in enumerate(LINES):
    for tok in ln.replace('—',' ').split():
        if norm(tok): script_words.append({'disp':tok.strip('.,—'),'norm':norm(tok),'line':li})

# --- align script -> transcript times (difflib) --------------------------
words=json.load(open(TMP+'/words.json'))
S=[x['norm'] for x in script_words]; T=[norm(x['w']) for x in words]; Tt=[x['s'] for x in words]
times=[None]*len(S)
for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,S,T,autojunk=False).get_opcodes():
    if tag=='equal':
        for k in range(i2-i1): times[i1+k]=Tt[j1+k]
known=[(i,t) for i,t in enumerate(times) if t is not None]
for idx in range(len(times)):
    if times[idx] is None:
        prev=[k for k in known if k[0]<idx]; nxt=[k for k in known if k[0]>idx]
        if prev and nxt:
            (pi,pt),(ni,nt)=prev[-1],nxt[0]; times[idx]=pt+(nt-pt)*((idx-pi)/(ni-pi))
        elif prev: times[idx]=prev[-1][1]
        elif nxt: times[idx]=nxt[0][1]
        else: times[idx]=0.0
line_words=defaultdict(list)
for i,sw in enumerate(script_words): line_words[sw['line']].append((sw['disp'],times[i]))
for li in line_words: line_words[li].sort(key=lambda x:x[1])
starts=[line_words[li][0][1] for li in range(7)]
for i in range(1,7): starts[i]=max(starts[i],starts[i-1]+0.3)
spans=[(round(starts[i],2), round((starts[i+1] if i<6 else CONTENT_END),2)) for i in range(7)]
print('beat spans:',spans)

# --- PNG renderers -------------------------------------------------------
def word_png(word,dest):
    img=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(img); fo=font(110)
    bb=d.textbbox((0,0),word,font=fo); twd=bb[2]-bb[0]; x=(W-twd)/2-bb[0]; y=1290; pad=40
    d.rounded_rectangle([x+bb[0]-pad,y-pad,x+bb[0]+twd+pad,y+(bb[3]-bb[1])+pad+16],radius=32,fill=(14,27,44,190))
    d.text((x,y-bb[1]),word,font=fo,fill=CREAM); img.save(dest)
def text_png(text,sz,color,y,dest,x=None,angle=0):
    img=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(img); fo=font(sz)
    if angle:
        bb=d.textbbox((0,0),text,font=fo); chip=Image.new('RGBA',(bb[2]-bb[0]+40,bb[3]-bb[1]+40),(0,0,0,0))
        ImageDraw.Draw(chip).text((20-bb[0],20-bb[1]),text,font=fo,fill=color); chip=chip.rotate(angle,expand=True,resample=Image.BICUBIC)
        img.alpha_composite(chip,(int(x if x is not None else (W-chip.width)/2),int(y))); img.save(dest); return
    twd=d.textlength(text,font=fo); d.text(((W-twd)/2 if x is None else x,y),text,font=fo,fill=color); img.save(dest)
def img_clip(src,dur,out,crop=True):
    vf=(f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p' if crop else f'scale={W}:{H},fps={FPS},setsar=1,format=yuv420p')
    sh(['ffmpeg','-y','-loop','1','-i',src,'-t',f'{dur:.3f}','-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',out])
def norm_stock(src,dur,out):
    vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p'
    sh(['ffmpeg','-y','-stream_loop','-1','-i',src,'-t',f'{dur:.3f}','-vf',vf,'-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',out])
def overlay_timed(base,ovs,dur,out):
    ins=['-i',base]; [ins.extend(['-i',o[0]]) for o in ovs]; fc=''; prev='[0:v]'
    for i,(p,s,e) in enumerate(ovs):
        en=f":enable='between(t,{s:.2f},{e:.2f})'" if (s>0.01 or e<dur-0.01) else ''
        fc+=f"{prev}[{i+1}:v]overlay=0:0:format=auto{en}[v{i}];"; prev=f'[v{i}]'
    sh(['ffmpeg','-y']+ins+['-filter_complex',fc.rstrip(';'),'-map',prev,'-t',f'{dur:.3f}','-r',str(FPS),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',out])

# --- beats ---------------------------------------------------------------
photos={2:TMP+'/pexels-iefproductions-31626712.jpg',6:TMP+'/pexels-jayjay13-479671953-16142972.jpg'}
stock={0:'S01',1:'S02',4:'S05',5:'S06'}
final=[]
for i in range(7):
    bs,be=spans[i]; dur=round(be-bs,3); base=f'{TMP}/b{i}.mp4'; out=f'{TMP}/s{i}.mp4'
    if i==3:  # ballot
        Image.new('RGB',(W,H),NAVY).save(TMP+'/navy.png'); img_clip(TMP+'/navy.png',dur,base,crop=False)
        ov=[]; text_png('Houston put zoning to a vote',54,CREAM,470,TMP+'/bal_t.png'); ov.append((TMP+'/bal_t.png',0,dur))
        yrs=[(w['w'].strip('.,'),w['s']) for w in words if w['w'].strip('.,').isdigit() and len(w['w'].strip('.,'))==4]
        for (yr,gt),ry in zip(yrs,[780,1070,1360]):
            rel=max(0,gt-bs); yp=f'{TMP}/y{yr}.png'; rp=f'{TMP}/r{yr}.png'
            text_png(yr,118,CREAM,ry,yp,x=W/2-300); text_png('REJECTED',66,RED,ry+18,rp,x=W/2+30,angle=-9)
            ov.append((yp,round(rel,2),dur)); ov.append((rp,round(rel+0.45,2),dur))
        overlay_timed(base,ov,dur,out); print(f'S04 ballot {dur:.1f}s years@',[round(g-bs,1) for _,g in yrs])
    else:
        if i in photos: img_clip(photos[i],dur,base)
        else: norm_stock(glob.glob(os.path.join(ASSETS,stock[i]+'_*',stock[i]+'_cand*.mp4'))[0],dur,base)
        lw=line_words[i]; ov=[]
        for j,(disp,t) in enumerate(lw):
            wp=f'{TMP}/w{i}_{j}.png'; word_png(disp,wp)
            rs=max(0,t-bs); re=(lw[j+1][1]-bs) if j+1<len(lw) else dur
            ov.append((wp,round(rs,2),round(min(re,dur),2)))
        overlay_timed(base,ov,dur,out); print(f'beat{i} {dur:.1f}s {len(lw)} captions')
    final.append(Path(out))

# --- brand + compose -----------------------------------------------------
bc=Image.new('RGB',(W,H),NAVY); d=ImageDraw.Draw(bc); y=760
lg=Image.open(wm).convert('RGBA'); r=620/lg.width; lg=lg.resize((620,int(lg.height*r))); bc.paste(lg,((W-lg.width)//2,560),lg); y=560+lg.height+70
nf,hf=font(74),font(46)
d.text(((W-d.textlength('Curated Curiosities',font=nf))/2,y),'Curated Curiosities',font=nf,fill=CREAM)
d.text(((W-d.textlength('@CuratedCuriosities',font=hf))/2,y+100),'@CuratedCuriosities',font=hf,fill=AMBER)
bc.save(TMP+'/brand_card.png'); brand=Path(TMP)/'S08.mp4'; img_clip(TMP+'/brand_card.png',BRAND,str(brand),crop=False)
content=Path(TMP)/'content_s.mp4'; assemble.concat_clips(final,content,Path(TMP))
content_wm=Path(TMP)/'content_s_wm.mp4'; assemble.overlay_watermark(content,Path(wm),content_wm)
combined=Path(TMP)/'combined_s.mp4'; assemble.concat_clips([content_wm,brand],combined,Path(TMP))
vo=Path(TMP)/'vo55.m4a'; sh(['ffmpeg','-y','-i',BASE+'/voiceover.mp3','-af','apad','-t',str(TOTAL),'-c:a','aac','-b:a','192k',str(vo)])
out=BASE+'/rough_cut.mp4'; sh(['ffmpeg','-y','-i',str(combined),'-i',str(vo),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',out])
print('OUTPUT',out)
