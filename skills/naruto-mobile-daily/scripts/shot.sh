#!/usr/bin/env bash
# 截图并拉回本机。用法: ./shot.sh [输出文件名]
set -euo pipefail
export MSYS_NO_PATHCONV=1

out="${1:-shot.png}"
adb shell screencap -p /sdcard/_nl.png
adb pull /sdcard/_nl.png "$out" >/dev/null
adb shell rm /sdcard/_nl.png
echo "$out"
