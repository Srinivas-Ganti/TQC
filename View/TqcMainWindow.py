
import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)
sys.path.append(uiDir)

from Model.TheaQC import *




class TqcMainWindow(QWidget):

    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()

    def initUI(self):

        uic.loadUi("C:/Users/TeraSmart/Documents/API_MenloSystem/RamGlobalSystem/TQC/View/Designer/MainWindow.ui", self)
        self.setWindowTitle("THEA QC v1.05")
        self.livePlot.setLabel('left', 'Transmission Intensity (dB)')
        self.livePlot.setLabel('bottom', 'Frequency (THz)')
        self.livePlot.setTitle("""Live QC""", color = 'g', size = "45 pt")   
        self.livePlot.showGrid(x = True, y = True)
        self.livePlot.setMouseTracking(True)
        
        self.textbox.setReadOnly(True)
        # self.progAvg.setValue(self.avgProgVal)
        # self.progTimelapse.setValue(self.tlapseProgVal)



if __name__ == '__main__':
    
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, '../Model/theaConfig.yml')
    win = TqcMainWindow()
    win.show()

    with loop:
        sys.exit(loop.run_forever())


    

