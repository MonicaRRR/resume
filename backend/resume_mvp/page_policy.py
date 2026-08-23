from __future__ import annotations

from pydantic import BaseModel

from resume_mvp.domain import ApplicationType, ResumeDocument


class PagePolicyResult(BaseModel):
    compact: bool
    max_pages: int | None
    estimated_units: int
    capacity_units: int | None
    overflow: bool
    largest_sections: list[str]


_ONE_PAGE_CAPACITY = 1_700


def evaluate_page_policy(
    resume: ResumeDocument,
    application_type: ApplicationType,
) -> PagePolicyResult:
    section_units = _measure_sections(resume)
    estimated = sum(section_units.values())
    ranked = [
        name
        for name, units in sorted(section_units.items(), key=lambda item: item[1], reverse=True)
        if units > 0
    ]
    one_page = application_type in {"campus", "internship"}
    return PagePolicyResult(
        compact=one_page,
        max_pages=1 if one_page else None,
        estimated_units=estimated,
        capacity_units=_ONE_PAGE_CAPACITY if one_page else None,
        overflow=one_page and estimated > _ONE_PAGE_CAPACITY,
        largest_sections=ranked,
    )


def _measure_sections(resume: ResumeDocument) -> dict[str, int]:
    basics = 90 + sum(
        len(value)
        for value in [
            resume.basics.name,
            resume.basics.email,
            resume.basics.phone,
            resume.basics.location,
            resume.basics.target_role.value,
            resume.basics.summary.value,
        ]
    )
    work = sum(
        70
        + len(item.company)
        + len(item.title)
        + sum(len(bullet.value) + 20 for bullet in item.bullets)
        for item in resume.work_experience
    )
    projects = sum(
        65
        + len(item.name)
        + len(item.role)
        + sum(len(bullet.value) + 20 for bullet in item.bullets)
        for item in resume.projects
    )
    education = sum(
        55
        + len(item.institution)
        + len(item.degree)
        + len(item.field)
        + sum(len(value.value) + 15 for value in item.highlights)
        for item in resume.education
    )
    skills = sum(35 + len(group.name) + sum(len(item.value) + 5 for item in group.items) for group in resume.skills)
    custom = sum(
        35 + len(section.title) + sum(len(item.value) + 15 for item in section.items)
        for section in resume.custom_sections
    )
    extras = sum(35 + len(item.name) + len(item.detail.value) for item in [*resume.certificates, *resume.awards])
    return {
        "basics": basics,
        "work_experience": work,
        "projects": projects,
        "education": education,
        "skills": skills,
        "custom_sections": custom,
        "extras": extras,
    }
