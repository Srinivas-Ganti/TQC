import sys
import os

from numpy import double



baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")
configDir = os.path.join(viewDir, "config")

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)
sys.path.append(configDir)
sys.path.append(uiDir)

from Model.PolarisationSweep import *
from Model import ur

from pint.errors import *
from PIL import Image


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


class AnotherWindow(QWidget):

    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want - to display the animation.
    """

    def __init__(self):

        super().__init__()
        layout = QVBoxLayout()
        self.setWindowTitle("GIF RESULT")
        self.height = 400
        self.width = 570
        self.left =10 
        self.top = 40
        self.label = QLabel()
        self.setGeometry(self.left, self.top, self.width, self.height)  
        layout.addWidget(self.label)
        self.setLayout(layout)


class PolSweepMainWindow(QMainWindow):

    """
    THEA Timelapse GUI Main window class
    """

    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()
        #self.openSerial()
    
    
    def connectEvents(self):
        
        """
            Connect GUI object and validator signals to respective methods.
        """
      
        self.experiment.serial.readyRead.connect(self.receive)
        self.experiment.device.scanControl.statusChanged.connect(self._statusChanged)
        self.experiment.nextScan.connect(self.updateGraphics)
        self.experiment.device.pulseReady.connect(self.processPulses)
        self.experiment.device.pulseReady.connect(self.experiment.processPulses)
        self.experiment.device.dataUpdateReady.connect(self.experiment.device.done)
        self.experiment.polSweepFinished.connect(self.enableAnimation)
        self.experiment.polSweepFinished.connect(self.makeGIF)
        self.lEditMaterial.editingFinished.connect(self.validateMaterial)
        self.lEditInterval.editingFinished.connect(self.validateInterval)
        self.btnStart.clicked.connect(self.experiment.polSweepStart)
        self.btnStart.clicked.connect(self.disableLEdit)
        self.btnStart.clicked.connect(self.startObs)
        self.btnStop.clicked.connect(self.experiment.device.stop) 
        self.btnStop.clicked.connect(self.stop) 
        self.btnStop.clicked.connect(self.experiment.cancelTasks)
        self.btnStop.clicked.connect(self.stopObs)
        self.btnAnimateResult.clicked.connect(self.animateGIF)
        self.lEditTdsStart.editingFinished.connect(self.validateEditStart)
        self.lEditTdsAvgs.editingFinished.connect(self.validateEditAverages)
        self.lEditAngle1.editingFinished.connect(self.validateEditAngle1)
        self.lEditAngle2.editingFinished.connect(self.validateEditAngle2)
        self.lEditFrames.editingFinished.connect(self.validateFrames)
        self.lEditTdsAvgs.textChanged.connect(self.avgsChanged)
        self.livePlot.scene().sigMouseMoved.connect(self.mouseMoved)
        self.experiment.tempSensorModel.serial.readyRead.connect(self.receive)
        self.experiment.tempSensorModel.nextScan.connect(self.plotTemp)
        self.livePlot_2.scene().sigMouseMoved.connect(self.mouseMoved2)
        self.btnStartTemp.clicked.connect(self.startObs)
        self.btnStopTemp.clicked.connect(self.stopObs)
        self.btnEject.clicked.connect(self.experiment.ejectFreezer)
        self.btnContact.clicked.connect(self.experiment.contactFreezer)
        self.btnLift.clicked.connect(self.experiment.liftFreezer)
        self.lEditPreChill.editingFinished.connect(self.validatePreChill)


    @asyncSlot()
    async def startObs(self):

        """
        Start temperature sensing historical
        """

        self.btnStartTemp.setEnabled(False)
        self.experiment.tempSensorModel.keepRunning = True
        self.experiment.tempSensorModel.clearData()
        while self.experiment.tempSensorModel.keepRunning:
            self.experiment.tempSensorModel.tempObsTask =  asyncio.ensure_future(self.experiment.tempSensorModel.readTemp())
            asyncio.gather(self.experiment.tempSensorModel.tempObsTask)
            while not self.experiment.tempSensorModel.tempObsTask.done():
                await asyncio.sleep(1/self.experiment.tempSensorModel.config['TemperatureSensor']['samplingRate'])


    @asyncSlot()
    async def stopObs(self):
        """
        Stop temperature sensing historical
        """
        self.btnStartTemp.setEnabled(True)
        self.experiment.tempSensorModel.keepRunning = False
        try:
            self.experiment.tempSensorModel.tempObsTask.cancel()
            self.experiment.tempSensorModel.ackTask.cancel()
            self.epoch = 1
            self.ctr = 0
            self.experiment.tempSensorModel.clearData()
            self.lblTempBig.setText(f"Cold finger Temp (C): --")    
            self.xmin = 1
            self.xmax = self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength'] 
            self.livePlot_2.setXRange(self.xmin, self.xmax)
            #self.experiment.tempSensorModel.time = np.linspace(1,self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength'],
            #                                  self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength'])
            self.experiment.tempSensorModel.clearData()
            self.data[:] = np.NaN
            self.plotT.curve.setData(self.experiment.tempSensorModel.time,self.data)
        except asyncio.exceptions.CancelledError:
            print("Cancelled Observation")



    def mouseMoved2(self, evt):

        """
            Track mouse movement on data plot in plot units (deg C vs sec)

            :type evt: pyqtSignal 
            :param evt: Emitted when the mouse cursor moves over the scene. Contains scene cooridinates of the mouse cursor.

        """

        pos = evt
        if self.livePlot_2.sceneBoundingRect().contains(pos):
            mousePoint = self.livePlot_2.plotItem.vb.mapSceneToView(pos)
            x = float("{0:.3f}".format(mousePoint.x()))
            y = float("{0:.3f}".format(mousePoint.y()))
            self.xyLabel_2.setText(f"last cursor position: {x, y}")


    def validatePreChill(self):

        """
            Validate user input for Requested Interval of the timelapse
        """ 

        try:
            isinstance(ur(self.lEditPreChill.text()), ur.Quantity)
            preChill = ur(self.lEditPreChill.text())
            if isinstance(preChill, int):
                preChill = preChill*ur("s")
            if preChill.units in ["second", "minute", "hour"]: 
                logger.info("pre-Chill value is a valid time input")
                logger.info("Freezer pre-Chill time ACCEPTED")
                self.experiment.preChill = preChill.m_as("second")
                logger.info(f"Pre-chill time is set to {self.experiment.preChill} seconds")
            else:
                logger.warning("Pre-Chill quantity units are not valid time inputs, Setting default config values")
                logger.warning("Enter valid units, for example: '0.5hour', '420ms', '5min' . . . ")
                self.lEditPreChill.setText(str(self.experiment.config['PolSweep']['preChill']))
                self.experiment.preChill = ur(str(self.experiment.config['PolSweep']['preChill'])).m_as("second")
            self.experiment.preChilllOk = True
        except UndefinedUnitError:
            self.experiment.preChillOk = False
            logger.info("Undefined / Incorrect units. Setting default config value")
            self.lEditPreChill.setText(str(self.experiment.config['PolSweep']['preChill']))
            self.experiment.preChill = ur(str(self.experiment.config['PolSweep']['preChill']))
            self.experiment.preChillOk = True


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
                logger.info("Interval is a valid time input")
                logger.info("Timelapse interval ACCEPTED")
                self.experiment.interval = interval.m_as("second")
                logger.info(f"Interval is set to {self.experiment.interval} seconds")
            else:
                logger.warning("Interval units are not valid time inputs, Setting default config values")
                logger.warning("Enter valid units, for example: '0.5hour', '420ms', '5min' . . . ")
                self.lEditInterval.setText(str(self.experiment.config['PolSweep']['interval']))
                self.interval = ur(str(self.experiment.config['PolSweep']['interval'])).m_as("second")
            self.experiment.intervalOk = True
        except UndefinedUnitError:
            self.experiment.intervalOk = False
            logger.info("Undefined / Incorrect units. Setting default config value")
            self.lEditInterval.setText(str(self.experiment.config['PolSweep']['interval']))
            self.experiment.interval = ur(str(self.experiment.config['PolSweep']['interval']))
            self.experiment.intervalOk = True


    def plotTemp(self, line):

        """
        Plot temperature vs time
        """

        if "deg C" in line:

            self.experiment.tempSensorModel.ctr += 1
            temp = line.split("deg")[0]
            self.lblTempBig.setText(f"Cold finger Temp: {temp} C")  

            def correctData():
                self.experiment.tempSensorModel.temperatures = np.append(self.experiment.tempSensorModel.temperatures,
                                                                         double(line.split("deg")[0]))
                self.experiment.tempSensorModel.temperatures = np.roll(self.experiment.tempSensorModel.temperatures, 1)
                self.experiment.tempSensorModel.temperatures = np.delete(self.experiment.tempSensorModel.temperatures, -1)
                flipped = np.flip(self.experiment.tempSensorModel.temperatures)
                return flipped
                                
            if self.experiment.tempSensorModel.ctr != self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength']:
                nanidx = self.experiment.tempSensorModel.ctr
                flipped = correctData()
                self.data = np.append(flipped[len(flipped)-nanidx:], flipped[:len(flipped)-nanidx])      
            
            else:
                self.experiment.tempSensorModel.ctr = 1
                self.experiment.tempSensorModel.epoch+=1
                self.experiment.tempSensorModel.clearData()
                self.xmin = self.xmin + self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength']
                self.xmax = self.xmax + self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength']
                self.experiment.tempSensorModel.time = np.linspace(self.xmin,self.xmax,
                                                                   self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength'])
                self.livePlot_2.setXRange(self.xmin, self.xmax)
                flipped = correctData()
                nanidx =  self.experiment.tempSensorModel.ctr
                self.data = self.experiment.tempSensorModel.temperatures
           
            self.experiment.currentTemp = self.data[np.isfinite(self.data)][-1]  
            self.plotT.curve.setData(self.experiment.tempSensorModel.time,self.data)
            self.plotT.curve.setPen(color = self.colorTemp, width = self.averagePlotLineWidth)
            


    def validateMaterial(self):

        if self.lEditMaterial.text() is not None and self.lEditMaterial.text() != "":
            str = self.lEditMaterial.text()
            filteredStr = ''.join(e for e in str if e.isalnum())
            self.lEditMaterial.setText(filteredStr)
            self.experiment.scanName = filteredStr
            print(f"Material accepted: {self.experiment.scanName}")
        else:
            self.lEditMaterial.setText("Data")
            self.experiment.scanName = "Data"
            print("Using default name - data")


    @asyncSlot()
    async def receive(self):

        """Receive messages on serial port and redirect to message box"""

        
        while self.experiment.serial.canReadLine():
            
            codec = QTextCodec.codecForName("UTF-8")
            line = codec.toUnicode(self.experiment.serial.readLine()).strip()
            if "deg C" in line:
                self.experiment.tempSensorModel.nextScan.emit(line) 
            self.experiment.tempSensorModel.lastMessage = line
            
            self.experiment.lastMessage = line
            await asyncio.sleep(0.1)


    def openSerial(self):
        
        """Open serial port for communication with QC robot"""

        
        self.experiment.serial.open(QIODevice.ReadWrite)
        self.experiment.tempSensorModel.serial.open(QIODevice.ReadWrite)

    def animateGIF(self):
        
        self.movie = QMovie(f"{os.path.join(self.savingFolder, self.gifName)}.gif")
        self.gifWindow.label.setMovie(self.movie)
        self.gifWindow.setWindowTitle(f"GIF RESULT: {self.gifName}")
        self.movie.start()
        self.gifWindow.show()


    def updateGraphics(self):

        """Update text labels on plot, previous data color schemes"""  

        self.labelValue.setText(f"""Data: {self.experiment.numFramesDone}/{self.experiment.numRequestedFrames}\nPhi: {self.experiment.actualAngle:.2f} deg""")
        if self.checkBoxCreateGIF.isChecked():
            
            self.savingFolder = os.path.join(self.experiment.exportPath, "Images")
            if not os.path.isdir(self.savingFolder):
                os.makedirs(self.savingFolder)
            if len(self.experiment.results) > 0:    
                dt =  str(self.experiment.results.iloc[-1]['datetime']).replace(' ','_').split('.')[0].replace(':','-')
                name = f"{dt}_{self.experiment.results.iloc[-1]['frameNum']}.png"
                if name not in self.experiment.GIFSourceNames:
                    self.experiment.GIFSourceNames.append(name)
                    self.exporter.export(os.path.join(self.savingFolder, name))


    def makeGIF(self):

        """Make GIF using result data"""

        if self.checkBoxCreateGIF.isChecked() and len(self.experiment.GIFSourceNames) > 0 and not self.experiment.continuePolSweep:
            self.experiment.polSweepDone = False
            dfListGIF = [os.path.join(self.savingFolder, image) for image in self.experiment.GIFSourceNames]
            for imgPath in dfListGIF:
                if not os.path.isfile(imgPath):
                    print("Images not found, revising GIF source list")
                    self.experiment.GIFSourceNames.remove(imgPath.split(f"{self.savingFolder}")[1])
                    print(f"{imgPath.split(self.savingFolder)[1]}")
                    print("************************************")
                    print(f"{imgPath.split(self.savingFolder)[0]}")


            self.gifList = [Image.open(os.path.join(self.savingFolder, image)) for image in self.experiment.GIFSourceNames] 

            frame_one = self.gifList[0]
            self.gifName = f"{self.experiment.GIFSourceNames[0].split('.')[0].split('.png')[0]}_{self.experiment.GIFSourceNames[-1].split('.')[0].split('.png')[0]}"
            frame_one.save(f"{os.path.join(self.savingFolder, self.gifName)}.gif", format="GIF", append_images=self.gifList,
                save_all=True, duration=100, loop=0)
            if not self.checkBox_keepSrcImgs.isChecked(): 
                    print("DELETING SOURCE IMAGES")
                    self.filesToRemove = [os.path.join(self.savingFolder, img) for img in self.experiment.GIFSourceNames]
                    for f in self.filesToRemove:
                        print(f"Removing {f}")
                        try:
                            os.remove(f)
                        except ValueError:
                            print("file already removed")
            self.btnAnimateResult.setEnabled(True)
                

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
        self.lEditAngle2.setReadOnly(True)
        self.lEditAngle1.setReadOnly(True)
        self.lEditFrames.setReadOnly(True)
        self.btnAnimateResult.setEnabled(False)


    def enableLEdit(self):

        """"Enable line edit fields when ScanControl has stopped"""

        self.lEditTdsStart.setReadOnly(False)
        self.lEditTdsAvgs.setReadOnly(False)
        self.lEditAngle2.setReadOnly(False)
        self.lEditAngle1.setReadOnly(False)
        self.lEditFrames.setReadOnly(False)
      

    def avgsChanged(self):

        """"Terminal Message"""

        print(f"Experiment averages changed to : {self.experiment.numAvgs}")
        

    def validateFrames(self):

        """
            Validate user input for Requested Interval of the timelapse
        """ 

        try:
            
            frames = self.lEditFrames.text()
            self.experiment.framesLim = round((self.experiment.angle1- self.experiment.angle2)/self.experiment.angRes)
            validationRule = QIntValidator(2, self.experiment.framesLim)
        
            print(validationRule.validate(frames,self.experiment.framesLim))
            if validationRule.validate(frames,self.experiment.framesLim)[0] == QValidator.Acceptable:
                print("Frames accepted")
                self.experiment.sweepArray = np.linspace(self.experiment.angle1, self.experiment.angle2, int(frames))
                if (abs(self.experiment.sweepArray[0] - self.experiment.sweepArray[1]) > self.experiment.angRes):
                    self.experiment.numRequestedFrames = int(frames)
                    logger.info(f"Frame count is set to {self.experiment.numRequestedFrames}")
            else:
                logger.info(f"Anglular resolution of the holder is limited to {self.experiment.angRes}. Preparing approximate angles . . . ")
                self.experiment.numRequestedFrames = round((self.experiment.angle1- self.experiment.angle2)/self.experiment.angRes)
                self.experiment.sweepArray = np.linspace(self.experiment.angle1, self.experiment.angle2, int(frames))
                self.lEditFrames.setText(str(self.experiment.numRequestedFrames))
                self.frames = self.experiment.numRequestedFrames
            logger.info(f"Sensor angles to scan : {self.experiment.sweepArray}")                
            self.experiment.framesOk = True
        except UndefinedUnitError:
            self.experiment.framesOk = False
            
   
    def validateEditAngle2(self):

        
        """
            Validate user input for Requested Frames of the timelapse
        """ 
        
        validationRule = QDoubleValidator(self.experiment.config['Robots']['angle2Lim'],0, 3)
        print(validationRule.validate(self.lEditAngle2.text(),self.experiment.config['Robots']['angle2Lim']))
        if validationRule.validate(self.lEditAngle2.text(),
                                   self.experiment.config['Robots']['angle2Lim'])[0] == QValidator.Acceptable:
            print(f"ANGLE 2 ACCEPTED")
            self.experiment.angle2Ok = True
            self.experiment.angle2 = double(self.lEditAngle2.text())
        else:
            print(f"> [WARNING]:Invalid angle.")
            print(f"Setting default config values: {self.experiment.config['PolSweep']['angle2']}")
            self.experiment.angle2 = self.experiment.config['PolSweep']['angle2']
            self.lEditAngle2.setText(str(self.experiment.angle2))
     

    def validateEditAngle1(self):

        
        """
            Validate user input for Requested Frames of the timelapse
        """ 
        
        validationRule = QDoubleValidator(0,self.experiment.config['Robots']['angle1Lim'],3)
        print(validationRule.validate(self.lEditAngle1.text(),self.experiment.config['Robots']['angle1Lim']))
        if validationRule.validate(self.lEditAngle1.text(),
                                   self.experiment.config['Robots']['angle1Lim'])[0] == QValidator.Acceptable:
            print(f"ANGLE 1 ACCEPTED")
            self.experiment.angle1Ok = True
            self.experiment.angle1 = double(self.lEditAngle1.text())
        else:
            print(f"> [WARNING]:Invalid angle.")
            print(f"Setting default config values: {self.experiment.config['PolSweep']['angle1']}")
            self.experiment.angle1 = self.experiment.config['PolSweep']['angle1']
            self.lEditAngle1.setText(str(self.experiment.angle1))


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
        self.lEditAngle1.setText(str(self.experiment.config['PolSweep']['angle1']))
        self.lEditAngle1.editingFinished.emit()
        self.lEditAngle2.setText(str(self.experiment.config['PolSweep']['angle2']))
        self.lEditAngle2.editingFinished.emit()
        
        self.lEditFrames.setText(str(self.experiment.config['PolSweep']['frames']))
        self.lEditFrames.editingFinished.emit()
        self.lEditInterval.setText(str(self.experiment.config['PolSweep']['interval']))
        self.lEditInterval.editingFinished.emit()
        self.lEditPreChill.setText(str(self.experiment.config['PolSweep']['preChill']))
        self.lEditPreChill.editingFinished.emit()
        self.loadTDSParams()
    
        print("> [SCANCONTROL] Setting TDS parameters: Done\n")        


    def loadTDSParams(self):

        """
            Load the TDS measurement parameters related to pulse duration and timing, required number of averages from config file.
        """

        if (self.experiment.startOk and self.experiment.endOk and self.experiment.avgsOk and self.experiment.framesOk and self.experiment.angle1Ok and self.experiment.angle2Ok):
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
        self.width = 1100
        self.left = 10
        self.top = 40      
        self.labelValue = None         #LabelItem to display timelapse frames on plot
        self.setGeometry(self.left, self.top, self.width, self.height)   
        self.livePlot.setXRange(0.2,2.2, padding = 0)
        self.livePlot.setYRange(-200, -100, padding = 0)
        self.colorLivePulse = (66,155,184, 145)
        self.colorlivePulseBackground = (66,155,184,145)
        self.livePlotLineWidth = 1
        self.averagePlotLineWidth = 1.5
        self.plotDataContainer = {'livePulseFft': None}       # Dictionary for plot items
        self.lEditTdsEnd.setReadOnly(True)
        self.btnStartTemp.setEnabled(True)
        self.scanName = None


    def initUI(self):

        """
            Initialise UI from design file
        """

        uic.loadUi("../View/Designer/polSweepUI.ui", self)
        self.setWindowTitle("THEA PhiScan")
        self.disableButtons()
        self.initAttribs()
        self.connectEvents()

        self.validateDefaultInputs()
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.progPolSweep.setValue(self.experiment.polSweepProgVal)
        
        self.livePlot.setLabel('left', 'Transmission Intensity (dB)')
        self.livePlot.setLabel('bottom', 'Frequency (THz)')
        self.livePlot.setTitle("""Phi Scan""", color = 'g', size = "45 pt")   
        self.livePlot.showGrid(x = True, y = True)
        self.labelValue = TextItem('', **{'color': '#FFF'})
        self.labelValue.setPos(QPointF(4,-100))

        self.lEditTdsStart.setAlignment(Qt.AlignCenter) 
        self.lEditTdsEnd.setAlignment(Qt.AlignCenter) 
        self.lEditTdsAvgs.setAlignment(Qt.AlignCenter) 
        self.livePlot.addItem(self.labelValue)

        self.checkBoxCreateGIF.setCheckable(True)
        self.checkBox_keepSrcImgs.setCheckable(True)
       
        self.exporter = ImageExporter(self.livePlot.scene())   # Exporter for creating plot images
        self.exporter.parameters()['width'] = 500
        self.gifList = None
        self.gifWindow = AnotherWindow()
        self.gifName = ""
        self.colorTemp = (255,255,0, 180)
        self.livePlot_2.setLabel('left', 'Temperature (C)')
        self.livePlot_2.setLabel('bottom', 'Observations - 1/Sampling Rate (sec)')
        self.livePlot_2.setTitle("""Temperature historical""", color = 'g', size = "45 pt")   
        self.livePlot_2.showGrid(x = True, y = True)
        self.TplotDataContainer = {}
        
        self.xmin = 1
        self.xmax = self.experiment.tempSensorModel.config['TemperatureSensor']['scrollLength'] 
        self.plotT = self.livePlot_2.plot(self.experiment.tempSensorModel.temperatures)
        self.livePlot_2.setXRange(self.xmin, self.xmax)
        self.livePlot_2.setYRange(50, -100)
        self.lblTempBig.setText("Cold Finger temp. (C): --")
               


    def disableButtons(self):

        """
            Disable GUI buttons from user interactions.
        """

        self.btnStart.setEnabled(False)
        self.btnAnimateResult.setEnabled(False)
        self.btnStartTemp.setEnabled(False)


    def enableButtons(self):

        """
            Enable GUI buttons for user interaction
        """
        
        self.btnStart.setEnabled(True)
        self.btnStop.setEnabled(True)
        self.btnStartTemp.setEnabled(True)
        

    def stop(self):

        """Reset icons to offline state"""
        
        self.enableButtons()
        self.progPolSweep.setValue(self.experiment.polSweepProgVal)
        self.progAvg.setValue(self.experiment.avgProgVal)
        self.enableLEdit()
        self.experiment.device.resetAveraging()
        self.resetAveraging()
        self.lblFrameCount.setText("Scan: ")
        self.progAvg.setValue(0)
   
   
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
        
        if self.checkBoxCreateGIF.isChecked() and self.experiment.polSweepDone and not self.experiment.continuePolSweep:
            self.btnAnimateResult.setEnabled(True)
            
        elif not self.checkBoxCreateGIF.isChecked():
            self.btnAnimateResult.setEnabled(False)
          


    @asyncSlot()
    async def processPulses(self,data):

        """"GUI button state management during data processing"""

        await asyncio.sleep(0.1)
        lblSceneX = self.livePlot.getViewBox().state['targetRange'][0][0] + np.abs(self.livePlot.getViewBox().state['targetRange'][0][1] - self.livePlot.getViewBox().state['targetRange'][0][0])*0.80
        lblSceneY =  self.livePlot.getViewBox().state['targetRange'][1][0] + np.abs(self.livePlot.getViewBox().state['targetRange'][1][1] - self.livePlot.getViewBox().state['targetRange'][1][0])*0.95
        self.labelValue.setPos(QPointF(lblSceneX,lblSceneY))

        if self.experiment.device.isAcquiring:
            self.lEditTdsAvgs.setText(str(self.experiment.numAvgs))
            self.progAvg.setValue(self.experiment.avgProgVal)
            self.progPolSweep.setValue(self.experiment.polSweepProgVal)
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

    tps = TheaPolSweep(loop, '../config/polSweepConfig.yml')
    win = PolSweepMainWindow(tps)
    win.show()

    with loop:
        sys.exit(loop.run_forever())


    

