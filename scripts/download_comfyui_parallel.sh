#!/usr/bin/env bash
# 并行分片下载 ComfyUI 便携包（国内加速）
set -u
cd "$(dirname "$0")/.."

URL="https://gh-proxy.com/https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
OUT="comfyui_portable.7z"
N=16
UA="Mozilla/5.0"

mkdir -p .dlparts
TOTAL=$(curl -sIL -A "$UA" "$URL" | grep -i '^content-length' | tail -1 | tr -d '\r' | awk '{print $2}')
if [ -z "${TOTAL}" ] || [ "${TOTAL}" -lt 100000000 ]; then
  echo "FATAL: 无法获取文件大小 (got: ${TOTAL:-none})"
  exit 1
fi
echo "总大小: $((TOTAL/1024/1024)) MB，分 $N 段并行下载"
CHUNK=$(( (TOTAL + N - 1) / N ))

fetch_part() {
  local i=$1 start=$2 end=$3
  local part=".dlparts/part_$(printf '%02d' "$i")"
  [ -s "$part" ] && [ "$(stat -c%s "$part" 2>/dev/null || echo 0)" -eq $((end-start+1)) ] && return 0
  for try in 1 2 3 4 5 6; do
    curl -sL -A "$UA" -r "${start}-${end}" -o "$part" --speed-time 30 --speed-limit 30000 "$URL" \
      && [ "$(stat -c%s "$part" 2>/dev/null || echo 0)" -eq $((end-start+1)) ] && return 0
    echo "  part $i 第 $try 次失败，重试..."
    sleep 3
  done
  echo "  part $i FAILED"
  return 1
}

pids=()
for i in $(seq 0 $((N-1))); do
  start=$((i*CHUNK)); end=$(( (i+1)*CHUNK - 1 ))
  [ $end -ge $TOTAL ] && end=$((TOTAL-1))
  [ $start -gt $end ] && break
  fetch_part "$i" "$start" "$end" &
  pids+=($!)
done

fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
if [ $fail -ne 0 ]; then echo "存在失败分片，重跑本脚本可断点续传"; exit 1; fi

cat .dlparts/part_* > "$OUT"
size=$(stat -c%s "$OUT")
if [ "$size" -eq "$TOTAL" ]; then
  echo "下载完成: $OUT ($((size/1024/1024)) MB)"
  rm -rf .dlparts
else
  echo "大小不匹配: $size != $TOTAL"
  exit 1
fi
