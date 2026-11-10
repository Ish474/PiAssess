"""Dashboard: summary statistics, recent exams, activity feed, first-run checklist."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func

from ..database import get_db
from ..models import AuditLog, Document, Examination, Klass, OMRScan, QuestionPaper, Student, Subject
from ..schemas import ActivityOut, DashboardOut, RecentExamOut
from ..security import get_current_user
from ..services.common import get_setting

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(cu=Depends(get_current_user), db=Depends(get_db)):
    total_students = db.query(Student).filter(Student.status == "active").count()
    total_exams = db.query(Examination).count()
    total_subjects = db.query(Subject).count()

    exams = (
        db.query(Examination)
        .options()  # keep simple; class joined below via lookup
        .order_by(Examination.created_at.desc())
        .limit(8)
        .all()
    )
    class_names = {k.id: k.name for k in db.query(Klass).all()}
    # an exam has results to view once at least one sheet has been scored
    scored_exam_ids = {s for (s,) in db.query(OMRScan.exam_id).filter(OMRScan.score.isnot(None)).all()}
    recent = [
        RecentExamOut(
            id=e.id,
            name=e.name,
            class_name=class_names.get(e.class_id, "—"),
            exam_date=e.exam_date,
            student_count=db.query(Student).filter(Student.class_id == e.class_id).count(),
            status=e.status,
            results_available=e.id in scored_exam_ids,
        )
        for e in exams
    ]

    activity = [
        ActivityOut.model_validate(a)
        for a in db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(10).all()
    ]

    # real average performance: mean score percentage across all scored sheets
    scored = db.query(OMRScan.score, OMRScan.max_score).filter(OMRScan.score.isnot(None)).all()
    pcts = [s / m * 100 for s, m in scored if m]
    avg_performance = round(sum(pcts) / len(pcts), 1) if pcts else None

    checklist = {
        "school_profile": bool(get_setting(db, "school_name")),
        "classes_created": db.query(Klass).count() > 0,
        "subjects_added": total_subjects > 0,
        "students_added": total_students > 0,
        "exam_created": total_exams > 0,
        "question_paper": db.query(QuestionPaper).count() > 0,
        "omr_evaluated": len(scored) > 0,
        "results_published": len(scored) > 0,
    }
    return DashboardOut(
        total_students=total_students,
        total_examinations=total_exams,
        total_subjects=total_subjects,
        average_performance=avg_performance,
        recent_exams=recent,
        activity=activity,
        checklist=checklist,
    )


@router.get("/notifications")
def notifications(cu=Depends(get_current_user), db=Depends(get_db)):
    """The 15 latest audit-log events for the bell menu."""
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(15)
        .all()
    )
    return {"items": [
        {
            "id": a.id,
            "username": a.username,
            "action": a.action,
            "entity": a.entity,
            "details": a.details,
            "created_at": a.created_at.isoformat(),
        }
        for a in logs
    ]}
