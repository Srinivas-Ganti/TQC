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
from Model import ur

from pint.errors import *

class TqcMainWindow(QWidget):

    dataUpdateReady = pyqtSignal(object)

    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()


    def connectEvents(self):
        
        """
            Connect GUI object and validator signals to respective methods.
        """
        
        self.btnStart.clicked.connect(self.experiment.device.start)
        self.btnStop.clicked.connect(self.experiment.device.stop) 
        self.livePlot.scene().sigMouseMoved.connect(self.mouseMoved)
        self.btnResetAvg.clicked.connect(self.experiment.device.resetAveraging)
        # self.btnStartAveraging.clicked.connect(self.startAveraging)
        # self.btnStartTimelapse.clicked.connect(self.startTimelapse)
        # self.btnStartQC.clicked.connect(self.startQC)
        # self.btnFinishQC.clicked.connect(self.finishQC)
        # self.btnNewStdRef.clicked.connect(self.measureStandardRef)
        self.dataUpdateReady.connect(self.updatePlot)
        # self.sensorUpdateReady.connect(self.checkNextSensor)

        self.lEditTdsStart.editingFinished.connect(self.validateEditStart)
        self.lEditTdsEnd.setReadOnly(True)
        self.lEditTdsAvgs.editingFinished.connect(self.validateEditAverages)
        self.lEditInterval.editingFinished.connect(self.validateEditInterval)
        self.lEditRepeatNum.editingFinished.connect(self.validateEditRepeats) 
        self.lEditWaferId.editingFinished.connect(self.validateEditWaferId)
        self.lEditSensorId.editingFinished.connect(self.validateEditSensorId)

 
    def mouseMoved(self, evt):

        """
            Track mouse movement on data plot in plot units (arb.dB vs THz)

            :type evt: pyqtSignal 
            :param evt: Emitted when the mouse cursor moves over the scene. Contains scene cooridinates of the mouse cursor.

        """

        pos = evt
        if self.livePlot.sceneBoundingRect().contains(pos):
            mousePoint = self.livePlot.plotItem.vb.mapSceneToView(pos)
            x = float("{0:.3f}".format(mousePoint.x()))
            y = float("{0:.3f}".format(mousePoint.y()))
            self.xyLabel.setText(f"last cursor position: {x, y}")

         
    def plot(self, x, y):

        """
            Plot data on existing plot widget.

            :type x: numpy array
            :param x: frequency axis data
            :type y: numpy array
            :param y: Pulse FFT data.

            :return: plot data.
            :rtype: PlotWidget.plot  

        """   

        return self.livePlot.plot(x,y)


    def updatePlot(self, avgPulseFft):
        
        """
            Update plot items.

            :type avgPulseFft: numpy array
            :param avgPulseFft: averaged value of FFT pulse (in progress)
        """

        self.experiment.plotDataContainer['currentAveragePulseFft'].curve.setData(self.experiment.freq, 20*np.log(np.abs(avgPulseFft)))


    def validateEditStart(self):

        """
            Validate user input for Start time
        """

        validationRule = QDoubleValidator(-420,420,3)
        print(validationRule.validate(self.lEditTdsStart.text(),420))
        if validationRule.validate(self.lEditTdsStart.text(),
                                   420)[0] == QValidator.Acceptable:
            print("TDS START TIME ACCEPTED")
            self.experiment.startOk = True
            self.experiment.startTime = float(self.lEditTdsStart.text())
            
            self.experiment.endTime = float(self.lEditTdsStart.text()) + self.experiment.TdsWin
            self.lEditTdsEnd.setText(str(self.experiment.endTime))
            self.experiment.endOk = True
            self.experiment.tdsParams['start'] = self.experiment.startTime
            self.experiment.tdsParams['end'] = self.experiment.endTime
            print(f"End time is set to be {self.experiment.TdsWin} ps after THz pulse start at {self.experiment.startTime} ps")
            print("TDS END TIME ACCEPTED")
        else:
            print("[ERROR] InvalidInput: Setting default config value")
            self.experiment.startOk = False
            self.lEditTdsStart.setText(str(self.experiment.config['TScan']['begin']))


    def validateDefaultInputs(self):
        
        """
            Validate GUI input parameters on startup
        """
        self.lEditTdsStart.setText(str(self.experiment.config['TScan']['begin']))
        self.lEditTdsStart.editingFinished.emit()
        self.lEditTdsAvgs.setText(str(self.experiment.config['TScan']['numAvgs']))
        self.lEditTdsAvgs.editingFinished.emit()
        self.loadTDSParams()
        print("> [SCANCONTROL] Setting TDS parameters: Done\n")        
        self.lEditInterval.setText(str(self.experiment.config['Timelapse']['interval']))
        self.lEditInterval.editingFinished.emit()
        self.lEditRepeatNum.setText(str(self.experiment.config['Timelapse']['repeats']))
        self.lEditRepeatNum.editingFinished.emit()
        self.loadTimelapseParams()
        print("> [TIMELAPSE] Setting Timelapse parameters: Done\n")
        self.chipsPerWafer = int(self.experiment.config['QC']['chipsPerWafer'])
        self.lEditWaferId.setText(str(self.experiment.config['QC']['waferId']))
        self.lEditWaferId.editingFinished.emit()
        self.loadQC()
        self.lEditSensorId.setText(str(self.experiment.config['QC']['sensorId']))
        self.lEditSensorId.editingFinished.emit() 
        


    def loadTDSParams(self):

        """
            Load the TDS measurement parameters related to pulse duration and timing, required number of averages from config file.
        """

        if (self.experiment.startOk and self.experiment.endOk and self.experiment.avgsOk):
            print("TDS Inputs accepted")
            self.experiment.device.setBegin(self.experiment.startTime)
            self.experiment.device.setEnd(self.experiment.endTime)
            self.experiment.device.setDesiredAverages(self.experiment.numAvgs)
            self.btnStart.setEnabled(True)
            self.btnStartAveraging.setEnabled(True)
            self.btnResetAvg.setEnabled(True)


    def loadQC(self):

        """
            Load QC parameters from config file and validate inputs
        """

        self.experiment.loadQcConfig()
        if self.experiment.waferIdOk and self.experiment.sensorIdOk and self.experiment.keepRunning:
            self.btnStartQC.setEnabled(True)
        else:
            self.btnStartQC.setEnabled(False)
    

    def loadTimelapseParams(self):

        """
            Load timelapse measurement parameters related to interval and duration.
        """


        if self.experiment.intervalOK and self.experiment.repeatsOk:
            self.btnStartTimelapse.setEnabled(True)
            self.lblTlapseStatus.setText("Timelapse: Ready")
        else:
            self.btnStartTimelapse.setEnabled(False)
            self.lblTlapseStatus.setText("Timelapse: Not available")

    
    def validateEditAverages(self):

        """
            Validate user input for required number of averages.
        """
                
        validationRule = QIntValidator(1,2000)
        print(validationRule.validate(self.lEditTdsAvgs.text(),2000))
        if validationRule.validate(self.lEditTdsAvgs.text(),
                                   2000)[0] == QValidator.Acceptable:
            print("TDS AVGS ACCEPTED")
            self.experiment.avgsOk = True
            self.experiment.numAvgs = int(self.lEditTdsAvgs.text())
            self.experiment.tdsParams['numAvgs'] = self.experiment.numAvgs
            self.experiment.device.setDesiredAverages(self.experiment.tdsParams['numAvgs'])
        else:
            print("[ERROR] InvalidInput: Setting default config value")
            self.experiment.avgsOK = False
            self.lEditTdsAvgs.setText(str(self.experiment.config['TScan']['numAvgs']))
            self.experiment.device.setDesiredAverages(self.experiment.config['TScan']['numAvgs'])

        
    def validateEditInterval(self):
        
        """
            Validate user input for timelapse interval - check units for consistency
        """

        try:
            self.experiment.intervalOk = False
            isinstance(ur(self.lEditInterval.text()), ur.Quantity)
            interval = ur(self.lEditInterval.text())
            if isinstance(interval, int):
                interval = interval*ur("s")

            if interval.units in ["second", "minute", "hour"]: 
                print("Interval is a valid time input")
                print("Timelapse interval ACCEPTED")
                self.experiment.interval = interval.m_as("second")
                print(f"Interval is set to {self.experiment.interval} seconds")
            else:
                print("Interval units are not valid time inputs, Setting default config values")
                print("Enter valid units, for example: '0.5hour', '420ms', '5min' . . . ")
                self.lEditInterval.setText(str(self.experiment.config['Timelapse']['interval']))
                self.interval = ur(str(self.experiment.config['Timelapse']['interval'])).m_as("second")
            self.experiment.intervalOK = True
        except UndefinedUnitError:
            self.experiment.intervalOK = False
            print("Undefined / Incorrect units. Setting default config value")
            self.lEditInterval.setText(str(self.experiment.config['Timelapse']['interval']))
            self.experiment.interval = ur(str(self.experiment.config['Timelapse']['interval']))
            self.experiment.intervalOK = True
            
    
    def validateEditRepeats(self):
        
        """
            Validate user input for timelapse repeats - check units and dimensions for consistency
        """

        self.experiment.repeatsOk = False
        validationRule = QIntValidator(1,2000)
            
        print(validationRule.validate(self.lEditRepeatNum.text(),2000))
        if validationRule.validate(self.lEditRepeatNum.text(),
                                   2000)[0] == QValidator.Acceptable:
            print("Timelapse frames count ACCEPTED")
            self.experiment.repeatNum = int(self.lEditRepeatNum.text())
            
        else:
            print("Repeats must be non zero integers")
            
            self.experiment.repeatNum = int(self.experiment.config['Timelapse']['repeats'])
            print(f"Setting default config value: {self.experiment.repeatNum} frames")
            self.lEditRepeatNum.setText(str(self.experiment.repeatNum))
        self.experiment.repeatsOk = True


    def validateEditWaferId(self):

        """
            Validate user input for QC wafer ID - check naming format for consistency
        """

        self.experiment.waferIdOk = False
        wId = self.lEditWaferId.text()
        
        if wId.startswith("W"):
            try:    
                wnum = int(wId.split("W")[1])
                print(f"Wafer ID ACCEPTED: W{wnum}")
                self.experiment.waferId = f"W{wnum}"
            except ValueError:
                print("Wafer ID must follow the pattern 'W<integer>'")
                print("Setting default config value")
                self.lEditWaferId.setText(self.experiment.config['QC']['waferId'])
                self.experiment.waferId = self.experiment.config['QC']['waferId']
        else:
            print("Wafer ID must follow the pattern 'W<integer>'")
            print("Setting default config value")
            self.lEditWaferId.setText(self.experiment.config['QC']['waferId'])
            self.experiment.waferId = self.experiment.config['QC']['waferId']
        self.experiment.waferIdOk = True
        if not self.experiment.waferIdOk:
            self.btnStartQC.setEnabled(False)
        

    def validateEditSensorId(self):
                
        """
            Validate user input for QC/timelapse sensor ID.
        """

        
        self.experiment.sensorIdOk = False
        validationRule = QIntValidator(1,self.experiment.chipsPerWafer)                         
        print(validationRule.validate(self.lEditSensorId.text(),self.experiment.chipsPerWafer))
        if validationRule.validate(self.lEditSensorId.text(),
                                  self.chipsPerWafer)[0] == QValidator.Acceptable:
            print("Sensor ID ACCEPTED")
            self.experiment.sensorId =  int(self.lEditSensorId.text())
        else:
            print(f"Sensor ID must be non zero integer in range of (1 , {self.experiment.chipsPerWafer})")
            
            self.experiment.sensorId = int(self.experiment.config['QC']['sensorId'])
            print(f"Setting default config value: Sensor ID is set to {self.experiment.sensorId}")
            self.lEditSensorId.setText(str(self.experiment.sensorId))
        self.experiment.sensorIdOk = True
        if not self.experiment.sensorIdOk:
            self.btnStartQC.setEnabled(False)


    def initAttribs(self):

        """
            Initialise class attributes for QC, timelapse application with default values.
        """

        self.height = 900
        self.width = 750
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

        uic.loadUi("../View/Designer/MainWindow.ui", self)
        self.setWindowTitle("THEA QC v1.05")
        self.disableButtons()
        self.loadIcons()
        self.initAttribs()
        self.connectEvents()
        self.validateDefaultInputs()

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


    

