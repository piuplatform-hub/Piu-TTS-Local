# Engine feasibility matrix (unverified; future Phase 1B)

| Engine and candidate | Role | Target device | Status | Evidence needed |
|---|---|---|---|---|
| VieNeu-TTS v3 Turbo | Vietnamese TTS + consented voice clone | CPU / ONNX candidate | **Not installed / not benchmarked by this package** | Upstream pinned release/weights, RAM peak, RTF, reference sample quality, license |
| Qwen3-TTS 12Hz 0.6B CustomVoice | Mandarin preset TTS | RTX 3050 6GB GPU candidate | **Not installed / not benchmarked by this package** | CUDA/Python wheel, peak VRAM, 50/100/250 Chinese-character cases, audio quality |
| Qwen3-TTS 12Hz 0.6B Base | Future Mandarin clone | GPU/offload research | **Deferred** | Separate spike/license/resource estimates |

Hardware reported in Gemini R1: Windows 11, i5-12400F, 16GB RAM, RTX 3050 6GB. The reported free VRAM (~3.8GB) is **not a service-level guarantee**, and competing Windows apps can change availability at any time.

**Recommended spike outputs:** version manifest, `nvidia-smi` snapshots and sampled time series, process RAM and VRAM peak, model load time, inference speed, audio correctness, failure traces, repeatability and fallback plan. Do not mark pass from README claims alone.
