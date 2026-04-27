import pytest
from domain.device.models import Energy, DieselData

def test_energy_model_should_not_have_kvarh():
    """Energy 모델에서 kvarh 필드가 제거되었는지 확인"""
    energy = Energy()
    
    # kWh는 존재해야 함
    assert hasattr(energy, "kWh")
    # kvarh는 존재하지 않아야 함
    assert not hasattr(energy, "kvarh")

def test_diesel_data_serialization_excludes_kvarh():
    """DieselData 직렬화 시 kvarh 필드가 포함되지 않는지 확인"""
    data = DieselData()
    data_dict = data.model_dump() # Pydantic v2 기준
    
    assert "kWh" in data_dict["energy"]
    assert "kvarh" not in data_dict["energy"]
