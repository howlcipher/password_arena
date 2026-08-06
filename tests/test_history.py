from typing import Any

import pytest

from password_arena.history import HistoryManager
from password_arena.models import ArenaConfig, ExperimentResult


def test_history_manager_save_load_list_delete(tmp_path: Any) -> None:
    hm = HistoryManager(storage_dir=tmp_path)
    
    config = ArenaConfig(rounds=2)
    exp = ExperimentResult(config=config)
    
    hm.save(exp)
    runs = hm.list_runs()
    assert len(runs) == 1
    assert runs[0]["experiment_id"] == exp.experiment_id
    
    loaded = hm.load(exp.experiment_id)
    assert loaded.experiment_id == exp.experiment_id
    assert loaded.config.rounds == 2
    
    export_path = tmp_path / "exports" / "export.json"
    hm.export(exp.experiment_id, export_path)
    assert export_path.exists()
    
    hm.delete(exp.experiment_id)
    assert len(hm.list_runs()) == 0
    with pytest.raises(FileNotFoundError):
        hm.load(exp.experiment_id)
