#!/usr/bin/env python3
import concurrent.futures
import hashlib
import html
import json
import math
import os
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


WORKDIR = Path(__file__).resolve().parent
DATASET_PATH = WORKDIR / os.environ.get(
    "DAYFOLD_EVAL_DATASET", "mini_retest_cases_v0.2.json"
)
PROMPT_PATH = WORKDIR / os.environ.get(
    "DAYFOLD_EVAL_PROMPT", "extraction_prompt_v0.2.md"
)
BASELINE_PATH = WORKDIR / os.environ.get(
    "DAYFOLD_EVAL_BASELINE", "benchmark-results.json"
)
RESULT_PATH = WORKDIR / os.environ.get(
    "DAYFOLD_EVAL_RESULT", "mini-retest-results.json"
)
REPORT_DIR_NAME = os.environ.get(
    "DAYFOLD_EVAL_REPORT_DIR", "dayfold-p1-mini-retest-report"
)
REPORT_TITLE = os.environ.get(
    "DAYFOLD_EVAL_REPORT_TITLE", "Dayfold P1 Mini 复测报告"
)
REPORT_VERSION = os.environ.get("DAYFOLD_EVAL_VERSION", "v0.2")
BASELINE_LABEL = os.environ.get("DAYFOLD_EVAL_BASELINE_LABEL", "v0.1")
REPORT_PATH = (
    WORKDIR
    / REPORT_DIR_NAME
    / f"{REPORT_DIR_NAME}.html"
)
ENDPOINT = "https://ark.cn-beijing.volces.com/api/plan/v1/messages"
MODEL = "doubao-seed-2-0-mini"
PRINT_LOCK = threading.Lock()


