import sys
import os

from pint.errors import UndefinedUnitError
from pyqtgraph.graphicsItems.PlotDataItem import dataType
import pandas as pd

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
# configDir  = os.path.join(baseDir, "Config") # use only if making a separate config dir
configDir = os.path.join(baseDir, "Model")  # if keeping in same dir as model
sys.path.append(baseDir)


from Model.experiment import *
from Model.QCSM import *
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
        self.lastMessage = None                               # Store the last message received from the robot
        

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
        self.lotNum = None                         # Wafer Lot number
        self.waferId = None                        # QC wafer ID
        self.sensorId = None                       # QC sensor ID
        self.tdsParams = {}                        # Empty dictionary to hold TDS pulse parameters
        self.currentAverageFft = None              # averaged pulse FFT
        self.chipsPerWafer = None                  # Parameter to trigger wafer ID change (not used)
        self.stdRefDir = None                      # Directory path for std refs.
        self.classificationDistance = None         # Pulse peak fitting parameters for classification- distance (see scipy.find_peaks())
        self.classificationProminence = None
        self.classificationWidth = None
        self.classificationThreshold = None
        self.stdRef = None                         # Standard reference TDS pulse data
        self.qcAvgResult = None                    # Store QC averagining result 
        self.qcStep = None
        self.qcResults = {}                        # Store QC results from current session
        self.state = -1                             # QC state machine. Load in 'starting state' 
        self.timeout = None
        self.ackTask = None                         # wait for ack with timeout
        self.quickScanTask = None                 # task for performing a quick scan
        self.qcAvgTask = None                       # QC averaging task
        self.qcLoopTask = None                      # QC test loop
        self.sessionName = None                     # Name of report
        
        
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
        self.stdRefDir = self.config['QC']['stdRefDir']
        self.lotNum = self.config['QC']['lotNum']
        qcSaveDir = self.config['QC']['qcSaveDir']
        self.reportsDir = self.config['QC']['ReportsDir']
        self.timeout = self.config['Robots']['timeout']

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
        except FileNotFoundError:
            logger.error(f"[ERROR]: FileNotFound. No resource file called {self.config['QC']['stdRefFileName']}")
        

    async def classifyTDS(self):

        """
            Classify the latest pulse data as "logger.infoor "Sensor".
        """
        await asyncio.sleep(0.5)
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
            logger.debug("CLASSIFICATION DISTANCE : SENSOR")
        else:
            isAir += 1   
            logger.debug("CLASSIFICATION DISTANCE : AIR")
        
        if len(self.pulsePeaks['threshold'][0]) > 3:
            isAir += 1     
            logger.debug("CLASSIFICATION THRESHOLD : AIR")
        else:
            isSensor += 1
            logger.debug("CLASSIFICATION THRESHOLD : SENSOR")
        if len(self.pulsePeaks['prominence'][0]) > 4:
            isAir += 1    
            logger.debug("CLASSIFICATION PROMINENCE : AIR")
        else:
            isSensor +=1  
            logger.debug("CLASSIFICATION PROMINENCE : SENSOR")
        sensorUpdate = {'isSensor': isSensor, 'isAir': isAir}

        if sensorUpdate['isAir'] < sensorUpdate['isSensor']:
            self.classification = "Sensor"
            logger.debug("CLASSIFICATION RESULT <<<<<<<<<< SENSOR")
        if sensorUpdate['isAir'] > sensorUpdate['isSensor']:
            self.classification = "Air"
            logger.debug("CLASSIFICATION RESULT <<<<<<<<<< AIR")
        self.sensorUpdateReady.emit()  


    async def quickScan(self):

        """Collect single shot data and then restore to default value"""

        
        logger.info("Begin quick scan")
        await self.startAveraging(1)
        while not self.device.isAveragingDone():
            await asyncio.sleep(0.5)
        
        self.device.avgTask = None         
        await self.classifyTDS()
        await self.device.stop()
        
        

    def findResonanceMinima(self,data):

        """
            Find the resonance minima in between 0.71 - 0.81 THz.
            
            data: this is the unsliced FFT array from the measurement

            :return: resonance minima in THz.
            :rtype: float
        """

        f1 = 0.71
        f2 = 0.81
        x = self.freq
        fStartId = self.mLoader.find_nearest(x, f1)[0]
        fEndId = self.mLoader.find_nearest(x, f2)[0]
        f = x[fStartId:fEndId]    
        y = 20*np.log(np.abs(data))[fStartId:fEndId]
        rMinima = f[np.argmin(y)]
        return rMinima


    def generateReport(self):

        """Dump results from QC session as a csv"""

        df = pd.DataFrame(self.qcResultsList + [self.qcParams])
        logger.info("Exporting QC report to Reports dir")
        try:       
            df.to_csv(os.path.join(self.reportsDir,f'{self.sessionName}.csv'))

        except Exception as e:
            raise e

