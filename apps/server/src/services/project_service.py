"""
Project Management Service
Implements CRUD, optimistic concurrency control, character configuration,
and script segment synchronization with partial invalidation.
"""

import asyncio
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
from apps.server.src.models.artifact import ArtifactRecord
from apps.server.src.models.user import User
from apps.server.src.config import settings
from apps.server.src.schemas.job import TTSJobSubmitRequest
from apps.server.src.services.job_service import JobService
from apps.server.src.services.job_state_machine import JobState
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
    _admission_lock: Optional[asyncio.Lock] = None

    @classmethod
    def get_admission_lock(cls) -> asyncio.Lock:
        if cls._admission_lock is None:
            cls._admission_lock = asyncio.Lock()
        return cls._admission_lock

    @staticmethod
    async def get_project_record(session: AsyncSession, project_id: str, user_id: str, is_admin: bool = False) -> ProjectRecord:
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
        if project.user_id != user_id and not is_admin:
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
    async def list_projects(cls, session: AsyncSession, user_id: str, is_admin: bool = False) -> List[Dict[str, Any]]:
        stmt = (
            select(ProjectRecord)
            .options(
                selectinload(ProjectRecord.segments),
            )
            .order_by(ProjectRecord.updated_at.desc())
        )
        if not is_admin:
            stmt = stmt.where(ProjectRecord.user_id == user_id)
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

        engine_id = req.engine_id
        voice_id = req.voice_id
        language = req.language
        parameters = dict(req.parameters or {})

        if req.character_id:
            char_stmt = select(CharacterRecord).where(
                CharacterRecord.id == req.character_id,
                CharacterRecord.project_id == project_id,
            )
            char_res = await session.execute(char_stmt)
            char_obj = char_res.scalar_one_or_none()
            if char_obj:
                if not voice_id or voice_id in ("hai_dang", "default"):
                    voice_id = char_obj.voice_id
                if not engine_id or engine_id in ("mock-tts", "vieneu-tts"):
                    engine_id = char_obj.engine_id
                if not language:
                    language = char_obj.language
                if not parameters:
                    parameters = dict(char_obj.parameters or {})

        text_hash = compute_segment_hash(req.text, engine_id, voice_id, parameters)
        seg = ScriptSegmentRecord(
            project_id=project.id,
            character_id=req.character_id,
            sequence_order=req.sequence_order,
            text=req.text.strip(),
            language=language,
            engine_id=engine_id,
            voice_id=voice_id,
            parameters=parameters,
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
            new_char_id = req.character_id if req.character_id != "" else None
            seg.character_id = new_char_id
            if new_char_id:
                char_stmt = select(CharacterRecord).where(
                    CharacterRecord.id == new_char_id,
                    CharacterRecord.project_id == project_id,
                )
                char_res = await session.execute(char_stmt)
                char_obj = char_res.scalar_one_or_none()
                if char_obj:
                    if req.engine_id is None:
                        seg.engine_id = char_obj.engine_id
                    if req.voice_id is None:
                        seg.voice_id = char_obj.voice_id
                    if req.language is None:
                        seg.language = char_obj.language
                    if req.parameters is None:
                        seg.parameters = dict(char_obj.parameters or {})
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

        # Partial Invalidation: If content changed, mark as stale if completed or had audio, else draft
        if new_hash != old_hash:
            if seg.status == "completed" or seg.active_artifact_id:
                seg.status = "stale"
            else:
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

        # Resolve effective character parameters & settings
        effective_params = dict(seg.parameters or {})
        effective_engine_id = seg.engine_id
        effective_voice_id = seg.voice_id
        effective_language = seg.language or "vi"

        if seg.character_id:
            stmt_char = select(CharacterRecord).where(
                CharacterRecord.id == seg.character_id,
                CharacterRecord.project_id == project_id,
            )
            res_char = await session.execute(stmt_char)
            char = res_char.scalar_one_or_none()
            if char:
                merged_params = dict(char.parameters or {})
                merged_params.update(effective_params)
                effective_params = merged_params
                if not effective_voice_id:
                    effective_voice_id = char.voice_id
                if not effective_engine_id:
                    effective_engine_id = char.engine_id
                if not effective_language and char.language:
                    effective_language = char.language

        # Submit speech synthesis job via JobService
        job_req = TTSJobSubmitRequest(
            engine_id=effective_engine_id,
            text=seg.text,
            language=effective_language,
            voice_id=effective_voice_id,
            parameters=effective_params,
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

        # Bounded Progressive Submission Strategy:
        # Check current active/queued jobs for current_user to respect MAX_OUTSTANDING_JOBS_PER_USER
        active_stmt = select(func.count(JobRecord.id)).where(
            JobRecord.user_id == current_user.id,
            JobRecord.status.in_([JobState.QUEUED.value, JobState.PREPARING.value, JobState.RUNNING.value]),
        )
        active_res = await session.execute(active_stmt)
        outstanding_count = active_res.scalar() or 0
        available_slots = max(0, settings.MAX_OUTSTANDING_JOBS_PER_USER - outstanding_count)

        # Cache project characters for fast parameter resolution
        stmt_chars = select(CharacterRecord).where(CharacterRecord.project_id == project_id)
        res_chars = await session.execute(stmt_chars)
        chars_map = {c.id: c for c in res_chars.scalars().all()}

        rendered = []
        for seg in targets:
            if available_slots > 0:
                eff_params = dict(seg.parameters or {})
                eff_engine_id = seg.engine_id
                eff_voice_id = seg.voice_id
                eff_lang = seg.language or "vi"

                if seg.character_id and seg.character_id in chars_map:
                    ch = chars_map[seg.character_id]
                    merged = dict(ch.parameters or {})
                    merged.update(eff_params)
                    eff_params = merged
                    if not eff_voice_id:
                        eff_voice_id = ch.voice_id
                    if not eff_engine_id:
                        eff_engine_id = ch.engine_id
                    if not eff_lang and ch.language:
                        eff_lang = ch.language

                job_req = TTSJobSubmitRequest(
                    engine_id=eff_engine_id,
                    text=seg.text,
                    language=eff_lang,
                    voice_id=eff_voice_id,
                    parameters=eff_params,
                    priority=1,
                    idempotency_key=f"seg-{seg.id}-{seg.text_hash[:32]}",
                )
                job = await JobService.submit_speech_job(session, job_req, current_user)
                seg.last_job_id = job.id
                seg.status = "queued"
                seg.updated_at = datetime.now(timezone.utc)
                rendered.append((seg, job))
                available_slots -= 1
            else:
                # Mark excess segments as pending to be progressively pumped as slots free up
                seg.status = "pending"
                seg.last_job_id = None
                seg.updated_at = datetime.now(timezone.utc)
                rendered.append((seg, None))

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
        is_admin = getattr(current_user, "role", "user") == "admin"
        project = await cls.get_project_record(session, project_id, current_user.id, is_admin=is_admin)
        if is_admin and project.user_id != current_user.id:
            # Operational inspection only: Admin cannot mutate another user's project content
            return project
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

            payload = getattr(job, "payload_data", None) or getattr(job, "request_payload", None) or {}
            job_text = payload.get("text", "")
            job_voice = payload.get("voice_id", "")
            job_params = payload.get("parameters", {})
            job_hash = compute_segment_hash(job_text, job.engine_id, job_voice, job_params)
            is_matching_job = (job_hash == seg.text_hash)

            if job.status == "completed" and job.artifact_id:
                if is_matching_job:
                    # Job corresponds to CURRENT segment content
                    if seg.active_artifact_id != job.artifact_id:
                        # Non-destructive: archive previous artifact to revisions
                        if seg.active_artifact_id:
                            next_rev = len(seg.revisions) + 1
                            dur = 0.0
                            old_art = await session.get(ArtifactRecord, seg.active_artifact_id)
                            if old_art and old_art.duration_seconds:
                                dur = float(old_art.duration_seconds)
                            rev = SegmentRevisionRecord(
                                segment_id=seg.id,
                                revision_number=next_rev,
                                text=seg.text,
                                engine_id=seg.engine_id,
                                voice_id=seg.voice_id,
                                parameters=seg.parameters,
                                artifact_id=seg.active_artifact_id,
                                job_id=seg.last_job_id,
                                duration_seconds=dur,
                            )
                            session.add(rev)

                        seg.active_artifact_id = job.artifact_id
                        seg.status = "completed"
                        seg.updated_at = datetime.now(timezone.utc)
                        changed = True
                    elif seg.status != "completed":
                        seg.status = "completed"
                        seg.updated_at = datetime.now(timezone.utc)
                        changed = True
                else:
                    # STALE JOB: Segment was edited while older job was rendering!
                    # Do NOT overwrite current segment's active artifact or mark it completed.
                    # Preserve older audio into a SegmentRevisionRecord.
                    rev_exists = any(r.artifact_id == job.artifact_id for r in seg.revisions)
                    if not rev_exists:
                        next_rev = len(seg.revisions) + 1
                        dur = 0.0
                        art = await session.get(ArtifactRecord, job.artifact_id)
                        if art and art.duration_seconds:
                            dur = float(art.duration_seconds)
                        rev = SegmentRevisionRecord(
                            segment_id=seg.id,
                            revision_number=next_rev,
                            text=job_text,
                            engine_id=job.engine_id,
                            voice_id=job_voice,
                            parameters=job_params,
                            artifact_id=job.artifact_id,
                            job_id=job.id,
                            duration_seconds=dur,
                        )
                        session.add(rev)
                        changed = True
                    if seg.status in ("rendering", "queued"):
                        seg.status = "stale" if seg.active_artifact_id else "draft"
                        seg.updated_at = datetime.now(timezone.utc)
                        changed = True

            elif job.status == "failed":
                if is_matching_job and seg.status != "failed":
                    seg.status = "failed"
                    seg.updated_at = datetime.now(timezone.utc)
                    changed = True
            elif job.status == "running":
                if is_matching_job and seg.status != "rendering":
                    seg.status = "rendering"
                    seg.updated_at = datetime.now(timezone.utc)
        # Progressive Pump for Pending Segments (Bounded Batch Processing):
        pending_segs = [s for s in project.segments if s.status == "pending"]
        if pending_segs:
            # Query in-flight jobs count for this user
            active_stmt = select(func.count(JobRecord.id)).where(
                JobRecord.user_id == current_user.id,
                JobRecord.status.in_([JobState.QUEUED.value, JobState.PREPARING.value, JobState.RUNNING.value]),
            )
            active_res = await session.execute(active_stmt)
            curr_active = active_res.scalar() or 0
            free_slots = max(0, settings.MAX_OUTSTANDING_JOBS_PER_USER - curr_active)

            if free_slots > 0:
                pending_sorted = sorted(pending_segs, key=lambda s: s.sequence_order)
                for seg_to_queue in pending_sorted[:free_slots]:
                    job_req = TTSJobSubmitRequest(
                        engine_id=seg_to_queue.engine_id,
                        text=seg_to_queue.text,
                        language=seg_to_queue.language,
                        voice_id=seg_to_queue.voice_id,
                        parameters=seg_to_queue.parameters,
                        priority=1,
                        idempotency_key=f"seg-{seg_to_queue.id}-{seg_to_queue.text_hash[:32]}",
                    )
                    try:
                        job = await JobService.submit_speech_job(session, job_req, current_user)
                        seg_to_queue.last_job_id = job.id
                        seg_to_queue.status = "queued"
                        seg_to_queue.updated_at = datetime.now(timezone.utc)
                        changed = True
                    except AppException as exc:
                        if exc.code == "TOO_MANY_OUTSTANDING_JOBS":
                            break
                        raise

        if changed:
            project.updated_at = datetime.now(timezone.utc)
            await session.commit()

        return await cls.get_project_record(session, project_id, current_user.id, is_admin=is_admin)

    @classmethod
    async def reconcile_and_admit_pending_segments(cls) -> int:
        """
        Autonomous background reconciliation and progressive batch admission.
        Runs inside the DurableJobScheduler daemon loop without requiring browser polling.

        1. Finds in-flight segments whose associated JobRecord has finished (completed/failed)
           and reconciles their status and active audio artifacts.
        2. Finds projects with 'pending' segments, checks per-user outstanding limits,
           and transactionally admits pending segments into the durable queue as slots open up.

        Returns the number of pending segments newly admitted to the queue.
        """
        from apps.server.src.database import AsyncSessionLocal
        admitted_count = 0

        async with AsyncSessionLocal() as session:
            # Step 1: Reconcile in-flight segments with finished/updated jobs
            stmt_inflight = (
                select(ScriptSegmentRecord)
                .where(
                    ScriptSegmentRecord.status.in_(["rendering", "queued"]),
                    ScriptSegmentRecord.last_job_id.is_not(None),
                )
                .options(selectinload(ScriptSegmentRecord.revisions))
            )
            res_inflight = await session.execute(stmt_inflight)
            inflight_segs = res_inflight.scalars().all()

            for seg in inflight_segs:
                stmt_j = select(JobRecord).where(JobRecord.id == seg.last_job_id)
                res_j = await session.execute(stmt_j)
                job = res_j.scalar_one_or_none()
                if not job:
                    continue

                payload = getattr(job, "payload_data", None) or getattr(job, "request_payload", None) or {}
                job_text = payload.get("text", "")
                job_voice = payload.get("voice_id", "")
                job_params = payload.get("parameters", {})
                job_hash = compute_segment_hash(job_text, job.engine_id, job_voice, job_params)
                is_matching_job = (job_hash == seg.text_hash)

                if job.status == "completed" and job.artifact_id:
                    if is_matching_job:
                        if seg.active_artifact_id != job.artifact_id:
                            if seg.active_artifact_id:
                                next_rev = len(seg.revisions) + 1
                                dur = 0.0
                                old_art = await session.get(ArtifactRecord, seg.active_artifact_id)
                                if old_art and old_art.duration_seconds:
                                    dur = float(old_art.duration_seconds)
                                rev = SegmentRevisionRecord(
                                    segment_id=seg.id,
                                    revision_number=next_rev,
                                    text=seg.text,
                                    engine_id=seg.engine_id,
                                    voice_id=seg.voice_id,
                                    parameters=seg.parameters,
                                    artifact_id=seg.active_artifact_id,
                                    job_id=seg.last_job_id,
                                    duration_seconds=dur,
                                )
                                session.add(rev)

                            seg.active_artifact_id = job.artifact_id
                            seg.status = "completed"
                            seg.updated_at = datetime.now(timezone.utc)
                        elif seg.status != "completed":
                            seg.status = "completed"
                            seg.updated_at = datetime.now(timezone.utc)
                    else:
                        rev_exists = any(r.artifact_id == job.artifact_id for r in seg.revisions)
                        if not rev_exists:
                            next_rev = len(seg.revisions) + 1
                            dur = 0.0
                            art = await session.get(ArtifactRecord, job.artifact_id)
                            if art and art.duration_seconds:
                                dur = float(art.duration_seconds)
                            rev = SegmentRevisionRecord(
                                segment_id=seg.id,
                                revision_number=next_rev,
                                text=job_text,
                                engine_id=job.engine_id,
                                voice_id=job_voice,
                                parameters=job_params,
                                artifact_id=job.artifact_id,
                                job_id=job.id,
                                duration_seconds=dur,
                            )
                            session.add(rev)
                        if seg.status in ("rendering", "queued"):
                            seg.status = "stale" if seg.active_artifact_id else "draft"
                            seg.updated_at = datetime.now(timezone.utc)
                elif job.status == "failed":
                    if is_matching_job and seg.status != "failed":
                        seg.status = "failed"
                        seg.updated_at = datetime.now(timezone.utc)
                elif job.status == "running":
                    if is_matching_job and seg.status != "rendering":
                        seg.status = "rendering"
                        seg.updated_at = datetime.now(timezone.utc)

            await session.commit()

            # Step 2: Autonomous Progressive Admission of 'pending' segments
            stmt_pending = (
                select(ScriptSegmentRecord)
                .where(ScriptSegmentRecord.status == "pending")
                .order_by(ScriptSegmentRecord.sequence_order.asc())
            )
            res_pending = await session.execute(stmt_pending)
            pending_segs = res_pending.scalars().all()

            if not pending_segs:
                return 0

            # Group pending segments by user_id
            projects_cache: Dict[str, Optional[ProjectRecord]] = {}
            user_cache: Dict[str, Optional[User]] = {}
            user_pending: Dict[str, List[ScriptSegmentRecord]] = {}

            for s in pending_segs:
                if s.project_id not in projects_cache:
                    p = await session.get(ProjectRecord, s.project_id)
                    projects_cache[s.project_id] = p
                proj = projects_cache[s.project_id]
                if not proj:
                    continue
                uid = proj.user_id
                if uid not in user_pending:
                    user_pending[uid] = []
                user_pending[uid].append(s)

            for uid, segs_for_user in user_pending.items():
                if uid not in user_cache:
                    u = await session.get(User, uid)
                    user_cache[uid] = u
                usr = user_cache[uid]
                if not usr:
                    continue

                # Query current active jobs for this user
                active_stmt = select(func.count(JobRecord.id)).where(
                    JobRecord.user_id == uid,
                    JobRecord.status.in_([JobState.QUEUED.value, JobState.PREPARING.value, JobState.RUNNING.value]),
                )
                active_res = await session.execute(active_stmt)
                curr_active = active_res.scalar() or 0
                free_slots = max(0, settings.MAX_OUTSTANDING_JOBS_PER_USER - curr_active)

                if free_slots <= 0:
                    continue

                for seg_to_queue in segs_for_user[:free_slots]:
                    job_req = TTSJobSubmitRequest(
                        engine_id=seg_to_queue.engine_id,
                        text=seg_to_queue.text,
                        language=seg_to_queue.language,
                        voice_id=seg_to_queue.voice_id,
                        parameters=seg_to_queue.parameters,
                        priority=1,
                        idempotency_key=f"seg-{seg_to_queue.id}-{seg_to_queue.text_hash[:32]}",
                    )
                    try:
                        job = await JobService.submit_speech_job(session, job_req, usr)
                        seg_to_queue.last_job_id = job.id
                        seg_to_queue.status = "queued"
                        seg_to_queue.updated_at = datetime.now(timezone.utc)
                        admitted_count += 1
                    except AppException as exc:
                        if exc.code == "TOO_MANY_OUTSTANDING_JOBS":
                            break
                        raise

            if admitted_count > 0:
                await session.commit()

        return admitted_count
