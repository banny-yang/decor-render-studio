#!/usr/bin/env bash
# 并行分片下载 torch cu126 三件套轮子（阿里云镜像）
set -u
cd "$(dirname "$0")/.."
mkdir -p .wheels .dlparts
BASE="https://mirrors.aliyun.com/pytorch-wheels/cu126"
N=12

declare -A WHEELS=(
  [torch-2.7.1+cu126-cp313-cp313-win_amd64.whl]="torch-2.7.1%2Bcu126-cp313-cp313-win_amd64.whl"
  [torchvision-0.22.1+cu126-cp313-cp313-win_amd64.whl]="torchvision-0.22.1%2Bcu126-cp313-cp313-win_amd64.whl"
  [torchaudio-2.7.1+cu126-cp313-cp313-win_amd64.whl]="torchaudio-2.7.1%2Bcu126-cp313-cp313-win_amd64.whl"
)

fetch_one() {
  local local_name=$1 remote=$2
  local out=".wheels/$local_name"
  local url="$BASE/$remote"
  local total
  total=$(curl -sIL -A "Mozilla/5.0" "$url" | grep -i '^content-length' | tail -1 | tr -d '\r' | awk '{print $2}')
  if [ -z "$total" ] || [ "$total" -lt 1000 ]; then echo "FATAL: $local_name 拿不到大小"; return 1; fi
  if [ -f "$out" ] && [ "$(stat -c%s "$out")" -eq "$total" ]; then echo "$local_name 已完成"; return 0; fi
  local chunk=$(( (total + N - 1) / N ))
  local pids=()
  for i in $(seq 0 $((N-1))); do
    (
      local s=$((i*chunk)); local e=$(( (i+1)*chunk - 1 ))
      [ $e -ge $total ] && e=$((total-1))
      [ $s -gt $e ] && exit 0
      local part=".dlparts/${local_name}.part$(printf '%02d' $i)"
      for try in 1 2 3 4 5; do
        curl -sL -A "Mozilla/5.0" -r "${s}-${e}" -o "$part" --speed-time 30 --speed-limit 30000 "$url" \
          && [ "$(stat -c%s "$part" 2>/dev/null || echo 0)" -eq $((e-s+1)) ] && exit 0
        sleep 2
      done
      exit 1
    ) &
    pids+=($!)
  done
  local fail=0
  for p in "${pids[@]}"; do wait "$p" || fail=1; done
  [ $fail -ne 0 ] && { echo "$local_name 有分片失败"; return 1; }
  cat .dlparts/${local_name}.part* > "$out"
  [ "$(stat -c%s "$out")" -eq "$total" ] || { echo "$local_name 大小不符"; return 1; }
  rm -f .dlparts/${local_name}.part*
  echo "$local_name 下载完成 $((total/1024/1024))MB"
}

rc=0
for local_name in "${!WHEELS[@]}"; do
  fetch_one "$local_name" "${WHEELS[$local_name]}" || rc=1
done
[ $rc -eq 0 ] && rm -rf .dlparts
exit $rc
