import sys, re, threading, time
import cv2
import numpy as np
import easyocr
from PyQt5 import QtWidgets, QtCore, QtGui

def has_chinese(text):
    return re.search(r'[\u4e00-\u9fff]', text) is not None

class Overlay(QtWidgets.QWidget):
    def __init__(self, block_size=15):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint |
                            QtCore.Qt.FramelessWindowHint |
                            QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.block_size = block_size
        self.target_rect = None
        self.current_rect = None

    def set_target_rect(self, rect):
        self.target_rect = rect
        if self.current_rect is None:
            self.current_rect = rect
        self.update()

    def paintEvent(self, event):
        if not self.current_rect:
            return
        # 平滑过渡
        cur = self.current_rect
        tgt = self.target_rect
        if tgt:
            new_x = int(cur.x() + (tgt.x() - cur.x()) * 0.3)
            new_y = int(cur.y() + (tgt.y() - cur.y()) * 0.3)
            new_w = int(cur.width() + (tgt.width() - cur.width()) * 0.3)
            new_h = int(cur.height() + (tgt.height() - cur.height()) * 0.3)
            self.current_rect = QtCore.QRect(new_x, new_y, new_w, new_h)

        painter = QtGui.QPainter(self)
        screen = QtWidgets.QApplication.primaryScreen()
        pixmap = screen.grabWindow(0, self.current_rect.x(), self.current_rect.y(),
                                   self.current_rect.width(), self.current_rect.height())
        image = pixmap.toImage()
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        arr = np.array(ptr).reshape(image.height(), image.width(), 4)
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

        # 像素化处理
        h, w = arr.shape[:2]
        temp = cv2.resize(arr, (max(1, w // self.block_size), max(1, h // self.block_size)),
                          interpolation=cv2.INTER_LINEAR)
        pix = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)
        qimg = QtGui.QImage(pix.data, pix.shape[1], pix.shape[0],
                            pix.strides[0], QtGui.QImage.Format_BGR888)
        painter.drawImage(self.current_rect, qimg)

class SubtitleMaskApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动字幕遮罩（中文，EasyOCR）")
        self.overlay = Overlay()
        self.ocr = easyocr.Reader(['ch_sim','en'])  # 支持中文简体和英文
        self.running = False

        self.block_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.block_slider.setRange(5, 50)
        self.block_slider.setValue(15)
        self.block_slider.valueChanged.connect(self.change_block)

        start_btn = QtWidgets.QPushButton("启动自动遮罩")
        stop_btn = QtWidgets.QPushButton("关闭遮罩")

        start_btn.clicked.connect(self.start)
        stop_btn.clicked.connect(self.stop)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("像素化强度"))
        layout.addWidget(self.block_slider)
        layout.addWidget(start_btn)
        layout.addWidget(stop_btn)
        self.setLayout(layout)

    def change_block(self, val):
        self.overlay.block_size = val

    def start(self):
        self.running = True
        self.overlay.show()
        threading.Thread(target=self.detect_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.overlay.close()

    def detect_loop(self):
        screen = QtWidgets.QApplication.primaryScreen()
        last_rect = None
        while self.running:
            geo = screen.geometry()
            h, w = geo.height(), geo.width()
            roi_h = int(h * 0.3)  # 底部30%
            pixmap = screen.grabWindow(0, 0, h - roi_h, w, roi_h)
            image = pixmap.toImage()
            ptr = image.bits()
            ptr.setsize(image.byteCount())
            arr = np.array(ptr).reshape(image.height(), image.width(), 4)
            arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

            result = self.ocr.readtext(arr)
            rect = None
            if result:
                x_min, y_min, x_max, y_max = None, None, None, None
                for (bbox, text, score) in result:
                    if score > 0.6 and has_chinese(text):
                        (x1,y1),(x2,y2),(x3,y3),(x4,y4) = bbox
                        x1,x2,x3,x4 = int(x1),int(x2),int(x3),int(x4)
                        y1,y2,y3,y4 = int(y1),int(y2),int(y3),int(y4)
                        x_left = min(x1,x2,x3,x4)
                        x_right = max(x1,x2,x3,x4)
                        y_top = min(y1,y2,y3,y4)
                        y_bottom = max(y1,y2,y3,y4)
                        # 转换到全屏坐标
                        x, y, w_box, h_box = x_left, h - roi_h + y_top, x_right - x_left, y_bottom - y_top
                        if x_min is None:
                            x_min, y_min, x_max, y_max = x, y, x+w_box, y+h_box
                        else:
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x+w_box)
                            y_max = max(y_max, y+h_box)
                if x_min is not None:
                    pad = 10
                    rect = QtCore.QRect(x_min-pad, y_min-pad, (x_max-x_min)+2*pad, (y_max-y_min)+2*pad)

            if rect:
                last_rect = rect
            elif last_rect:
                rect = last_rect  # 使用缓存结果

            if rect:
                self.overlay.set_target_rect(rect)

            time.sleep(0.4)  # 每秒检测约 2–3 次
            self.overlay.update()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = SubtitleMaskApp()
    panel.show()
    sys.exit(app.exec_())
