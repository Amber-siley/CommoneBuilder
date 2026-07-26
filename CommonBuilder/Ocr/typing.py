from cv2.typing import MatLike

class OCR:
    def readtext(self, img: MatLike, cls: bool = False) -> list:
        return ["模拟 OCR 识别结果"]