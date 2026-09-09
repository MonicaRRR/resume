from resume_mvp.domain import JobAnalysis, JobRequirement
from resume_mvp.style_guides import select_style_guides


def test_campus_backend_picks_one_pager_and_backend_guides() -> None:
    analysis = JobAnalysis(
        role_title="后端开发实习生",
        keywords=["Python", "API"],
        requirements=[
            JobRequirement(text="熟悉 Python", evidence_quote="熟悉 Python", weight=2),
        ],
    )
    guides = select_style_guides(analysis, "campus", limit=4)
    ids = [guide["id"] for guide in guides]
    assert "campus-one-pager" in ids
    assert "backend-engineering" in ids
    assert "layout-density-skills" in ids
    assert "evidence-first-writing" in ids


def test_experienced_role_prefers_impact_guide() -> None:
    analysis = JobAnalysis(role_title="高级产品经理", keywords=["产品", "增长"])
    guides = select_style_guides(analysis, "experienced")
    ids = [guide["id"] for guide in guides]
    assert "experienced-impact" in ids
    assert "layout-density-skills" in ids
    assert "campus-one-pager" not in ids
    assert "evidence-first-writing" in ids


def test_star_guide_available_for_general_roles() -> None:
    analysis = JobAnalysis(role_title="软件工程师", keywords=["工程"])
    guides = select_style_guides(analysis, "experienced", limit=4)
    ids = [guide["id"] for guide in guides]
    assert "experienced-impact" in ids
    assert "layout-density-skills" in ids
    assert "evidence-first-writing" in ids
