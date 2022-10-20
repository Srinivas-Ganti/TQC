import sys
import random
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

class MyApp(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        ## Creating the Widgets and Layouts
        self.plot_widget = pg.PlotWidget()
        self.layout = QtGui.QVBoxLayout()
        self.sbutton = QtGui.QPushButton("Start / Continue")
        self.ebutton = QtGui.QPushButton("Stop")
        self.timer = pg.QtCore.QTimer()
        self.scroll = QtGui.QScrollBar(QtCore.Qt.Horizontal)
        ## Creating the variables and constants
        self.data = [[0], [random.randint(0,9)]]  ## [xVal, yVal] to create less variables
        self.plot_item = self.plot_widget.plot(*self.data)
        self.plot_widget.setYRange(0, 10)
        self.xTime = self.genTime()
        self.vsize = 10
        self.psize = 30
        ## Building the Widget
        self.setLayout(self.layout)
        self.layout.addWidget(self.sbutton)
        self.layout.addWidget(self.ebutton)
        self.layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.scroll)
        ## Changing some properties of the widgets
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.ebutton.setEnabled(False)
        self.scroll.setEnabled(False)
        self.scroll.setMaximum(self.psize-self.vsize)
        self.scroll.setValue(self.psize-self.vsize)
        ## Coneccting the signals
        self.sbutton.clicked.connect(self.start)
        self.ebutton.clicked.connect(self.stop)
        self.timer.timeout.connect(self.update)
        self.scroll.valueChanged.connect(self.upd_scroll)

    def genTime(self):  # used to generate time
        t = 0
        while True:
            t += np.random.random_sample()
            yield t
            t = np.ceil(t)

    def upd_scroll(self):
        val = self.scroll.value()
        xmax = np.ceil(self.data[0][-1+self.vsize-self.psize+val])-1
        xmin = xmax-self.vsize
        self.plot_widget.setXRange(xmin, xmax)

    def update(self):
        num = len(self.data[0])
        if num <= self.psize:
            self.plot_item.setData(*self.data)
        else:
            self.plot_item.setData(
                self.data[0][-self.psize:],
                self.data[1][-self.psize:]
            )

        if num == self.vsize:
            self.scroll.setEnabled(True)
        self.data[0].append(next(self.xTime))
        self.data[1].append(random.randint(0,9))
        if num > self.vsize :
            self.upd_scroll()
     
    def start(self):
        self.sbutton.setEnabled(False)
        self.ebutton.setEnabled(True)
        self.timer.start(100)

    def stop(self):
        self.sbutton.setEnabled(True)
        self.ebutton.setEnabled(False)
        self.timer.stop()
        self.upd_scroll()
        
    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())