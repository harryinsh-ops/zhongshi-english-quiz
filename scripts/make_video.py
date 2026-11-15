#!/usr/bin/env python3
"""情景英语短剧生成器：PIL 画面 + flite 配音 + ffmpeg 合成。
用法: python3 make_video.py script.json out.mp4
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
SR = 22050
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
FONT_K = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
TMP = "tmp_audio"
os.makedirs(TMP, exist_ok=True)

def font(path, size):
    return ImageFont.truetype(path, size, index=2)  # SC

# ---------------------------------------------------------------- audio
def tts(text, voice, path, tempo=0.88):
    safe = text.replace("'", "").replace(":", " ")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"flite=text='{safe}':voice={voice}",
                    "-af", f"atempo={tempo},highpass=f=90,lowpass=f=7000,volume=1.6",
                    "-ar", str(SR), "-ac", "1", path], check=True)
    with wave.open(path) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return data

def tone(freq, dur, vol=0.3, decay=6.0):
    t = np.arange(int(SR * dur)) / SR
    return vol * np.sin(2 * np.pi * freq * t) * np.exp(-decay * t)

def music(total):
    """柔和的循环琶音做背景音乐。"""
    out = np.zeros(int(SR * total) + SR)
    chords = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7]]
    step = 0.3
    i = 0
    t = 0.0
    while t < total:
        ch = chords[(i // 8) % 4]
        f = ch[i % 3] * (2 if i % 8 >= 6 else 1)
        n = tone(f, 1.2, 0.05, 3.0)
        s = int(t * SR)
        out[s:s + len(n)] += n[:len(out) - s]
        if i % 8 == 0:
            b = tone(ch[0] / 2, 2.4, 0.05, 1.2)
            out[s:s + len(b)] += b[:len(out) - s]
        t += step
        i += 1
    return out[:int(SR * total)]

# ---------------------------------------------------------------- drawing helpers
def rrect(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)

def wrap(text, fnt, maxw, d):
    words, lines, cur = text.split(" "), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if d.textlength(test.replace("*", ""), font=fnt) <= maxw:
            cur = test
        else:
            lines.append(cur); cur = w_
    lines.append(cur)
    return lines

def draw_marked(d, xy, line, fnt, base, hi):
    """**重点** 用高亮色绘制。"""
    x, y = xy
    parts = line.split("**")
    for k, p in enumerate(parts):
        if not p: continue
        d.text((x, y), p, font=fnt, fill=hi if k % 2 else base)
        x += d.textlength(p, font=fnt)

def line_width(d, line, fnt):
    return d.textlength(line.replace("*", ""), font=fnt)

# ---------------------------------------------------------------- scene
def scene_bg(theme):
    img = Image.new("RGB", (W, H), theme["wall"])
    d = ImageDraw.Draw(img)
    # 墙面条纹
    for x in range(0, W, 90):
        d.rectangle([x, 300, x + 45, 1250], fill=theme["wall2"])
    # 护墙板
    d.rectangle([0, 1000, W, 1250], fill=theme["panel"])
    d.line([0, 1000, W, 1000], fill=theme["trim"], width=10)
    # 窗户
    rrect(d, [90, 420, 470, 820], 24, theme["trim"])
    rrect(d, [110, 440, 450, 800], 16, (180, 220, 240))
    d.ellipse([300, 470, 400, 570], fill=(255, 236, 170))
    d.line([280, 440, 280, 800], fill=theme["trim"], width=12)
    d.line([110, 620, 450, 620], fill=theme["trim"], width=12)
    # 菜单板
    rrect(d, [620, 420, 990, 800], 20, (60, 64, 62), outline=theme["trim"], width=14)
    fb = font(FONT_B, 54); fr = font(FONT_R, 34)
    d.text((805, 450), theme["board_title"], font=fb, fill=(255, 255, 255), anchor="ma")
    for k, item in enumerate(theme["board_items"]):
        d.text((660, 540 + k * 62), item, font=fr, fill=(235, 235, 225))
    # 吊灯
    for cx in (280, 805):
        d.line([cx, 300, cx, 350], fill=(70, 60, 50), width=6)
        d.chord([cx - 70, 330, cx + 70, 430], 180, 360, fill=theme["lamp"])
    # 地板
    d.rectangle([0, 1250, W, 1500], fill=theme["floor"])
    for x in range(-200, W + 200, 140):
        d.line([x, 1250, x + 120, 1500], fill=theme["floor2"], width=4)
    return img

def scene_table(theme):
    """桌子单独一层，盖在人物下半身前面。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([560, 1150, 1080, 1185], fill=theme["table"])
    d.rectangle([560, 1185, 1080, 1215], fill=theme["table2"])
    d.rectangle([600, 1215, 625, 1480], fill=theme["table2"])
    d.rectangle([1010, 1215, 1035, 1480], fill=theme["table2"])
    d.ellipse([700, 1120, 860, 1160], fill=(250, 250, 250), outline=(210, 210, 210), width=3)
    rrect(d, [900, 1070, 950, 1155], 10, (200, 230, 245), outline=(160, 190, 210), width=3)
    return layer

