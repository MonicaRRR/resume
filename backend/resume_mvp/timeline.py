from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from resume_mvp.domain import JobProject, PracticeSession, ResumeVersion
from resume_mvp.optimization_models import OptimizationRun


TimelineEventKind = Literal[
    "resume_version",
    "match_report",
    "optimization_run",
    "practice_session",
]


class TimelineEvent(BaseModel):
    """A read-only projection of activity in one job application."""

    id: str
    kind: TimelineEventKind
    source_id: str
    project_id: str
    label: str
    detail: str = ""
    status: str = ""
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


_OPTIMIZATION_STATUS_LABELS = {
    "queued": "排队中",
    "analyzing": "分析中",
    "waiting_for_user": "等待补充",
    "optimizing": "优化中",
    "rendering": "渲染中",
    "reviewing": "审核中",
    "ready_for_user": "待确认",
    "failed": "失败",
    "cancelled": "已取消",
}


def project_timeline(
    project: JobProject,
    versions: list[ResumeVersion],
    optimization_runs: list[OptimizationRun],
    practice_sessions: list[PracticeSession],
) -> list[TimelineEvent]:
    """Build a deterministic chronological activity projection without writes."""
    events: list[TimelineEvent] = []
    for version in versions:
        events.append(
            TimelineEvent(
                id=f"resume_version:{version.id}",
                kind="resume_version",
                source_id=version.id,
                project_id=version.project_id,
                label="保存简历版本",
                detail=version.reason,
                timestamp=version.created_at,
                metadata={"active": version.id == project.active_resume_version_id},
            )
        )
    if project.match_report is not None:
        events.append(
            TimelineEvent(
                id=f"match_report:{project.id}",
                kind="match_report",
                source_id=project.id,
                project_id=project.id,
                label="完成岗位匹配",
                detail=f"匹配度 {round(project.match_report.coverage * 100)}%",
                status="completed",
                timestamp=project.updated_at,
                metadata={"coverage": project.match_report.coverage},
            )
        )
    for run in optimization_runs:
        status_label = _OPTIMIZATION_STATUS_LABELS.get(run.status, run.status)
        events.append(
            TimelineEvent(
                id=f"optimization_run:{run.id}",
                kind="optimization_run",
                source_id=run.id,
                project_id=run.project_id,
                label="简历优化",
                detail=status_label,
                status=run.status,
                timestamp=run.updated_at,
                metadata={"mode": run.mode, "template_id": run.template_id},
            )
        )
    for session in practice_sessions:
        kind_label = "模拟面试" if session.kind == "interview" else "笔试训练"
        status_label = "进行中" if session.status == "active" else "已完成"
        events.append(
            TimelineEvent(
                id=f"practice_session:{session.id}",
                kind="practice_session",
                source_id=session.id,
                project_id=session.project_id,
                label=kind_label,
                detail=f"{status_label}，已回答 {len(session.turns)} 题",
                status=session.status,
                timestamp=session.updated_at,
                metadata={"kind": session.kind, "turn_count": len(session.turns)},
            )
        )
    # Timestamp descending is useful for an activity feed. The ID tie-breaker keeps
    # repeated reads stable even when SQLite timestamps have the same precision.
    def sort_key(event: TimelineEvent) -> tuple[float, str]:
        timestamp = event.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.timestamp(), event.id

    return sorted(events, key=sort_key, reverse=True)
