"""Engine scripts the film stages run in other Python environments.

Each is a standalone file (it imports nothing from autonovel) that
`autonovel mechanical …` runs with the interpreter of the environment that
holds the model, passing a job file and reading one JSON result from the
last line of its stdout.
"""

from pathlib import Path


def engine_path(name: str) -> Path:
    return Path(__file__).with_name(f"{name}.py")
