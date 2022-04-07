import sys
import os

from pint.errors import UndefinedUnitError
from pyqtgraph.graphicsItems.PlotDataItem import dataType

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
# configDir  = os.path.join(baseDir, "Config") # use only if making a separate config dir
configDir = os.path.join(baseDir, "Model")  # if keeping in same dir as model
sys.path.append(baseDir)


from Model.experiment import *
from Resources import ur
from MenloLoader import MenloLoader
from PyQt5 import QtSerialPort
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s:%(name)s:%(message)s")

file_handler = logging.FileHandler(os.path.join(logDir, 'experiment.log'))
stream_handler = logging.StreamHandler()

file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)


logger.addHandler(file_handler)
logger.addHandler(stream_handler)

class TheaQC(Experiment):

    sensorUpdateReady = pyqtSignal()
    qcUpdateReady = pyqtSignal()
    
    def __init__(self, loop = None, configFile = None):
        
        super().__init__(loop, configFile)
        self.initialise()
        

    def initialise(self):

        if self.configLoaded:
            self.initAttribs()
            self.initResources()
            self.mLoader = MenloLoader([])          # fileLoader object
            self.TdsWin = self.config['TScan']['window']
            self.loadRobotConfig()
            self.initRobot()


    def initRobot(self):

        """Initialise robot via serial port"""

        
        self.serial = QtSerialPort.QSerialPort(self.port)
        self.serial.setBaudRate(self.baudrate)
        

    def loadRobotConfig(self):

        """Load serial port config for robot"""

        if self.configLoaded:
            self.port = self.config['Robots']['port']
            self.baudrate = self.config['Robots']['baudrate']
            

    def initResources(self):

        """
            Initialise class attributes for QC application with default values.
        """

        self.startOk = False                                  # Flag for TDS pulse start time validation
        self.endOk = False                                    # Flag for TDS pulse end time validation
        self.avgsOk = False                                   # Flag for required pulse averages validation
        self.waferIdOk = False                                # Flag for wafer ID validation
        self.sensorIdOk = False                               # Flag for sensor ID validation
        self.classification = None                            # Result of TDS pulse classification.
        self.qcAvgTask = None                                 # QC averaging task (automatic - cartridge sensing)
        self.pulsePeaks = None                                # result of peak finding on TDS pulse for classification
        self.qcParams = {}                                    # empty dictionary to hold qc parameters
        self.qcComplete = False                               # Flag to track qc task completeion
        self.qcResult = None                                  # QC result 
        self.qcRunNum = 0                                     # tracking inspected sensors
        self.qcRunning = None                                # Flag for QC running status
        self.qcNumAvgs = None                                 # number of averages for QC
        self.previousClassification = None                    # previous classification result 
        self.qcResultsList = []                               # empty list to hold accumulated QC data on multiple sensors 
        self.stdRef = None                                    # Standard reference data for QC  

        self.port = None                                      # Serial port name
        self.baudrate = None                                  # baudrate for serial communication  
        self.serial = None                                    # Serial object to communicate with robots


    def initAttribs(self):

        """
            Initialise class attributes for QC application with default values.
        """

        self.pulseAmp = None                       # Received pulse data              
        self.timeAxis = None                       # time data 
        
        self.TdsWin = None                         # TDS windowing duration (ps)
        self.dcOffsetFile = None                   # DC offset file path
        self.dcOffset = None                       # DC background correction data
        self.FFT = None                            # FFT of the current pulse data
        self.freq = None                           # frequency (THz)
        
        self.avgProgVal = 0                        # counter for averaging progress bar
        self.numAvgs = None                        # number of set averages
        self.startTime = None                      # TDS pulse start time (ps)
        self.endTime = None                        # TDS pulse end time (ps)
        self.waferId = None                        # QC wafer ID
        self.sensorId = None                       # QC sensor ID
        self.tdsParams = {}                        # Empty dictionary to hold TDS pulse parameters
        self.currentAverageFft = None              # averaged pulse FFT
        self.chipsPerWafer = None                  # Parameter to trigger wafer ID change (not used)
        self.classificationDistance = None         # Pulse peak fitting parameters for classification- distance (see scipy.find_peaks())
        self.classificationProminence = None
        self.classificationWidth = None
        self.classificationThreshold = None
        self.stdRef = None                         # Standard reference TDS pulse data
        self.qcAvgResult = None                    # Store QC averagining result 
        self.qcStep = None
        self.qcResults = {}                        # Store QC results from current session


    def loadDcBkg(self):

        """
            Subtracts the dc background signal from the raw pulse data. (Not used)
        """

        self.dcOffsetFile = self.config['Spectrometer']['dcBkgFilename']
        src = [os.path.join(rscDir, "dcBkg Measurements", self.dcOffsetFile)]
        self.dcOffset = self.mLoader.getTDS(src, [])[0]['amp']
        self.timeAxis = self.mLoader.getTDS(src, [])[0]['time']
        

    def loadQcConfig(self):
        
        """
            Load QC paramters for comparitive error checking against standard reference from config file.
        """
        self.loadStandardRef()
        self.classificationDistance = self.config['Classification']['distance']
        self.classificationProminence = self.config['Classification']['prominence']
        self.classificationThreshold = self.config['Classification']['threshold']
        self.classificationWidth = self.config['Classification']['width']
        self.qcParams ={'fLB':self.config['QC']['lowerFreqBound'],
                        'fUB':self.config['QC']['upperFreqBound'],
                        'errTh':self.config['QC']['allowedErrordB'],
                        'nErrV':self.config['QC']['maxViolations']}
        self.qcNumAvgs = self.config['QC']['qcAverages']
        self.chipsPerWafer = self.config['QC']['chipsPerWafer']
        qcSaveDir = self.config['QC']['qcSaveDir']
        if qcSaveDir is None or not os.path.isdir(qcSaveDir):
            self.qcSaveDir = os.path.join(baseDir, "qcData")
            print(f"Setting default directory for qcData at: {self.qcSaveDir}")
        else:
            self.qcSaveDir = qcSaveDir
            print(f"QC data will be saved in: {self.qcSaveDir}")
        try:
            handlingTime = self.config['QC']['handlingTime']
            if isinstance(handlingTime, int):
                handlingTime = handlingTime*ur("s")
            elif isinstance(ur(self.config['QC']['handlingTime']), ur.Quantity) and ur(handlingTime).units in ["second"]:
                self.handlingTime = ur(handlingTime).m_as("second")
            print(f"QC cartridge handling time set to : {self.handlingTime}s")
        except UndefinedUnitError:
            self.handlingTime = 1
            print("CONFIG ERROR: ensure handling time units in seconds,\
                   or unitless, setting handling time to: 1s")
            

    def loadStandardRef(self):

        """
            Load Standard Reference file for comparative QC
        """


        refPath = os.path.join(rscDir,"StandardReferences", self.config['QC']['stdRefFileName'])
        
        try:
            stdRefData = MenloLoader([refPath]).data
            self.stdRef = stdRefData
            logger.info("Standard reference loaded")
            logger.info(self.stdRef)
        except:
            logger.error(f"[ERROR]: FileNotFound. No resource file called {self.config['QC']['stdRefFileName']}")


    def classifyTDS(self):

        """
            Classify the latest pulse data as "logger.infoor "Sensor".
        """

        self.pulsePeaks = {}
        isAir, isSensor = [0 for i in range(2)]
        start = self.find_nearest(self.timeAxis, self.config["Classification"]["tdsInspectStart"])[0]
        end =  self.find_nearest(self.timeAxis, self.config["Classification"]["tdsInspectEnd"])[0]
        self.pulsePeaks['distance'] = find_peaks(self.pulseAmp[start:end], distance = self.classificationDistance)
        self.pulsePeaks['width'] = find_peaks(self.pulseAmp[start:end], width = self.classificationWidth)
        
        self.pulsePeaks['prominence'] = find_peaks(self.pulseAmp[start:end], prominence = self.classificationProminence)
        self.pulsePeaks['threshold'] = find_peaks(self.pulseAmp[start:end], threshold = self.classificationThreshold)
        
        if self.find_nearest(self.pulsePeaks['distance'][0], 250)[1]  > 260: # checking array indices not values
            isSensor += 1 
            #logger.debug("CLASSIFICATION DISTANCE : SENSOR")
        else:
            isAir += 1   
            #logger.debug("CLASSIFICATION DISTANCE : AIR")
        
        if len(self.pulsePeaks['threshold'][0]) > 3:
            isAir += 1     
            #logger.debug("CLASSIFICATION THRESHOLD : AIR")
        else:
            isSensor += 1
            #logger.debug("CLASSIFICATION THRESHOLD : SENSOR")
        if len(self.pulsePeaks['prominence'][0]) > 4:
            isAir += 1    
            #logger.debug("CLASSIFICATION PROMINENCE : AIR")
        else:
            isSensor +=1  
            #logger.debug("CLASSIFICATION PROMINENCE : SENSOR")
        sensorUpdate = {'isSensor': isSensor, 'isAir': isAir}

        if sensorUpdate['isAir'] < sensorUpdate['isSensor']:
            self.classification = "Sensor"
            logger.debug("CLASSIFICATION RESULT <<<<<<<<<< SENSOR")
        if sensorUpdate['isAir'] > sensorUpdate['isSensor']:
            self.classification = "Air"
            logger.debug("CLASSIFICATION RESULT <<<<<<<<<< AIR")
        self.sensorUpdateReady.emit()  


    async def measureSensor(self):
    
        """Coroutine to measure sensor during QC"""
    
        if self.classification == "Sensor":

            self.device.setDesiredAverages(self.qcNumAvgs)        
            print("Sensor confirmed, begin processing cartridge")
            await self.startAveraging(self.qcNumAvgs)
            while not self.device.isAveragingDone():
                await asyncio.sleep(0.5)

            self.device.avgTask = None
            self.device.setDesiredAverages(1)


    def findResonanceMinima(self,data):

        """
            Find the resonance minima in between 0.71 - 0.81 THz.
            
            data: this is the unsliced FFT array from the measurement

            :return: resonance minima in THz.
            :rtype: float
        """

        minList = []
        f1 = 0.71
        f2 = 0.81
        x = self.freq
        fStartId = self.mLoader.find_nearest(x, f1)[0]
        fEndId = self.mLoader.find_nearest(x, f2)[0]
        f = x[fStartId:fEndId]    
        y = 20*np.log(np.abs(data))[fStartId:fEndId]
        rMinima = f[np.argmin(y)]
        return rMinima
        

