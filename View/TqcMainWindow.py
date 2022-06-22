import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")
configDir = None

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)
sys.path.append(os.path.join(viewDir, "Icons"))
sys.path.append(uiDir)


from Model.TheaQC import *
from Model import ur

from pint.errors import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s:%(name)s:%(message)s")

file_handler = logging.FileHandler(os.path.join(logDir, 'App.log'))
stream_handler = logging.StreamHandler()

file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


class TqcMainWindow(QWidget, Machine):

    dataUpdateReady = pyqtSignal(object)

    def __init__(self, experiment = None):

        super().__init__()
        logger.info("THEA QC 1.05 - Session started")
        self.experiment = experiment
        self.initUI()
        self.openSerial()
        self.machine = AsyncMachine(self.experiment, states = QCStates, transitions = transitions , initial = QCStates.OFF, auto_transitions= False)
        
    
    def closeEvent(self, event):

        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'THEA QC Confirm shutdown', 
                        quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            
            loop = asyncio.get_event_loop()
            tasks = asyncio.all_tasks(loop = loop)
            for t in tasks:
                t.cancel()
            asyncio.gather(*tasks, return_exceptions=True)
        
        else:
            event.ignore()    
        

    def openSerial(self):
        
        """Open serial port for communication with QC robot"""

        
        self.experiment.serial.open(QIODevice.ReadWrite)

    
    def connectEvents(self):
        
        """
            Connect GUI object and validator signals to respective methods.
        """
        
        self.experiment.device.scanControl.statusChanged.connect(self._statusChanged)
        self.experiment.serial.readyRead.connect(self.receive)
        self.experiment.device.pulseReady.connect(self.processPulses)
        self.experiment.device.pulseReady.connect(self.experiment.processPulses)
        self.experiment.device.dataUpdateReady.connect(self.experiment.device.done)
        self.experiment.device.pulseReady.connect(self.startAveraging)
        self.experiment.qcUpdateReady.connect(self.qcResult)
        self.experiment.sensorUpdateReady.connect(self.checkNextSensor)     
        self.livePlot.scene().sigMouseMoved.connect(self.mouseMoved)
        
        self.btnStartAveraging.clicked.connect(self.experiment.startAveraging)

        self.btnSaveData.clicked.connect(self.experiment.saveAverageData)
        self.btnStop.clicked.connect(self.experiment.device.stop) 
        self.btnStop.clicked.connect(self.stop) 
        self.btnStop.clicked.connect(self.experiment.cancelTasks)
        
        self.btnResetAvg.clicked.connect(self.experiment.device.resetAveraging)
        self.btnResetAvg.clicked.connect(self.resetAveraging)
       
        self.btnStartQC.clicked.connect(self.startQC)
        self.btnStartQC.clicked.connect(self.experiment.startQC)
        self.btnFinishQC.clicked.connect(self.finishQC)
        self.btnFinishQC.clicked.connect(self.experiment.finishQC)
        self.btnNewStdRef.clicked.connect(self.experiment.measureStandardRef)
        self.btnNewStdRef.clicked.connect(self.measureStandardRef)
        
        self.btnInsertCartridge.clicked.connect(self.experiment.insertCartridge)
        self.btnEjectCartridge.clicked.connect(self.experiment.ejectCartridge)

        self.experiment.sensorUpdateReady.connect(self.classifyTDS)
        self.lEditTdsStart.editingFinished.connect(self.validateEditStart)
        self.lEditTdsEnd.setReadOnly(True)
        self.lEditTdsAvgs.editingFinished.connect(self.validateEditAverages)
        self.lEditTdsAvgs.textChanged.connect(self.avgsChanged)
        self.lEditLotNum.editingFinished.connect(self.validateEditLotNum)
        self.lEditWaferId.editingFinished.connect(self.validateEditWaferId)
        self.lEditSensorId.editingFinished.connect(self.validateEditSensorId)
        self.experiment.stopUpstream.connect(self.stopListener)


    def avgsChanged(self):

        logger.info(f"Experiment averages changed to : {self.experiment.numAvgs}")


    def checkNextSensor(self):

        """Update sensor id in GUI"""

        if self.experiment.qcRunNum > 0:
            self.lEditSensorId.setText(str(self.experiment.sensorId))

            # if self.experiment.qcResult is None:
                
            #     self.lblQcStatusIcon.setPixmap(QPixmap("Icons/hourglass--arrow.png"))
            #     self.lblQcStatusIcon.setScaledContents(True)
            #     self.qCcurrentMsg.setText("NEXT SENSOR")

            
    def stopListener(self):

        """Listening for stop request from model level"""

        self.btnStop.clicked.emit()


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


    def validateEditStart(self):

        """
            Validate user input for Start time
        """

        validationRule = QDoubleValidator(-420,420,3)
        logger.info(validationRule.validate(self.lEditTdsStart.text(),420))
        if validationRule.validate(self.lEditTdsStart.text(),
                                   420)[0] == QValidator.Acceptable:
            logger.info("TDS START TIME ACCEPTED")
            self.experiment.startOk = True
            self.experiment.startTime = float(self.lEditTdsStart.text())
            
            self.experiment.endTime = float(self.lEditTdsStart.text()) + self.experiment.TdsWin
            self.lEditTdsEnd.setText(str(self.experiment.endTime))
            self.experiment.endOk = True
            self.experiment.tdsParams['start'] = self.experiment.startTime
            self.experiment.tdsParams['end'] = self.experiment.endTime
            logger.info(f"End time is set to be {self.experiment.TdsWin} ps after THz pulse start at {self.experiment.startTime} ps")
            logger.info("TDS END TIME ACCEPTED")
        else:
            logger.error("[ERROR] InvalidInput: Setting default config value")
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
        logger.info("> [SCANCONTROL] Setting TDS parameters: Done\n")        
    
        self.loadQC()
        self.chipsPerWafer = int(self.experiment.config['QC']['chipsPerWafer'])
        
        self.lEditWaferId.setText(str(self.experiment.config['QC']['waferId']))
        self.lEditWaferId.editingFinished.emit()
        
        self.lEditSensorId.setText(str(self.experiment.config['QC']['sensorId']))
        self.lEditSensorId.editingFinished.emit()     

        self.lEditLotNum.setText(str(self.experiment.config['QC']['lotNum']))  
        self.lEditLotNum.editingFinished.emit()  
        
        if self.experiment.waferIdOk and self.experiment.sensorIdOk:
            self.btnStartQC.setEnabled(True)        
        else:
            self.btnStartQC.setEnabled(False)
    

    def loadTDSParams(self):

        """
            Load the TDS measurement parameters related to pulse duration and timing, required number of averages from config file.
        """

        if (self.experiment.startOk and self.experiment.endOk and self.experiment.avgsOk):
            logger.info("TDS Inputs accepted")
            self.experiment.device.setBegin(self.experiment.startTime)
            self.experiment.device.setEnd(self.experiment.endTime)
            
            self.btnStartAveraging.setEnabled(True)
            self.btnResetAvg.setEnabled(True)


    def loadQC(self):

        """
            Load QC parameters from config file and validate inputs
        """
        
        self.experiment.loadQcConfig()
        logger.info("QC config loaded")
        
    
    def validateEditLotNum(self):

        """
            Validate user input for required number of averages.
        """
                
        validationRule = QIntValidator(1,99)
        logger.info(validationRule.validate(self.lEditLotNum.text(),2000))
        if validationRule.validate(self.lEditLotNum.text(),
                                   99)[0] == QValidator.Acceptable:
            logger.info("Wafer Lot Number Accepted")
            self.experiment.lotNumOk = True
            self.experiment.lotNum = int(self.lEditLotNum.text())
        else:
            logger.error("[ERROR] InvalidInput: Setting default config value")
            self.lEditLotNum.setText(str(self.experiment.config['QC']['lotNUm']))
        self.experiment.lotNumOk = True
        


    def validateEditAverages(self):

        """
            Validate user input for required number of averages.
        """
                
        validationRule = QIntValidator(1,2000)
        logger.info(validationRule.validate(self.lEditTdsAvgs.text(),2000))
        if validationRule.validate(self.lEditTdsAvgs.text(),
                                   2000)[0] == QValidator.Acceptable:
            logger.info("TDS AVGS ACCEPTED")
            self.experiment.avgsOk = True
            self.experiment.numAvgs = int(self.lEditTdsAvgs.text())
            self.experiment.tdsParams['numAvgs'] = self.experiment.numAvgs
            
        else:
            logger.error("[ERROR] InvalidInput: Setting default config value")
            self.experiment.avgsOK = False
            self.lEditTdsAvgs.setText(str(self.experiment.config['TScan']['numAvgs']))
        

    def validateEditWaferId(self):

        """
            Validate user input for QC wafer ID - check naming format for consistency
        """

        self.experiment.waferIdOk = False
        wId = self.lEditWaferId.text()
        
        try:    
            assert wId[:2].isalpha()
            assert int(wId[2:])
            logger.info(f"Wafer ID ACCEPTED: {wId}")
            self.experiment.waferId = wId
        except AssertionError:
            logger.warning("Wafer ID must follow the pattern 'AA0001, AB0001 etc'")
            logger.warning("Setting default config value")
            self.lEditWaferId.setText(self.experiment.config['QC']['waferId'])
            self.experiment.waferId = self.experiment.config['QC']['waferId']
        self.experiment.waferIdOk = True
        

    def validateEditSensorId(self):
                
        """
            Validate user input for QC sensor ID.
        """

        
        self.experiment.sensorIdOk = False
        validationRule = QIntValidator(1,self.experiment.chipsPerWafer)                         
        logger.info(validationRule.validate(self.lEditSensorId.text(),self.experiment.chipsPerWafer))
        if validationRule.validate(self.lEditSensorId.text(),
                                  self.chipsPerWafer)[0] == QValidator.Acceptable:
            logger.info("Sensor ID ACCEPTED")
            self.experiment.sensorId =  int(self.lEditSensorId.text())
        else:
            logger.warning(f"Sensor ID must be non zero integer in range of (1 , {self.experiment.chipsPerWafer})")
            
            self.experiment.sensorId = int(self.experiment.config['QC']['sensorId'])
            logger.warning(f"Setting default config value: Sensor ID is set to {self.experiment.sensorId}")
            self.lEditSensorId.setText(str(self.experiment.sensorId))
        self.experiment.sensorIdOk = True
        if not self.experiment.sensorIdOk:
            self.btnStartQC.setEnabled(False)


    def initAttribs(self):

        """
            Initialise class attributes for QC application with default values.
        """

        self.height = 900
        self.width = 750
        self.left = 10
        self.top = 40      
        self.setGeometry(self.left, self.top, self.width, self.height)   

        self.livePlot.setXRange(0, 5.3, padding = 0)
        self.livePlot.setYRange(-280, -100, padding = 0)
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
        self.lEditWaferId.setAlignment(Qt.AlignCenter) 
        self.lEditSensorId.setAlignment(Qt.AlignCenter) 

        self.plotDataContainer = {'currentAveragePulseFft': None,
                                  'livePulseFft': None}       # Dictionary for plot items


    def loadIcons(self):

        self.lblQcStatusIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblQcStatusIcon.setScaledContents(True)
        self.lblClassResultIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblClassResultIcon.setScaledContents(True) 


    def initUI(self):

        uic.loadUi("../View/Designer/MainWindow2.ui", self)
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
        
        
    def disableButtons(self):

        """
            Disable GUI buttons from user interactions.
        """

        self.btnResetAvg.setEnabled(False)
        self.btnStartAveraging.setEnabled(False)
        self.btnFinishQC.setEnabled(False)
       

    def enableButtons(self):

        """
            Enable GUI buttons for user interaction
        """

        
        # self.btnStart.setEnabled(True)
        self.btnNewStdRef.setEnabled(True)
        self.btnStop.setEnabled(True)
        self.btnStartQC.setEnabled(True)
        self.btnStartAveraging.setEnabled(True)
        self.btnResetAvg.setEnabled(True)


    def message(self, msgStrPattern):

        """
            Prints messages in the GUI Output textbox
        """

        self.textbox.appendPlainText(f"{msgStrPattern}")
        logger.info(msgStrPattern)


    @asyncSlot()
    async def startQC(self):
        
        """GUI button states during QC"""
        
        self.disableButtons()
        self.btnFinishQC.setEnabled(True)

        if self.experiment.stdRef is not None and not self.experiment.qcComplete:
            if self.experiment.qcRunNum == 0:
                self.message(f'> [QC]: Starting {datetime.now().strftime("%d-%m-%y %H:%M:%S")}')
            
            self.lblQcStatusIcon.setPixmap(QPixmap("Icons/arrow-circle-double.png"))
            self.lblQcStatusIcon.setScaledContents(True)
            self.qCcurrentMsg.setText("Result: Processing . . . ") 

            if isinstance(self.experiment.numAvgs, int):
                self.lEditTdsAvgs.setText(str(self.experiment.qcNumAvgs))
                self.lEditTdsAvgs.editingFinished.emit()    

            stdRefPlot = self.plot(self.experiment.stdRef.freq[0], 20*np.log(np.abs(self.experiment.stdRef.FFT[0])))
            stdRefPlot.curve.setPen(color = self.colorstdRef, width = self.averagePlotLineWidth)