# ---------------------------------------------------------------- characters
def character(spec, mouth_open, blink):
    """画一个扁平风人物（半身），返回 RGBA。"""
    cw, ch = 460, 820
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cw // 2
    skin, hair, shirt = spec["skin"], spec["hair"], spec["shirt"]
    # 身体
    rrect(d, [cx - 150, 420, cx + 150, 820], 90, shirt)
    if spec.get("apron"):
        rrect(d, [cx - 100, 520, cx + 100, 820], 30, spec["apron"])
        d.line([cx - 100, 525, cx - 60, 430], fill=spec["apron"], width=14)
        d.line([cx + 100, 525, cx + 60, 430], fill=spec["apron"], width=14)
    # 领口 / 领结
    d.polygon([(cx - 45, 420), (cx + 45, 420), (cx, 480)], fill=skin)
    if spec.get("bowtie"):
        d.polygon([(cx, 470), (cx - 40, 450), (cx - 40, 495)], fill=spec["bowtie"])
        d.polygon([(cx, 470), (cx + 40, 450), (cx + 40, 495)], fill=spec["bowtie"])
        d.ellipse([cx - 12, 460, cx + 12, 482], fill=spec["bowtie"])
    # 脖子
    d.rectangle([cx - 35, 360, cx + 35, 430], fill=skin)
    # 后发
    if spec.get("long_hair"):
        rrect(d, [cx - 150, 120, cx + 150, 470], 120, hair)
    # 头
    d.ellipse([cx - 130, 110, cx + 130, 390], fill=skin)
    # 耳朵
    d.ellipse([cx - 148, 230, cx - 108, 290], fill=skin)
    d.ellipse([cx + 108, 230, cx + 148, 290], fill=skin)
    # 刘海
    d.chord([cx - 140, 90, cx + 140, 300], 180, 360, fill=hair)
    d.polygon([(cx - 140, 200), (cx - 20, 190), (cx - 120, 260)], fill=hair)
    # 眼睛
    for ex in (cx - 55, cx + 55):
        if blink:
            d.line([ex - 18, 262, ex + 18, 262], fill=(40, 30, 30), width=7)
        else:
            d.ellipse([ex - 16, 244, ex + 16, 282], fill=(40, 30, 30))
            d.ellipse([ex - 6, 250, ex + 4, 260], fill=(255, 255, 255))
    # 眉毛
    d.line([cx - 75, 222, cx - 35, 216], fill=hair, width=8)
    d.line([cx + 35, 216, cx + 75, 222], fill=hair, width=8)
    # 腮红
    d.ellipse([cx - 105, 290, cx - 65, 315], fill=spec["blush"])
    d.ellipse([cx + 65, 290, cx + 105, 315], fill=spec["blush"])
    # 嘴
    if mouth_open:
        d.ellipse([cx - 28, 312, cx + 28, 356], fill=(150, 50, 60))
        d.chord([cx - 18, 335, cx + 18, 360], 180, 360, fill=(235, 120, 130))
    else:
        d.arc([cx - 30, 300, cx + 30, 340], 20, 160, fill=(150, 50, 60), width=7)
    return img