##################################### AsyncSlot coroutines #######################################


    @asyncSlot()
    async def ejectCartridge(self):

        """Send command on serial to eject cartridge"""

        await asyncio.sleep(0.1)
        txt = "EJECT\n"
        self.serial.write(txt.encode())


    @asyncSlot()
    async def insertCartridge(self):

        """Send command on serial to insert cartridge"""

        await asyncio.sleep(0.1)
        txt = "INSERT\n"
        self.serial.write(txt.encode())


    @asyncSlot()
    async def checkNextSensor(self):

        """
            AsyncSlot coroutine to check for the event transition that corresponds to a new sensor being inserted in the beam path.
            If a new sensor is introduced, then increment the sensor number and begin a new round of QC on the 
            new sensor.
        """        

        if self.qcRunning and not self.qcComplete and self.qcRunNum > 0:   

            print("Checking next sensor")
            
            if (self.previousClassification in [None, "Air"] and self.classification == "Sensor"):
                print("Detected new sensor")
                if self.qcAvgTask.done():
                    await self.doQC()
                if self.qcRunNum > 0:
                    print("Incrementing sensor ID for next QC")
                    self.sensorId += 1
            elif self.previousClassification == "Sensor" and self.classification == "Air":
                print("Sensor removed")
                self.previousClassification = "Air"

            elif self.previousClassification == "Sensor" and self.classification == "Sensor":
                print("Waiting for next sensor")
                
            await asyncio.sleep(0.01)
            

    @asyncSlot()
    async def doQC(self):

        """Comparitive QC against standard reference.As sensors are being 
            detected and measured, the QC results are updated and files are exported to the destination directory
            as specified in the config file."""

        if self.qcRunning:
   
            if (self.previousClassification in [None, "Air"]) and self.classification == 'Sensor':
                self.device.avgTask = None
                print("Sensor Detected. Double checking . . .")
                self.previousClassification = "Sensor" 
                await asyncio.sleep(self.handlingTime)
                if self.classification == "Sensor":
                    self.device.setDesiredAverages(self.qcNumAvgs)
                    self.qcAvgTask = asyncio.ensure_future(self.measureSensor())
                    await asyncio.gather(self.qcAvgTask)
                    while not self.qcAvgTask.done():
                        await asyncio.sleep(0.5)
                    if self.qcAvgTask.done():
                        currentDatetime = datetime.now()
                        qcAvgResult = self.device.avgResult
                        self.device.setDesiredAverages(1)
                        _ , self.qcAvgFFT = self.calculateFFT(self.timeAxis, qcAvgResult['amplitude'][0])
                        diff =  20*np.log(np.abs(self.stdRefFFT)) - 20*np.log(np.abs(self.qcAvgFFT[self.start_idx:self.end_idx]))
                        err = 0
                        
                        for j in diff:
                            if abs(j) > self.config['QC']['allowedErrordB']:                # <<<<<<<<< QC criterion
                                err+=1
                        if err > self.config['QC']['maxViolations']:                  # <<<<<<<<< QC criterion
                            print("QC FAIL")
                            self.qcResult = "FAIL"
                            resonanceMin = self.findResonanceMinima()
                            self.qcResultsList.append({'datetime': currentDatetime.strftime("%d-%m-%y %H:%M:%S"),
                                                        'sensorId':self.sensorId,
                                                        'waferId': self.waferId,
                                                        'qcResult': self.qcResult,
                                                        'resonance': resonanceMin})
                        else:
                            print("QC PASS")
                            self.qcResult = "PASS"
                        self.qcRunNum += 1
                        self.qcUpdateReady.emit()
                        rawExportData = np.vstack([self.timeAxis,  qcAvgResult['amplitude'][0]]).T

                        
                        header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.05\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}, QC Parameters: {self.qcParams}
    Time [ps]              THz Signal [mV]"""
                        base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_WID_{self.waferId}_SN_{self.sensorId}_{self.qcResult}_Reference"""
                        saveWaferDir = os.path.join(self.qcSaveDir, str(datetime.now().date()) , self.waferId)
                        if not os.path.isdir(saveWaferDir):
                            os.makedirs(os.path.join(saveWaferDir))
                            data_file = os.path.join(saveWaferDir.replace("/","\\"), f'{base_name}.txt')
                            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
                        else:                        
                            data_file = os.path.join(saveWaferDir.replace("/","\\"), f'{base_name}.txt')
                            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
                        # self.qcResult = None
     

            elif (self.previousClassification == "Sensor" and self.classification == 'Air'):
                self.previousClassification = "Air"
                print("Sensor removed . . . ")
                

    @asyncSlot()
    async def startQC(self):

        """Set QC running flag and prepare for QC averaging"""

        self.qcRunning = True
        self.qcComplete = False
        
        ### sensor must be inserted first . Need to read ACK to proceed
        

        if self.stdRef is not None:
            print("Preparing QC resources . . . ")
            self.start_idx = self.find_nearest(self.freq, self.config['QC']['lowerFreqBound'])[0]
            self.end_idx =  self.find_nearest(self.freq, self.config['QC']['upperFreqBound'])[0]
            self.stdRefAmp =  self.stdRef.amp[0]
            _, self._stdRefFFT = self.calculateFFT(self.timeAxis, self.stdRefAmp)
            self.stdRefFFT = self._stdRefFFT[self.start_idx: self.end_idx]
            self.fRange = self.freq[self.start_idx: self.end_idx]
            self.doQC()
        await asyncio.sleep(0.01)
        

    @asyncSlot()
    async def finishQC(self):

        """Set QC running flag and wrap up session"""

        self.qcRunning = False
        self.qcComplete = True
           

    @asyncSlot()
    async def processPulses(self,data):

        """Process data for event loop
        
            :type data: dict
            :param data: dictionary containig pulse information from Controller.
        """
       
        self.pulseAmp = data['amplitude'][0]
        self.timeAxis = data['timeaxis'] -  data['timeaxis'][0]
        self.timeAxis = self.timeAxis[:self.find_nearest(self.timeAxis, self.TdsWin)[0]+1]                   
        self.pulseAmp = self.pulseAmp[:self.find_nearest(self.timeAxis, self.TdsWin)[0]+1]
        self.pulseAmp = self.pulseAmp.copy()
        self.classifyTDS()                            # Live Cartridge sensing
        self.freq, self.FFT = self.calculateFFT(self.timeAxis,self.pulseAmp)
        self.avgProgVal = self.device.scanControl.currentAverages/\
                                 self.device.scanControl.desiredAverages*100
        self.checkNextSensor()
        await asyncio.sleep(0.1)
        
 
    @asyncSlot()
    async def measureStandardRef(self):

        """Measure standard reference for QC and update config file."""
   
        await self.measureSensor()
    
        if self.device.isAveragingDone():
            rawExportData = np.vstack([self.timeAxis, self.pulseAmp]).T
            currentDatetime = datetime.now()
            header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.04\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_WID_{self.waferId}_SN_{self.sensorId}_STANDARD_Reference"""
            refPath = os.path.join(rscDir,"StandardReferences", base_name)
            data_file = os.path.join(refPath.replace("/","\\") +'.txt')
            
            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            
            newStdRef = data_file.split('/')[-1]
            self.config['QC']['stdRefFileName'] = newStdRef
            with open(os.path.join(configDir,"theaConfig.yml"), 'w') as f:
                f.write(yaml.dump(self.config, default_flow_style = False))
            
            self.loadConfig()
            self.initialise()
            self.loadStandardRef()
            logger.info("STD REF LOADED")
            

    @asyncSlot()
    async def startAveraging(self, numAvgs = None):

        """
            AsyncSlot coroutine to initiate the averaging task. Buttons are partially disabled during the process. 
        """                
        await asyncio.sleep(0.1)
        if numAvgs == None:            
            self.device.setDesiredAverages(self.numAvgs)
            logger.info(f"default averaginig: {self.numAvgs}")
        else:
            self.device.setDesiredAverages(numAvgs)
            logger.info(f"special averaginig: {numAvgs}")
                
        await asyncio.sleep(1)
        self.device.keepRunning = True
        self.device.avgTask = asyncio.ensure_future(self.device.doAvgTask())
        await asyncio.gather(self.device.avgTask)
        while not self.device.isAveragingDone():
            await asyncio.sleep(1)
        if self.device.isAveragingDone():
            print(f"{self.device.scanControl.currentAverages}/{self.device.scanControl.desiredAverages}")
            print("DONE")
            rawExportData = np.vstack([self.timeAxis, self.pulseAmp]).T
            currentDatetime = datetime.now()
            header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.04\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1} ps
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_WID_{self.waferId}_SN_{self.sensorId}_Reference"""
            exportPath = os.path.join(self.qcSaveDir, base_name)
            data_file = os.path.join(exportPath.replace("/","\\") +'.txt')
            print(data_file)
            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            

            

    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """
        logger.warning("cancelling tasks")
        try:
            if self.device.avgTask is not None:
                self.device.avgTask.cancel()
                logger.info("Averaging cancelled")
            if self.qcAvgTask is not None:
                logger.info("QC cancelled")
                self.qcAvgTask.cancel()   
                self.qcRunning = False             
        except CancelledError:
            logger.warning("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, 'theaConfig.yml')
