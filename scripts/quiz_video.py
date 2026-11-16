#!/usr/bin/env python3
"""选择题纠错短视频 v2（无人声）：PIL 画面 + 合成音效 + ffmpeg。
用法: python3 quiz_video.py script.json out.mp4 cover.png
"""
import json, math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw
from make_video import (W, H, FPS, SR, FONT_B, FONT_R, FONT_K, font, tone, rrect,
                        wrap, line_width, draw_marked, ease_out)

BG = (255, 246, 228); NAVY = (31, 52, 120); YEL = (255, 200, 40)
RED = (230, 70, 70); GRN = (46, 170, 100); INK = (35, 35, 45)

# ------------------------------------------------------------ audio
def buzz(dur=0.35, vol=0.18):
    t = np.arange(int(SR * dur)) / SR
    return vol * np.sign(np.sin(2 * np.pi * 140 * t)) * np.exp(-5 * t)

def ding():
    a = tone(1046.5, 0.8, 0.22, 5); b = tone(1568, 0.7, 0.18, 5)
    o = int(0.09 * SR); a[o:o + len(b)] += b[:len(a) - o]
    return a

def pop():
    t = np.arange(int(SR * 0.08)) / SR
    return 0.15 * np.sin(2 * np.pi * (600 + 2500 * t) * t) * np.exp(-30 * t)

def tick(): return tone(1800, 0.06, 0.12, 40)

def music(total):
    out = np.zeros(int(SR * total) + SR)
    prog = [[261.6, 329.6, 392.0], [293.7, 349.2, 440.0], [220.0, 261.6, 329.6], [196.0, 246.9, 293.7]]
    step, i, t = 0.25, 0, 0.0
    while t < total:
        ch = prog[(i // 8) % 4]
        n = tone(ch[[0, 1, 2, 1][i % 4]] * 2, 0.5, 0.035, 6)
        s = int(t * SR); out[s:s + len(n)] += n[:len(out) - s]
        if i % 4 == 0:
            b = tone(ch[0] / 2, 1.0, 0.05, 2.5); out[s:s + len(b)] += b[:len(out) - s]
        t += step; i += 1
    return out[:int(SR * total)]

# ------------------------------------------------------------ drawing
def background():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(0, H, 60):
        for x in range((y // 60) % 2 * 30, W, 60):
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(245, 230, 200))
    return img

def check(d, cx, cy, s, col):
    d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=col)
    d.line([(cx - s * .45, cy), (cx - s * .1, cy + s * .38), (cx + s * .5, cy - s * .35)],
           fill=(255, 255, 255), width=int(s * .22), joint="curve")

def cross(d, cx, cy, s, col):
    d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=col)
    k = s * .4
    d.line([cx - k, cy - k, cx + k, cy + k], fill=(255, 255, 255), width=int(s * .22))
    d.line([cx - k, cy + k, cx + k, cy - k], fill=(255, 255, 255), width=int(s * .22))

def option_card(d, box, letter, text, state, alpha_p=1.0):
    x0, y0, x1, y1 = box
    fill, edge, lc = (255, 255, 255), NAVY, NAVY
    if state == "right": fill, edge, lc = (225, 248, 233), GRN, GRN
    if state == "wrong": fill, edge, lc = (253, 228, 228), RED, RED
    if state == "dim": fill, edge, lc = (240, 236, 228), (190, 185, 175), (190, 185, 175)
    rrect(d, [x0 + 8, y0 + 10, x1 + 8, y1 + 10], 40, (225, 212, 188))
    rrect(d, [x0, y0, x1, y1], 40, fill, outline=edge, width=7)
    cy = (y0 + y1) / 2
    d.ellipse([x0 + 35, cy - 50, x0 + 135, cy + 50], fill=lc)
    d.text((x0 + 85, cy), letter, font=font(FONT_K, 60), fill=(255, 255, 255), anchor="mm")
    size = 62
    fe = font(FONT_B, size)
    while d.textlength(text, font=fe) > (x1 - x0) - 310 and size > 36:
        size -= 2; fe = font(FONT_B, size)
    tc = INK if state != "dim" else (160, 155, 145)
    d.text((x0 + 170, cy), text, font=fe, fill=tc, anchor="lm")
    if state == "wrong":
        tw = d.textlength(text, font=fe)
        d.line([x0 + 165, cy + 4, x0 + 175 + tw, cy + 4], fill=RED, width=6)
    if state == "right": check(d, x1 - 80, cy, 46, GRN)
    if state == "wrong": cross(d, x1 - 80, cy, 46, RED)

def ring(d, cx, cy, r, frac, num):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255), outline=(230, 220, 200), width=14)
    if frac > 0:
        d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=YEL, width=14)
    d.text((cx, cy), str(num), font=font(FONT_K, 90), fill=NAVY, anchor="mm")

def multiline_center(d, text, fnt, y, maxw, col, hi=(230, 90, 40), gap=1.35):
    for l in wrap(text, fnt, maxw, d) if " " in text else [text]:
        lw = line_width(d, l, fnt)
        draw_marked(d, ((W - lw) / 2, y), l, fnt, col, hi)
        y += int(fnt.size * gap)
    return y

