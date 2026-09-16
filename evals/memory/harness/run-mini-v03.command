#!/bin/bash
set -eo pipefail
set +v
set +x

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$WORKDIR/mini-v03-run.log"

finish() {
  local status=$?
  trap - EXIT
  unset DAYFOLD_ARK_API_KEY
  echo
  if [[ $status -eq 0 ]]; then
    echo "Mini v0.3 复测进程已完成。"
  else
    echo "Mini v0.3 复测未完成，退出码：$status"
  fi
  read -r -p "按回车关闭窗口..." _
  exit $status
}
trap finish EXIT

exec > >(tee "$LOG") 2>&1

echo "Dayfold P1 Mini Memory Pipeline v0.3 复测"
echo "18 次 Mini 请求 + 2 个确定性删除案例"
echo "全部使用人工编写的虚构数据"
echo

DAYFOLD_ARK_API_KEY="$(
  security find-generic-password -a "$USER" -s "dayfold-ark-api-key" -w 2>/dev/null || true
)"

if [[ -z "$DAYFOLD_ARK_API_KEY" ]]; then
  echo "请输入 Agent Plan API Key。输入时不会显示字符，粘贴后按回车。"
  read -r -s -p "API Key: " DAYFOLD_ARK_API_KEY
  echo
fi

if [[ -z "$DAYFOLD_ARK_API_KEY" ]]; then
  echo "API Key 为空，复测未开始。"
  exit 2
fi

export DAYFOLD_ARK_API_KEY
export DAYFOLD_EVAL_DATASET="mini_retest_cases_v0.3.json"
export DAYFOLD_EVAL_PROMPT="extraction_prompt_v0.3.md"
export DAYFOLD_EVAL_BASELINE="mini-retest-results.json"
export DAYFOLD_EVAL_RESULT="mini-v03-results.json"
export DAYFOLD_EVAL_REPORT_DIR="dayfold-p1-mini-v03-report"
export DAYFOLD_EVAL_REPORT_TITLE="Dayfold P1 Mini v0.3 复测报告"
export DAYFOLD_EVAL_VERSION="v0.3"
export DAYFOLD_EVAL_BASELINE_LABEL="v0.2"

echo "开始复测，预计需要数分钟，请保持窗口打开..."
python3 "$WORKDIR/run_mini_retest.py"
