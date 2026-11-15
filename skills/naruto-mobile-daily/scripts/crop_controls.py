#!/usr/bin/env python3
"""把截图右侧的战斗按钮区裁出来并 2 倍放大，方便读出按钮圆心坐标。

不同忍者的技能按钮位置不同，每进一场战斗都要重新量一次。

用法:
    python crop_controls.py shot.png [out.png]

输出会打印换算公式：屏幕x = x0 + 裁剪图x/2 ，屏幕y = 裁剪图y/2
"""

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "shot.png")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "controls.png")

    if not src.is_file():
        print(f"找不到源图: {src}", file=sys.stderr)
        return 1

    im = Image.open(src)
    w, h = im.size
    x0 = w * 2 // 3

    crop = im.crop((x0, 0, w, h))
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    crop.save(out)

    print(f"源图 {w}x{h}，自 x={x0} 起裁切，2 倍放大 -> {out}")
    print(f"换算：屏幕x = {x0} + 裁剪图x/2 ，屏幕y = 裁剪图y/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