def _tokens(text):
    """英文单词/数字连在一起作为一个词，中文逐字。"""
    import re
    return re.findall(r"[A-Za-z0-9'’.,?!:;%$\-]+|\s|.", text)

NO_START = set("，。、；：？！）》」』”’,.;:?!)%")

def zh_wrap(text, fnt, maxw, d):
    lines, cur = [], ""
    for tk in _tokens(text):
        if cur == "" and tk == " ": continue
        if d.textlength(cur + tk, font=fnt) > maxw and cur.strip():
            if tk in NO_START:            # 标点不放行首：挂在上一行末尾
                cur += tk; continue
            lines.append(cur.rstrip()); cur = "" if tk == " " else tk
        else:
            cur += tk
    if cur.strip(): lines.append(cur.rstrip())
    return lines

def balanced_lines(text, path, size, maxw, d, minsize=50):
    """先缩小字号争取一行；放不下就分两行并尽量等长。"""
    f = font(path, size)
    while d.textlength(text, font=f) > maxw and size > minsize:
        size -= 2; f = font(path, size)
    if d.textlength(text, font=f) <= maxw:
        return f, [text]
    total = d.textlength(text, font=f)
    for target in range(int(total / 2), int(maxw), 20):
        ls = zh_wrap(text, f, target, d)
        if len(ls) <= 2: return f, ls
    return f, zh_wrap(text, f, maxw, d)

def header(d, meta, qtxt):
    """v2：压缩后的标题栏（150px），题号放在栏内右侧。"""
    d.rectangle([0, 0, W, 150], fill=NAVY)
    d.text((60, 75), meta["title"], font=font(FONT_K, 56), fill=(255, 255, 255), anchor="lm")
    tw = d.textlength(meta["title"], font=font(FONT_K, 56))
    d.text((60 + tw + 24, 82), meta["series"], font=font(FONT_R, 34), fill=(200, 215, 255), anchor="lm")
    if qtxt:
        rrect(d, [W - 250, 42, W - 50, 108], 33, YEL)
        d.text((W - 150, 75), qtxt, font=font(FONT_K, 38), fill=INK, anchor="mm")

def fit_font(d, text, path, size, maxw, minsize=30):
    f = font(path, size)
    while d.textlength(text, font=f) > maxw and size > minsize:
        size -= 2; f = font(path, size)
    return f


