from paddleocr import PaddleOCR

from cv2.typing import MatLike

class OCR(PaddleOCR):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def readtext(self, img: MatLike, det = True, rec = True, cls = False, bin = False, inv = False) -> list:
        data = self.predict(
            img,
            det=det,
            rec=rec,
            cls=cls,
            use_angle_cls=bin,
            box_thresh=inv
        )
        result = []
        if all(data):
            for line in data[0]:
                text = line[1][0]
                result.append(text)
        return result