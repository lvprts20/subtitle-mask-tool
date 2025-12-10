import sys
from PyQt5 import QtWidgets, QtCore, QtGui

class Overlay(QtWidgets.QWidget):
    def __init__(self, x, y, w, h, block_size=15):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint |
                            QtCore.Qt.FramelessWindowHint |
                            QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(x, y, w, h)
        self.block_size = block_size
        self.setMouseTracking(True)
        self.dragging = False
        self.resizing = False
        self.resize_margin = 10

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        screen = QtWidgets.QApplication.primaryScreen()
        pixmap = screen.grabWindow(0, self.x(), self.y(), self.width(), self.height())
        image = pixmap.toImage()
        small = image.scaled(max(1, self.width() // self.block_size),
                             max(1, self.height() // self.block_size),
                             QtCore.Qt.IgnoreAspectRatio,
                             QtCore.Qt.FastTransformation)
        pixelated = small.scaled(self.width(), self.height(),
                                 QtCore.Qt.IgnoreAspectRatio,
                                 QtCore.Qt.FastTransformation)
        painter.drawImage(rect, pixelated)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.is_on_edge(event.pos()):
                self.resizing = True
            else:
                self.dragging = True
            self.drag_start = event.globalPos()
            self.start_geometry = self.geometry()

    def mouseMoveEvent(self, event):
        if self.dragging or self.resizing:
            delta = event.globalPos() - self.drag_start
            geom = self.start_geometry
            if self.dragging:
                self.setGeometry(geom.x() + delta.x(), geom.y() + delta.y(),
                                 geom.width(), geom.height())
            elif self.resizing:
                self.setGeometry(geom.x(), geom.y(),
                                 max(20, geom.width() + delta.x()),
                                 max(20, geom.height() + delta.y()))
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False

    def is_on_edge(self, pos):
        return (abs(pos.x() - self.width()) < self.resize_margin or
                abs(pos.y() - self.height()) < self.resize_margin)

class RegionSelector(QtWidgets.QWidget):
    regionSelected = QtCore.pyqtSignal(int, int, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint |
                            QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowState(QtCore.Qt.WindowFullScreen)
        self.start = None
        self.end = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.start = event.pos()
            self.end = None
            self.update()

    def mouseMoveEvent(self, event):
        if self.start:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.start and self.end:
            x1, y1 = self.start.x(), self.start.y()
            x2, y2 = self.end.x(), self.end.y()
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            self.regionSelected.emit(x, y, w, h)
            self.close()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 60))
        if self.start and self.end:
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0), 2))
            painter.drawRect(QtCore.QRect(self.start, self.end))

class ControlPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("字幕像素化遮罩")
        self.overlay = None
        self.region = None

        self.block_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.block_slider.setRange(5, 60)
        self.block_slider.setValue(18)

        select_btn = QtWidgets.QPushButton("用鼠标选择区域")
        start_btn = QtWidgets.QPushButton("启动遮罩")
        stop_btn = QtWidgets.QPushButton("关闭遮罩")

        select_btn.clicked.connect(self.select_region)
        start_btn.clicked.connect(self.start_overlay)
        stop_btn.clicked.connect(self.stop_overlay)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("像素化强度（块大小）"))
        layout.addWidget(self.block_slider)
        layout.addWidget(select_btn)
        layout.addWidget(start_btn)
        layout.addWidget(stop_btn)
        self.setLayout(layout)
        self.resize(300, 180)

    def select_region(self):
        self.selector = RegionSelector()
        self.selector.regionSelected.connect(self.set_region)
        self.selector.show()

    def set_region(self, x, y, w, h):
        self.region = (x, y, w, h)

    def start_overlay(self):
        if self.region:
            x, y, w, h = self.region
            block_size = self.block_slider.value()
            if self.overlay:
                self.overlay.close()
            self.overlay = Overlay(x, y, w, h, block_size)
            self.overlay.show()

    def stop_overlay(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec_())
