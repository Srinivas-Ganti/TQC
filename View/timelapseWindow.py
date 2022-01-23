import sys
import os

from numpy.lib.arraysetops import isin

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")
configDir = None

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)

sys.path.append(uiDir)

from Model.theaTimelapse import *
from Model import ur

from pint.errors import *

class TimelapseMainWindow(QMainWindow):

    dataUpdateReady = pyqtSignal(object)


    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()
        
    
    def connectEvents(self):
        
        """
            Connect GUI object and validator signals to respective methods.
        """
      
        self.experiment.device.scanControl.statusChanged.connect(self._statusChanged)
        
        self.experiment.device.pulseReady.connect(self.processPulses)
        self.experiment.device.pulseReady.connect(self.experiment.processPulses)
        self.experiment.device.dataUpdateReady.connect(self.experiment.device.done)
        self.experiment.timelapseFinished.connect(self.enableAnimation)
        self.btnStart.clicked.connect(self.experiment.timelapseStart)
        self.btnStart.clicked.connect(self.disableLEdit)
        self.btnStop.clicked.connect(self.experiment.device.stop) 
        self.btnStop.clicked.connect(self.stop) 
        self.btnStop.clicked.connect(self.experiment.cancelTasks)
     
        self.lEditTdsStart.editingFinished.connect(self.validateEditStart)
        
        self.lEditTdsAvgs.editingFinished.connect(self.validateEditAverages)

        self.lEditFrames.editingFinished.connect(self.validateEditFrames)
        self.lEditInterval.editingFinished.connect(self.validateInterval)
        self.lEditTdsAvgs.textChanged.connect(self.avgsChanged)
        self.livePlot.scene().sigMouseMoved.connect(self.mouseMoved)
            

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



    def disableLEdit(self):

        """"Disable line edit fields during acquisition"""

        self.lEditTdsStart.setReadOnly(True)
        self.lEditTdsAvgs.setReadOnly(True)
        self.lEditFrames.setReadOnly(True)
        self.lEditInterval.setReadOnly(True)
    


    def enableLEdit(self):

        """"Enable line edit fields when ScanControl has stopped"""

        self.lEditTdsStart.setReadOnly(False)
        self.lEditTdsAvgs.setReadOnly(False)
        self.lEditFrames.setReadOnly(False)
        self.lEditInterval.setReadOnly(False)
      


    def avgsChanged(self):

        """"Terminal Message"""

        print(f"Experiment averages changed to : {self.experiment.numAvgs}")
        

    def validateInterval(self):

        """
            Validate user input for Requested Interval of the timelapse
        """ 

        try:
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
            self.experiment.intervalOk = True
        except UndefinedUnitError:
            self.experiment.intervalOk = False
            print("Undefined / Incorrect units. Setting default config value")
            self.lEditInterval.setText(str(self.experiment.config['Timelapse']['interval']))
            self.interval = ur(str(self.experiment.config['Timelapse']['interval']))
            self.experiment.intervalOk = True
        

    def validateEditFrames(self):

        
        """
            Validate user input for Requested Frames of the timelapse
        """ 
        
        validationRule = QIntValidator(0,self.experiment.maxFrames)
        print(validationRule.validate(self.lEditFrames.text(),self.experiment.maxFrames))
        if validationRule.validate(self.lEditFrames.text(),
                                   self.experiment.maxFrames)[0] == QValidator.Acceptable:
            print(f"TIMELAPSE FRAMES ACCEPTED")
            self.experiment.framesOk = True
            self.experiment.numRequestedFrames = int(self.lEditFrames.text())
        else:
            print(f"> [WARNING]:Requested frames exceed allowed storage of {self.experiment.maxStorage}")
            print(f"Setting frames to default maximum: {self.experiment.maxFrames} ")
            self.experiment.numRequestedFrames = self.experiment.maxFrames
            self.lEditFrames.setText(str(self.experiment.numRequestedFrames))


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
        self.lEditFrames.setText(str(self.experiment.config['Timelapse']['frames']))
        self.lEditFrames.editingFinished.emit()
        self.lEditInterval.setText(str(self.experiment.config['Timelapse']['interval']))
        self.lEditInterval.editingFinished.emit()
        self.loadTDSParams()
    
        print("> [SCANCONTROL] Setting TDS parameters: Done\n")        


    def loadTDSParams(self):

        """
            Load the TDS measurement parameters related to pulse duration and timing, required number of averages from config file.
        """

        if (self.experiment.startOk and self.experiment.endOk and self.experiment.avgsOk and self.experiment.intervalOk and self.experiment.framesOk):
            print("TDS Inputs accepted")
            self.experiment.device.setBegin(self.experiment.startTime)
            self.experiment.device.setEnd(self.experiment.endTime)
            self.btnStart.setEnabled(True)

    
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
            
        else:
            print("[ERROR] InvalidInput: Setting default config value")
            self.experiment.avgsOK = False
            self.lEditTdsAvgs.setText(str(self.experiment.config['TScan']['numAvgs']))


    def initAttribs(self):

        """
            Initialise class attributes for Timelapse application with default values.
        """

        self.height = 950
        self.width = 570
        self.left = 10
        self.top = 40      
        self.setGeometry(self.left, self.top, self.width, self.height)   
        self.livePlot.setXRange(0, 5.3, padding = 0)
        self.livePlot.setYRange(-280, -100, padding = 0)
        self.colorLivePulse = (66,155,184, 145)
        self.colorlivePulseBackground = (66,155,184,145)

        self.livePlotLineWidth = 1
        self.averagePlotLineWidth = 1.5

        self.lEditTdsStart.setAlignment(Qt.AlignCenter) 
        self.lEditTdsEnd.setAlignment(Qt.AlignCenter) 
        self.lEditTdsAvgs.setAlignment(Qt.AlignCenter) 
        self.plotDataContainer = {'livePulseFft': None}       # Dictionary for plot items
        self.lEditTdsEnd.setReadOnly(True)

    def initUI(self):

        """
            Initialise UI from design file
        """

        uic.loadUi("../View/Designer/periodicMeasurementUI.ui", self)
        self.setWindowTitle("THEA Timelapse")
        self.disableButtons()
        self.initAttribs()
        self.connectEvents()
        self.validateDefaultInputs()
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.progTlapse.setValue(self.experiment.tlapseProgVal)
        
        self.livePlot.setLabel('left', 'Transmission Intensity (dB)')
        self.livePlot.setLabel('bottom', 'Frequency (THz)')
        self.livePlot.setTitle("""Timelapse FFT""", color = 'g', size = "45 pt")   
        self.livePlot.showGrid(x = True, y = True)
        self.checkBoxCreateGIF.setCheckable(True)
        self.checkBox_keepSrcImgs.setCheckable(True)
       
       

    def disableButtons(self):

        """
            Disable GUI buttons from user interactions.
        """

        self.btnStart.setEnabled(False)
        self.btnAnimateResult.setEnabled(False)

    def enableButtons(self):

        """
            Enable GUI buttons for user interaction
        """
        
        self.btnStart.setEnabled(True)
        self.btnStop.setEnabled(True)
        

    
    def stop(self):

        """Reset icons to offline state"""
        
        self.enableButtons()
        self.progTlapse.setValue(self.experiment.tlapseProgVal)
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.enableLEdit()
        self.lblFrameCount.setText("Frame Count: ")
   


   
    def resetAveraging(self):

        """"Reset averaging progress bar"""

        self.progAvg.setValue(0)


    

