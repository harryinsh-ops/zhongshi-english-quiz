---
name: zhongshi-english-quiz-video
description: Make new episodes of the user's Douyin series 中式英语急救室 (no-voice English quiz videos) from this repo; render with ffmpeg and save to ~/project.
---

# 中式英语急救室 · 无人声选择题短视频

用户的抖音英语账号系列。每期：竖屏 1080×1920、30fps、约 40–45 秒、无人声（只有合成背景音乐和音效）。受众是国内学英语的人，场景用通用英语国家，不强调加拿大。

本仓库就是这个系列的全部资料。用户会在新对话里发来仓库地址；只按本文件和仓库里的代码做，不和其他系列混用。

## 仓库内容
- `scripts/quiz_video.py` 生成器，`scripts/make_video.py` 公共函数（两者必须在同一目录）
- `episodes/epNN.json` 历期脚本，可当格式参考
- `used_questions.md` 已用题目，出题前必须先读，避免重复

## 流程
1. 取得仓库文件：先试 `git clone <仓库地址>`；云端 shell 没有网络时，用 WebFetch 读 `raw.githubusercontent.com` 上的这几个文件，原样写到工作目录；还不行就请用户把仓库 clone 到 `~/project` 下，用设备文件工具取。
2. 在 `scripts/` 目录里工作（会自动建 `tmp_audio/`）。渲染在云端做：那里有 ffmpeg（含 libx264）和 Noto Sans CJK 字体（/usr/share/fonts/opentype/noto/）。
3. 读 `used_questions.md`，按下面的规则写本期 `episodes/epNN.json`（NN 接着已有编号）。
4. 运行 `python3 quiz_video.py ../episodes/epNN.json out.mp4 cover.png`（约 45 秒）。
5. 检查：抽开头、题目、揭晓、解释卡、结尾几帧拼成小图看，重点看长选项、解释文字有没有溢出或压到图标。有问题先改再交付。
6. 交付：成品放到用户电脑 `~/project/NN_中式英语急救室_第N期/`（视频 `中式英语急救室_第N期.mp4`、`封面.png`、`脚本.json`），没有权限先申请 `~/project`；同时 SendUserFile 发给用户。
7. 仓库更新：把新的 `epNN.json` 和追加了本期题目的 `used_questions.md` 交给用户（发文件），提醒用户提交到 GitHub。不要自己 push。

## 脚本 JSON 格式
```json
{
  "meta": {"title": "中式英语急救室", "series": "你能答对几题？· 第 N 期"},
  "hook": ["这 3 句英语", "90% 的人说错！", "看完评论区报分"],
  "cover": ["这 3 句英语", "90%的人说错", "你中招了吗？"],
  "questions": [
    {"prompt": "“我好无聊啊”",
     "options": ["I'm so boring.", "I'm so bored."], "answer": 1,
     "why": "中文解释，为什么错、为什么对",
     "extra": "一句拓展说法"}
  ],
  "outro": ["你答对了几题？", "评论区告诉我！", "关注我 · 每天一期"]
}
```
`answer` 是正确选项的下标（从 0 开始）。封面自动用第 1 题做错/对对比。

## 出题规则
- 每期 3 题，每题 2 个选项（一个典型中式错误，一个地道说法）。
- 正确答案位置 A/B 要混着放，不能每题都是同一个位置。
- 只选对错明确的点：语法错误、直译错误、搭配错误、意思完全不同的词。不选"两种都能说、只是更自然"的有争议题。
- 英文必须准确，拿不准就换题。
- 长度：prompt ≤ 约 15 个汉字；选项 ≤ 约 32 个字符（过长会自动缩小字号，但越短越好看）；`why` ≤ 约 70 个汉字；`extra` 一句短英文。
- 3 题尽量覆盖不同类型（如形容词、动词、生活表达）。
- hook 和 cover 可以换说法，但保持"数字 + 说错 + 互动"的句式。

## 固定风格（改风格就改 quiz_video.py 顶部常量）
- 配色：米色点阵背景 BG、深蓝 NAVY 标题栏和解释卡、黄色 YEL 强调、红色 RED 错误、绿色 GRN 正确。
- 节奏：`T_IN` 出题 2.4 秒、`T_CD` 倒计时 3 秒、`T_REV` 揭晓 1.6 秒、`T_EXP` 解释 5.2 秒；开头 3.2 秒，结尾 3.6 秒。
- 音效：选项弹出 pop、倒计时滴答、揭晓时错误 buzz 加正确 ding，背景是合成琶音循环。
- 字体：Noto Sans CJK（Black 标题、Bold 英文、Medium 中文正文）。字体里没有 ✓ ✦ 🔊 这类符号，图标用代码画。

## 调整风格
用户要求改颜色、节奏、版式时：改 `scripts/quiz_video.py`，渲染一条确认效果，再把改过的代码和同步更新的本文件"固定风格"一节交给用户提交到仓库。
