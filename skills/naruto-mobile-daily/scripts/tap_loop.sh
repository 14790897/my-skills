#!/usr/bin/env bash
# 在设备内执行连点循环。
# host 端每条 `adb shell input tap` 要走一次进程往返，实测只有 ~6 次/秒；
# 把 while 循环塞进设备 shell 可以到 ~20 次/秒，是决斗场能不能赢的分界线。
#
# 用法: ./tap_loop.sh <循环次数> <x,y> [<x,y> ...]
# 例:   ./tap_loop.sh 400 2126,875 2137,236 2129,410 1705,942
set -euo pipefail
export MSYS_NO_PATHCONV=1

if [ $# -lt 2 ]; then
  echo "用法: $0 <循环次数> <x,y> [<x,y> ...]" >&2
  exit 1
fi

count="$1"; shift
body=""
for pair in "$@"; do
  x="${pair%,*}"
  y="${pair#*,}"
  if ! [[ "$x" =~ ^[0-9]+$ && "$y" =~ ^[0-9]+$ ]]; then
    echo "坐标格式错误: $pair（应为 x,y，且为纯数字）" >&2
    exit 1
  fi
  body="$body input tap $x $y;"
done

adb shell "i=0; while [ \$i -lt $count ]; do$body i=\$((i+1)); done"
echo "完成 $count 轮"
