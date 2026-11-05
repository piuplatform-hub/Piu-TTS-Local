"""
Engine Registry & Discovery Service (Headless Core)
"""

from pathlib import Path
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.engine import EngineRecord
from ..schemas.engine import (
    EngineDetailResponse,
    PresetVoiceSchema,
    EngineCapabilityDetailResponse,
    ParameterDefinitionSchema,
    VoicePresetSchema,
)
from ..supervisor.supervisor import supervisor
from engine_sdk.manifest import EngineManifest


class EngineService:
    @staticmethod
    async def discover_and_register_engines(db: AsyncSession, workspace_root: Path, spawn_workers: bool = True):
        engines_dir = workspace_root / "engines"
        if not engines_dir.exists():
            return

        for entry in engines_dir.iterdir():
            if entry.is_dir():
                manifest_file = entry / "engine.manifest.json"
                if manifest_file.exists():
                    try:
                        manifest = EngineManifest.from_file(str(manifest_file))
                        runtime_device = manifest.hardware_profile.default_device
                        # Start worker subprocess via supervisor if requested and not running
                        if spawn_workers:
                            worker = await supervisor.start_worker(manifest=manifest, workspace_root=workspace_root)
                            try:
                                health = await worker.client.get_health()
                                if health.device in {"cpu", "gpu"}:
                                    runtime_device = health.device
                            except Exception:
                                # Keep the manifest preference if a health probe
                                # cannot report the runtime device yet.
                                pass

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
                                device_target=runtime_device,
                                capabilities=[c.value for c in manifest.capabilities],
                                manifest_data=manifest.model_dump(),
                            )
                            db.add(rec)
                        else:
                            rec.name = manifest.name
                            rec.version = manifest.version
                            rec.device_target = runtime_device
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

    @staticmethod
    async def get_engine_capabilities(db: AsyncSession, engine_id: str) -> EngineCapabilityDetailResponse:
        """
        Deep discovery endpoint returning verified parameters, ranges, labels, and presets
        for a specific AI engine, or structured audit response for uninstalled engines.
        """
        # 1. Special Handling for Kokoro Engine Audit
        if engine_id.lower() in ("kokoro", "kokoro-tts", "kokoro-82m"):
            return EngineCapabilityDetailResponse(
                engine_id="kokoro-tts",
                name="Kokoro-82M TTS",
                version="0.19.0",
                installed=False,
                status="not_installed",
                device_target="cpu",
                capabilities=["text_to_speech", "multilingual_synthesis"],
                supported_languages=["en", "ja", "zh", "es", "fr", "hi", "it", "pt"],
                default_sample_rate=24000,
                description="Kokoro-82M lightweight multilingual TTS is audited but NOT INSTALLED in the current local environment.",
                parameters=[],
                presets=[],
                preset_voices=[],
            )

        # 2. Query Engine Record from Database
        stmt = select(EngineRecord).where(EngineRecord.id == engine_id)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            from ..core.errors import AppException
            raise AppException(
                status_code=404,
                title="Engine Not Found",
                detail=f"Engine '{engine_id}' is not installed or registered in the Capability Registry.",
                code="ENGINE_NOT_FOUND",
            )

        manifest = record.manifest_data or {}
        capabilities = record.capabilities or []
        device = record.device_target or "cpu"
        sample_rate = manifest.get("default_sample_rate", 48000)

        # Check worker process status via supervisor
        client = supervisor.get_client(record.id)
        status = "ready" if client else "unloaded"
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

        # Define engine-specific verified parameters and presets
        parameters: List[ParameterDefinitionSchema] = []
        presets: List[VoicePresetSchema] = []

        if record.id == "vieneu-tts":
            parameters = [
                ParameterDefinitionSchema(
                    name="speed",
                    type="number",
                    min=0.5,
                    max=2.0,
                    default=1.0,
                    step=0.05,
                    category="dsp",
                    label="Tốc độ nói (Speed)",
                    description="Điều chỉnh tốc độ phát âm (0.5x - 2.0x, bảo toàn cao độ xấp xỉ qua thuật toán DSP phase vocoder).",
                ),
                ParameterDefinitionSchema(
                    name="temperature",
                    type="number",
                    min=0.1,
                    max=1.5,
                    default=0.8,
                    step=0.05,
                    category="native",
                    label="Độ biến thiên lấy mẫu (Sampling Randomness)",
                    description="Độ ngẫu nhiên trong phân phối xác suất lấy mẫu token âm thanh. Giá trị cao tăng tính đa dạng âm tiết nhưng không cam kết cảm xúc cụ thể; giá trị thấp mang lại tính ổn định và lặp lại cao.",
                ),
                ParameterDefinitionSchema(
                    name="top_p",
                    type="number",
                    min=0.1,
                    max=1.0,
                    default=0.95,
                    step=0.01,
                    category="native",
                    label="Ngưỡng Top-P (Nucleus Sampling)",
                    description="Xác suất tích lũy tối đa để chọn lọc các âm vị phát âm hợp lý.",
                ),
                ParameterDefinitionSchema(
                    name="top_k",
                    type="integer",
                    min=1,
                    max=100,
                    default=25,
                    step=1,
                    category="native",
                    label="Giới hạn Top-K",
                    description="Số lượng âm vị ứng viên có xác suất cao nhất được xét trong mỗi bước sinh âm.",
                ),
                ParameterDefinitionSchema(
                    name="repetition_penalty",
                    type="number",
                    min=1.0,
                    max=2.5,
                    default=1.2,
                    step=0.05,
                    category="native",
                    label="Chống vấp / Lặp âm (Repetition Penalty)",
                    description="Hình phạt lặp lại âm tiết, giúp câu nói trôi chảy và hạn chế nói vấp hoặc kéo dài vô tận.",
                ),
                ParameterDefinitionSchema(
                    name="denoise",
                    type="boolean",
                    default=True,
                    category="native",
                    label="Khử tạp âm mẫu giọng (Denoise)",
                    description="Tự động lọc sạch tiếng ồn nền từ file mẫu trước khi trích xuất vector âm sắc nhân bản.",
                ),
            ]
            presets = [
                VoicePresetSchema(
                    id="natural_default",
                    label="Gợi ý: Tự nhiên / Chuẩn mực",
                    description="Bộ tham số gợi ý tầng ứng dụng: Cân bằng giữa độ trôi chảy và tính chuẩn xác của giọng đọc.",
                    values={"speed": 1.0, "temperature": 0.8, "top_p": 0.95, "top_k": 25, "repetition_penalty": 1.2, "denoise": True},
                ),
                VoicePresetSchema(
                    id="expressive_story",
                    label="Gợi ý: Biến thiên cao / Đọc truyện",
                    description="Bộ tham số gợi ý tầng ứng dụng: Tăng độ biến thiên ngữ điệu cho podcast và kịch truyền thanh.",
                    values={"speed": 0.95, "temperature": 1.05, "top_p": 0.98, "top_k": 35, "repetition_penalty": 1.15, "denoise": True},
                ),
                VoicePresetSchema(
                    id="fast_news",
                    label="Gợi ý: Nhanh / Bản tin thời sự",
                    description="Bộ tham số gợi ý tầng ứng dụng: Tốc độ nói nhanh, giảm biến thiên để đọc tin tức rõ ràng.",
                    values={"speed": 1.15, "temperature": 0.65, "top_p": 0.90, "top_k": 20, "repetition_penalty": 1.25, "denoise": True},
                ),
                VoicePresetSchema(
                    id="stable_audiobook",
                    label="Gợi ý: Ổn định / Đọc sách",
                    description="Bộ tham số gợi ý tầng ứng dụng: Ổn định tối đa, hạn chế biến thiên ngẫu nhiên cho sách nói dài.",
                    values={"speed": 1.0, "temperature": 0.5, "top_p": 0.85, "top_k": 15, "repetition_penalty": 1.3, "denoise": True},
                ),
            ]
        elif record.id == "qwen3-tts":
            parameters = [
                ParameterDefinitionSchema(
                    name="speaker",
                    type="string",
                    default="vivian",
                    category="native",
                    label="Nhân vật giọng nói (Speaker)",
                    description="Nhân vật giọng đọc tiếng Trung tích hợp trong mô hình Qwen3-TTS.",
                    enum=["vivian", "uncle_fu", "serena", "aiden", "dylan", "eric", "ono_anna", "ryan", "sohee"],
                ),
                ParameterDefinitionSchema(
                    name="speed",
                    type="number",
                    min=0.5,
                    max=2.0,
                    default=1.0,
                    step=0.05,
                    category="dsp",
                    label="Tốc độ nói (Speed)",
                    description="Điều chỉnh tốc độ đọc tiếng Trung qua DSP resampling.",
                ),
            ]
            presets = [
                VoicePresetSchema(
                    id="default_chinese",
                    label="Giọng nữ chuẩn (Vivian)",
                    description="Giọng đọc nữ phổ thông chuẩn, âm vực thanh thoát.",
                    values={"speaker": "vivian", "speed": 1.0},
                ),
                VoicePresetSchema(
                    id="mature_male",
                    label="Giọng nam trầm (Uncle Fu)",
                    description="Giọng nam trung niên ấm áp, tự tin.",
                    values={"speaker": "uncle_fu", "speed": 1.0},
                ),
                VoicePresetSchema(
                    id="gentle_female",
                    label="Giọng nữ dịu dàng (Serena)",
                    description="Giọng nữ nhẹ nhàng, êm dịu.",
                    values={"speaker": "serena", "speed": 0.95},
                ),
            ]
        elif record.id == "mock-tts":
            parameters = [
                ParameterDefinitionSchema(
                    name="speed",
                    type="number",
                    min=0.25,
                    max=4.0,
                    default=1.0,
                    step=0.05,
                    category="dsp",
                    label="Tốc độ thử nghiệm",
                    description="Tốc độ phát âm mô phỏng.",
                ),
            ]
            presets = [
                VoicePresetSchema(
                    id="mock_standard",
                    label="Mặc định QA",
                    description="Cấu hình thử nghiệm mặc định.",
                    values={"speed": 1.0},
                ),
            ]

        return EngineCapabilityDetailResponse(
            engine_id=record.id,
            name=record.name,
            version=record.version,
            installed=True,
            status=status,
            device_target=device,
            capabilities=capabilities,
            supported_languages=manifest.get("supported_languages", ["vi"]),
            default_sample_rate=sample_rate,
            description=manifest.get("description", ""),
            parameters=parameters,
            presets=presets,
            preset_voices=preset_voices,
        )
