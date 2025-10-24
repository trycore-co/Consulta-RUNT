from typing import List
from datetime import datetime
from app.infrastructure.pdf_builder import images_to_pdf
from config import settings
from pathlib import Path


class PDFService:
    def __init__(self, pdf_dir: str = settings.PDF_DIR):
        self.pdf_dir = pdf_dir

    def consolidate_images_to_pdf(
        self, image_paths: List[str], correlation_id: str
    ) -> str:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        out_folder = Path(self.pdf_dir) / date
        out_folder.mkdir(parents=True, exist_ok=True)
        out_pdf = out_folder / f"{correlation_id}_{date}_ResumenPlacas.pdf"
        images_to_pdf(image_paths, str(out_pdf))
        return str(out_pdf)
