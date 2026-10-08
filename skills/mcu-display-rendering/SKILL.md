---
name: mcu-display-rendering
description: MCU 屏幕渲染的性能与显示质量规范。写或改动任何驱动 LCD/OLED 的代码前必须先读：DMA 传输、帧缓冲分配、刷新策略、文字排版、动画时序。触发场景：显示屏 / 图形库（LovyanGFX、TFT_eSPI、LVGL、Adafruit_GFX、U8g2）/ 播放 GIF 或动画 / 刷图片 / 时钟或仪表界面 / 屏幕闪烁或数字抖动 / SPI 屏刷新慢。Keywords: display, LCD, OLED, TFT, SPI, DMA, framebuffer, flicker, refresh, animation, ESP32, ESP-IDF.
---

# mcu-display-rendering

Instructions for the agent to follow when this skill is activated.

## When to use

只要任务涉及给 MCU 写屏幕相关的代码就用这个技能 —— 包括新写驱动、加动画、加界面、优化刷新速度、排查闪烁或画面错位。**不要等用户抱怨慢或闪才想起来看。**

下面每一条都是实际踩过的坑，代价是大量返工或用户直接指出「你怎么没用 DMA」。**这些不是优化建议，是交付底线。**

## 交付前自检清单

代码能跑不等于写对了。提交前逐条确认：

- [ ] **批量像素传输走 DMA 了吗？** 超过几 KB 的传输用 CPU 轮询是浪费
- [ ] **帧缓冲用了正确的内存能力标志吗？** `MALLOC_CAP_DMA`，不是普通 malloc
- [ ] **分配前查过最大连续块吗？** 空闲总量够 ≠ 能分配
- [ ] **刷新是「清整块再重绘」吗？** 是的话必然闪，改用脏区追踪
- [ ] **文字位置会随内容变化吗？** 比例字体居中会左右抖，改固定字位
- [ ] **动画扣除了渲染耗时吗？** 不扣的话整体变慢

## 1. 批量像素传输必须走 DMA

**原则**：一次推送上 KB 像素时，不要让 CPU 轮询等 SPI 传完。这是最容易被忽略、影响也最大的一条。

LovyanGFX（ESP32）：

```cpp
// 总线配置里必须显式打开 DMA 通道，默认是不开的
auto cfg = bus.config();
cfg.freq_write = 40000000;
cfg.dma_channel = SPI_DMA_CH_AUTO;   // ← 漏了这行就退化成 CPU 推送
bus.config(cfg);

// 推送时用 DMA 版本，且必须等传输结束再返回，
// 否则下一帧会覆盖还在被 DMA 读的缓冲，画面出撕裂
lcd.startWrite();
lcd.pushImageDMA(0, 0, w, h, buf);
lcd.waitDMA();
lcd.endWrite();
```

其它库对应关系：TFT_eSPI 用 `pushImageDMA()`；LVGL 走 `disp_drv.flush_cb` 时也应把 `lv_disp_flush_ready` 与 DMA 完成回调对齐。

**缓冲必须 DMA 可访问**，否则静默退化成逐字节拷贝：

```cpp
buf = heap_caps_malloc(bytes, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
```

**实测收益**（240×240 RGB565，40MHz SPI）：把「逐段 CPU 推送」换成「整屏帧缓冲 + DMA 单次推送」后，每帧绘制从 **93ms 降到 28ms**，动画从慢动作恢复到原速。

## 2. 帧缓冲分配：小心「连续块」陷阱

**最容易踩的坑**：`heap_caps_get_free_size()` 报告有 214KB 空闲，但分配 115KB 却失败。

原因是 DMA 内存要求**物理连续**。真实约束是 `heap_caps_get_largest_free_block()`，不是空闲总量。实测遇到过：最大连续块 **114,688** 字节，而需要 **115,200** —— 差 512 字节就是失败。

**对策**：

```cpp
// 先查最大连续块，别只看 free_size
size_t need = w * h * 2;
if (heap_caps_get_largest_free_block(MALLOC_CAP_DMA) < need) {
    // 拆成多块，分别分配、分别推送
}
```

拆块是常规做法，不是退而求其次。实测把 240×240 的帧缓冲拆成上下两个 57,600 字节的块后稳定分配成功，每帧推送两次而非一次，性能损失可忽略。

**另外**：在 WiFi / 蓝牙栈启动**之前**分配大缓冲，之后堆会碎片化得厉害。

## 3. 刷新策略：清屏重绘必然闪

**反例**（会闪）：

