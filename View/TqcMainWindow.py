
import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)
sys.path.append(os.path.join(viewDir, "Icons"))
sys.path.append(uiDir)

from Model.TheaQC import *




class TqcMainWindow(QWidget):

    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()


    def initAttribs(self):

        """
            Initialise class attributes for QC, timelapse application with default values.
        """

        self.height = 900
        self.width = 720
        self.left = 10
        self.top = 40      
        self.setGeometry(self.left, self.top, self.width, self.height)   

        self.livePlot.setXRange(0, 5.3, padding = 0)
        self.livePlot.setYRange(-250, -90, padding = 0)
        self.colorLivePulse = (66,155,184, 145)
        self.colorlivePulseBackground = (66,155,184,145)
        self.colorAvgPulse = (200, 200, 200, 160)
        self.colorstdRef = (160,150,27,140)
        self.colorPass = (125,245,0,190)
        self.colorFail = (255,0,0,190)
        self.livePlotLineWidth = 1
        self.averagePlotLineWidth = 1.5
    
        self.lEditTdsStart.setAlignment(Qt.AlignCenter) 
        self.lEditTdsEnd.setAlignment(Qt.AlignCenter) 
        self.lEditTdsAvgs.setAlignment(Qt.AlignCenter) 
        self.lEditInterval.setAlignment(Qt.AlignCenter) 
        self.lEditRepeatNum.setAlignment(Qt.AlignCenter) 
        self.lEditWaferId.setAlignment(Qt.AlignCenter) 
        self.lEditSensorId.setAlignment(Qt.AlignCenter) 


    def loadIcons(self):

        self.lblQcStatusIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblQcStatusIcon.setScaledContents(True)
        self.lblClassResultIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblClassResultIcon.setScaledContents(True) 


    def initUI(self):

        uic.loadUi("C:/Users/TeraSmart/Documents/API_MenloSystem/RamGlobalSystem/TQC/View/Designer/MainWindow.ui", self)
        self.setWindowTitle("THEA QC v1.05")
        self.disableButtons()
        self.loadIcons()
        self.livePlot.setLabel('left', 'Transmission Intensity (dB)')
        self.livePlot.setLabel('bottom', 'Frequency (THz)')
        self.livePlot.setTitle("""Live QC""", color = 'g', size = "45 pt")   
        self.livePlot.showGrid(x = True, y = True)
        self.livePlot.setMouseTracking(True)
        
        self.textbox.setReadOnly(True)
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.progTimelapse.setValue(self.experiment.tlapseProgVal)


    def disableButtons(self):

        """
            Disable GUI buttons from user interactions.
        """

        self.btnStart.setEnabled(False)
        self.btnResetAvg.setEnabled(False)
        self.btnStartAveraging.setEnabled(False)
        self.btnStartTimelapse.setEnabled(False)
        self.btnStartQC.setEnabled(False)
        self.btnFinishQC.setEnabled(False)
        self.btnNewStdRef.setEnabled(False)


    def enableButtons(self):

        """
            Enable GUI buttons for user interaction
        """

        self.btnStartTimelapse.setEnabled(True)
        self.btnStart.setEnabled(True)
        self.btnStop.setEnabled(True)
        self.btnStartQC.setEnabled(True)
        self.btnStartAveraging.setEnabled(True)
        self.btnResetAvg.setEnabled(True)


    def message(self, msgStrPattern):

        """
            Prints messages in the GUI Output textbox
        """

        self.textbox.appendPlainText(f"{msgStrPattern}")







#******************************************************************************************
if __name__ == '__main__':
    
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, '../Model/theaConfig.yml')
    win = TqcMainWindow(tqc)
    win.show()

    with loop:
        sys.exit(loop.run_forever())


    

