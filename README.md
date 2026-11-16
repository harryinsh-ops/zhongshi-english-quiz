# 中式英语急救室 · 无人声英语选择题短视频

抖音竖屏系列（1080×1920，约 30 秒，无人声）。每期 3 道"中式英语 vs 地道英语"选择题：第一帧直接出题 → 2 秒倒计时 → 揭晓 → 解释卡 → 下期预告。

## 目录
- `SKILL.md`：给 Claude 的完整制作说明（风格、出题规则、流程）。新对话里把本仓库地址发给 Claude 即可。
- `scripts/quiz_video.py`：本系列生成器（依赖同目录 `make_video.py` 的公共函数）。
- `scripts/make_video.py`：公共函数；单独运行是情景对话短剧模板（flite 机器配音，目前不用）。
- `episodes/epNN.json`：每期脚本。
- `used_questions.md`：已用题目，出新题前查重。

## 手动生成
需要 Python 3 + Pillow + numpy、ffmpeg（含 libx264）、Noto Sans CJK 字体（路径见 make_video.py 顶部）。
```bash
cd scripts
python3 quiz_video.py ../episodes/ep01.json ep01.mp4 ep01_cover.png
```
