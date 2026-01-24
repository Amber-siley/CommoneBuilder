import asyncio
import base64
import math
import os
from pdb import run
import subprocess
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike

from ..FileTools.File import FileManage, UrlManage


class Adb:
    ADB_TOOLS_URL = "https://googledownloads.cn/android/repository/platform-tools-latest-windows.zip"

    def __init__(self, adb_path: Optional[str] = None, connect_port: int = 7555, max_workers: int = 10):
        self.adb_path = FileManage(adb_path).file_path if adb_path else None
        self.max_workers = max_workers
        self.connect_port = connect_port
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_workers)
        self.startupinfo = subprocess.STARTUPINFO()
        self._resetStartupInfo()
        self.ready_env()

    def _resetStartupInfo(self):
        self.startupinfo.dwFlags = (
            subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
        )
        self.startupinfo.wShowWindow = subprocess.SW_HIDE

    def ready_env(self):
        if self.adb_path:
            self.connenct(self.connect_port)
            return
        unzip_path = FileManage(UrlManage.dowload(self.ADB_TOOLS_URL)).unzip(
            retain=False
        )
        self.adb_path = os.path.join(unzip_path, "adb.exe")
        self.connenct(self.connect_port)

    def connenct(self, port: int):
        cmd = [self.adb_path, "connect", f"127.0.0.1:{port}"]
        return self.run(cmd)

    async def execute_command_async(self, device_id, *command):
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, self.execute, device_id, command
            )

    def run(self, cmd: list[str]):
        return subprocess.check_output(
            cmd, startupinfo=self.startupinfo, stderr=subprocess.STDOUT
        )

    def execute(self, device_id: str, *command):
        cmd = [self.adb_path, "-s", device_id] + list(command)
        return subprocess.check_output(
            cmd, startupinfo=self.startupinfo, stderr=subprocess.STDOUT
        )

    async def get_devices_async(self):
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.executor, self.get_device_names)

    def get_device_names(self) -> list[str]:
        try:
            info = subprocess.check_output(
                [self.adb_path, "devices"], startupinfo=self.startupinfo
            )
            devices = list(
                map(lambda x: x[: x.find("\t")], info.decode().split("\r\n"))
            )[1:-2]
            return devices
        except:
            raise Exception("端口占用")

    @abstractmethod
    def get_device(self, device_id: str = None):
        if not device_id:
            device_id = self.get_device_names()[0]
        return Device(self.adb_path, device_id, self.max_workers)


class ScreenCut:
    def __init__(self, cx: int, cy: int, x: int, y: Optional[int] = None) -> None:
        self.cx = cx
        self.cy = cy
        self.x = x
        self.y = y

    def cut(self, w: int, h: int) -> tuple[int, int]:
        w = w // self.cx
        h = h // self.cy
        if not self.y:
            y = math.ceil(self.x / self.cx)
            x = self.x - (y - 1) * self.cx
            return ((w * x, h * y), (w * (x + 1), h * (y + 1)))
        else:
            return ((w * self.x, h * self.y), (w * (self.x + 1), h * (self.y + 1)))


class MatchTempleteDetailInfo:
    def __init__(
        self,
        baseGrayScreenshot: MatLike,
        grayScreenshot: MatLike,
        templeteSize: tuple[int, int],
        matchTempletePoints: list[tuple[int, ...]],
        matchTempleteCenterPoints: list[tuple[int, int]],
    ):
        self.baseGrayScreenshot = baseGrayScreenshot
        self.grayScreenshot = grayScreenshot
        self.templeteSize = templeteSize
        self.templeteWidth = templeteSize[0]
        self.templeteHeight = templeteSize[1]
        self.matchTempletePoints = matchTempletePoints
        self.matchTempletePointRanges = (
            list(map(lambda point: (point[0], point[-1]), matchTempletePoints))
            if matchTempletePoints
            else None
        )
        self.matchTempletePointRange = (
            self.matchTempletePointRanges[0] if self.matchTempletePointRanges else None
        )
        self.matchTempletePoint = (
            matchTempletePoints[0] if matchTempletePoints else None
        )
        self.matchTempleteCenterPoints = matchTempleteCenterPoints
        self.matchTempleteCenterPoint = (
            matchTempleteCenterPoints[0] if matchTempleteCenterPoints else None
        )
        self.matched = True if self.matchTempletePoint else False


