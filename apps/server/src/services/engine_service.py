"""
Engine Registry & Discovery Service (Headless Core)
"""

from pathlib import Path
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.engine import EngineRecord
from ..schemas.engine import EngineDetailResponse, PresetVoiceSchema
from ..supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest


class EngineService:
    @staticmethod
    async def discover_and_register_engines(db: AsyncSession, workspace_root: Path):
        engines_dir = workspace_root / "engines"
        if not engines_dir.exists():
            return

        for entry in engines_dir.iterdir():
            if entry.is_dir():
                manifest_file = entry / "engine.manifest.json"
                if manifest_file.exists():
                    try:
                        manifest = EngineManifest.from_file(str(manifest_file))
                        # Start worker subprocess via supervisor if not running
                        await supervisor.start_worker(manifest=manifest, workspace_root=workspace_root)

                        # Sync with database registry
                        stmt = select(EngineRecord).where(EngineRecord.id == manifest.engine_id)
                        res = await db.execute(stmt)
                        rec = res.scalar_one_or_none()
                        if not rec:
                            rec = EngineRecord(
                                id=manifest.engine_id,
                                name=manifest.name,
                                version=manifest.version,
                                approval_status="approved",
                                device_target=manifest.hardware_profile.default_device,
                                capabilities=[c.value for c in manifest.capabilities],
                                manifest_data=manifest.model_dump(),
                            )
                            db.add(rec)
                        else:
                            rec.name = manifest.name
                            rec.version = manifest.version
                            rec.capabilities = [c.value for c in manifest.capabilities]
                            rec.manifest_data = manifest.model_dump()
                        await db.commit()
                    except Exception as e:
                        # Log error and continue with other engines
                        print(f"Warning: Failed to initialize engine at {entry}: {e}")

    @staticmethod
    async def list_engines(db: AsyncSession) -> List[EngineDetailResponse]:
        stmt = select(EngineRecord).where(EngineRecord.approval_status == "approved")
        res = await db.execute(stmt)
        records = res.scalars().all()

        responses = []
        for r in records:
            manifest_dict = r.manifest_data or {}
            client = supervisor.get_client(r.id)
            preset_voices = []
            if client:
                try:
                    info = await client.get_info()
                    preset_voices = [
                        PresetVoiceSchema(
                            id=pv.id,
                            name=pv.name,
                            language=pv.language,
                            gender=pv.gender or "unspecified",
                        )
                        for pv in info.preset_voices
                    ]
                except Exception:
                    pass

            responses.append(
                EngineDetailResponse(
                    id=r.id,
                    name=r.name,
                    version=r.version,
                    approval_status=r.approval_status,
                    device_target=r.device_target,
                    capabilities=r.capabilities,
                    supported_languages=manifest_dict.get("supported_languages", ["vi"]),
                    preset_voices=preset_voices,
                    parameters_schema=manifest_dict.get("parameters_schema", {}),
                )
            )
        return responses