##################################### AsyncSlot coroutines #######################################
    
    @asyncSlot()
    async def _statusChanged(self, status):

        """
            AsyncSlot Coroutine to indicate ScanControl Staus.

        """        
        
        
        self.lblStatus.setText("Status: " + self.experiment.device.status) 
        

    @asyncSlot()
    async def enableAnimation(self):

        """Enable animation button when timelapse finished"""
        
        if self.checkBoxCreateGIF.isChecked() and self.experiment.timelapseDone and not self.experiment.continueTimelapse:
            self.btnAnimateResult.setEnabled(True)
            
        elif not self.checkBoxCreateGIF.isChecked():
            self.btnAnimateResult.setEnabled(False)
          


    @asyncSlot()
    async def processPulses(self,data):

        """"GUI button state management during data processing"""

        await asyncio.sleep(0.01)

        if self.experiment.device.isAcquiring:
            self.lEditTdsAvgs.setText(str(self.experiment.numAvgs))
            self.progAvg.setValue(self.experiment.avgProgVal)
            self.progTlapse.setValue(self.experiment.tlapseProgVal)
            self.lblFrameCount.setText(f"Frame count: {self.experiment.numFramesDone}/{self.experiment.numRequestedFrames}")
                       
            if self.plotDataContainer['livePulseFft'] is None :
                self.plotDataContainer['livePulseFft'] = self.plot(self.experiment.freq, 20*np.log(np.abs(self.experiment.FFT))) 
               
            self.plotDataContainer['livePulseFft'].curve.setData(self.experiment.freq, 20*np.log(np.abs(self.experiment.FFT))) 
            self.plotDataContainer['livePulseFft'].curve.setPen(color = self.colorLivePulse, width = self.averagePlotLineWidth)



#******************************************************************************************

if __name__ == '__main__':
    
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = TheaTimelapse(loop, '../Model/timelapseConfig.yml')
    win = TimelapseMainWindow(ttl)
    win.show()

    with loop:
        sys.exit(loop.run_forever())


    

