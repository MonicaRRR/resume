"""优秀简历「写法范式」——只学结构与句式，不抄别人经历正文。

如何扩充本目录（合法、可审计）：
1. 自己或同事同意脱敏后的投递稿：删姓名/公司/项目专名，只保留结构笔记。
2. 高校就业指导、大厂校招公开讲座、开源 career guide 中的「写法原则」
   （提炼成条目，不要整段粘贴范文正文）。
3. 招聘方公开的「简历筛选标准」博文：转成 anti_patterns / 优先规则。
4. 禁止：爬取求职平台私密简历、整份抄袭网红模板正文、把他人项目当素材库。

每条范式进 prompt 时会被明确约束：只能润色用户已有事实，不得引入范式中的公司/项目/数字。
"""

from __future__ import annotations

from typing import Any

from resume_mvp.domain import ApplicationType, JobAnalysis


StyleGuide = dict[str, Any]


STYLE_GUIDES: list[StyleGuide] = [
    {
        "id": "campus-one-pager",
        "title": "校招/实习一页密度",
        "tags": ["campus", "internship", "one-page"],
        "section_priority": ["教育经历", "专业技能", "实习工作经历", "项目经历", "个人概述"],
        "principles": [
            "信息密度优先：删空话与重复，保留可验证结果",
            "默认顺序：教育 → 专业技能 → 实习工作经历 → 项目；再按与 JD 相关度微调，弱相关后移或建议移出",
            "技能用岗位关键词对齐，避免长串无关技术栈",
            "概述最多 2 句，服务岗位匹配，不写人生感想",
            "无实习时把课程/个人项目写成可核对的「准经历」，而不是空技能列表",
            "避免一行只有几个字：过短要点合并，技能按类写成一行，别留大片空白",
            "项目通常保留 2–3 个最相关项并按 JD 改写要点；勿为压页删到只剩空壳",
        ],
        "bullet_patterns": [
            "用什么方法完成了什么，带来可核对的结果（延迟/准确率/规模/周期）",
            "先职责边界，再关键动作，最后结果；一句一事",
        ],
        "anti_patterns": [
            "堆砌课程名而无成果",
            "「负责参与了解熟悉」等无法验证的动词",
            "把社团/兴趣写成与 JD 无关的长段落",
            "高中经历占大量版面",
            "一行只写两三个字或单个词，版面显得空疏",
        ],
        "sources_note": "公开实习简历写作指南中的一页与项目优先原则（蒸馏，非原文）",
    },
    {
        "id": "experienced-impact",
        "title": "社招成果导向",
        "tags": ["experienced", "impact"],
        "section_priority": ["个人概述", "工作经历", "项目经历", "专业技能", "教育经历"],
        "principles": [
            "工作经历按相关度与近因排序；教育可压缩到一行",
            "每条经历突出业务影响与技术决策，而非日常琐事清单",
            "允许自然分页，但仍应去掉与 JD 弱相关的陈旧经历",
            "概述用 3 句内讲清领域、能力边界与代表成果",
        ],
        "bullet_patterns": [
            "问题/目标 → 方案与取舍 → 可量化结果与影响范围",
            "强调 ownership：独立负责 / 主导 / 推动跨团队，而非「参与」",
        ],
        "anti_patterns": [
            "只写技术栈名词、不写解决了什么问题",
            "把职责描述复制成 JD 关键词堆砌",
            "罗列十年前且与岗位无关的细节",
        ],
    },
    {
        "id": "layout-density-skills",
        "title": "版面密度与技能分行",
        "tags": ["general", "layout", "campus", "internship", "experienced"],
        "section_priority": ["教育经历", "专业技能", "实习工作经历", "项目经历"],
        "principles": [
            "经典单栏骨架：页眉姓名 + 紧凑联系方式 → 教育 → 专业技能 → 实习/工作 → 项目；自定义章节仅在有实质内容时保留",
            "条目标题行写满：左「机构/项目 · 角色/专业」，右对齐起止时间，避免标题行空一半",
            "章节标题只出现一次：已有「专业技能」标题时，条目不要再前缀「专业技能：」",
            "技能按 2–5 条分行写；每条尽量「类别：技术栈/场景」，占满半行以上",
            "不要输出空的「技能」分组；没有内容的条目直接删除",
            "过短 bullet（≤8 字）应合并到相邻要点，避免一行只剩两三个字",
            "STAR 写进经历要点，不要在简历正文末尾另开「写作注意事项」说明段",
        ],
        "bullet_patterns": [
            "后端：Python、FastAPI、PostgreSQL（接口与数据访问）",
            "工具：Git、Linux、Docker（协作与部署）",
            "机构名，角色 · 专业/方向　　　　YYYY.MM - YYYY.MM",
        ],
        "anti_patterns": [
            "专业技能标题下再写「专业技能：…」或一串空「技能：」",
            "三个技能挤成一行顿号列表却没有分行",
            "单独一行只写「Python」或「负责开发」",
            "把 STAR 定义整段贴进简历当正文",
            "首轮只改一两处点缀，其余章节仍是素材库原样",
        ],
        "sources_note": "docs/resume-templates/fang-hongjian-layout-star.pdf 版式蒸馏（仅结构；戏仿正文禁用）+ 公开校招排版原则",
    },
    {
        "id": "star-bullet-craft",
        "title": "STAR 要点句式",
        "tags": ["general", "writing", "star", "campus", "internship", "experienced"],
        "section_priority": [],
        "principles": [
            "Situation 只保留必要背景与约束，不写故事开场白",
            "Task 写清目标与衡量标准，避免「完成领导交办」",
            "Action 写决策与取舍，而不只列工具名",
            "Result 优先可核对指标；没有数字就写范围/对象/周期，绝不补造",
            "一条 bullet 尽量覆盖 S/T/A/R 中的关键两三项，不要拆成四句小作文",
        ],
        "bullet_patterns": [
            "在…约束下，为解决…，采用…（相对…的取舍），使…达到…",
            "定位问题 → 对比方案 → 落地与兜底 → 结果",
        ],
        "anti_patterns": [
            "流水账：需求分析、编码、测试、上线",
            "只有 Result 形容词（「显著提升」）而无依据",
            "把 STAR 写成四句小作文挤占一页版面",
            "简历末尾再抄一遍 STAR 名词解释",
        ],
        "sources_note": "docs/resume-templates/fang-hongjian-layout-star.pdf 文末 STAR 提示蒸馏 + 公开项目经历写法原则",
    },
    {
        "id": "project-conflict-decision",
        "title": "项目经历：冲突与决策",
        "tags": ["campus", "internship", "project", "backend", "frontend"],
        "section_priority": ["项目经历"],
        "principles": [
            "用场景量级或约束交代项目难度，而不是空喊「大型系统」",
            "写出技术/业务冲突点，再写你为何选该方案",
            "结果尽量给对比（优化前/后、周期、影响对象）；仅使用用户事实中已有数字",
        ],
        "bullet_patterns": [
            "冲突锚点：在 A 与 B 之间，因 C 约束选择 D",
            "复盘一句即可：若事实中有「踩坑→纠正」，可保留为可信度加分",
        ],
        "anti_patterns": [
            "技术词典式罗列框架",
            "只写成功不写约束，显得不可信",
            "从范文借来的 QPS/营收数字",
        ],
        "sources_note": "公开校招项目经历写法拆解中的结构公式（蒸馏，不含他人项目细节）",
    },
    {
        "id": "backend-engineering",
        "title": "后端工程表述",
        "tags": ["backend", "server", "api", "infra", "python", "java", "go"],
        "section_priority": ["工作/项目经历", "专业技能", "个人概述"],
        "principles": [
            "突出可用性、性能、数据一致性、可观测性与排障经验",
            "技能区分精通/熟悉，并与经历中的证据呼应",
            "接口、存储、异步、稳定性治理用具体场景支撑",
        ],
        "bullet_patterns": [
            "优化某链路：手段（缓存/批处理/索引/限流）+ 指标变化（P99/QPS/错误率）",
            "设计某能力：约束条件 + 关键决策 + 上线后效果",
        ],
        "anti_patterns": [
            "只写「使用 Redis/MySQL」而无场景与结果",
            "夸大「高并发」却无量级",
        ],
    },
    {
        "id": "frontend-product",
        "title": "前端/体验与产品协作",
        "tags": ["frontend", "web", "react", "vue", "产品", "设计"],
        "section_priority": ["项目经历", "工作经历", "专业技能"],
        "principles": [
            "同时写清交互体验与工程结果（性能、可维护、交付质量）",
            "体现与设计/后端的协作边界与推动方式",
        ],
        "bullet_patterns": [
            "复杂交互/状态：方案选择 + 对用户或转化的影响",
            "工程化：构建、组件化、质量门禁带来的效率或缺陷下降",
        ],
        "anti_patterns": [
            "只列组件库名称",
            "把视觉稿还原当成唯一成果",
        ],
    },
    {
        "id": "data-ml-writing",
        "title": "数据/算法表述",
        "tags": ["data", "ml", "算法", "机器学习", "分析", "sql", "推荐"],
        "section_priority": ["项目经历", "专业技能", "个人概述"],
        "principles": [
            "写清问题定义、数据与特征、方法选型理由、评测指标与业务影响",
            "离线指标与线上影响分开写，避免混为一谈",
        ],
        "bullet_patterns": [
            "数据/样本约束 → 方法与对照 → 指标（仅用户已有）→ 业务或工程落地",
        ],
        "anti_patterns": [
            "只写模型名称清单",
            "把公开论文指标写成自己的结果",
        ],
    },
    {
        "id": "jd-keyword-alignment",
        "title": "JD 关键词对齐（不堆砌）",
        "tags": ["general", "writing", "ats", "campus", "internship", "experienced"],
        "section_priority": [],
        "principles": [
            "从 JD 抽取真实匹配的技能与职责词，自然嵌入已有经历表述",
            "关键词必须能在用户事实中找到对应动作或对象",
            "宁可少写匹配词，也不要用用户没做过的词去「过筛」",
        ],
        "bullet_patterns": [
            "在原要点中替换更贴 JD 的动词/对象，保持事实不变",
        ],
        "anti_patterns": [
            "把 JD 原文整段粘贴进简历",
            "技能栏堆满 JD 词但经历中无证据",
        ],
    },
    {
        "id": "evidence-first-writing",
        "title": "证据优先措辞（通用）",
        "tags": ["general", "writing"],
        "section_priority": [],
        "principles": [
            "每个强表述都应能在用户事实中找到依据",
            "不确定的数字宁可不写，也不要补造",
            "润色是换说法与取舍，不是换经历",
        ],
        "bullet_patterns": [
            "保留用户原有主体与对象，只收紧动词与结果表达",
        ],
        "anti_patterns": [
            "引入范文中的公司、项目名或指标",
            "把「可能」「大概」写成确定成果",
        ],
    },
]