class Device(Adb):
    size = None

    def __init__(self, adb_path: str, device_id: str, max_workers: int = 10):
        super().__init__(adb_path, max_workers)
        self.device_id = device_id
        self.size = self.getScreenSize()

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    async def screenshot_async(self):
        img_bytes = await self.execute_command_async(
            self.device_id, "exec-out", "screencap", "-p"
        )
        img = await self.convertImg_async(img_bytes)
        return img

    def screenshot(self):
        img_bytes = self.execute(self.device_id, "exec-out", "screencap", "-p")
        img = self.convertImg(img_bytes)
        return img

    def get_device(self):
        return self

    async def convertImg_async(self, img_bytes) -> MatLike:
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self.executor, self.convertImg, img_bytes)

    def launch_app(self, activity: str):
        return self.execute(self.device_id, "shell", "am", "start", activity)
    
    def get_app_pid(self, package_name: str) -> str:
        try:
            return self.execute(self.device_id, "shell", "pidof", package_name).decode().strip()
        except:
            # non-zero exit code 应用未运行
            return None

    def get_app_activity(self, package_name: str) -> str:
        running_str = self.execute(self.device_id, "shell", "dumpsys", "activity", "activities", "|", "grep", package_name).decode().strip()
        if running_str:
            lines = running_str.split("\n")
            for line in lines:
                if line.strip().startswith("mActivityComponent"):
                    activity = line.split("=")[-1].strip()
                    return activity
            return None
        else:
            return None

    def convertImg(self, img_bytes) -> MatLike:
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_ANYCOLOR)
        return img

    def toGrayImg(self, img: str | MatLike) -> MatLike:
        if isinstance(img, str):
            return cv2.imread(img, cv2.IMREAD_GRAYSCALE)
        elif isinstance(img, MatLike):
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            raise TypeError("图像类型错误")

    def toBase64Img(self, img: MatLike) -> str:
        """将MatLike对象转换为base64编码"""
        image_bytes = cv2.imencode('.png', img)[1].tobytes()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return base64_image

    def show_img(self, img: MatLike):
        cv2.namedWindow("test", cv2.WINDOW_NORMAL)
        cv2.imshow("test", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def grayScreenshot(self, cutPoints: tuple[tuple[int, int]] = None) -> MatLike:
        screenshot = self.screenshot()
        if cutPoints:
            screenshot = self.cutScreenshot(screenshot, cutPoints)
        return cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

    def cutScreenshot(self, screenshot: MatLike, cutPoints=None):
        if cutPoints:
            (x0, y0), (x1, y1) = cutPoints
            return screenshot[y0:y1, x0:x1]
        else:
            return screenshot

    def getScreenSize(self) -> tuple[int, int]:
        if self.size:
            return self.size
        else:
            msg = (
                subprocess.check_output(
                    [self.adb_path, "-s", self.device_id, "shell", "wm", "size"],
                    startupinfo=self.startupinfo,
                )
                .decode()
                .split(" ")[-1]
                .replace("\r\n", "")
            )
            w, h = map(int, msg.split("x"))
            self.size = (max(w, h), min(w, h))
        return self.size

    def click(self, x: int, y: int):
        cmd = [
            self.adb_path,
            "-s",
            self.device_id,
            "shell",
            "input",
            "tap",
            str(x),
            str(y),
        ]
        subprocess.run(cmd, startupinfo=self.startupinfo, check=True)

    def clickButton(
        self, button: str | MatLike, per: float = 0.9, grayScreenshot: MatLike = None
    ):
        locations = self.findImageCenterLocations(
            button, per=per, grayScreenshot=grayScreenshot
        )
        self.click(*locations[0])

    def findImageCenterLocations(
        self,
        button: str | MatLike,
        cutPoints: tuple[tuple[int, int]] = None,
        per: float = 0.9,
        grayScreenshot: MatLike = None,
    ) -> list[tuple[int, int]] | None:
        """返回图像中心点坐标"""
        match_result = self.findImageDetail(button, cutPoints, per, grayScreenshot)
        if match_result.matched:
            return match_result.matchTempleteCenterPoints
        else:
            return None

    def findImageDetail(
        self,
        button: str | MatLike,
        cutPoints=None,
        per: float = 0.9,
        grayScreenshot=None,
    ) -> MatchTempleteDetailInfo | None:
        """返回详细的匹配图像信息"""
        if cutPoints:
            x0, y0 = cutPoints[0]
        else:
            x0, y0 = 0, 0
        if grayScreenshot is None:
            baseGrayScreenshot = self.grayScreenshot()
            screenshot_gray = self.cutScreenshot(baseGrayScreenshot, cutPoints)
        else:
            baseGrayScreenshot = grayScreenshot
            screenshot_gray = self.cutScreenshot(grayScreenshot, cutPoints)
        if isinstance(button, str):
            template_gray = cv2.imread(button, cv2.IMREAD_GRAYSCALE)
        elif isinstance(button, MatLike):
            template_gray = button
        else:
            raise TypeError("匹配图像类型错误")
        matcher = cv2.matchTemplate(
            screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED
        )
        locations = np.where(matcher > per)
        templeteHeight, temleteWidth = template_gray.shape[0:2]
        if any(locations[0]):
            tmp_y, tmp_x = self._ceilPosition(locations)
            matchTempletePoints = [
                (
                    (x + x0, y + y0),
                    (x + x0 + temleteWidth, y + y0),
                    (x + x0, y + y0 + templeteHeight),
                    (x + x0 + temleteWidth, y + y0 + templeteHeight),
                )
                for x, y in zip(tmp_x, tmp_y)
            ]
            matchTempleteCenterPoints = [
                ((x + temleteWidth // 2) + x0, (y + templeteHeight // 2) + y0)
                for x, y in zip(tmp_x, tmp_y)
            ]
            return MatchTempleteDetailInfo(
                baseGrayScreenshot=baseGrayScreenshot,
                grayScreenshot=screenshot_gray,
                templeteSize=template_gray.shape[1::-1],
                matchTempletePoints=matchTempletePoints,
                matchTempleteCenterPoints=matchTempleteCenterPoints,
            )
        else:
            return MatchTempleteDetailInfo(
                baseGrayScreenshot=baseGrayScreenshot,
                grayScreenshot=screenshot_gray,
                templeteSize=template_gray.shape[1::-1],
                matchTempletePoints=None,
                matchTempleteCenterPoints=None,
            )

    def _ceilPosition(self, locations):
        tmp_y = [locations[0][0]]
        tmp_x = [locations[1][0]]
        for y, x in zip(*locations):
            if x - 10 >= tmp_x[-1]:
                tmp_x.append(x)
                tmp_y.append(y)
                continue
            if y - 10 >= tmp_y[-1]:
                tmp_x.append(x)
                tmp_y.append(y)
                continue
        return tmp_y, tmp_x