def load_dataset(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not raw.get("extends"):
        return raw
    base = load_dataset(path.parent / raw["extends"])
    merged = dict(base)
    merged["dataset_id"] = raw["dataset_id"]
    merged["decision"] = raw.get("decision", base.get("decision"))
    merged["thresholds"] = raw.get("thresholds", base["thresholds"])
    merged["cases"] = base["cases"] + raw.get("additional_cases", [])
    return merged


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def multiset_f1(expected, actual):
    expected_counter = Counter(expected)
    actual_counter = Counter(actual)
    if not expected_counter and not actual_counter:
        return 1.0
    if not expected_counter or not actual_counter:
        return 0.0
    true_positive = sum(
        min(expected_counter[key], actual_counter[key])
        for key in expected_counter.keys() | actual_counter.keys()
    )
    precision = true_positive / sum(actual_counter.values())
    recall = true_positive / sum(expected_counter.values())
    return (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )


def parse_json_text(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def valid_operation(operation, valid_memory_ids):
    if not isinstance(operation, dict):
        return False
    op = operation.get("op")
    if op == "upsert":
        confidence = operation.get("confidence")
        return (
            operation.get("type") in {"event", "interest", "goal"}
            and isinstance(operation.get("content"), str)
            and bool(operation["content"].strip())
            and isinstance(confidence, (int, float))
            and 0 <= confidence <= 1
        )
    if op == "archive":
        return (
            operation.get("target_memory_id") in valid_memory_ids
            and isinstance(operation.get("reason"), str)
            and bool(operation["reason"].strip())
        )
    return False


def score_model_case(case, parsed):
    operations = parsed.get("operations") if isinstance(parsed, dict) else None
    valid_memory_ids = {item["id"] for item in case["existing_memories"]}
    structure_ok = (
        isinstance(operations, list)
        and all(valid_operation(item, valid_memory_ids) for item in operations)
    )
    if not structure_ok:
        return {
            "score": 0,
            "structure_ok": False,
            "operation_f1": 0,
            "type_f1": 0,
            "target_f1": 0,
            "term_recall": 0,
            "forbidden_ok": False,
            "count_ok": False,
        }

    actual_ops = [item["op"] for item in operations]
    actual_types = [
        item["type"] for item in operations if item.get("op") == "upsert"
    ]
    actual_targets = [
        item["target_memory_id"]
        for item in operations
        if item.get("op") == "archive"
    ]
    operation_f1 = multiset_f1(case["expected_ops"], actual_ops)
    type_f1 = multiset_f1(case["expected_types"], actual_types)
    target_f1 = multiset_f1(case["expected_target_ids"], actual_targets)

    combined_text = " ".join(
        str(item.get("content", "")) + " " + str(item.get("reason", ""))
        for item in operations
    )
    groups = case["required_term_groups"]
    if not groups:
        term_recall = 1.0
    else:
        matched_groups = sum(
            1 for group in groups if any(term in combined_text for term in group)
        )
        term_recall = matched_groups / len(groups)

    forbidden_ok = not any(
        term in combined_text for term in case["forbidden_terms"]
    )
    count_ok = (
        case["min_operations"] <= len(operations) <= case["max_operations"]
    )
    score = (
        20
        + 20 * operation_f1
        + 20 * type_f1
        + 15 * target_f1
        + 15 * term_recall
        + (5 if forbidden_ok else 0)
        + (5 if count_ok else 0)
    )
    return {
        "score": round(score, 2),
        "structure_ok": True,
        "operation_f1": round(operation_f1, 4),
        "type_f1": round(type_f1, 4),
        "target_f1": round(target_f1, 4),
        "term_recall": round(term_recall, 4),
        "forbidden_ok": forbidden_ok,
        "count_ok": count_ok,
    }


def normalize_delete_text(text):
    aliases = {
        "考研": "研究生考试",
        "不再": "",
        "去掉": "删除",
        "忘记": "删除",
    }
    normalized = text
    for source, target in aliases.items():
        normalized = normalized.replace(source, target)
    return normalized


def run_deterministic_delete(case):
    started = time.perf_counter()
    normalized_input = normalize_delete_text(case["input"])
    candidates = []
    for memory in case["existing_memories"]:
        normalized_content = normalize_delete_text(memory["content"])
        score = sum(
            1
            for term in case["delete_match_terms"]
            if normalize_delete_text(term) in normalized_input
            and normalize_delete_text(term) in normalized_content
        )
        if score:
            candidates.append((score, memory))
    candidates.sort(key=lambda item: item[0], reverse=True)
    target_id = candidates[0][1]["id"] if len(candidates) == 1 else None
    passed = target_id == case["expected_target_id"]
    return {
        "case_id": case["id"],
        "slice": case["slice"],
        "route": case["route"],
        "critical": case["critical"],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "selected_target_id": target_id,
        "expected_target_id": case["expected_target_id"],
        "candidate_count": len(candidates),
        "score": 100 if passed else 0,
        "passed": passed,
    }


def call_model(api_key, system_prompt, case):
    context = json.dumps(
        case["existing_memories"], ensure_ascii=False, separators=(",", ":")
    )
    user_message = (
        f"已有记忆：{context}\n"
        f"当前记录：{case['input']}"
    )
    payload = {
        "model": MODEL,
        "max_tokens": 300,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    started = time.perf_counter()
    result = {
        "case_id": case["id"],
        "slice": case["slice"],
        "route": case["route"],
        "critical": case["critical"],
        "model": MODEL,
    }
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            text = "".join(
                item.get("text", "")
                for item in data.get("content", [])
                if isinstance(item, dict) and item.get("type") == "text"
            )
            result.update(
                {
                    "http_status": response.status,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    "usage": data.get("usage", {}),
                    "raw_output": text,
                }
            )
            try:
                parsed = parse_json_text(text)
                result["parsed_output"] = parsed
                result["json_ok"] = True
                result["scoring"] = score_model_case(case, parsed)
            except Exception as exc:
                result["json_ok"] = False
                result["parse_error"] = repr(exc)
                result["scoring"] = {
                    "score": 0,
                    "structure_ok": False,
                }
    except urllib.error.HTTPError as exc:
        error = exc.read().decode("utf-8", errors="replace")
        result.update(
            {
                "http_status": exc.code,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "error": error.replace(api_key, "[REDACTED_KEY]")[:1200],
                "json_ok": False,
                "scoring": {"score": 0, "structure_ok": False},
            }
        )
    except Exception as exc:
        result.update(
            {
                "http_status": None,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "error": repr(exc).replace(api_key, "[REDACTED_KEY]")[:1200],
                "json_ok": False,
                "scoring": {"score": 0, "structure_ok": False},
            }
        )
    with PRINT_LOCK:
        print(
            f"[Mini] {case['id']} "
            f"score={result['scoring'].get('score', 0)} "
            f"latency={result.get('elapsed_ms')}ms"
        )
    return result


def summarize(dataset, model_results, delete_results):
    thresholds = dataset["thresholds"]
    scores = [item["scoring"].get("score", 0) for item in model_results]
    latencies = [
        item["elapsed_ms"] for item in model_results if item.get("elapsed_ms")
    ]
    output_tokens = [
        item.get("usage", {}).get("output_tokens", 0)
        for item in model_results
        if isinstance(item.get("usage", {}).get("output_tokens", 0), (int, float))
    ]
    input_tokens = [
        item.get("usage", {}).get("input_tokens", 0)
        for item in model_results
        if isinstance(item.get("usage", {}).get("input_tokens", 0), (int, float))
    ]
    json_rate = (
        sum(1 for item in model_results if item.get("json_ok"))
        / len(model_results)
    )
    critical_model_results = [
        item for item in model_results if item["critical"]
    ]
    critical_model_pass = all(
        item["scoring"].get("score", 0)
        >= thresholds["critical_case_min_score"]
        for item in critical_model_results
    )
    delete_rate = (
        sum(1 for item in delete_results if item["passed"]) / len(delete_results)
        if delete_results
        else 1.0
    )
    average_score = statistics.mean(scores)
    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)
    output_p95 = percentile(output_tokens, 0.95)

    blockers = []
    warnings = []
    if average_score < thresholds["model_average_score_pass"]:
        blockers.append("model_average_score_below_90")
    if json_rate < thresholds["json_success_rate_pass"]:
        blockers.append("json_success_rate_below_100_percent")
    if not critical_model_pass:
        blockers.append("critical_model_case_failed")
    if delete_rate < thresholds["deterministic_delete_success_rate_pass"]:
        blockers.append("deterministic_delete_case_failed")
    if p95 and p95 > thresholds["latency_p95_ms_warn"]:
        warnings.append("latency_p95_above_20s")
    if output_p95 and output_p95 > thresholds["output_tokens_p95_warn"]:
        warnings.append("output_tokens_p95_above_400")

    verdict = "block" if blockers else ("warn" if warnings else "pass")
    return {
        "model_case_count": len(model_results),
        "deterministic_delete_case_count": len(delete_results),
        "average_score": round(average_score, 2),
        "json_success_rate": round(json_rate, 4),
        "critical_model_cases_passed": critical_model_pass,
        "deterministic_delete_success_rate": round(delete_rate, 4),
        "latency_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "max": max(latencies),
        },
        "tokens": {
            "input_total": sum(input_tokens),
            "output_total": sum(output_tokens),
            "output_p95": round(output_p95, 2),
        },
        "verdict": verdict,
        "blockers": blockers,
        "warnings": warnings,
        "failed_model_cases": [
            {
                "case_id": item["case_id"],
                "slice": item["slice"],
                "score": item["scoring"].get("score", 0),
                "scoring": item["scoring"],
            }
            for item in model_results
            if item["scoring"].get("score", 0) < 90
        ],
        "failed_delete_cases": [
            item for item in delete_results if not item["passed"]
        ],
    }


def render_report(report):
    summary = report["summary"]
    baseline = report.get("baseline", {})
    report_meta = report["report_meta"]
    verdict_labels = {
        "pass": "通过",
        "warn": "有条件通过",
        "block": "未通过",
    }
    verdict = summary["verdict"]
    verdict_label = verdict_labels[verdict]
    conclusion = {
        "pass": "Mini 已满足 Memory Extraction 的预设发布门槛，可冻结为首版提取模型。",
        "warn": "Mini 的质量门槛已通过，但仍有性能或 Token 风险需要在实现阶段设置预算。",
        "block": "Mini 尚未达到预设门槛，本轮结果只能用于继续修正，不能冻结为生产提取模型。",
    }[verdict]
    generated = html.escape(report["generated_at"])
    failures = summary["failed_model_cases"]

    failure_rows = ""
    for item in failures:
        failure_rows += (
            "<tr>"
            f"<th scope='row'>{html.escape(item['case_id'])}</th>"
            f"<td>{html.escape(item['slice'])}</td>"
            f"<td>{item['score']:.2f}</td>"
            f"<td>{html.escape(json.dumps(item['scoring'], ensure_ascii=False))}</td>"
            "</tr>"
        )
    if not failure_rows:
        failure_rows = (
            "<tr><th scope='row'>无</th><td colspan='3'>所有模型案例均达到 90 分。</td></tr>"
        )

    baseline_score = baseline.get("average_score", "—")
    baseline_json = baseline.get("json_success_rate", "—")
    baseline_p95 = baseline.get("latency_ms", {}).get("p95", "—")
    baseline_tokens = baseline.get("tokens", {}).get("output_total", "—")
    status_class = f"status-{verdict}"

    return f"""<!-- Generated by Trae Work -->
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(report_meta['title'])}</title>
  <style>
    :root {{
      --page-bg: #F7F8F3;
      --page-surface: #FFFFFF;
      --page-surface-muted: #EEF1E8;
      --page-text: #17241B;
      --page-text-secondary: #34463A;
      --page-text-muted: #6B786F;
      --page-text-disabled: #98A198;
      --page-border: #D9DED5;
      --page-brand: #245A38;
      --page-brand-hover: #1C482D;
      --page-brand-active: #143421;
      --page-brand-soft: #E7EFE8;
      --page-brand-soft-strong: #D7E5DA;
      --page-brand-text: #173A25;
      --bg: #F7F8F3;
      --bg2: #FFFFFF;
      --rule: #D9DED5;
      --ink: #17241B;
      --muted: #6B786F;
      --text-secondary: #34463A;
      --text-disabled: #98A198;
      --accent: #245A38;
      --accent-hover: #1C482D;
      --accent-active: #143421;
      --accent-soft: #E7EFE8;
      --accent2: #5E8069;
      --chart-series-1: #245A38;
      --chart-series-2: #4F7A5D;
      --chart-series-3: #7B9B84;
      --chart-series-4: #9E7C52;
      --chart-other: #D9DED5;
      --chart-accent: #4F7A5D;
      --chart-accent-2: #9E7C52;
      --chart-positive: #2E7D4D;
      --chart-warning: #B7791F;
      --chart-negative: #B53A3A;
      --chart-grid: rgba(23, 36, 27, 0.12);
      --chart-axis: #6B786F;
      --chart-label: #6B786F;
      --chart-tooltip-bg: #FFFFFF;
      --success: #2E7D4D;
      --info: #245A38;
      --reminder: #A8662C;
      --warning: #B7791F;
      --danger: #B53A3A;
      --positive: #2E7D4D;
      --negative: #B53A3A;
      --radius: 12px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page-bg);
      color: var(--page-text);
      font: 14px/1.65 -apple-system, BlinkMacSystemFont, "PingFang SC",
        "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif;
    }}
    a {{ color: var(--accent); overflow-wrap: anywhere; }}
    .report-intro {{ padding: 32px 20px 0; }}
    .report-intro__surface {{
      max-width: 1000px;
      margin: 0 auto;
      padding: 48px;
      background: var(--page-brand-soft);
      border: 1px solid var(--page-border);
      border-radius: var(--radius);
    }}
    .report-intro__content {{ max-width: 760px; }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--page-brand);
      font: 600 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h1 {{ margin: 0 0 14px; font-size: clamp(30px, 5vw, 52px); line-height: 1.08; }}
    h2 {{ margin: 0 0 18px; font-size: 24px; line-height: 1.25; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; }}
    .summary {{ margin: 0; max-width: 720px; color: var(--page-text-secondary); font-size: 17px; }}
    .meta {{ margin-top: 18px; color: var(--page-text-muted); }}
    main, footer {{ max-width: 1000px; margin: 0 auto; padding: 0 20px; }}
    section {{ margin: 48px 0; }}
    .status {{
      display: inline-block;
      margin-top: 20px;
      padding: 5px 10px;
      border-radius: 999px;
      font-weight: 700;
    }}
    .status-pass {{ color: var(--success); background: #E8F3EC; }}
    .status-warn {{ color: var(--warning); background: #F8F0DF; }}
    .status-block {{ color: var(--danger); background: #F7E8E8; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-top: 20px;
    }}
    .metric {{
      padding: 18px;
      background: var(--page-surface);
      border: 1px solid var(--page-border);
      border-radius: var(--radius);
    }}
    .metric span {{ display: block; color: var(--page-text-muted); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 5px; font-size: 25px; font-variant-numeric: tabular-nums; }}
    .callout {{
      padding: 18px 20px;
      background: var(--page-surface);
      border: 1px solid var(--page-border);
      border-radius: var(--radius);
    }}
    .feature-list {{ border-top: 1px solid var(--page-border); }}
    .feature {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 20px;
      padding: 15px 0;
      border-bottom: 1px solid var(--page-border);
    }}
    table {{ width: 100%; border-collapse: collapse; background: var(--page-surface); }}
    caption {{ text-align: left; margin-bottom: 10px; font-weight: 700; }}
    th, td {{ padding: 12px; border-bottom: 1px solid var(--page-border); text-align: left; vertical-align: top; }}
    thead th {{ background: var(--page-surface-muted); }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    footer {{ padding-bottom: 48px; color: var(--page-text-muted); }}
    @media (max-width: 720px) {{
      .report-intro__surface {{ padding: 30px 22px; }}
      .metrics {{ grid-template-columns: repeat(2, 1fr); }}
      .feature {{ grid-template-columns: 1fr; gap: 4px; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
      tr {{ padding: 12px; border-bottom: 1px solid var(--page-border); }}
      th, td {{ padding: 5px 0; border: 0; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      .report-intro {{ padding-top: 0; }}
      .report-intro__surface {{ border-radius: 0; }}
    }}
  </style>
</head>
<body>
  <header class="report-intro">
    <div class="report-intro__surface">
      <div class="report-intro__content">
        <p class="eyebrow">Dayfold · P1 Evaluation</p>
        <h1>{html.escape(report_meta['title'])}</h1>
        <p class="summary">{html.escape(conclusion)}</p>
        <span class="status {status_class}">{verdict_label}</span>
        <p class="meta">数据集 {html.escape(report_meta['version'])} · 生成时间 {generated} · 全部案例为虚构数据</p>
      </div>
    </div>
  </header>

  <main>
    <section id="overview">
      <h2>核心指标</h2>
      <div class="metrics">
        <div class="metric"><span>模型案例平均分</span><strong>{summary['average_score']:.2f}</strong></div>
        <div class="metric"><span>JSON 成功率</span><strong>{summary['json_success_rate'] * 100:.0f}%</strong></div>
        <div class="metric"><span>p95 延迟</span><strong>{summary['latency_ms']['p95'] / 1000:.2f}s</strong></div>
        <div class="metric"><span>确定性删除成功率</span><strong>{summary['deterministic_delete_success_rate'] * 100:.0f}%</strong></div>
      </div>
    </section>

    <section id="method">
      <h2>测试口径</h2>
      <div class="feature-list">
        <div class="feature"><strong>模型路径</strong><span>{summary['model_case_count']} 个新增、归档与拒绝记忆案例调用 <code>doubao-seed-2-0-mini</code>。</span></div>
        <div class="feature"><strong>删除路径</strong><span>{summary['deterministic_delete_case_count']} 个明确删除案例绕过模型，由已有 Memory ID 与当前用户范围内的确定性匹配处理。</span></div>
        <div class="feature"><strong>输出契约</strong><span><code>operations</code> 支持 <code>upsert</code> 和 <code>archive</code>，解决旧版单一 action 无法表达目标替换的问题。</span></div>
        <div class="feature"><strong>门槛</strong><span>平均分 ≥90、JSON 100%、关键案例 ≥90、确定性删除 100%。性能和 Token 超限记为警告。</span></div>
      </div>
    </section>

    <section id="comparison">
      <h2>与基线对比</h2>
      <table>
        <caption>Mini 基线与本轮复测（案例集和输出契约可能不同，仅用于方向观察）</caption>
        <thead><tr><th>指标</th><th>{html.escape(report_meta['baseline_label'])}</th><th>{html.escape(report_meta['version'])}</th></tr></thead>
        <tbody>
          <tr><th scope="row">平均分</th><td>{baseline_score}</td><td>{summary['average_score']}</td></tr>
          <tr><th scope="row">JSON 成功率</th><td>{baseline_json}</td><td>{summary['json_success_rate']}</td></tr>
          <tr><th scope="row">p95 延迟</th><td>{baseline_p95} ms</td><td>{summary['latency_ms']['p95']} ms</td></tr>
          <tr><th scope="row">输出 Token 总量</th><td>{baseline_tokens}</td><td>{summary['tokens']['output_total']}</td></tr>
        </tbody>
      </table>
    </section>

    <section id="failures">
      <h2>失败与风险</h2>
      <table>
        <caption>低于 90 分的模型案例</caption>
        <thead><tr><th>案例</th><th>切片</th><th>分数</th><th>评分细节</th></tr></thead>
        <tbody>{failure_rows}</tbody>
      </table>
      <div class="callout" style="margin-top:20px">
        <h3>Token 解释边界</h3>
        <p>Agent Plan 的 usage 可能包含不可见推理消耗。本报告记录原始统计，但不把它直接等同于可见 JSON 长度；是否关闭思考模式仍需单独验证。</p>
      </div>
    </section>

    <section id="decision">
      <h2>P1 决策</h2>
      <div class="feature-list">
        <div class="feature"><strong>模型</strong><span>{html.escape(conclusion)}</span></div>
        <div class="feature"><strong>删除</strong><span>明确删除不进入 LLM 提取；后端必须按 <code>user_id + memory_id</code> 执行，并同步删除向量。</span></div>
        <div class="feature"><strong>Dify 时点</strong><span>本轮通过所有真实阻断案例后，在 P1 最终冻结前接入硅基流动，使用同一数据集建立独立 baseline；不进入真实用户数据链路。</span></div>
        <div class="feature"><strong>Dify 阻断条件</strong><span>若本轮仍有质量阻断，先修正 Dayfold 自有 Prompt 与契约，不同时引入 Dify，以免混淆变量。</span></div>
      </div>
    </section>
  </main>

  <footer>
    <p>证据文件：<a href="../{html.escape(report_meta['result_file'])}">本轮脱敏结果</a> · <a href="../{html.escape(report_meta['baseline_file'])}">基线结果</a> · <a href="../{html.escape(report_meta['dataset_file'])}">版本化案例</a> · <a href="../{html.escape(report_meta['prompt_file'])}">版本化 Prompt</a></p>
    <p>静态报告，不包含 API Key、真实用户数据或完整向量。浏览器渲染 QA：NOT RUN。</p>
  </footer>
</body>
</html>
"""


def main():
    api_key = os.environ.get("DAYFOLD_ARK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("缺少 DAYFOLD_ARK_API_KEY")

    dataset = load_dataset(DATASET_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    model_cases = [item for item in dataset["cases"] if item["route"] == "model"]
    delete_cases = [
        item for item in dataset["cases"] if item["route"] == "deterministic_delete"
    ]

    delete_results = [run_deterministic_delete(case) for case in delete_cases]
    for item in delete_results:
        print(
            f"[Delete] {item['case_id']} score={item['score']} "
            f"target={item['selected_target_id']}"
        )

    jobs = list(model_cases)
    random.Random(20260916).shuffle(jobs)
    model_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(call_model, api_key, prompt, case) for case in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            model_results.append(future.result())
    model_results.sort(key=lambda item: item["case_id"])
    delete_results.sort(key=lambda item: item["case_id"])

    baseline = {}
    if BASELINE_PATH.exists():
        baseline_report = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        if "summary" in baseline_report:
            baseline = baseline_report["summary"]
        else:
            baseline = next(
                (
                    item
                    for item in baseline_report.get("summaries", [])
                    if item.get("model") == MODEL
                ),
                {},
            )

    report = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "report_meta": {
            "title": REPORT_TITLE,
            "version": REPORT_VERSION,
            "baseline_label": BASELINE_LABEL,
            "result_file": RESULT_PATH.name,
            "baseline_file": BASELINE_PATH.name,
            "dataset_file": DATASET_PATH.name,
            "prompt_file": PROMPT_PATH.name,
        },
        "dataset": {
            "id": dataset["dataset_id"],
            "case_count": len(dataset["cases"]),
            "model_case_count": len(model_cases),
            "deterministic_delete_case_count": len(delete_cases),
            "data_class": dataset["data_class"],
            "sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        },
        "prompt": {
            "version": PROMPT_PATH.stem,
            "sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        },
        "model": MODEL,
        "endpoint_protocol": "anthropic-compatible",
        "key_fingerprint": hashlib.sha256(api_key.encode()).hexdigest()[:8],
        "run_config": {
            "temperature": 0,
            "max_tokens": 300,
            "concurrency": 2,
            "timeout_seconds": 60,
            "random_seed": 20260916,
        },
        "thresholds": dataset["thresholds"],
        "summary": summarize(dataset, model_results, delete_results),
        "baseline": baseline,
        "model_results": model_results,
        "deterministic_delete_results": delete_results,
        "secret_written_to_report": False,
    }
    RESULT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(report), encoding="utf-8")

    summary = report["summary"]
    print()
    print(f"Mini {REPORT_VERSION} 复测完成")
    print("模型案例平均分：", summary["average_score"])
    print("JSON 成功率：", summary["json_success_rate"])
    print("确定性删除成功率：", summary["deterministic_delete_success_rate"])
    print("p95 延迟：", summary["latency_ms"]["p95"], "ms")
    print("输出 Token：", summary["tokens"]["output_total"])
    print("结论：", summary["verdict"])
    print("脱敏结果：", RESULT_PATH)
    print("HTML 报告：", REPORT_PATH)


if __name__ == "__main__":
    main()
