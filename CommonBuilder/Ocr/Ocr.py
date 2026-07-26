from paddleocr import PaddleOCR

from cv2.typing import MatLike

import onnxruntime
onnxruntime.set_default_logger_severity(3)

class OCR(PaddleOCR):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def readtext(self, img: MatLike, cls: bool = False) -> list:
        data = self.predict(img, use_textline_orientation=cls)
        result = []
        if data:
            for item in data:
                texts = item.get("rec_texts", [])
                result.extend(texts)
        return result
