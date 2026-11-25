#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A 股风格轮动研究 —— 数据源验证与落库脚本

功能
----
1. 读取 config/data_sources.yaml，逐个真实调用 AkShare 接口（不使用文档推测）。
2. 每个数据集：记录状态 / 实际返回字段 / 起止日期 / 行数 / 重复键 / 空值率 / 失败原因 / 耗时。
3. 全部原始返回（未改名的原始 DataFrame）gzip 归档到 SQLite 表 raw_archive，一次下载的东西不丢弃。
4. 清洗后（英文字段名 + 主键）写入各业务表，可重复运行（按主键覆盖）。
5. 自动生成 docs/data_catalog.md（数据本身的说明文档：表名、字段、行数、覆盖区间、数据样例）。
6. 自动生成 data/verification_report.json（机器可读的验证结论）。

用法
----
    .venv/Scripts/python.exe scripts/verify_data_sources.py                # 全部
    .venv/Scripts/python.exe scripts/verify_data_sources.py --only px_index_daily_csi macro_pmi
    .venv/Scripts/python.exe scripts/verify_data_sources.py --list
    .venv/Scripts/python.exe scripts/verify_data_sources.py --no-fetch     # 只重建文档

约定
----
- 接口失败一律记录并打印，绝不静默跳过。
- 单位不做自动换算（保留源口径），换算规则写在 yaml 的 unit_note 与数据字典中。
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import platform
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "data_sources.yaml"
DOCS = ROOT / "docs"
DATA = ROOT / "data"

# 循环参数 -> 落库后的列名
LOOP_COLUMN = {
    "px_index_daily_csi": "index_code",
    "px_index_daily_cni": "index_code",
    "px_index_daily_tx": "index_code",
    "px_index_daily_em": "index_code",
    "px_etf_daily": "etf_code",
    "px_index_cons": "index_code",
    "val_index_value_csi": "index_code",
    "val_index_pe_lg": "index_name",
    "val_index_pb_lg": "index_name",
    "val_stock_value_em": "stock_code",
    "fin_yjbb": "report_period",
    "fin_disclosure": "report_period",
    "fin_indicator_sina": "stock_code",
    "fin_dividend_detail": "stock_code",
    "cyc_futures_foreign": "symbol",
    "cyc_inventory": "symbol",
}

DATE_CANDIDATES = ["trade_date", "report_period", "report_date", "stat_month",
                   "ex_date", "publish_date", "start_date", "stat_date", "as_of_date"]

# 这些接口单次查询有行数/区间上限，按年循环
YEAR_LOOP = {"macro_dr007", "flow_margin_sse"}


# ----------------------------------------------------------------------------
# 基础设施
# ----------------------------------------------------------------------------
def log(msg: str = "") -> None:
    print(msg, flush=True)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def gz_blob(df: pd.DataFrame) -> bytes:
    payload = df.to_json(orient="split", date_format="iso", force_ascii=False)
    return gzip.compress(payload.encode("utf-8"))


def normalize_date_cols(df: pd.DataFrame) -> pd.DataFrame:
    """把整型日期/月份列（如 20180821、201501）统一成字符串，避免主键类型混乱。"""
    for col in DATE_CANDIDATES:
        if col in df.columns and pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].astype(str)
    return df


def apply_column_map(df: pd.DataFrame, cmap: dict | None) -> pd.DataFrame:
    if not cmap:
        return df
    keep = {k: v for k, v in cmap.items() if k in df.columns}
    out = df[list(keep.keys())].rename(columns=keep)
    return out


def key_series(df: pd.DataFrame, keys: list[str]) -> pd.Series:
    """把主键列统一转成字符串拼接，避免 Timestamp / str 混排导致去重失效。"""
    parts = []
    for k in keys:
        s = df[k]
        if pd.api.types.is_datetime64_any_dtype(s):
            s = s.dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            s = s.astype("object").astype(str)
        parts.append(s)
    out = parts[0]
    for p in parts[1:]:
        out = out + "|" + p
    return out