# ---------------------------------------------------------------- overlays
def bubble(text, speaker_x, tail_down=True):
    fnt = font(FONT_B, 50)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = wrap(text, fnt, 640, tmp)
    tw = max(line_width(tmp, l, fnt) for l in lines)
    bw, bh = int(tw + 80), 70 * len(lines) + 50
    img = Image.new("RGBA", (bw + 40, bh + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rrect(d, [6, 6, bw + 6, bh + 6], 36, (0, 0, 0, 40))
    rrect(d, [0, 0, bw, bh], 36, (255, 255, 255), outline=(40, 40, 40), width=5)
    tx = min(max(60, speaker_x), bw - 60)
    d.polygon([(tx - 25, bh - 4), (tx + 25, bh - 4), (tx, bh + 45)], fill=(255, 255, 255))
    d.line([(tx - 25, bh - 2), (tx, bh + 45), (tx + 25, bh - 2)], fill=(40, 40, 40), width=5)
    for k, l in enumerate(lines):
        draw_marked(d, (40, 25 + k * 70), l, fnt, (30, 30, 30), (225, 80, 40))
    return img

def subtitle(en, zh):
    img = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fe, fz = font(FONT_B, 58), font(FONT_R, 46)
    lines = wrap(en, fe, 940, d)
    y = 30
    for l in lines:
        lw = line_width(d, l, fe)
        x = (W - lw) / 2
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            d.text((x + dx, y + dy), l.replace("*", ""), font=fe, fill=(20, 20, 20))
        draw_marked(d, (x, y), l, fe, (255, 255, 255), (255, 214, 60))
        y += 76
    y += 10
    d.text((W / 2, y), zh, font=fz, fill=(255, 236, 200), anchor="ma",
           stroke_width=3, stroke_fill=(20, 20, 20))
    return img

def header(meta):
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 300], fill=meta["accent"])
    fk, fr = font(FONT_K, 76), font(FONT_R, 40)
    d.text((W / 2, 70), meta["title"], font=fk, fill=(255, 255, 255), anchor="ma")
    d.text((W / 2, 180), meta["series"], font=fr, fill=(255, 245, 225), anchor="ma")
    return img

