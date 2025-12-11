import sys, re, threading, time
import cv2
import numpy as np
import easyocr
import pygetwindow as gw
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
        self.browser_hwnd = None

    def set_target_rect(self, rect):
        self.target_rect = rect
        if self.current_rect is None:
            self.current_rect = rect
        self.update()

    def paintEvent(self, event):
        if not self.current_rect or not self.browser_hwnd:
            return
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
        pixmap = screen.grabWindow(self.browser_hwnd,
                                   self.current_rect.x(), self.current_rect.y(),
                                   self.current_rect.width(), self.current_rect.height())
        image = pixmap.toImage()
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        arr = np.array(ptr).reshape(image.height(), image.width(), 4)
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

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
        self.setWindowTitle("网页视频字幕遮罩（中文）")
        self.overlay = Overlay()
        self.ocr = easyocr.Reader(['ch_sim','en'])
        self.running = False
        self.browser_hwnd = None

        self.block_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.block_slider.setRange(5, 50)
        self.block_slider.setValue(15)
        self.block_slider.valueChanged.connect(self.change_block)

        self.site_input = QtWidgets.QLineEdit()
        self.site_input.setPlaceholderText("请输入网站或浏览器标题关键字，例如 Netflix 或 Edge")

        start_btn = QtWidgets.QPushButton("启动自动遮罩")
        stop_btn = QtWidgets.QPushButton("关闭遮罩")

        start_btn.clicked.connect(self.start)
        stop_btn.clicked.connect(self.stop)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("像素化强度"))
        layout.addWidget(self.block_slider)
        layout.addWidget(QtWidgets.QLabel("浏览器窗口关键字"))
        layout.addWidget(self.site_input)
        layout.addWidget(start_btn)
        layout.addWidget(stop_btn)
        self.setLayout(layout)

    def change_block(self, val):
        self.overlay.block_size = val

    def start(self):
        keyword = self.site_input.text().strip()
        if not keyword:
            print("请输入关键字")
            return
        windows = gw.getWindowsWithTitle(keyword)
        if not windows:
            print(f"未找到包含关键字 {keyword} 的窗口")
            return
        self.browser_hwnd = windows[0]._hWnd
        self.overlay.browser_hwnd = self.browser_hwnd

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
            win = gw.getWindowsWithTitle(self.site_input.text().strip())[0]
            w, h = win.width, win.height
            roi_h = int(h * 0.3)
            pixmap = screen.grabWindow(self.browser_hwnd, 0, h - roi_h, w, roi_h)
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
                        xs = [int(pt[0]) for pt in bbox]
                        ys = [int(pt[1]) for pt in bbox]
                        x1, x2 = min(xs), max(xs)
                        y1, y2 = min(ys), max(ys)
                        x, y, w_box, h_box = x1, h - roi_h + y1, x2 - x1, y2 - y1
                        if x_min is None:
                            x_min, y_min, x_max, y_max = x, y, x+w_box, y+h_box
                        else:
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x+w_box)
                            y_max = max(y_max, y+h_box)
                if x_min is not None:
                    pad = 10
                    rect = QtCore.QRect(x_min-pad, y_min-pad,
                                        (x_max-x_min)+2*pad, (y_max-y_min)+2*pad)

            if rect:
                last_rect = rect
            elif last_rect:
                rect = last_rect

            if rect:
                self.overlay.set_target_rect(rect)

            time.sleep(0.4)
            self.overlay.update()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = SubtitleMaskApp()
    panel.show()
    sys.exit(app.exec_())
