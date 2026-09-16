# Life Companion Visual Refinement Design Contract

## 技术与交付

- 技术：现有单文件 HTML + CSS + Vanilla JavaScript
- 交付：纯静态、离线可打开
- 修改范围：Today、Chat、Memory、Growth 与 Me 原型面板
- 不变项：功能、信息架构、页面路径、Memory 产品逻辑

## 视觉方向

- Style tier：minimal-light
- Aesthetic：hand-drawn daily paper
- Tone：simple / honest / quiet / playful / personal / low-tech
- 视觉命题：像一张每天都会重新打开的手写生活纸

## Design Tokens

- Canvas：`#C7E8F8`
- Surface：`#FFFFFF`
- Text：`#17191B`
- Muted：`#526774`
- Rule：`#9FC4D7`
- Accent：`#416F87`
- Accent strong：`#2E596F`
- Accent soft：`#EAF7FD`
- Memory surface：`#CDEFE2`
- Memory text：`#173129`
- Growth surface：`#0D5145`
- Growth text：`#F1FBF6`
- Me surface：`#A9DDF6`
- Me text：`#142832`
- Display font：`HanziPen SC / HanziPen TC / Bradley Hand / PingFang SC`
- Body font：`HanziPen SC / HanziPen TC / Bradley Hand / PingFang SC`
- 禁止字体：方正楷体、系统楷体、微软雅黑
- Display：28–30px / 1.22
- Section：22px / 1.35
- Body：16px / 1.65
- Metadata：13px / 1.5
- Radius：普通容器最大 8px
- Shadow：普通页面无阴影
- Spacing：4 / 8 / 12 / 16 / 24 / 32 / 48 / 64

## Component Rules

- Today：日期、问候、纸面输入、连续记录、轻时间标记
- Chat：日期、角色小标记、连续正文、Memory 脚注
- Input：无 SaaS 外框，使用底部细线与自然高度变化
- Primary action：细线椭圆中的单色箭头，不使用实心大型按钮
- Memory source：默认折叠的 footnote，展开后显示来源、日期、原文和类型
- Bottom navigation：保留四项，仅用文字与细线表达当前项
- Atmosphere：Today 奶蓝、Chat 白色、Memory 薄荷绿、Growth 深森林绿、Me 天空蓝；所有页面使用平涂纸张、居中原创线稿和大面积空白
- Typography：中文使用轻字重手写体、自然字距和短行宽；所有信息直接落在整屏纸张上
- Metadata：日期、时间、类型和状态分别换行或独立对齐，不使用中点分隔字段
- 禁止：Card、Bubble、Badge、Pill、Avatar、Shadow 成为主要语言

## Interaction Thesis

1. 输入区聚焦时轻微展开，底线加深。
2. 发送动作使用轻量箭头，提交后内容进入连续记录或对话。
3. Memory 来源通过脚注展开，不在首屏展示数据库式元数据。
4. Memory 来源在原位置展开；Growth 依据在原位置展开；Me 数字入口切换到 Today 或 Memory。
5. 页面切换使用 220ms 淡入与 6px 轻位移，线稿使用 560ms 描边动画。
6. 展开区域使用 220ms 高度变化和 180ms 透明度变化。
7. 系统开启减少动态效果后，取消描边、位移和缩放。

## Mock Schema

- Journal entry：`id / time / paragraphs[]`
- Conversation item：`id / role / time / paragraphs[] / source?`
- Memory source：`label / date / excerpt / type`