def upsert(con: sqlite3.Connection, table: str, df: pd.DataFrame, keys: list[str]) -> tuple[int, str]:
    """按主键覆盖写入。返回 (表内总行数, 提示信息)。"""
    note = ""
    df = df.loc[:, ~df.columns.duplicated()]
    if keys and all(k in df.columns for k in keys):
        df = df.loc[~key_series(df, keys).duplicated(keep="last")]
    try:
        old = pd.read_sql(f'SELECT * FROM "{table}"', con)
    except Exception:
        old = None
    if old is not None and len(old):
        dropped = [c for c in old.columns if c not in df.columns]
        if dropped:
            note = f"旧表有 {len(dropped)} 列未出现在本次结果中，已保留旧值: {dropped[:5]}"
        keep_cols = [c for c in old.columns if c in df.columns]
        old = old[keep_cols]
        df = pd.concat([old, df], ignore_index=True)
        if keys and all(k in df.columns for k in keys):
            df = df.loc[~key_series(df, keys).duplicated(keep="last")]
    df.to_sql(table, con, if_exists="replace", index=False)
    con.commit()
    return len(df), note


def date_range(df: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    for col in DATE_CANDIDATES:
        if col in df.columns:
            s = df[col].astype(str).str.strip()
            s = s[s.notna() & (s != "") & (s.str.lower() != "nan")]
            if not s.empty:
                return col, s.min(), s.max()
    return None, None, None


# ----------------------------------------------------------------------------
# 参数构造
# ----------------------------------------------------------------------------
def build_params(spec: dict, value) -> dict:
    params = dict(spec.get("params") or {})
    ds_id = spec["id"]
    loop = spec.get("loop")
    if not loop:
        return params
    param = loop["param"]
    if ds_id in YEAR_LOOP:
        y = int(value)
        params["start_date"] = f"{y}0101"
        params["end_date"] = f"{y}1231"
    elif ds_id == "fin_yjbb":
        params["date"] = str(value)
    else:
        params[param] = value
    return params


def reshape(spec: dict, df: pd.DataFrame, value) -> pd.DataFrame:
    """国家统计局接口返回『指标 × 月份』宽表，转成长表。"""
    pv = spec.get("pivot")
    if not pv:
        return df
    wide = df.copy()
    wide.index.name = pv["index"]
    long = wide.reset_index().melt(id_vars=[pv["index"]], var_name=pv["columns"], value_name="value")
    long = long.rename(columns={pv["index"]: "indicator", pv["columns"]: "stat_month"})
    long = long[long["value"].notna()]
    return long


# ----------------------------------------------------------------------------
# 单次抓取
# ----------------------------------------------------------------------------
def fetch_one(ak, spec: dict, value) -> tuple[pd.DataFrame | None, str, str, float]:
    params = build_params(spec, value)
    t0 = time.time()
    try:
        fn = getattr(ak, spec["interface"])
    except AttributeError as e:
        return None, "AttributeError", f"接口不存在或已更名: {e}", time.time() - t0
    try:
        df = fn(**params)
        if not isinstance(df, pd.DataFrame):
            return None, "TypeError", f"返回类型不是 DataFrame: {type(df)}", time.time() - t0
        return df, "", "", time.time() - t0
    except Exception as e:  # noqa: BLE001 - 需要区分所有失败类型
        return None, type(e).__name__, str(e)[:500], time.time() - t0


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def run(only: list[str] | None, fetch: bool) -> int:
    import akshare as ak

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    meta = cfg["meta"]
    db_path = ROOT / meta["db_path"]
    con = connect(db_path)

    con.execute(
        """CREATE TABLE IF NOT EXISTS meta_run(
            run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT,
            akshare_version TEXT, python_version TEXT, platform TEXT, db_path TEXT)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS meta_fetch(
            run_id TEXT, dataset_id TEXT, category TEXT, interface TEXT,
            loop_value TEXT, params_json TEXT, status TEXT, rows INTEGER, n_cols INTEGER,
            col_names TEXT, date_col TEXT, date_min TEXT, date_max TEXT,
            n_dup_key INTEGER, null_rate REAL, n_null_cells INTEGER,
            error_type TEXT, error_msg TEXT, elapsed_s REAL, fetched_at TEXT,
            table_name TEXT, PRIMARY KEY(run_id, dataset_id, loop_value))"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS raw_archive(
            archive_id TEXT PRIMARY KEY, run_id TEXT, dataset_id TEXT, loop_value TEXT,
            params_json TEXT, rows INTEGER, n_cols INTEGER, columns_json TEXT,
            fetched_at TEXT, payload_gz BLOB)"""
    )
    con.commit()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    started = datetime.now().isoformat(timespec="seconds")
    con.execute(
        "INSERT INTO meta_run VALUES (?,?,?,?,?,?,?)",
        (run_id, started, "", ak.__version__, platform.python_version(),
         f"{platform.system()}-{platform.release()}", str(db_path)),
    )
    con.commit()

    specs = cfg["datasets"]
    if only:
        specs = [s for s in specs if s["id"] in only]

    results: list[dict] = []
    log("=" * 96)
    log(f"AkShare 版本: {ak.__version__} | Python {platform.python_version()} | run_id={run_id}")
    log(f"数据库: {db_path}")
    log("=" * 96)

    for spec in specs:
        ds_id = spec["id"]
        loop = spec.get("loop")
        values = loop["values"] if loop else [None]
        agg_rows, ok_cnt, fail_msgs = 0, 0, []
        frames, raw_frames = [], []

        log(f"\n[{ds_id}] {spec['cn_name']}  <-  ak.{spec['interface']}")

        for value in values:
            params = build_params(spec, value)
            if not fetch:
                break
            raw, err_type, err_msg, elapsed = fetch_one(ak, spec, value)
            status = "verified"
            rows = n_cols = 0
            date_col = dmin = dmax = None
            n_dup = n_null = 0
            null_rate = 0.0
            col_names = ""

            if raw is None:
                status = "failed"
                fail_msgs.append(f"{value}: {err_type}: {err_msg}")
            else:
                rows, n_cols = raw.shape
                col_names = json.dumps([str(c) for c in raw.columns], ensure_ascii=False)
                date_col, dmin, dmax = date_range(raw)
                n_null = int(raw.isna().sum().sum())
                null_rate = round(n_null / max(rows * max(n_cols, 1), 1), 4)
                if rows == 0:
                    status = "empty"
                else:
                    ok_cnt += 1
                # 归档原始结果（未改名）
                arch_id = f"{run_id}:{ds_id}:{value}"
                con.execute(
                    "INSERT OR REPLACE INTO raw_archive VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (arch_id, run_id, ds_id, str(value), json.dumps(params, ensure_ascii=False),
                     rows, n_cols, col_names, datetime.now().isoformat(timespec="seconds"), gz_blob(raw)),
                )
                clean = apply_column_map(reshape(spec, raw, value), spec.get("column_map"))
                clean = normalize_date_cols(clean)
                if loop:
                    col = LOOP_COLUMN.get(ds_id, loop["param"])
                    if col not in clean.columns:
                        clean.insert(0, col, value)
                clean["_source"] = spec["interface"]
                clean["_fetched_at"] = datetime.now().isoformat(timespec="seconds")
                if dmin is None:
                    date_col, dmin, dmax = date_range(clean)
                frames.append(clean)
                # 主键重复检查
                keys = spec.get("key_cols") or []
                if all(k in clean.columns for k in keys):
                    n_dup = int(clean.duplicated(subset=keys).sum())
                agg_rows += rows
                log(f"    {'OK ' if status == 'verified' else 'EMPTY'} {value} | {rows} 行 x {n_cols} 列"
                    f" | {date_col}: {dmin} ~ {dmax} | 空值率 {null_rate:.2%} | 重复键 {n_dup} | {elapsed:.1f}s")

            con.execute(
                "INSERT OR REPLACE INTO meta_fetch VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, ds_id, spec.get("category", ""), spec["interface"], str(value),
                 json.dumps(params, ensure_ascii=False), status, rows, n_cols, col_names,
                 date_col or "", dmin or "", dmax or "", n_dup, null_rate, n_null,
                 err_type, err_msg, round(elapsed, 2),
                 datetime.now().isoformat(timespec="seconds"), spec.get("table", "")),
            )
            con.commit()
            if status == "failed":
                log(f"    FAIL {value} | {err_type}: {err_msg[:160]}")

        total_rows, note = 0, ""
        if frames:
            merged = pd.concat(frames, ignore_index=True)
            keys = spec.get("key_cols") or []
            total_rows, note = upsert(con, spec["table"], merged, keys)
            if note:
                log(f"    注意: {note}")

        n_vals = len(values)
        if not fetch:
            status_all = "skipped"
        elif ok_cnt == n_vals:
            status_all = "verified"
        elif ok_cnt == 0:
            status_all = "failed"
        else:
            status_all = "partial"

        results.append({
            "dataset_id": ds_id,
            "category": spec.get("category", ""),
            "cn_name": spec.get("cn_name", ""),
            "interface": spec["interface"],
            "table": spec.get("table", ""),
            "status": status_all,
            "loop_values": n_vals,
            "ok_values": ok_cnt,
            "rows_fetched": agg_rows,
            "rows_in_table": total_rows,
            "errors": fail_msgs,
            "notes": spec.get("notes", ""),
        })
        log(f"    => 状态 {status_all} | 本次 {agg_rows} 行 | 表内累计 {total_rows} 行")

    # 汇总
    con.execute("UPDATE meta_run SET finished_at=? WHERE run_id=?",
                (datetime.now().isoformat(timespec="seconds"), run_id))
    con.commit()

    DATA.mkdir(exist_ok=True)
    results = collect_results(con, cfg)
    (DATA / "verification_report.json").write_text(
        json.dumps({"run_id": run_id, "akshare_version": ak.__version__,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "datasets": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    write_catalog(con, cfg, results, run_id)
    con.close()

    ok = sum(1 for r in results if r["status"] == "verified")
    part = sum(1 for r in results if r["status"] == "partial")
    bad = sum(1 for r in results if r["status"] == "failed")
    log("\n" + "=" * 96)
    log(f"完成: verified={ok}  partial={part}  failed={bad}  共 {len(results)} 个数据集")
    log(f"报告: data/verification_report.json")
    log(f"目录: docs/data_catalog.md")
    log("=" * 96)
    return 0


# ----------------------------------------------------------------------------
# 从数据库汇总最近一次真实抓取的结果（保证报告与库内状态一致）
# ----------------------------------------------------------------------------
def collect_results(con: sqlite3.Connection, cfg: dict) -> list[dict]:
    out: list[dict] = []
    try:
        latest = pd.read_sql("SELECT dataset_id, MAX(run_id) AS run_id FROM meta_fetch GROUP BY dataset_id", con)
    except Exception:
        return out
    lmap = dict(zip(latest["dataset_id"], latest["run_id"]))
    order = {"verified": 3, "empty": 2, "partial": 1, "failed": 0}
    for spec in cfg["datasets"]:
        rid = lmap.get(spec["id"])
        rec = {"dataset_id": spec["id"], "category": spec.get("category", ""),
               "cn_name": spec.get("cn_name", ""), "interface": spec["interface"],
               "table": spec.get("table", ""), "status": "never_run", "loop_values": 0,
               "ok_values": 0, "rows_fetched": 0, "rows_in_table": 0, "errors": [],
               "last_run": rid, "notes": spec.get("notes", "")}
        if rid:
            d = pd.read_sql(f"SELECT * FROM meta_fetch WHERE dataset_id=? AND run_id=?",
                            con, params=(spec["id"], rid))
            rec["loop_values"] = len(d)
            rec["ok_values"] = int((d["status"] == "verified").sum())
            rec["rows_fetched"] = int(d["rows"].fillna(0).sum())
            n_ok, n_all = rec["ok_values"], rec["loop_values"]
            if n_all and n_ok == n_all:
                rec["status"] = "verified"
            elif n_ok == 0:
                rec["status"] = "failed"
            else:
                rec["status"] = "partial"
            rec["errors"] = [f"{r.loop_value}: {r.error_type}: {str(r.error_msg)[:200]}"
                             for r in d.itertuples() if r.status != "verified"]
        try:
            rec["rows_in_table"] = int(pd.read_sql(f'SELECT COUNT(*) c FROM "{spec["table"]}"', con)["c"][0])
        except Exception:
            pass
        out.append(rec)
    return out


# ----------------------------------------------------------------------------
# 生成数据目录文档（只描述数据本身）
# ----------------------------------------------------------------------------
def fmt_cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        if abs(v) >= 1e6 or (abs(v) < 1e-4 and v != 0):
            return f"{v:.6g}"
        return f"{v:.4f}".rstrip("0").rstrip(".")
    s = str(v)
    return s.replace("|", "/").replace("\n", " ")[:60]


def write_catalog(con: sqlite3.Connection, cfg: dict, results: list[dict], run_id: str) -> None:
    DOCS.mkdir(exist_ok=True)
    lines = [
        "# 数据目录（数据本身说明）",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 运行编号：`{run_id}`",
        f"- 数据库：`{cfg['meta']['db_path']}`（SQLite）",
        "- 本文件由 `scripts/verify_data_sources.py` 自动生成，只描述「已经下载到库里的数据」，",
        "  不描述研究设计。研究口径见 `docs/data_dictionary.md`。",
        "",
        "## 1. 表清单总览",
        "",
        "| 数据集 | 类别 | AkShare 接口 | SQLite 表 | 状态 | 行数 | 列数 | 覆盖起始 | 覆盖终止 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    by_id = {r["dataset_id"]: r for r in results}
    for spec in cfg["datasets"]:
        r = by_id.get(spec["id"]) or {"status": "never_run", "ok_values": 0, "loop_values": 0}
        tbl = spec.get("table", "")
        try:
            info = pd.read_sql(f'SELECT * FROM "{tbl}"', con)
            rows, cols = info.shape
            dcol, dmin, dmax = date_range(info)
        except Exception:
            rows, cols, dmin, dmax = 0, 0, "", ""
        lines.append(
            f"| {spec['cn_name']} | {spec.get('category','')} | `{spec['interface']}` | `{tbl}` | "
            f"{r['status']} | {rows} | {cols} | {dmin or '-'} | {dmax or '-'} |"
        )

    lines += ["", "## 2. 各表字段与样例", ""]
    for spec in cfg["datasets"]:
        r = by_id.get(spec["id"]) or {"status": "never_run", "ok_values": 0, "loop_values": 0}
        tbl = spec.get("table", "")
        try:
            df = pd.read_sql(f'SELECT * FROM "{tbl}"', con)
        except Exception as e:
            lines += [f"### {spec['cn_name']}（`{tbl}`）", "", f"表不存在：{e}", ""]
            continue
        dcol, dmin, dmax = date_range(df)
        lines += [
            f"### {spec['cn_name']}（`{tbl}`）",
            "",
            f"- 接口：`ak.{spec['interface']}`　类别：{spec.get('category','')}　状态：{r['status']}"
            f"（成功 {r['ok_values']}/{r['loop_values']} 次调用）",
            f"- 行数：{len(df)}　列数：{df.shape[1]}　频率：{spec.get('freq','')}",
            f"- 日期范围：{dmin or '无日期列'} ~ {dmax or ''}" + (f"（日期列 `{dcol}`）" if dcol else ""),
        ]
        if spec.get("unit_note"):
            lines.append(f"- 单位：{spec['unit_note']}")
        if spec.get("notes"):
            lines.append(f"- 说明：{spec['notes']}")
        lines += ["", "| 字段 | 含义/英文名 | 类型 | 非空率 |", "|---|---|---|---|"]
        inv = {v: k for k, v in (spec.get("column_map") or {}).items()}
        for c in df.columns:
            if c.startswith("_"):
                continue
            nn = 1 - df[c].isna().mean() if len(df) else 0
            cn = inv.get(c, "-")
            lines.append(f"| `{c}` | {cn} | {df[c].dtype} | {nn:.1%} |")
        lines += ["", "数据样例（前 3 行）：", "", "```", df.head(3).to_string(max_cols=14), "```", ""]

    (DOCS / "data_catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="只跑指定 dataset id")
    ap.add_argument("--list", action="store_true", help="列出所有 dataset id")
    ap.add_argument("--no-fetch", action="store_true", help="不抓取，仅重建文档")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.list:
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        for s in cfg["datasets"]:
            print(f"{s['id']:28s} {s.get('category',''):6s} {s['interface']:36s} {s['cn_name']}")
        return 0

    try:
        return run(args.only, fetch=not args.no_fetch)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
