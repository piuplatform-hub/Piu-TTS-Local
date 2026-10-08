"""
Projects API Router
Handles project workspace CRUD, character configuration, and script segment synchronization.
"""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from apps.server.src.models.user import User
from apps.server.src.services.auth_service import get_current_user
from apps.server.src.services.project_service import ProjectService
from apps.server.src.services.text_segmenter import TextSegmenter
from apps.server.src.services.audio_dsp_service import AudioDspService
from apps.server.src.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectSummary, ProjectDetail,
    CharacterCreate, CharacterUpdate, CharacterResponse,
    SegmentCreate, SegmentUpdate, SegmentResponse, SegmentBulkSyncRequest,
    TextSegmentRequest, TextSegmentResponse, TextSegmentItem,
    MasterExportRequest, ProjectExportResponse
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await ProjectService.create_project(db, current_user.id, req)
    return project


@router.get("", response_model=List[ProjectSummary])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summaries = await ProjectService.list_projects(db, current_user.id)
    return summaries


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await ProjectService.reconcile_project_segments(db, current_user, project_id)
    return project


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await ProjectService.update_project(db, current_user.id, project_id, req)
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ProjectService.delete_project(db, current_user.id, project_id)


# -------------------------------------------------------------
# CHARACTERS ENDPOINTS
# -------------------------------------------------------------
@router.post("/{project_id}/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: str,
    req: CharacterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    char = await ProjectService.create_character(db, current_user.id, project_id, req)
    return char


@router.patch("/{project_id}/characters/{char_id}", response_model=CharacterResponse)
async def update_character(
    project_id: str,
    char_id: str,
    req: CharacterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await ProjectService.update_character(db, current_user.id, project_id, char_id, req)
    return updated


@router.delete("/{project_id}/characters/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    project_id: str,
    char_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ProjectService.delete_character(db, current_user.id, project_id, char_id)


# -------------------------------------------------------------
# SCRIPT SEGMENTS ENDPOINTS
# -------------------------------------------------------------
@router.post("/{project_id}/segments", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def add_segment(
    project_id: str,
    req: SegmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    seg = await ProjectService.add_segment(db, current_user.id, project_id, req)
    return seg


@router.patch("/{project_id}/segments/{seg_id}", response_model=SegmentResponse)
async def update_segment(
    project_id: str,
    seg_id: str,
    req: SegmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await ProjectService.update_segment(db, current_user.id, project_id, seg_id, req)
    return updated


@router.delete("/{project_id}/segments/{seg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    project_id: str,
    seg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ProjectService.delete_segment(db, current_user.id, project_id, seg_id)


@router.put("/{project_id}/segments", response_model=List[SegmentResponse])
async def bulk_sync_segments(
    project_id: str,
    req: SegmentBulkSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    segments = await ProjectService.bulk_sync_segments(db, current_user.id, project_id, req)
    return segments


# -------------------------------------------------------------
# AUTO-SEGMENTATION & PREVIEW
# -------------------------------------------------------------
@router.post("/segment-text", response_model=TextSegmentResponse)
async def preview_text_segmentation(
    req: TextSegmentRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Preview intelligent text segmentation without saving to a project.
    """
    raw_chunks = TextSegmenter.segment_text(req.text, language=req.language, max_chars=req.max_chars_per_segment)
    items = [TextSegmentItem(index=i, text=c, char_count=len(c)) for i, c in enumerate(raw_chunks)]
    return TextSegmentResponse(
        language=req.language,
        total_chars=len(req.text),
        segment_count=len(items),
        segments=items,
    )


@router.post("/{project_id}/auto-segment", response_model=List[SegmentResponse])
async def auto_segment_project(
    project_id: str,
    req: TextSegmentRequest,
    replace_existing: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Automatically segments long-form text and populates the project script segments.
    """
    engine_id = req.default_engine_id or ("qwen3-tts" if req.language == "zh" else "vieneu-tts")
    voice_id = req.default_voice_id or ("vivian" if req.language == "zh" else "mai_anh")

    segments = await ProjectService.auto_segment_text(
        db,
        current_user.id,
        project_id,
        text=req.text,
        language=req.language,
        default_engine_id=engine_id,
        default_voice_id=voice_id,
        replace_existing=replace_existing,
        max_chars=req.max_chars_per_segment,
    )
    return segments


# -------------------------------------------------------------
# RENDERING & JOB RECONCILIATION
# -------------------------------------------------------------
@router.post("/{project_id}/segments/{seg_id}/render", response_model=SegmentResponse)
async def render_single_segment(
    project_id: str,
    seg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a synthesis job for a single segment (Partial Invalidation & Regeneration).
    """
    seg, _ = await ProjectService.render_segment(db, current_user, project_id, seg_id)
    return seg


@router.post("/{project_id}/render-batch", response_model=List[SegmentResponse])
async def render_batch_segments(
    project_id: str,
    segment_ids: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits batch synthesis jobs for multiple or all draft/stale segments in the project.
    """
    rendered_pairs = await ProjectService.render_batch(db, current_user, project_id, segment_ids)
    return [pair[0] for pair in rendered_pairs]


@router.post("/{project_id}/reconcile", response_model=ProjectDetail)
async def reconcile_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reconciles in-flight job completion states with project segments.
    """
    project = await ProjectService.reconcile_project_segments(db, current_user, project_id)
    return project


# -------------------------------------------------------------
# AUDIO DSP & MASTER EXPORT
# -------------------------------------------------------------
@router.post("/{project_id}/export", response_model=ProjectExportResponse, status_code=status.HTTP_201_CREATED)
async def export_master_audio(
    project_id: str,
    req: MasterExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stitches all completed segments into a unified master WAV or MP3 audio file.
    Applies resampler, silence padding, and optional EBU R128 loudness normalization.
    """
    export_rec = await AudioDspService.export_project(db, current_user.id, project_id, req)
    return export_rec


@router.get("/{project_id}/exports/{export_id}/download")
async def download_master_audio(
    project_id: str,
    export_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Downloads an exported master audio file.
    """
    project = await ProjectService.get_project_record(db, project_id, current_user.id)
    target_exp = next((e for e in project.exports if e.id == export_id), None)
    if not target_exp or not Path(target_exp.file_path).is_file():
        raise HTTPException(status_code=404, detail="EXPORT_FILE_NOT_FOUND")

    ext = target_exp.format.lower()
    media_type = "audio/mpeg" if ext == "mp3" else "audio/wav"
    filename = f"{project.title.replace(' ', '_')}_{export_id[:8]}.{ext}"
    return FileResponse(
        path=target_exp.file_path,
        media_type=media_type,
        filename=filename,
    )