##################################### AsyncSlot coroutines #######################################
    
    def eventFilter(self, msg):
        pass



    def ejectCartridge(self):

        """Send command on serial to eject cartridge"""

        txt = "EJECT\n"
        self.serial.write(txt.encode())

  
    def insertCartridge(self):

        """Send command on serial to insert cartridge"""

        txt = "INSERT\n"
        self.serial.write(txt.encode())


    def homeRobot(self):

        """Send command on serial to insert cartridge"""

        # await asyncio.sleep(0.1)
        txt = "HOME\n"
        self.serial.write(txt.encode())
        
  
    async def waitOnRobot(self):

        """Reusable block of code to log timeout for Ack"""
        
        logger.info(f"last message : {self.lastMessage}")
        self.lastMessage = " "      #  clear previous ACK if any
        try:
            self.ackTask = asyncio.create_task(self.waitForAck())
            await asyncio.wait_for(self.ackTask, timeout = self.timeout)

        except asyncio.exceptions.TimeoutError:
            logger.error(f"[ERROR]: ACK not received")
            logger.info(f"Quitting . . .")
            self.cancelTasks()


    async def doQuickScan(self):

        """Reusable call to do a quick scan wrapped in ensure future"""

        self.quickScanTask = asyncio.ensure_future(self.quickScan())
        asyncio.gather(self.quickScanTask)
        while not self.quickScanTask.done():
            await asyncio.sleep(0.5)


    async def checkForSensor(self):

        """Reusable code block for verifyinf sensor"""

        try:    
            await self.doQuickScan()
            logger.info("Quick scan completed")

            if self.classification == 'Sensor':
                self.state = 1
            
            if self.classification == 'Air':
                self.state = 0
            
                self.insertCartridge()
                await self.waitOnRobot()
                await self.doQuickScan()
                logger.info("Verification scan completed")

                try:
                    await asyncio.sleep(1)
                    assert self.classification == "Sensor"
                    self.state = 1
                except AssertionError as a:
                    self.state = 3.2
                    logger.error(f"[ERROR] State {self.state}- Sensor not detected. Please check motion paths, cartridge holder for missing/ defective sensor")
                    raise a
        except asyncio.exceptions.TimeoutError:
            logger.error(f"[ERROR]: ACK not received")
            self.state = 3.1
            return
        except asyncio.exceptions.CancelledError:
            logger.warning(f"[WARNING]: Sensor check cancelled.")
            return


    @asyncSlot()
    async def doQC(self):

        """Comparative QC against standard reference.As sensors are being 
            detected and measured, the QC results are updated and files are exported to the destination directory
            as specified in the config file."""

        if self.qcRunning:
            try:    
                self.homeRobot()
                await self.waitOnRobot()
                logger.info("Homing complete. . .")

                while not self.qcComplete:                    
                    
                    self.qcUpdateReady.emit()
                    await self.checkForSensor()
        
                    self.qcAvgTask = asyncio.ensure_future(self.startAveraging(self.qcNumAvgs))
                    asyncio.gather(self.qcAvgTask)
                    while not self.qcAvgTask.done():
                        await asyncio.sleep(0.5)

                    if self.qcAvgTask.done():
                        logger.info("Averaging check - True")
                        self.compareToStdRef()
                        self.saveAverageData(data = self.qcAvgResult, path = self.qcSaveDir, headerType = 'qc') 
                        await self.device.stop()
                    ## mechanical loop
                    self.ejectCartridge()
                    await self.waitOnRobot()
                    self.sensorUpdateReady.emit()
                    self.sensorId += 1
                    self.qcResult = None
            
            except Exception as e:
                logger.error("Something went wrong")
                raise e
            except CancelledError:
                logger.error("Cancelling")

            
    def compareToStdRef(self):    

        """Compare last averaging result to the loaded standard reference. Update the qc result and update the run number"""            

        self.qcAvgResult = self.device.avgResult
        
        _ , self.qcAvgFFT = self.calculateFFT(self.timeAxis, self.qcAvgResult['amplitude'][0])
        diff =  10*np.log(np.abs(self.stdRefFFT)) - 10*np.log(np.abs(self.qcAvgFFT[self.start_idx:self.end_idx]))
        err = 0
        
        for j in diff:
            if abs(j) > self.config['QC']['allowedErrordB']:                # <<<<<<<<< QC criterion
                err+=1
        if err > self.config['QC']['maxViolations']:                  # <<<<<<<<< QC criterion
            print("QC FAIL")
            self.qcResult = "FAIL"
            
        else:
            print("QC PASS")
            self.qcResult = "PASS"

        resonanceMin = self.findResonanceMinima(self.qcAvgFFT)
        self.qcResultsList.append({'sensorId':self.sensorId,
                                        'waferId': self.waferId,
                                        'qcResult': self.qcResult,
                                        'resonance': resonanceMin})

        self.qcUpdateReady.emit()
        self.qcRunNum += 1
        

    @asyncSlot()
    async def startQC(self):

        """Set QC running flag and prepare for QC averaging"""

        self.qcRunning = True
        self.qcComplete = False
        self.qcResultsList = []
        startTime = datetime.now()
        self.sessionName = str(datetime.now()).split('.')[0].replace(' ','').replace(':','-')
        ### sensor must be inserted first . Need to read ACK to proceed
        

        if self.stdRef is not None:
            logger.info("Preparing QC resources . . . ")
            self.start_idx = self.find_nearest(self.stdRef.freq[0], self.config['QC']['lowerFreqBound'])[0]
            self.end_idx =  self.find_nearest(self.stdRef.freq[0], self.config['QC']['upperFreqBound'])[0]
            self.stdRefAmp =  self.stdRef.amp[0]
            _, self._stdRefFFT = self.calculateFFT(self.stdRef.time[0], self.stdRefAmp)
            self.stdRefFFT = self._stdRefFFT[self.start_idx: self.end_idx]
            self.fRange = self.stdRef.freq[0][self.start_idx: self.end_idx]
            self.qcLoopTask = asyncio.ensure_future(self.doQC())
            asyncio.gather(self.qcLoopTask)
        else:
            logger.error("[ERROR]: Config error > Standard reference is not loaded correctly.")
        await asyncio.sleep(0.01)
        

    @asyncSlot()
    async def finishQC(self):

        """Set QC running flag and wrap up session"""

        self.qcRunning = False
        self.qcComplete = True
        self.stopUpstream.emit()
        self.generateReport()
        await asyncio.sleep(3)
           

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
        #self.classifyTDS()                            # Live Cartridge sensing
        self.freq, self.FFT = self.calculateFFT(self.timeAxis,self.pulseAmp)
        self.avgProgVal = self.device.scanControl.currentAverages/\
                                 self.device.scanControl.desiredAverages*100
        
        await asyncio.sleep(0.1)
            

    async def waitForAck(self):

        """Wait for ACK from Robot"""

        while self.lastMessage != 'ACK':
            logger.info("Waiting for ACK")
            await asyncio.sleep(1)
        logger.info("ACK received")
            

    @asyncSlot()
    async def measureStandardRef(self):

        """Measure standard reference for QC and update config file."""
        
        await self.checkForSensor()
        await self.classifyTDS()
        await self.startAveraging(self.qcNumAvgs)

        if self.device.isAveragingDone():
            self.saveAverageData(data = self.device.avgResult, path = self.stdRefDir, headerType = 'stdRef')
            self.stopUpstream.emit()
        self.config['QC']['stdRefFileName'] = self.lastFile
        
        with open(self.config_file, 'w') as f:
            f.write(yaml.dump(self.config, default_flow_style = False))
            print(self.config)
            f.close()
            self.loadConfig()
            self.loadQcConfig()
            logger.info(f"Standard reference updated: {self.config['QC']['stdRefFileName']}")            


    @asyncSlot()
    async def startAveraging(self, numAvgs = None):

        """
            AsyncSlot coroutine to initiate the averaging task. Buttons are partially disabled during the process. 
        """                

        try:    
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
                logger.info(f"Scan completed: {self.device.scanControl.currentAverages}/{self.device.scanControl.desiredAverages}")
        
        except asyncio.CancelledError:
            logger.warning("Averaging interrupted")        


    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """
        logger.warning("cancelling tasks")
        try:
                
            if self.qcAvgTask is not None:
                logger.info("Cancelling qc averaging")
                self.qcAvgTask.cancel()   
                self.qcAvgTask.cancelled()   
                self.qcRunning = False        
            
            if self.qcLoopTask is not None:
                logger.info("Cancelling QC Loop Task")
                self.qcLoopTask.cancel()                     
                self.qcLoopTask.cancelled()                     
            
            if self.device.avgTask is not None:
                self.device.avgTask.cancel()
                self.device.avgTask.cancelled()
                logger.info("Averaging cancelled")

            if self.qcAvgTask is not None:
                logger.info("Cancelling qc averaging")
                self.qcAvgTask.cancel()   
                self.qcAvgTask.cancelled()   
                self.qcRunning = False        

            if self.quickScanTask is not None:
                logger.info("Cancelling quickscan task")
                self.quickScanTask.cancel() 
                self.quickScanTask.cancelled() 
                
            if self.ackTask is not None:
                logger.info("Cancelling Ack timer")
                self.ackTask.cancel()   
                self.ackTask.cancelled()

            await self.device.stop()
            await asyncio.sleep(2)

        except asyncio.CancelledError:
            logger.warning("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, 'theaConfig.yml')
