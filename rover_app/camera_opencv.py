import cv2
import time
import threading
from picamera2 import Picamera2
from base_camera import BaseCamera
import numpy as np

class Camera(BaseCamera):
    picam2 = None

    def __init__(self):
        if Camera.picam2 is None:
            Camera.picam2 = Picamera2()
            config = Camera.picam2.create_preview_configuration(main={"size": (640, 480)})
            Camera.picam2.configure(config)
            Camera.picam2.start()
            time.sleep(1.0)
        super(Camera, self).__init__()

    @staticmethod
    def frames():
        while True:
            # picamera2からフレームをNumpy配列として取得
            img = Camera.picam2.capture_array()
            # BGR形式からJPEG形式にエンコード
            ret, buffer = cv2.imencode('.jpg', img)
            if not ret:
                continue
            # バイト列としてフレームを返す
            yield buffer.tobytes()

    def take_photo(self, filename):
        """
        現在のカメラフレームを静止画としてファイルに保存します。
        :param filename: 保存先のファイルパス
        :return: 成功した場合はTrue、失敗した場合はFalse
        """
        try:
            # capture_array()で現在のフレームを取得
            frame = self.picam2.capture_array()
            # OpenCVはBGRフォーマットを標準とするため、RGBからBGRに変換
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # ファイルに書き出す
            cv2.imwrite(filename, frame_bgr)
            print(f"Photo saved successfully: {filename}")
            return True
        except Exception as e:
            print(f"Error saving photo: {e}")
            return False
