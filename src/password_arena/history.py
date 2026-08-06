import json
from pathlib import Path
from typing import Any

from password_arena.models import ExperimentResult


class HistoryManager:
    """Manages persistent storage for experiment history."""

    def __init__(self, storage_dir: str | Path = ".password_arena_history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: ExperimentResult) -> None:
        file_path = self.storage_dir / f"{result.experiment_id}.json"
        data = result.to_dict()
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_runs(self) -> list[dict[str, Any]]:
        runs = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                runs.append({
                    "experiment_id": data.get("experiment_id", file_path.stem),
                    "timestamp": data.get("timestamp", ""),
                    "schema_version": data.get("schema_version", "1.0"),
                    "solve_rate": data.get("summary", {}).get("solve_rate", 0.0),
                    "total_rounds": data.get("summary", {}).get("total_rounds", 0)
                })
            except Exception:
                continue
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return runs

    def load(self, experiment_id: str) -> ExperimentResult:
        file_path = self.storage_dir / f"{experiment_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Experiment {experiment_id} not found.")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return ExperimentResult.from_dict(data)

    def delete(self, experiment_id: str) -> None:
        file_path = self.storage_dir / f"{experiment_id}.json"
        if file_path.exists():
            file_path.unlink()
        else:
            raise FileNotFoundError(f"Experiment {experiment_id} not found.")

    def export(self, experiment_id: str, export_path: Path) -> None:
        data = self.load(experiment_id).to_dict()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
