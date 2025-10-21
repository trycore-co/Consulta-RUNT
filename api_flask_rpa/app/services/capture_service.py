from datetime import datetime
from typing import List
from config import settings
from pathlib import Path


class CaptureService:
    def __init__(self, base_dir: str = settings.SCREENSHOT_PATH):
        self.base_dir = base_dir

    def save_screenshot_bytes(
        self, bytes_png: bytes, correlation_id: str, placa: str
    ) -> str:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        folder = Path(self.base_dir) / date
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{correlation_id}_{placa}.png"
        path = folder / filename
        with open(path, "wb") as f:
            f.write(bytes_png)
        return str(path)

    def list_images_for_correlation(self, correlation_id: str) -> List[str]:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        folder = Path(self.base_dir) / date
        if not folder.exists():
            return []
        return [str(p) for p in folder.glob(f"{correlation_id}_*.png")]