##################################### AsyncSlot coroutines #######################################


    @asyncSlot()
    async def receive(self):

        """Receive messages on serial port and redirect to message box"""

        await asyncio.sleep(0.1)
        while self.experiment.serial.canReadLine():
            codec = QTextCodec.codecForName("UTF-8")
            line = codec.toUnicode(self.experiment.serial.readLine()).strip()
            self.message(line)
            self.experiment.lastMessage = line


    @asyncSlot()
    async def finishQC(self):
        
        """Finish QC, restore GUI state to idle"""

        self.enableButtons()
        self.message("QC session end. Generating report . . . ")

        self.lblQcStatusIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblQcStatusIcon.setScaledContents(True)
        self.qCcurrentMsg.setText("Result: Not available ") 


    @asyncSlot()
    async def measureStandardRef(self):

        """GUI button states during std reference measurement"""

        
        await asyncio.sleep(0.01)
        self.message("> [MESSAGE]: Recording new standard reference for QC . . .")
        self.btnNewStdRef.setEnabled(False)
        self.message(f"> [MESSAGE]: RELOADING CONFIG, updating internal reference . . . ")
        # while not 
        
    	
    @asyncSlot()
    async def qcResult(self):

        """Update graphics with latest QC results"""

        if self.experiment.qcResult == "FAIL":
            self.plotDataContainer['currentAveragePulseFft'] = self.plot(self.experiment.freq, 20*np.log(np.abs(self.experiment.qcAvgFFT))) 
            self.plotDataContainer['currentAveragePulseFft'].curve.setPen(color = self.colorFail, width = self.averagePlotLineWidth)
            self.lblQcStatusIcon.setPixmap(QPixmap("Icons/cross-circle.png"))
            self.lblQcStatusIcon.setScaledContents(True)
            self.qCcurrentMsg.setText("Result: QC FAIL")
            self.message(f"{self.experiment.waferId}_{self.experiment.sensorId} : {self.experiment.qcResult}")
         
        elif self.experiment.qcResult == "PASS":
            self.plotDataContainer['currentAveragePulseFft'] = self.plot(self.experiment.freq, 20*np.log(np.abs(self.experiment.qcAvgFFT))) 
            self.plotDataContainer['currentAveragePulseFft'].curve.setPen(color = self.colorPass, width = self.averagePlotLineWidth)
            self.lblQcStatusIcon.setPixmap(QPixmap("Icons/tick-circle.png"))
            self.lblQcStatusIcon.setScaledContents(True)
            self.qCcurrentMsg.setText("Result: QC PASS")
            self.message(f"{self.experiment.waferId}_{self.experiment.sensorId} : {self.experiment.qcResult}")
        
        elif self.experiment.qcResult is None:

            self.lblQcStatusIcon.setPixmap(QPixmap("Icons/arrow-circle-double.png"))
            self.lblQcStatusIcon.setScaledContents(True)
            self.qCcurrentMsg.setText("Result: Processing")


    @asyncSlot()
    async def classifyTDS(self):

        """Update graphics with classification result"""

        await asyncio.sleep(0.1)
        if self.experiment.classification == "Sensor":
        
            self.lblClassResultIcon.setPixmap(QPixmap("Icons/Sensor.png"))
            self.lblClassResultIcon.setScaledContents(True)  
            self.lblClassResult.setText("Result: Sensor")  
            
        if self.experiment.classification == "Air":
            self.lblClassResultIcon.setPixmap(QPixmap("Icons/Air.png"))
            self.lblClassResultIcon.setScaledContents(True)     
            self.lblClassResult.setText("Result: Air")   
           

    @asyncSlot()
    async def stop(self):

        """Reset icons to offline state"""

        self.lblClassResultIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblClassResultIcon.setScaledContents(True)  
        self.lblClassResult.setText("Result: Not available") 

        self.lblQcStatusIcon.setPixmap(QPixmap("Icons/status-offline.png"))
        self.lblQcStatusIcon.setScaledContents(True)
        self.qCcurrentMsg.setText("Result: not available")
        await asyncio.sleep(0.1)
        
        self.enableButtons()
        

    @asyncSlot()
    async def startAveraging(self, data):

        """"Update averaging progress bar"""
        
        await asyncio.sleep(0.01)
        self.progAvg.setValue(int(self.experiment.avgProgVal))


    @asyncSlot()
    async def resetAveraging(self):

        """"Reset averaging progress bar"""

        await asyncio.sleep(0.01)
        self.progAvg.setValue(0)


    @asyncSlot()
    async def processPulses(self,data):

        """"GUI button state management during data processing"""

        await asyncio.sleep(0.01)
        
        if self.experiment.device.isAcquiring:
            self.lEditTdsAvgs.setText(str(self.experiment.device.numAvgs))
            
            if self.plotDataContainer['livePulseFft'] is None :
                self.plotDataContainer['livePulseFft'] = self.plot(self.experiment.freq, 20*np.log(np.abs(self.experiment.FFT))) 
                
            self.plotDataContainer['livePulseFft'].curve.setData(self.experiment.freq, 20*np.log(np.abs(self.experiment.FFT))) 
            self.plotDataContainer['livePulseFft'].curve.setPen(color = self.colorLivePulse, width = self.averagePlotLineWidth)

            self.checkNextSensor()
            

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

    tqc = TheaQC(loop, '../Model/theaConfig.yml')
    win = TqcMainWindow(tqc)
    win.show()

    with loop:

        sys.exit(loop.run_forever())
        


    

