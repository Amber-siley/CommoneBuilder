from paddleocr import PaddleOCR

from cv2.typing import MatLike

class OCR(PaddleOCR):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def readtext(self, img: MatLike, det = True, rec = True, cls = False, bin = False, inv = False) -> list:
        data = self.ocr(
            img,
            det=det,
            rec=rec,
            cls=cls,
            bin=bin,
            inv=inv
        )
        result = []
        if all(data):
            for line in data[0]:
                text = line[1][0]
                result.append(text)
        return result