def select_style_guides(
    analysis: JobAnalysis,
    application_type: ApplicationType,
    *,
    limit: int = 4,
) -> list[StyleGuide]:
    """Pick a few relevant style notes for the current JD + application type."""
    haystack = " ".join(
        [
            analysis.role_title,
            analysis.seniority,
            " ".join(analysis.keywords),
            " ".join(analysis.responsibilities),
            " ".join(item.text for item in analysis.requirements),
            " ".join(analysis.bonus_skills),
        ]
    ).lower()

    generic_tags = {
        "campus", "internship", "experienced", "one-page", "impact",
        "general", "writing", "star", "ats", "project",
    }
    reserved_ids = {"evidence-first-writing", "layout-density-skills"}

    scored: list[tuple[int, StyleGuide]] = []
    for guide in STYLE_GUIDES:
        if guide["id"] in reserved_ids:
            continue
        score = 0
        tags = [str(tag).lower() for tag in guide.get("tags", [])]
        if application_type in tags:
            score += 5
        if application_type in {"campus", "internship"} and "one-page" in tags:
            score += 3
        if application_type == "experienced" and "impact" in tags:
            score += 3
        domain_hits = 0
        for tag in tags:
            if tag in generic_tags:
                continue
            if tag and tag in haystack:
                domain_hits += 1
                score += 4
        if "star" in tags or "writing" in tags:
            score += 1
        if domain_hits == 0 and set(tags).issubset(generic_tags | {application_type, "one-page", "impact", "layout"}):
            # Keep generic writing guides only as fillers after domain matches.
            score += 0
        if score > 0:
            scored.append((score, guide))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    reserved_slots = min(2, max(limit - 1, 1))
    selected = [guide for _, guide in scored[: max(limit - reserved_slots, 1)]]
    layout = next((guide for guide in STYLE_GUIDES if guide["id"] == "layout-density-skills"), None)
    if layout:
        selected.append(layout)
    evidence = next((guide for guide in STYLE_GUIDES if guide["id"] == "evidence-first-writing"), None)
    if evidence:
        selected.append(evidence)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[StyleGuide] = []
    for guide in selected:
        if guide["id"] in seen:
            continue
        seen.add(guide["id"])
        ordered.append(guide)
    return ordered[:limit]


def style_guides_for_prompt(guides: list[StyleGuide]) -> list[dict[str, Any]]:
    """Compact payload for model prompts."""
    return [
        {
            "id": guide["id"],
            "title": guide["title"],
            "section_priority": guide.get("section_priority") or [],
            "principles": guide.get("principles") or [],
            "bullet_patterns": guide.get("bullet_patterns") or [],
            "anti_patterns": guide.get("anti_patterns") or [],
        }
        for guide in guides
    ]