```cpp
lcd.fillRect(0, y, w, h, BG);   // 先清成背景色
lcd.drawString(text, x, y);     // 再画 —— 清完到画完之间有可见黑屏
```

每秒刷新的元素（秒数、进度条）这样写，屏幕上就是每秒闪一下。

**对策：脏区追踪** —— 缓存上一帧内容，只重画真正变化的区域。

同时注意**别把一次更新拆成很多次小推送**。SPI 每次传输都有固定开销，几千次小推送的开销会远超传输本身。能合并成一次大推送就合并。

**如果透明像素要透出上一帧**（GIF 的帧间增量就是这样），那必须有个持久的帧缓冲保存上一帧 —— 靠屏幕保留也行，但那样只能逐段推送，性能差一个量级。两者取舍得有意识。

## 4. 文字排版：比例字体居中会抖

**坑一：位置抖动。** 用 `drawCenterString` 之类按**字符串实际宽度**居中的接口时，比例字体下不同内容的宽度不同 —— `11:11` 比 `00:00` 窄得多，于是起始 x 随内容变化，时钟每走一秒整行左右跳一次。

**对策：固定字位。** 每个字符的位置预先算死，与内容无关。

**坑二：字位宽度取错会切出细线。** 字位宽度**不能取整串平均值**。比例字体里冒号远窄于数字，平均值小于数字实际宽度 → 数字溢出到相邻字位 → 被对方的清屏切掉一两列 → 数字边缘出现一道细线。

**正解：字位宽度取「字符集里最宽的字形」**：

```cpp
int32_t advance = 0;
for (const char* p = charset; *p; ++p) {      // charset 如 "0123456789:"
    char ch[2] = {*p, 0};
    advance = max(advance, lcd.textWidth(ch));
}
// 再把整串缩放到目标宽度：
float scale = (float)targetW / (advance * len);
```

每个字形在自己的字位里居中，宽窄不一也不会互相侵入。

**副作用要知道**：等宽字位下冒号会占一个数字宽的格子，看起来比原来「松」。这是电子表的标准排版，通常更好看；不满意的话给窄字符单独分配窄字位。

## 5. 动画时序：不补偿渲染耗时就会慢

**反例**：

```cpp
while (playFrame()) {
    vTaskDelay(frameDelay);   // 只等帧间隔，渲染耗时被叠加在上面
}
```

实际每帧耗时 = 渲染耗时 + 帧间隔。渲染 30ms + 间隔 60ms = 每帧 90ms，动画比原速慢 50%。

**对策：从帧间隔里扣掉已经花掉的时间**：

```cpp
int64_t t0 = esp_timer_get_time();
playFrame(&delay);
int elapsedMs = (esp_timer_get_time() - t0) / 1000;
int waitMs = delay - elapsedMs;
vTaskDelay(pdMS_TO_TICKS(waitMs > 1 ? waitMs : 1));
```

只要渲染快于帧间隔，就能跑出原速。**实测**：同一个 51 帧 GIF 从 9227ms 降到 3079ms，与原文件的帧间隔总和一致。

**推论**：优化渲染速度在「渲染 > 帧间隔」时才有意义。已经跑在原速上时，继续优化不会让它更快 —— 别白费功夫。

## 上机自检：先分离硬件和代码

屏幕不亮时，**不要先怀疑代码**。先刷一段纯色轮播（红→绿→蓝→白→黑），用现象分诊：

| 现象 | 指向 |
|---|---|
| 能依次变色 | 面板 / SPI / 背光都通，问题在绘图逻辑 |
| 全黑，一点光都没有 | 背光或供电，与 SPI 信号无关 |
| 有背光但不变色 | SPI 信号到了但没写进去，查 DC/CS 时序或引脚 |
| 变色但颜色不对 | 面板参数（`invert` / `rgb_order` / byte order） |

这个自检能把「接线错了」和「代码错了」分开，省掉大量来回猜。

**引脚相关的额外提醒**：

- 厂商文档里的引脚表可能自相矛盾，甚至同一仓库内有**两套冲突的定义**。以「实际能跑通的那套配置」为准，不要凭文档拼凑。
- 定义了但代码里从未使用的宏（比如某个 `TFT_BL`）往往未经硬件验证，照抄可能出错。
- 某些引脚在特定配置下被外设占用（如 ESP32-C3 的 GPIO12/13 是内部 flash 的 SPIHD/SPIWP）。**flash 跑 DIO 模式时它们空闲可用，改 QIO 就会冲突** —— 用之前先确认 flash 模式。同理，驱动这类引脚前必须确认它真的没被占用。
