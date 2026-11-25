# -*- coding: utf-8 -*-
"""
每日任务（供计划任务/自动化调用）：

  1. 采集舆情（热度榜 + 百度热搜）→ web_sentiment / web_sentiment_meta
  2. 生成日/周/月总结 → web_daily_summary（每天只写一次，重复跑覆盖）
  3. 保存当日快照 → web_daily_snapshot

用法：
  uv run python scripts/daily_job.py              # 正常跑（舆情 10 分钟内不重复抓）
  uv run python scripts/daily_job.py --force      # 强制重抓舆情
  Windows 计划任务：每天 20:10 执行
    schtasks /create /tn "ashare-daily" /tr "cmd /c cd /d C:\\path\\to\\panduan && uv run python scripts\\daily_job.py" /sc daily /st 20:10
"""
import os
import sys
import json
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import analytics as A  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="强制重抓舆情（忽略节流）")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()

    res = A.daily_job(force_sentiment=a.force)
    if not a.quiet:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    ok = all("error" not in (v or {}) for v in res["steps"].values())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