# ---------------------------------------------------------------- main
def ease_out(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def main(script_path, out_path):
    def tup(o):
        if isinstance(o, dict): return {k: tup(v) for k, v in o.items()}
        if isinstance(o, list) and o and all(isinstance(x, (int, float)) for x in o): return tuple(o)
        if isinstance(o, list): return [tup(x) for x in o]
        return o
    S = tup(json.load(open(script_path, encoding="utf-8")))
    meta, theme, chars = S["meta"], S["theme"], S["characters"]

    # ---- 时间线 + 音频
    timeline, clips = [], []
    t = 0.0
    hook_len = 3.2
    timeline.append(dict(kind="hook", start=0, end=hook_len)); t = hook_len
    ding = tone(880, 0.6, 0.25, 8)
    hi = tone(1320, 0.4, 0.2, 8); o = int(0.08 * SR)
    ding[o:o + len(hi)] += hi
    clips.append((0.05, ding))
    for k, ln in enumerate(S["dialogue"]):
        a = tts(ln["en"].replace("*", ""), chars[ln["who"]]["voice"], f"{TMP}/d{k}.wav")
        dur = len(a) / SR
        timeline.append(dict(kind="line", start=t, end=t + dur + 0.75, speak_end=t + dur, **ln))
        clips.append((t, a)); t += dur + 0.75
    for k, rv in enumerate(S["review"]):
        a = tts(rv["en"].replace("*", ""), "slt", f"{TMP}/r{k}.wav", tempo=0.8)
        dur = len(a) / SR
        # 听 → 跟读停顿 → 再听一遍
        seg = dict(kind="review", start=t, idx=k, n=len(S["review"]), en=rv["en"], zh=rv["zh"], note=rv.get("note", ""))
        seg["play1"] = (t + 0.6, t + 0.6 + dur)
        seg["repeat"] = (t + 0.6 + dur + 0.3, t + 0.6 + dur + 0.3 + dur * 1.3 + 0.8)
        seg["play2"] = (seg["repeat"][1] + 0.2, seg["repeat"][1] + 0.2 + dur)
        seg["end"] = seg["play2"][1] + 0.7
        clips += [(seg["play1"][0], a), (seg["play2"][0], a)]
        timeline.append(seg); t = seg["end"]
    timeline.append(dict(kind="outro", start=t, end=t + 3.0)); t += 3.0
    total = t

    audio = music(total)
    for st, a in clips:
        s = int(st * SR); e = min(len(audio), s + len(a))
        audio[s:e] += a[:e - s]
    audio = np.clip(audio, -1, 1)
    with wave.open(f"{TMP}/mix.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())

    # ---- 预渲染素材
    bg = scene_bg(theme)
    table = scene_table(theme)
    hdr = header(meta)
    sprites = {}
    for name, spec in chars.items():
        sprites[name] = {(m, b): character(spec, m, b) for m in (0, 1) for b in (0, 1)}
    pos = {name: tuple(spec["pos"]) for name, spec in chars.items()}
    for seg in timeline:
        if seg["kind"] == "line":
            px = pos[seg["who"]][0] + 230
            b = bubble(seg["en"], 0)
            bx = int(min(max(30, px - b.width / 2), W - b.width - 30))
            seg["bubble"] = bubble(seg["en"], px - bx)
            seg["bubble_xy"] = (bx, 330 + max(0, 160 - b.height // 2))
            seg["sub"] = subtitle(seg["en"], seg["zh"])
    base_scene = bg.copy(); base_scene.paste(hdr, (0, 0), hdr)
    blur_scene = bg.filter(ImageFilter.GaussianBlur(18))
    dim = Image.new("RGBA", (W, H), (20, 24, 30, 150))
    blur_scene = Image.alpha_composite(blur_scene.convert("RGBA"), dim).convert("RGB")

    # ---- 逐帧渲染并送入 ffmpeg
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", f"{TMP}/mix.wav",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path],
                          stdin=subprocess.PIPE)
    nframes = int(total * FPS)
    fk_big = font(FONT_K, 110); fk_mid = font(FONT_K, 72); fr_mid = font(FONT_R, 48)
    for fi in range(nframes):
        tt = fi / FPS
        seg = next((s for s in timeline if s["start"] <= tt < s["end"]), timeline[-1])
        kind = seg["kind"]
        if kind in ("hook", "review", "outro"):
            frame = blur_scene.copy(); d = ImageDraw.Draw(frame)
        else:
            frame = base_scene.copy(); d = ImageDraw.Draw(frame)

        if kind == "hook":
            p = ease_out((tt - 0.1) / 0.45)
            sc = 0.6 + 0.4 * p
            for k, (txt, f, col, y) in enumerate([(S["hook"][0], fk_mid, (255, 255, 255), 720),
                                                 (S["hook"][1], fk_big, (255, 214, 60), 860)]):
                pk = ease_out((tt - 0.1 - k * 0.35) / 0.4)
                if pk <= 0: continue
                fs = font(FONT_K, int(f.size * (0.6 + 0.4 * pk)))
                d.text((W / 2, y + 40 * (1 - pk)), txt, font=fs, fill=col, anchor="mm",
                       stroke_width=6, stroke_fill=(20, 20, 20))
            pk = ease_out((tt - 1.2) / 0.4)
            if pk > 0:
                rrect(d, [W / 2 - 300, 1060, W / 2 + 300, 1160], 50, meta["accent"])
                d.text((W / 2, 1110), S["hook"][2], font=fr_mid, fill=(255, 255, 255), anchor="mm")

        elif kind == "line":
            speaking = tt < seg["speak_end"]
            blink_now = (int(tt * 10) % 37) in (0, 1)
            for name in chars:
                is_sp = speaking and name == seg["who"]
                mouth = 1 if is_sp and int(tt * 8) % 2 == 0 else 0
                bob = int(6 * math.sin(tt * 9)) if is_sp else 0
                blink = blink_now if name == list(chars)[0] else (int(tt * 10 + 13) % 41) in (0, 1)
                spr = sprites[name][(mouth, int(blink))]
                x, y = pos[name]
                frame.paste(spr, (x, y + bob), spr)
            frame.paste(table, (0, 0), table)
            p = ease_out((tt - seg["start"]) / 0.25)
            b = seg["bubble"]
            if p < 1:
                bs = b.resize((max(1, int(b.width * (0.7 + 0.3 * p))), max(1, int(b.height * (0.7 + 0.3 * p)))))
                bx = seg["bubble_xy"][0] + (b.width - bs.width) // 2
                frame.paste(bs, (bx, seg["bubble_xy"][1] + (b.height - bs.height)), bs)
            else:
                frame.paste(b, seg["bubble_xy"], b)
            d.rectangle([0, 1500, W, H], fill=(28, 30, 36))
            frame.paste(seg["sub"], (0, 1540), seg["sub"])

        elif kind == "review":
            rrect(d, [W / 2 - 260, 330, W / 2 + 260, 440], 55, meta["accent"])
            d.text((W / 2, 385), f"今日重点句 {seg['idx'] + 1}/{seg['n']}", font=fr_mid, fill=(255, 255, 255), anchor="mm")
            rrect(d, [60, 560, W - 60, 1180], 40, (255, 255, 255))
            fe = font(FONT_B, 66)
            lines = wrap(seg["en"], fe, W - 220, d)
            y = 640
            for l in lines:
                lw = line_width(d, l, fe)
                draw_marked(d, ((W - lw) / 2, y), l, fe, (30, 30, 30), (225, 80, 40)); y += 90
            d.text((W / 2, y + 30), seg["zh"], font=fr_mid, fill=(90, 90, 90), anchor="ma")
            if seg["note"]:
                d.text((W / 2, y + 120), seg["note"], font=font(FONT_R, 38), fill=(150, 120, 80), anchor="ma")
            r0, r1 = seg["repeat"]
            if seg["play1"][0] <= tt < seg["play1"][1] or seg["play2"][0] <= tt < seg["play2"][1]:
                label, col, prog = "🔊 听", (90, 160, 230), None
                label = "听一遍" if tt < r0 else "再听一遍"
            elif r0 <= tt < r1:
                label, col, prog = "轮到你跟读！", (240, 120, 60), (tt - r0) / (r1 - r0)
            else:
                label, col, prog = "", None, None
            if label:
                rrect(d, [W / 2 - 280, 1290, W / 2 + 280, 1410], 60, col)
                d.text((W / 2, 1350), label, font=fk_mid, fill=(255, 255, 255), anchor="mm")
            if prog is not None:
                rrect(d, [160, 1470, W - 160, 1500], 15, (255, 255, 255, 80))
                rrect(d, [160, 1470, 160 + (W - 320) * prog, 1500], 15, (255, 214, 60))

        elif kind == "outro":
            p = ease_out((tt - seg["start"]) / 0.5)
            d.text((W / 2, 760 + 40 * (1 - p)), S["outro"][0], font=fk_mid, fill=(255, 255, 255), anchor="mm",
                   stroke_width=5, stroke_fill=(20, 20, 20))
            d.text((W / 2, 900 + 40 * (1 - p)), S["outro"][1], font=fk_big, fill=(255, 214, 60), anchor="mm",
                   stroke_width=6, stroke_fill=(20, 20, 20))
            pk = ease_out((tt - seg["start"] - 0.6) / 0.4)
            if pk > 0:
                rrect(d, [W / 2 - 330, 1080, W / 2 + 330, 1190], 55, (240, 70, 90))
                d.text((W / 2, 1135), S["outro"][2], font=fr_mid, fill=(255, 255, 255), anchor="mm")

        ff.stdin.write(frame.tobytes())
        if fi % 150 == 0:
            print(f"frame {fi}/{nframes}", flush=True)
    ff.stdin.close(); ff.wait()
    print("done", out_path, f"{total:.1f}s")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
