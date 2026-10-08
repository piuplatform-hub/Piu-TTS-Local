"""
Project Management Service
Implements CRUD, optimistic concurrency control, character configuration,
and script segment synchronization with partial invalidation.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import List, Optional, Dict, Any, Tuple
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.server.src.models.project import ProjectRecord
from apps.server.src.models.character import CharacterRecord
from apps.server.src.models.segment import ScriptSegmentRecord, SegmentRevisionRecord
from apps.server.src.models.export import ProjectExportRecord
from apps.server.src.models.job import JobRecord
from apps.server.src.models.user import User
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.job_service import JobService
from apps.server.src.services.text_segmenter import TextSegmenter
from apps.server.src.schemas.project import (
    ProjectCreate, ProjectUpdate, CharacterCreate, CharacterUpdate,
    SegmentCreate, SegmentUpdate, SegmentBulkSyncRequest, SegmentSyncItem
)


def compute_segment_hash(text: str, engine_id: str, voice_id: str, parameters: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash representing the segment content and voice parameters."""
    norm_text = text.strip()
    norm_params = json.dumps(parameters or {}, sort_keys=True)
    raw = f"{norm_text}|{engine_id}|{voice_id}|{norm_params}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProjectService:
    @staticmethod
    async def get_project_record(session: AsyncSession, project_id: str, user_id: str) -> ProjectRecord:
        stmt = (
            select(ProjectRecord)
            .where(ProjectRecord.id == project_id)
            .options(
                selectinload(ProjectRecord.characters),
                selectinload(ProjectRecord.segments).selectinload(ScriptSegmentRecord.revisions),
                selectinload(ProjectRecord.exports),
            )
        )
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="PROJECT_NOT_FOUND")
        if project.user_id != user_id:
            raise HTTPException(status_code=403, detail="FORBIDDEN_PROJECT_ACCESS")
        return project

    @classmethod
    async def create_project(cls, session: AsyncSession, user_id: str, req: ProjectCreate) -> ProjectRecord:
        project = ProjectRecord(
            user_id=user_id,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            project_type=req.project_type,
            settings=req.settings,
            version=1,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return await cls.get_project_record(session, project.id, user_id)

    @classmethod
    async def list_projects(cls, session: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
        stmt = (
            select(ProjectRecord)
            .where(ProjectRecord.user_id == user_id)
            .options(
                selectinload(ProjectRecord.segments),
            )
            .order_by(ProjectRecord.updated_at.desc())
        )
        res = await session.execute(stmt)
        projects = res.scalars().all()

        summaries = []
        for p in projects:
            seg_count = len(p.segments)
            completed_count = sum(1 for s in p.segments if s.status == "completed")
            summaries.append({
                "id": p.id,
                "user_id": p.user_id,
                "title": p.title,
                "description": p.description,
                "project_type": p.project_type,
                "settings": p.settings,
                "version": p.version,
                "segment_count": seg_count,
                "completed_segment_count": completed_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            })
        return summaries

    @classmethod
    async def update_project(cls, session: AsyncSession, user_id: str, project_id: str, req: ProjectUpdate) -> ProjectRecord:
        project = await cls.get_project_record(session, project_id, user_id)

        # Optimistic concurrency check
        if req.expected_version is not None and req.expected_version != project.version:
            raise HTTPException(
                status_code=409,
                detail=f"VERSION_CONFLICT: Project has been modified by another action. Current version is {project.version}, expected {req.expected_version}."
            )

        if req.title is not None:
            project.title = req.title.strip()
        if req.description is not None:
            project.description = req.description.strip() if req.description else None
        if req.settings is not None:
            merged = project.settings
            merged.update(req.settings)
            project.settings = merged

        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return await cls.get_project_record(session, project.id, user_id)

    @classmethod
    async def delete_project(cls, session: AsyncSession, user_id: str, project_id: str) -> None:
        project = await cls.get_project_record(session, project_id, user_id)
        await session.delete(project)
        await session.commit()

    # -------------------------------------------------------------
    # CHARACTER MANAGEMENT
    # -------------------------------------------------------------
    @classmethod
    async def create_character(cls, session: AsyncSession, user_id: str, project_id: str, req: CharacterCreate) -> CharacterRecord:
        project = await cls.get_project_record(session, project_id, user_id)
        
        char = CharacterRecord(
            project_id=project.id,
            name=req.name.strip(),
            avatar_color=req.avatar_color,
            engine_id=req.engine_id,
            voice_id=req.voice_id,
            language=req.language,
            parameters=req.parameters,
            sort_order=req.sort_order,
        )
        session.add(char)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(char)
        return char

    @classmethod
    async def update_character(cls, session: AsyncSession, user_id: str, project_id: str, char_id: str, req: CharacterUpdate) -> CharacterRecord:
        project = await cls.get_project_record(session, project_id, user_id)
        
        stmt = select(CharacterRecord).where(CharacterRecord.id == char_id, CharacterRecord.project_id == project_id)
        res = await session.execute(stmt)
        char = res.scalar_one_or_none()
        if not char:
            raise HTTPException(status_code=404, detail="CHARACTER_NOT_FOUND")

        if req.name is not None:
            char.name = req.name.strip()
        if req.avatar_color is not None:
            char.avatar_color = req.avatar_color
        if req.engine_id is not None:
            char.engine_id = req.engine_id
        if req.voice_id is not None:
            char.voice_id = req.voice_id
        if req.language is not None:
            char.language = req.language
        if req.parameters is not None:
            char.parameters = req.parameters
        if req.sort_order is not None:
            char.sort_order = req.sort_order

        char.updated_at = datetime.now(timezone.utc)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(char)
        return char

    @classmethod
    async def delete_character(cls, session: AsyncSession, user_id: str, project_id: str, char_id: str) -> None:
        project = await cls.get_project_record(session, project_id, user_id)
        stmt = select(CharacterRecord).where(CharacterRecord.id == char_id, CharacterRecord.project_id == project_id)
        res = await session.execute(stmt)
        char = res.scalar_one_or_none()
        if not char:
            raise HTTPException(status_code=404, detail="CHARACTER_NOT_FOUND")

        await session.delete(char)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

    # -------------------------------------------------------------
    # SCRIPT SEGMENT MANAGEMENT & AUTOSAVE
    # -------------------------------------------------------------
    @classmethod
    async def add_segment(cls, session: AsyncSession, user_id: str, project_id: str, req: SegmentCreate) -> ScriptSegmentRecord:
        project = await cls.get_project_record(session, project_id, user_id)

        text_hash = compute_segment_hash(req.text, req.engine_id, req.voice_id, req.parameters)
        seg = ScriptSegmentRecord(
            project_id=project.id,
            character_id=req.character_id,
            sequence_order=req.sequence_order,
            text=req.text.strip(),
            language=req.language,
            engine_id=req.engine_id,
            voice_id=req.voice_id,
            parameters=req.parameters,
            pause_after_ms=req.pause_after_ms,
            status="draft",
            text_hash=text_hash,
            version=1,
        )
        session.add(seg)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(seg)
        return seg

    @classmethod
    async def update_segment(cls, session: AsyncSession, user_id: str, project_id: str, seg_id: str, req: SegmentUpdate) -> ScriptSegmentRecord:
        project = await cls.get_project_record(session, project_id, user_id)

        stmt = select(ScriptSegmentRecord).where(ScriptSegmentRecord.id == seg_id, ScriptSegmentRecord.project_id == project_id).options(selectinload(ScriptSegmentRecord.revisions))
        res = await session.execute(stmt)
        seg = res.scalar_one_or_none()
        if not seg:
            raise HTTPException(status_code=404, detail="SEGMENT_NOT_FOUND")

        old_hash = seg.text_hash
        if req.character_id is not None:
            seg.character_id = req.character_id if req.character_id != "" else None
        if req.sequence_order is not None:
            seg.sequence_order = req.sequence_order
        if req.text is not None:
            seg.text = req.text.strip()
        if req.language is not None:
            seg.language = req.language
        if req.engine_id is not None:
            seg.engine_id = req.engine_id
        if req.voice_id is not None:
            seg.voice_id = req.voice_id
        if req.parameters is not None:
            seg.parameters = req.parameters
        if req.pause_after_ms is not None:
            seg.pause_after_ms = req.pause_after_ms

        new_hash = compute_segment_hash(seg.text, seg.engine_id, seg.voice_id, seg.parameters)
        seg.text_hash = new_hash

        # Partial Invalidation: If content changed on an already completed segment, mark it as stale
        if new_hash != old_hash:
            if seg.status == "completed":
                seg.status = "stale"
            elif seg.status not in ("queued", "rendering"):
                seg.status = "draft"

        seg.version += 1
        seg.updated_at = datetime.now(timezone.utc)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(seg)
        return seg

    @classmethod
    async def delete_segment(cls, session: AsyncSession, user_id: str, project_id: str, seg_id: str) -> None:
        project = await cls.get_project_record(session, project_id, user_id)
        stmt = select(ScriptSegmentRecord).where(ScriptSegmentRecord.id == seg_id, ScriptSegmentRecord.project_id == project_id)
        res = await session.execute(stmt)
        seg = res.scalar_one_or_none()
        if not seg:
            raise HTTPException(status_code=404, detail="SEGMENT_NOT_FOUND")

        await session.delete(seg)
        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @classmethod
    async def bulk_sync_segments(cls, session: AsyncSession, user_id: str, project_id: str, req: SegmentBulkSyncRequest) -> List[ScriptSegmentRecord]:
        project = await cls.get_project_record(session, project_id, user_id)

        # Optimistic Concurrency Control
        if req.expected_project_version != project.version:
            raise HTTPException(
                status_code=409,
                detail=f"VERSION_CONFLICT: Project has been modified by another action. Current version is {project.version}, expected {req.expected_project_version}."
            )

        existing_segments = {s.id: s for s in project.segments}
        keep_ids = set()

        for idx, item in enumerate(req.segments):
            text_hash = compute_segment_hash(item.text, item.engine_id, item.voice_id, item.parameters)
            
            if item.id and item.id in existing_segments:
                seg = existing_segments[item.id]
                old_hash = seg.text_hash
                seg.sequence_order = idx
                seg.character_id = item.character_id if item.character_id else None
                seg.text = item.text.strip()
                seg.language = item.language
                seg.engine_id = item.engine_id
                seg.voice_id = item.voice_id
                seg.parameters = item.parameters
                seg.pause_after_ms = item.pause_after_ms
                seg.text_hash = text_hash

                if new_hash := text_hash != old_hash:
                    if seg.status == "completed":
                        seg.status = "stale"
                    elif seg.status not in ("queued", "rendering"):
                        seg.status = "draft"

                seg.version += 1
                seg.updated_at = datetime.now(timezone.utc)
                keep_ids.add(seg.id)
            else:
                new_seg = ScriptSegmentRecord(
                    project_id=project.id,
                    character_id=item.character_id if item.character_id else None,
                    sequence_order=idx,
                    text=item.text.strip(),
                    language=item.language,
                    engine_id=item.engine_id,
                    voice_id=item.voice_id,
                    parameters=item.parameters,
                    pause_after_ms=item.pause_after_ms,
                    status="draft",
                    text_hash=text_hash,
                    version=1,
                )
                session.add(new_seg)

        # Delete removed segments
        for old_id, old_seg in existing_segments.items():
            if old_id not in keep_ids:
                await session.delete(old_seg)

        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # Query updated segments directly
        stmt_segs = (
            select(ScriptSegmentRecord)
            .where(ScriptSegmentRecord.project_id == project_id)
            .order_by(ScriptSegmentRecord.sequence_order)
        )
        res_segs = await session.execute(stmt_segs)
        return list(res_segs.scalars().all())

    # -------------------------------------------------------------
    # AUTO-SEGMENTATION
    # -------------------------------------------------------------
    @classmethod
    async def auto_segment_text(
        cls,
        session: AsyncSession,
        user_id: str,
        project_id: str,
        text: str,
        language: str = "vi",
        default_engine_id: str = "vieneu-tts",
        default_voice_id: str = "hai_dang",
        replace_existing: bool = True,
        max_chars: int = 220,
    ) -> List[ScriptSegmentRecord]:
        project = await cls.get_project_record(session, project_id, user_id)
        raw_chunks = TextSegmenter.segment_text(text, language=language, max_chars=max_chars)
        if not raw_chunks:
            raise HTTPException(status_code=400, detail="EMPTY_SEGMENT_RESULT: Văn bản không chứa nội dung hợp lệ để phân đoạn.")

        if replace_existing:
            # Delete old segments
            stmt_del = delete(ScriptSegmentRecord).where(ScriptSegmentRecord.project_id == project_id)
            await session.execute(stmt_del)
            start_seq = 0
        else:
            # Append after highest sequence_order
            stmt_max = select(func.max(ScriptSegmentRecord.sequence_order)).where(ScriptSegmentRecord.project_id == project_id)
            res_max = await session.execute(stmt_max)
            curr_max = res_max.scalar()
            start_seq = (curr_max + 1) if curr_max is not None else 0

        created_segments = []
        for idx, chunk in enumerate(raw_chunks):
            seq = start_seq + idx
            chunk_hash = compute_segment_hash(chunk, default_engine_id, default_voice_id, {})
            seg = ScriptSegmentRecord(
                project_id=project.id,
                sequence_order=seq,
                text=chunk,
                language=language,
                engine_id=default_engine_id,
                voice_id=default_voice_id,
                parameters={},
                pause_after_ms=300,
                status="draft",
                text_hash=chunk_hash,
                version=1,
            )
            session.add(seg)
            created_segments.append(seg)

        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # Query all current segments
        stmt_segs = (
            select(ScriptSegmentRecord)
            .where(ScriptSegmentRecord.project_id == project_id)
            .order_by(ScriptSegmentRecord.sequence_order)
        )
        res_segs = await session.execute(stmt_segs)
        return list(res_segs.scalars().all())

    # -------------------------------------------------------------
    # BATCH & PARTIAL RENDERING
    # -------------------------------------------------------------
    @classmethod
    async def render_segment(
        cls,
        session: AsyncSession,
        current_user: User,
        project_id: str,
        seg_id: str,
    ) -> Tuple[ScriptSegmentRecord, JobRecord]:
        project = await cls.get_project_record(session, project_id, current_user.id)
        stmt = select(ScriptSegmentRecord).where(ScriptSegmentRecord.id == seg_id, ScriptSegmentRecord.project_id == project_id)
        res = await session.execute(stmt)
        seg = res.scalar_one_or_none()
        if not seg:
            raise HTTPException(status_code=404, detail="SEGMENT_NOT_FOUND")

        # Submit speech synthesis job via JobService
        job_req = TTSJobSubmitRequest(
            engine_id=seg.engine_id,
            text=seg.text,
            language=seg.language,
            voice_id=seg.voice_id,
            parameters=seg.parameters,
            priority=1,
        )
        job = await JobService.submit_speech_job(session, job_req, current_user)

        seg.last_job_id = job.id
        seg.status = "queued"
        seg.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(seg)
        return seg, job

    @classmethod
    async def render_batch(
        cls,
        session: AsyncSession,
        current_user: User,
        project_id: str,
        segment_ids: Optional[List[str]] = None,
    ) -> List[Tuple[ScriptSegmentRecord, JobRecord]]:
        project = await cls.get_project_record(session, project_id, current_user.id)
        
        if segment_ids:
            stmt = (
                select(ScriptSegmentRecord)
                .where(ScriptSegmentRecord.project_id == project_id, ScriptSegmentRecord.id.in_(segment_ids))
                .order_by(ScriptSegmentRecord.sequence_order)
            )
        else:
            # Render all draft, stale or failed segments
            stmt = (
                select(ScriptSegmentRecord)
                .where(
                    ScriptSegmentRecord.project_id == project_id,
                    ScriptSegmentRecord.status.in_(["draft", "stale", "failed"])
                )
                .order_by(ScriptSegmentRecord.sequence_order)
            )

        res = await session.execute(stmt)
        targets = res.scalars().all()
        if not targets:
            return []

        rendered = []
        for seg in targets:
            job_req = TTSJobSubmitRequest(
                engine_id=seg.engine_id,
                text=seg.text,
                language=seg.language,
                voice_id=seg.voice_id,
                parameters=seg.parameters,
                priority=1,
            )
            job = await JobService.submit_speech_job(session, job_req, current_user)
            seg.last_job_id = job.id
            seg.status = "queued"
            seg.updated_at = datetime.now(timezone.utc)
            rendered.append((seg, job))

        await session.commit()
        return rendered

    @classmethod
    async def reconcile_project_segments(
        cls,
        session: AsyncSession,
        current_user: User,
        project_id: str,
    ) -> ProjectRecord:
        """
        Reconciles in-flight segment jobs with actual JobRecord states.
        Preserves previous audio in SegmentRevisionRecord on new completion.
        """
        project = await cls.get_project_record(session, project_id, current_user.id)
        changed = False

        for seg in project.segments:
            if not seg.last_job_id:
                continue

            # Check job state
            stmt_j = select(JobRecord).where(JobRecord.id == seg.last_job_id)
            res_j = await session.execute(stmt_j)
            job = res_j.scalar_one_or_none()
            if not job:
                continue

            if job.status == "completed" and job.artifact_id:
                if seg.active_artifact_id != job.artifact_id:
                    # Non-destructive: archive previous artifact to revisions
                    if seg.active_artifact_id:
                        next_rev = len(seg.revisions) + 1
                        rev = SegmentRevisionRecord(
                            segment_id=seg.id,
                            revision_number=next_rev,
                            text=seg.text,
                            engine_id=seg.engine_id,
                            voice_id=seg.voice_id,
                            parameters=seg.parameters,
                            artifact_id=seg.active_artifact_id,
                            job_id=seg.last_job_id,
                            duration_seconds=getattr(seg.active_artifact, "duration_seconds", 0.0) if seg.active_artifact else 0.0,
                        )
                        session.add(rev)

                    seg.active_artifact_id = job.artifact_id
                    seg.status = "completed"
                    seg.updated_at = datetime.now(timezone.utc)
                    changed = True
            elif job.status == "failed" and seg.status != "failed":
                seg.status = "failed"
                seg.updated_at = datetime.now(timezone.utc)
                changed = True
            elif job.status == "running" and seg.status != "rendering":
                seg.status = "rendering"
                seg.updated_at = datetime.now(timezone.utc)
                changed = True

        if changed:
            project.updated_at = datetime.now(timezone.utc)
            await session.commit()

        return await cls.get_project_record(session, project_id, current_user.id)
