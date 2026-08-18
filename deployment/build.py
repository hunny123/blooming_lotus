"""Build a self-contained zipapp for deployment."""

import shutil
import tempfile
import zipapp
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


class DeploymentBuilder:
    """Package the application modules without including local secrets."""

    MODULES = (
        "main.py",
        "app/__init__.py",
        "app/engine.py",
        "app/binance_api.py",
        "app/core_engine.py",
        "app/strategy.py",
        "app/telegram_service.py",
        "config/__init__.py",
        "config/settings.py",
        "utils/__init__.py",
        "utils/core.py",
    )

    def __init__(self, output_dir: Path = DIST):
        self.output_dir = output_dir

    def build(self) -> Path:
        self.output_dir.mkdir(exist_ok=True)

        with tempfile.TemporaryDirectory() as directory:
            staging = Path(directory)
            for module in self.MODULES:
                destination = staging / module
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / module, destination)

            output = self.output_dir / "signal_engine.pyz"
            zipapp.create_archive(
                staging,
                output,
                interpreter="/usr/bin/env python3",
                main="main:main",
            )
            return output


if __name__ == "__main__":
    print(DeploymentBuilder().build())