# ------------------------------------------------------------ main
def main(sp, out, cover_out):
    S = json.load(open(sp, encoding="utf-8"))
    meta, qs = S["meta"], S["questions"]
    # v2 节奏：第一帧就是第 1 题，没有单独的钩子
    T_IN, T_CD, T_REV, T_EXP = 1.2, 2.0, 1.2, 4.4
    outro_len = 3.4
    QLEN = T_IN + T_CD + T_REV + T_EXP
    segs, t = [], 0.0
    for i, q in enumerate(qs):
        segs.append(dict(kind="q", s=t, e=t + QLEN, i=i, q=q)); t += QLEN
    segs.append(dict(kind="outro", s=t, e=t + outro_len)); total = t + outro_len

    # 音频
    audio = music(total); sfx = []
    for sg in segs:
        if sg["kind"] != "q": continue
        s0 = sg["s"]
        if sg["i"] > 0:
            for k in range(len(sg["q"]["options"])): sfx.append((s0 + 0.05 + k * 0.12, pop()))
        for k in range(2): sfx.append((s0 + T_IN + k, tick()))
        r = s0 + T_IN + T_CD
        sfx.append((r, buzz())); sfx.append((r + 0.4, ding()))
    sfx.append((total - outro_len, ding()))
    for st, a in sfx:
        s = int(st * SR); e = min(len(audio), s + len(a)); audio[s:e] += a[:e - s]
    audio = np.clip(audio, -1, 1)
    with wave.open("tmp_audio/quiz.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())

    bg = background()
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", "tmp_audio/quiz.wav", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)

    follow_q = min(1, len(qs) - 1)   # 第 2 题解释阶段出关注提示

    def render(tt):
        sg = next((x for x in segs if x["s"] <= tt < x["e"]), segs[-1])
        img = bg.copy(); d = ImageDraw.Draw(img)
        lt = tt - sg["s"]
        if sg["kind"] == "q":
            q, i = sg["q"], sg["i"]
            header(d, meta, f"第 {i + 1}/{len(qs)} 题")
            d.text((W / 2, 290), "想说：", font=font(FONT_R, 44), fill=(120, 110, 95), anchor="mm")
            fz, plines = balanced_lines(q["prompt"], FONT_B, 72, W - 140, d)
            y = 345
            for l in plines:
                d.text((W / 2, y), l, font=fz, fill=INK, anchor="ma"); y += int(fz.size * 1.32)
            ask = q.get("ask", "你会选哪个？")
            rrect(d, [W / 2 - 230, y + 34, W / 2 + 230, y + 114], 40, RED)
            d.text((W / 2, y + 74), ask, font=font(FONT_K, 46), fill=(255, 255, 255), anchor="mm")
            revealed = lt >= T_IN + T_CD
            oy = y + 165
            for k, opt in enumerate(q["options"]):
                # 第 1 题第一帧就完整显示；之后的题快速滑入
                p = 1.0 if i == 0 else ease_out((lt - 0.05 - k * 0.12) / 0.25)
                if p <= 0: continue
                right = (k == q["answer"])
                state = "normal"
                if revealed:
                    state = "right" if right else "wrong"
                    if lt >= T_IN + T_CD + T_REV and not right: state = "dim"
                dx = 0
                if state == "wrong" and lt < T_IN + T_CD + 0.4:
                    dx = int(14 * math.sin((lt - T_IN - T_CD) * 60))
                xo = int(-W * (1 - p)) + dx
                option_card(d, (60 + xo, oy, W - 60 + xo, oy + 185), "ABC"[k], opt, state)
                oy += 220
            if lt < T_IN + T_CD:
                c = max(0.0, lt - T_IN)
                ring(d, W / 2, oy + 120, 85, c / T_CD if lt >= T_IN else 0, 2 - int(c) if lt >= T_IN else 2)
            if lt >= T_IN + T_CD + T_REV:
                p = ease_out((lt - T_IN - T_CD - T_REV) / 0.3)
                top = oy + 25 + int(50 * (1 - p))
                fr = font(FONT_R, 44)
                lines = zh_wrap(q["why"], fr, W - 220, d)
                h = 130 + 64 * len(lines) + (130 if q.get("extra") else 20)
                rrect(d, [60, top, W - 60, top + h], 40, NAVY)
                d.text((110, top + 40), q.get("why_label", "为什么？"), font=font(FONT_K, 50), fill=YEL)
                yy = top + 120
                for l in lines:
                    d.text((110, yy), l, font=fr, fill=(255, 255, 255)); yy += 64
                if q.get("extra"):
                    yy += 16
                    d.text((110, yy), "还可以说：", font=font(FONT_B, 40), fill=YEL); yy += 60
                    d.text((110, yy), q["extra"], font=fit_font(d, q["extra"], FONT_B, 48, W - 240), fill=(255, 255, 255))
            # 中途关注提示
            if i == follow_q and lt >= T_IN + T_CD + T_REV + 0.5:
                p = ease_out((lt - T_IN - T_CD - T_REV - 0.5) / 0.3)
                yb = H - 150 + int(120 * (1 - p))
                rrect(d, [W / 2 - 300, yb, W / 2 + 300, yb + 86], 43, RED)
                d.text((W / 2, yb + 43), meta.get("follow", "关注我 · 每天 3 道急救题"),
                       font=font(FONT_B, 40), fill=(255, 255, 255), anchor="mm")
        else:
            header(d, meta, None)
            p = ease_out(lt / 0.4)
            o = S["outro"]
            d.text((W / 2, 520 + 40 * (1 - p)), o[0], font=font(FONT_K, 88), fill=INK, anchor="mm")
            d.text((W / 2, 650 + 40 * (1 - p)), o[1], font=font(FONT_K, 68), fill=RED, anchor="mm")
            nxt = S.get("next")
            if nxt:
                p2 = ease_out((lt - 0.4) / 0.4)
                if p2 > 0:
                    top = 800 + int(60 * (1 - p2))
                    rrect(d, [70, top, W - 70, top + 300], 40, NAVY)
                    d.text((W / 2, top + 70), nxt[0], font=font(FONT_B, 46), fill=YEL, anchor="mm")
                    d.text((W / 2, top + 175), nxt[1], font=fit_font(d, nxt[1], FONT_K, 62, W - 220),
                           fill=(255, 255, 255), anchor="mm")
            p3 = ease_out((lt - 0.9) / 0.4)
            if p3 > 0:
                rrect(d, [W / 2 - 320, 1190, W / 2 + 320, 1300], 55, RED)
                d.text((W / 2, 1245), o[2], font=fit_font(d, o[2], FONT_B, 50, 600), fill=(255, 255, 255), anchor="mm")
        return img

    n = int(total * FPS)
    for fi in range(n):
        ff.stdin.write(render(fi / FPS).tobytes())
    ff.stdin.close(); ff.wait()

    # 封面（第一帧之外单独上传的封面）
    cv = bg.copy(); d = ImageDraw.Draw(cv)
    header(d, meta, None)
    for k, l in enumerate(S["cover"]):
        col = RED if k == 1 else INK
        f = fit_font(d, l, FONT_K, 130 if k == 1 else 96, W - 120)
        d.text((W / 2, 560 + k * 190), l, font=f, fill=col, anchor="mm")
    q0 = qs[0]
    for k, opt in enumerate(q0["options"][:2]):
        st = "right" if k == q0["answer"] else "wrong"
        option_card(d, (60, 1150 + k * 220, W - 60, 1335 + k * 220), "ABC"[k], opt, st)
    cv.save(cover_out)
    print(f"done {out} {total:.1f}s")

if __name__ == "__main__":
    main(*sys.argv[1:4])
