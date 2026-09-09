# 简历版式参考（蒸馏用）

本目录存放**结构/版式**参考材料，供写入 `backend/resume_mvp/style_guides.py` 时蒸馏原则。

## 使用约定

- 只学习：章节顺序、标题行信息密度、联系方式排版、STAR 要点写法。
- 禁止：把参考稿中的姓名、学校、公司、项目、数字或虚构情节写入用户简历或 AI `after` 正文。
- 禁止：把整份 PDF 原文贴进 prompt；应提炼成 `principles` / `anti_patterns`。

## 文件

| 文件 | 说明 |
|------|------|
| `fang-hongjian-layout-star.pdf` | 经典中文单栏版式示意（戏仿《围城》人物，正文不可用）+ 文末 STAR 写作提示 |

**产品落地：** Word/预览模板 ID `classic-cn`（界面名「经典中文单栏」）按该 PDF 的页眉居中、章节下划线、日期右对齐实现。  
蒸馏结果同时写入风格指南：`layout-density-skills`、`star-bullet-craft`。
