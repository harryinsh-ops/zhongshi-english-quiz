#!/usr/bin/env python3
"""选择题纠错短视频（无人声）：PIL 画面 + 合成音效 + ffmpeg。
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

def header(d, meta, qtxt):
    d.rectangle([0, 0, W, 260], fill=NAVY)
    d.text((W / 2, 60), meta["title"], font=font(FONT_K, 74), fill=(255, 255, 255), anchor="ma")
    d.text((W / 2, 170), meta["series"], font=font(FONT_R, 40), fill=(200, 215, 255), anchor="ma")
    if qtxt:
        rrect(d, [W / 2 - 150, 225, W / 2 + 150, 305], 40, YEL)
        d.text((W / 2, 265), qtxt, font=font(FONT_K, 44), fill=INK, anchor="mm")

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

def zh_wrap(text, fnt, maxw, d):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=fnt) > maxw:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines

# ------------------------------------------------------------ main
def main(sp, out, cover_out):
    S = json.load(open(sp, encoding="utf-8"))
    meta, qs = S["meta"], S["questions"]
    T_IN, T_CD, T_REV, T_EXP = 2.4, 3.0, 1.6, 5.2
    hook_len, outro_len = 3.2, 3.6
    segs, t = [dict(kind="hook", s=0, e=hook_len)], hook_len
    for i, q in enumerate(qs):
        segs.append(dict(kind="q", s=t, e=t + T_IN + T_CD + T_REV + T_EXP, i=i, q=q)); t = segs[-1]["e"]
    segs.append(dict(kind="outro", s=t, e=t + outro_len)); total = t + outro_len

    # 音频
    audio = music(total); sfx = [(0.05, ding())]
    for sg in segs:
        if sg["kind"] != "q": continue
        s0 = sg["s"]
        for k in range(len(sg["q"]["options"])): sfx.append((s0 + 0.5 + k * 0.25, pop()))
        for k in range(3): sfx.append((s0 + T_IN + k, tick()))
        r = s0 + T_IN + T_CD
        sfx.append((r, buzz())); sfx.append((r + 0.45, ding()))
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

    def render(tt):
        sg = next((x for x in segs if x["s"] <= tt < x["e"]), segs[-1])
        img = bg.copy(); d = ImageDraw.Draw(img)
        lt = tt - sg["s"]
        if sg["kind"] == "hook":
            header(d, meta, None)
            for k, (txt, f, col, y) in enumerate([(S["hook"][0], 78, INK, 720), (S["hook"][1], 120, RED, 880)]):
                p = ease_out((lt - 0.1 - 0.35 * k) / 0.4)
                if p > 0:
                    d.text((W / 2, y + 40 * (1 - p)), txt, font=font(FONT_K, int(f * (0.6 + 0.4 * p))),
                           fill=col, anchor="mm")
            p = ease_out((lt - 1.1) / 0.4)
            if p > 0:
                rrect(d, [W / 2 - 360, 1060, W / 2 + 360, 1170], 55, NAVY)
                d.text((W / 2, 1115), S["hook"][2], font=font(FONT_B, 50), fill=(255, 255, 255), anchor="mm")
        elif sg["kind"] == "q":
            q, i = sg["q"], sg["i"]
            header(d, meta, f"第 {i + 1} / {len(qs)} 题")
            fz = font(FONT_B, 56)
            d.text((W / 2, 400), "想说：", font=font(FONT_R, 44), fill=(120, 110, 95), anchor="mm")
            y = 470
            for l in zh_wrap(q["prompt"], fz, W - 160, d):
                d.text((W / 2, y), l, font=fz, fill=INK, anchor="ma"); y += 76
            d.text((W / 2, y + 20), "哪句更地道？", font=font(FONT_R, 44), fill=(120, 110, 95), anchor="ma")
            revealed = lt >= T_IN + T_CD
            oy = 760
            for k, opt in enumerate(q["options"]):
                p = ease_out((lt - 0.5 - k * 0.25) / 0.35)
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
                option_card(d, (70 + xo, oy, W - 70 + xo, oy + 170), "ABC"[k], opt, state)
                oy += 210
            if T_IN <= lt < T_IN + T_CD:
                c = lt - T_IN
                ring(d, W / 2, oy + 140, 95, c / T_CD, 3 - int(c))
            if lt >= T_IN + T_CD + T_REV:
                p = ease_out((lt - T_IN - T_CD - T_REV) / 0.4)
                top = oy + 40 + int(60 * (1 - p))
                rrect(d, [60, top, W - 60, top + 520], 40, NAVY)
                d.text((110, top + 45), "为什么？", font=font(FONT_K, 50), fill=YEL)
                fr = font(FONT_R, 44); yy = top + 125
                for l in zh_wrap(q["why"], fr, W - 220, d):
                    d.text((110, yy), l, font=fr, fill=(255, 255, 255)); yy += 64
                if q.get("extra"):
                    yy += 20
                    d.text((110, yy), "还可以说：", font=font(FONT_B, 42), fill=YEL); yy += 66
                    d.text((110, yy), q["extra"], font=font(FONT_B, 48), fill=(255, 255, 255))
        else:
            header(d, meta, None)
            p = ease_out(lt / 0.5)
            d.text((W / 2, 760 + 40 * (1 - p)), S["outro"][0], font=font(FONT_K, 84), fill=INK, anchor="mm")
            d.text((W / 2, 900 + 40 * (1 - p)), S["outro"][1], font=font(FONT_K, 64), fill=RED, anchor="mm")
            p2 = ease_out((lt - 0.6) / 0.4)
            if p2 > 0:
                rrect(d, [W / 2 - 330, 1060, W / 2 + 330, 1170], 55, RED)
                d.text((W / 2, 1115), S["outro"][2], font=font(FONT_B, 50), fill=(255, 255, 255), anchor="mm")
        return img

    n = int(total * FPS)
    for fi in range(n):
        ff.stdin.write(render(fi / FPS).tobytes())
    ff.stdin.close(); ff.wait()

    # 封面
    cv = bg.copy(); d = ImageDraw.Draw(cv)
    header(d, meta, None)
    for k, l in enumerate(S["cover"]):
        col = RED if k == 1 else INK
        d.text((W / 2, 700 + k * 190), l, font=font(FONT_K, 130 if k == 1 else 96), fill=col, anchor="mm")
    q0 = qs[0]
    option_card(d, (70, 1250, W - 70, 1420), "A", q0["options"][1 - q0["answer"]] if len(q0["options"]) == 2 else q0["options"][0], "wrong")
    option_card(d, (70, 1470, W - 70, 1640), "B", q0["options"][q0["answer"]], "right")
    cv.save(cover_out)
    print(f"done {out} {total:.1f}s")

if __name__ == "__main__":
    main(*sys.argv[1:4])
