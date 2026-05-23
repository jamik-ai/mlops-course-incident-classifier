from __future__ import annotations

from src.monitoring.drift import run_drift_check
from src.pipelines.retrain import retrain_pipeline


def main() -> None:
    result = run_drift_check()
    should_retrain = any([result.get("data_drift_detected", False), result.get("target_drift_detected", False), result.get("concept_drift_detected", False)])
    if should_retrain:
        print(retrain_pipeline())
    else:
        print("No drift detected. Retraining skipped.")


if __name__ == "__main__":
    main()
