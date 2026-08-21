"""One-off final renderer for houston-no-zoning: captions + ballot card + brand outro.
Pillow renders text to PNGs (this ffmpeg has no drawtext); ffmpeg composites.
Re-runnable. Run with: /usr/bin/python3 work/houston-no-zoning/_build.py
"""
import sys, os, glob, subprocess
sys.path.insert(0, '~/Projects/the-ninth-room')
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from worker import assemble, config

WORK = '~/Projects/the-ninth-room/work/houston-no-zoning'
ASSETS = WORK + '/assets/houston-has-no-zoning-laws'
TMP = WORK + '/tmp'
W, H, FPS = 1080, 1920, config.DEFAULT_FPS
NAVY=(14,27,44); CREAM=(244,239,230); AMBER=(232,163,61)
wm = str(config.PROJECT_ROOT/'brand'/'exports'/'watermark.png')

def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print('FAIL:', ' '.join(map(str,cmd))[:100]); print(p.stderr[-500:]); raise SystemExit(1)

def font(sz):
    for f in ['/System/Library/Fonts/Supplemental/Arial Bold.ttf','/System/Library/Fonts/Supplemental/Arial.ttf','/System/Library/Fonts/Helvetica.ttc']:
        if os.path.exists(f):
            try: return ImageFont.truetype(f, sz)
            except Exception: pass
    return ImageFont.load_default()

def wrap(d, text, fo, maxw):
    lines, cur = [], ''
    for w in text.split():
        t = (cur+' '+w).strip()
        if d.textlength(t, font=fo) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def caption_png(text, dest):
    img = Image.new('RGBA',(W,H),(0,0,0,0)); d = ImageDraw.Draw(img); fo = font(62)
    lines = wrap(d, text, fo, 900); lh = int(62*1.3); total = lh*len(lines)
    y0 = 1470 - total                      # block sits in the lower third, above UI safe zone
    mw = max(d.textlength(l,font=fo) for l in lines); pad = 32
    d.rounded_rectangle([(W-mw)/2-pad, y0-pad, (W+mw)/2+pad, y0+total+pad], radius=28, fill=(14,27,44,180))
    for i,l in enumerate(lines):
        lw = d.textlength(l,font=fo); d.text(((W-lw)/2, y0+i*lh), l, font=fo, fill=CREAM)
    img.save(dest)

def ballot_card(dest):
    img = Image.new('RGB',(W,H),NAVY); d = ImageDraw.Draw(img)
    tf = font(56)
    for i,l in enumerate(wrap(d,'Houston put zoning to a vote', tf, 900)):
        lw = d.textlength(l,font=tf); d.text(((W-lw)/2, 470+i*72), l, font=tf, fill=CREAM)
    yf, rf = font(104), font(58)
    for yr, yy in zip(['1948','1962','1993'], [780, 1070, 1360]):
        yw = d.textlength(yr,font=yf); rw = d.textlength('REJECTED',font=rf); gap=56
        x = (W-(yw+gap+rw))/2
        d.text((x, yy), yr, font=yf, fill=CREAM)
        d.text((x+yw+gap, yy+34), 'REJECTED', font=rf, fill=AMBER)
    img.save(dest)

def brand_card(dest):
    img = Image.new('RGB',(W,H),NAVY); d = ImageDraw.Draw(img); y = 760
    try:
        lg = Image.open(wm).convert('RGBA'); r = 620/lg.width; lg = lg.resize((620, int(lg.height*r)))
        img.paste(lg, ((W-lg.width)//2, 560), lg); y = 560 + lg.height + 70
    except Exception as e:
        print('logo skip:', e)
    nf, hf = font(74), font(46)
    t='Curated Curiosities'; d.text(((W-d.textlength(t,font=nf))/2, y), t, font=nf, fill=CREAM)
    h='@CuratedCuriosities'; d.text(((W-d.textlength(h,font=hf))/2, y+100), h, font=hf, fill=AMBER)
    img.save(dest)

def img_clip(src, dur, out, crop=True):
    vf = (f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p'
          if crop else f'scale={W}:{H},fps={FPS},setsar=1,format=yuv420p')
    sh(['ffmpeg','-y','-loop','1','-i',src,'-t',str(dur),'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',out])

def add_caption(base, cap_png, out):
    sh(['ffmpeg','-y','-i',base,'-i',cap_png,'-filter_complex','[0:v][1:v]overlay=0:0:format=auto[v]','-map','[v]',
        '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',out])

# --- build beats ---------------------------------------------------------
captions = {
 'S01':'Houston has NO zoning',
 'S02':'Skyscraper next to a house. Bar next to a school.',
 'S03':'Every other big city zones — not Houston',
 'S05':'Not lawless: lot size, density, parking, deed restrictions',
 'S06':'No single rulebook',
 'S07':'Would your city ever do this?',
}
durs = {'S01':5,'S02':8,'S03':7,'S04':11,'S05':11,'S06':5,'S07':6}
photos = {'S03': TMP+'/pexels-iefproductions-31626712.jpg', 'S07': TMP+'/pexels-jayjay13-479671953-16142972.jpg'}

order = ['S01','S02','S03','S04','S05','S06','S07']
final_clips = []
for sid in order:
    base = Path(TMP)/f'{sid}_base.mp4'; final = Path(TMP)/f'{sid}_final.mp4'
    if sid == 'S04':
        card = Path(TMP)/'S04_ballot.png'; ballot_card(str(card)); img_clip(str(card), durs[sid], str(final), crop=False)
        print('S04: ballot card (1948/1962/1993)')
    else:
        if sid in photos:
            img_clip(photos[sid], durs[sid], str(base))
        else:
            cand = glob.glob(os.path.join(ASSETS, sid+'_*', sid+'_cand*.mp4'))
            assemble.normalize_stock_shot(Path(cand[0]), base, durs[sid], W, H)
        cap = Path(TMP)/f'{sid}_cap.png'; caption_png(captions[sid], str(cap)); add_caption(str(base), str(cap), str(final))
        print(f'{sid}: footage + caption \"{captions[sid][:40]}\"')
    final_clips.append(final)

# brand outro
brand = Path(TMP)/'S08_brand.mp4'; bc = Path(TMP)/'brand_card.png'; brand_card(str(bc)); img_clip(str(bc), 2, str(brand), crop=False)
print('S08: brand outro with wordmark')

# --- compose -------------------------------------------------------------
content = Path(TMP)/'content53.mp4'; assemble.concat_clips(final_clips, content, Path(TMP))
content_wm = Path(TMP)/'content53_wm.mp4'; assemble.overlay_watermark(content, Path(wm), content_wm)
combined = Path(TMP)/'combined55.mp4'; assemble.concat_clips([content_wm, brand], combined, Path(TMP))
vo55 = Path(TMP)/'vo55.m4a'
sh(['ffmpeg','-y','-i',WORK+'/voiceover.mp3','-af','apad','-t','55','-c:a','aac','-b:a','192k',str(vo55)])
out = WORK+'/rough_cut.mp4'
sh(['ffmpeg','-y','-i',str(combined),'-i',str(vo55),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',out])
print('OUTPUT', out)
