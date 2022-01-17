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
      
        self.btnStart.clicked.connect(self.experiment.timelapseStart)
        self.btnStop.clicked.connect(self.experiment.device.stop) 
        self.btnStop.clicked.connect(self.stop) 
        self.btnStop.clicked.connect(self.experiment.cancelTasks)
     
        self.lEditTdsStart.editingFinished.connect(self.validateEditStart)
        self.lEditTdsEnd.setReadOnly(True)
        self.lEditTdsAvgs.editingFinished.connect(self.validateEditAverages)

        self.lEditFrames.editingFinished.connect(self.validateFrames)
        self.lEditInterval.editingFinished.connect(self.validateInterval)
        self.lEditTdsAvgs.textChanged.connect(self.avgsChanged)
    

    def avgsChanged(self):

        print(f"Experiment averages changed to : {self.experiment.numAvgs}")
        

    def validateInterval(self):

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
        

    def validateFrames(self):

        maxNumFiles = int(ur(self.experiment.maxStorage).m_as('kB')/ur(self.experiment.filesize).m_as('kB'))
        validationRule = QIntValidator(0,maxNumFiles)
        print(validationRule.validate(self.lEditFrames.text(),maxNumFiles))
        if validationRule.validate(self.lEditFrames.text(),
                                   maxNumFiles)[0] == QValidator.Acceptable:
            print("Timelapse frames accepted")
            self.experiment.framesOk = True


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
            Initialise class attributes for QC application with default values.
        """

        self.height = 350
        self.width = 450
        self.left = 10
        self.top = 40      
        self.setGeometry(self.left, self.top, self.width, self.height)   



    def initUI(self):

        uic.loadUi("../View/Designer/periodicMeasurementUI.ui", self)
        self.setWindowTitle("THEA Timelapse")
        self.disableButtons()
        self.initAttribs()
        self.connectEvents()
        self.validateDefaultInputs()
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.progTlapse.setValue(self.experiment.tlapseProgVal)

       

    def disableButtons(self):

        """
            Disable GUI buttons from user interactions.
        """

        self.btnStart.setEnabled(False)
    

    def enableButtons(self):

        """
            Enable GUI buttons for user interaction
        """

        
        self.btnStart.setEnabled(True)
        self.btnStop.setEnabled(True)
        




##################################### AsyncSlot coroutines #######################################

    @asyncSlot()
    async def stop(self):

        """Reset icons to offline state"""

        await asyncio.sleep(0.1)
        
        self.enableButtons()
      


    @asyncSlot()
    async def processPulses(self,data):

        """"GUI button state management during data processing"""

        await asyncio.sleep(0.01)

        if self.experiment.device.isAcquiring:
            self.lEditTdsAvgs.setText(str(self.experiment.device.numAvgs))
            

    @asyncSlot()
    async def _statusChanged(self, status):

        """
            AsyncSlot Coroutine to indicate ScanControl Staus.
        """        

        self.lblStatus.setText("Status: " + self.experiment.device.status) 
    


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


    

