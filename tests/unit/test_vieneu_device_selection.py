import sys
import types

import numpy as np

from engines.vieneu.worker import VieNeuModelManager, _fast_speed_adjust


def _fake_torch(cuda_available: bool):
    return types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: cuda_available),
    )


def test_vieneu_prefers_gpu_when_cuda_is_available(monkeypatch):
    calls = []
    monkeypatch.delenv("VIENEU_DEVICE", raising=False)

    class FakeModel:
        pass

    class FakeVieneu:
        def __new__(cls, **kwargs):
            calls.append(kwargs)
            return FakeModel()

    monkeypatch.setitem(sys.modules, "torch", _fake_torch(True))
    monkeypatch.setitem(sys.modules, "vieneu", types.SimpleNamespace(Vieneu=FakeVieneu))

    manager = VieNeuModelManager()
    assert manager.device == "gpu"
    assert manager.get_model().__class__ is FakeModel
    assert calls == [{}]
    assert manager.backend == "pytorch"


def test_vieneu_falls_back_to_onnx_when_gpu_initialization_fails(monkeypatch):
    calls = []
    monkeypatch.delenv("VIENEU_DEVICE", raising=False)

    class FakeModel:
        pass

    class FakeVieneu:
        def __new__(cls, **kwargs):
            calls.append(kwargs)
            if not kwargs:
                raise RuntimeError("CUDA out of memory")
            assert kwargs == {"backend": "onnx"}
            return FakeModel()

    monkeypatch.setitem(sys.modules, "torch", _fake_torch(True))
    monkeypatch.setitem(sys.modules, "vieneu", types.SimpleNamespace(Vieneu=FakeVieneu))

    manager = VieNeuModelManager()
    assert manager.get_model().__class__ is FakeModel
    assert manager.device == "cpu"
    assert manager.backend == "onnx"
    assert manager.fallback_reason == "CUDA out of memory"
    assert calls == [{}, {"backend": "onnx"}]


def test_fast_speed_adjust_is_bounded_and_preserves_audio_shape_contract():
    audio = np.linspace(-1.0, 1.0, 100, dtype=np.float32)
    adjusted = _fast_speed_adjust(audio, 0.95)

    assert adjusted.dtype == np.float32
    assert len(adjusted) == 105
    assert np.isfinite(adjusted).all()
