import sys
import os
from pyqtgraph.exporters import ImageExporter

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")
configDir = os.path.join(viewDir, "config")
rscDir = os.path.join(baseDir, "Resources")

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(rscDir)
sys.path.append(viewDir)
sys.path.append(configDir)
sys.path.append(uiDir)


from Model.experiment import *
from Resources import ur
from MenloLoader import MenloLoader
import pandas as pd


from Model.TemperatureSensor import *
# from scipy.signal import find_peaks

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

class TheaTimelapse(Experiment):

    timelapseFinished = pyqtSignal()
    nextScan = pyqtSignal() 
    
    def __init__(self, loop = None, config_file = None):
        
        super().__init__(loop, config_file)
        try:
            self.initialise()
        except Exception as e:
            raise e


    def initialise(self):

        """
            Initialise experiment parameters
        """

        if self.configLoaded:
            self.initAttribs()
            self.initResources()
            self.mLoader = MenloLoader([])          # fileLoader object
            self.TdsWin = self.config['TScan']['window']
            self.maxStorage = self.config['Timelapse']['maxStorage']
            self.filesize =  self.config['Timelapse']['_filesize']
            self.exportPath = self.config['Export']['saveDir']
            self.checkSessionStorage()


    def initResources(self):

        """
            Initialise class attributes for timelapse with default values.
        """

        self.startOk = False                                  # Flag for TDS pulse start time validation
        self.endOk = False                                    # Flag for TDS pulse end time validation
        self.avgsOk = False                                   # Flag for required pulse averages validation
        self.framesOk = False                                 # Flag for timelapse frame num validation
        self.intervalOk = False                               # Flag for timelapse interval validation
        self.srcTDS = []                                      # list to store tds dictionaries
        self.dtlist = []                                      # list to store datetime information  
        

    def initAttribs(self):

        """
            Initialise class attributes for QC application with default values.
        """

        self.pulseAmp = None                       # Received pulse data              
        self.timeAxis = None                       # time data 
        self.TdsWin = None                         # TDS windowing duration (ps)
        self.FFT = None                            # FFT of the current pulse data
        self.freq = None                           # frequency (THz)
        self.avgProgVal = 0                        # counter for averaging progress bar
        self.tlapseProgVal = 0                     # counter for timelapse progress bar     
        self.numAvgs = None                        # number of set averages
        self.startTime = None                      # TDS pulse start time (ps)
        self.endTime = None                        # TDS pulse end time (ps)
        self.interval = None                       # frame interval
        self.numRequestedFrames = None             # frames requested by user 
        self.tdsParams = {}                        # Empty dictionary to hold TDS pulse parameters
        self.currentAverageFft = None              # averaged pulse FFT
        self.scanName = None                       # Name for dataframe to be saved
        self.currentFrame = None                   # current frame to be saved
        self.numData = None                        # progress ctr for timelapse         
        self.filesize = None                       # filesize in kB , +1 kB for safety 
        self.maxStorage = None                     # maximum allocated data storage loaded from config file
        self.maxFrames = None                      # Upper limit for frames viz maxStorage
        self.numFramesDone = 0                     # variable to mark timelapse progress 
        self.timelapseTask = None
        self.continueTimelapse = None              # flag to control/ suspend aqcuisition
        self.timelapseDone = False                 # flag to control progress
        self.results = pd.DataFrame()                      # this will be the resulting dataFrame
        self.GIFSourceNames = []                   # names of files to make a GIF out of
        self.tempSensorModel = None                # temperature sensor model
        self.port = None                           # serial communication port
        self.configLoaded = None                   # config loaded flag
        self.serial = None                         # serial communications object
        self.baudrate = None                       # baudrate for serial communication
        self.lastMessage = None                    # serial data received
        self.ackTask = None                        # wait for ACK task  
        self.ctr = 0                               # temperature observations counter 
        self.epoch = 1                             # temperature data buffer counter
        self.keepRunning = False                   # continue flag for temperature observations
        self.tempObsTask = None                    # temperature observation task
        self.currentTemp = None                    # sensor reading temperature


    def checkSessionStorage(self):

        """
        Compute maximum allowable frames to be saved
        """

        self.maxFrames = int(ur(self.maxStorage).m_as('kB')/ur(self.filesize).m_as('kB'))


    def initTemperatureSensor(self, loop, configFileName):
        
        """
            Initialise MAX31855 sensor object
        """

        self.tempSensorModel = MAXSerialTemp(loop, configFileName)


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
        
        self.freq, self.FFT = self.calculateFFT(self.timeAxis,self.pulseAmp)
        self.avgProgVal = int(self.device.scanControl.currentAverages/\
                                 self.device.scanControl.desiredAverages*100)
        
        await asyncio.sleep(0.1)
        
 
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
        temp1 = self.currentTemp
        await asyncio.gather(self.device.avgTask)
        while not self.device.isAveragingDone():
            await asyncio.sleep(1)
        if self.device.isAveragingDone():
            temp2 = self.currentTemp
            logger.info(f"{self.device.scanControl.currentAverages}/{self.device.scanControl.desiredAverages}")
            logger.info("Averaging completed")
            rawExportData = np.vstack([self.timeAxis, self.pulseAmp]).T
            currentDatetime = datetime.now()

            header = f"""THEA TIMELAPSE - RAM Group GmbH, powered by Menlo Systems\nProgram Version 0.2\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_{self.scanName}_{temp1}C_{temp2}C_data{self.numFramesDone+1:04d}"""
            exportPath = os.path.join(self.exportPath, base_name)
            data_file = os.path.join(exportPath.replace("/","\\") +'.txt')
            logger.info(f"EXPORTED: {data_file}")
            df = pd.DataFrame.from_dict({'frameNum': f"data{self.numFramesDone+1:04d}" , 
                                         'datetime': currentDatetime, 
                                         'time':self.timeAxis, 
                                         'amp':self.pulseAmp, 
                                         'freq' : self.freq, 
                                         'FFT': self.FFT, 
                                         'startTemp':temp1,
                                         "endTemp":temp2},
                                          orient='index')
            df = df.transpose()
            self.results = pd.concat([self.results, df], axis = 0).reset_index(drop = True)
            #np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            self.numFramesDone +=1
            print(self.results.tail())


    @asyncSlot()
    async def newScan(self):

        """Do a new scan"""

        self.device.resetAveraging()
        await self.startAveraging()
        

    @asyncSlot()
    async def timelapseStart(self):

        try:
            self.results = pd.DataFrame()
            self.timelapseDone = False
            self.continueTimelapse = True
            self.GIFSourceNames = [] 
            self.timelapseFinished.emit()   # emit this to check validity of the btn states

            if self.numRequestedFrames == 0:     
                self.numRequestedFrames = self.maxFrames
            for i in range(self.numRequestedFrames):
                if self.continueTimelapse:       
                    logger.info(f"[TIMELAPSE]: FRAME {i+1}/{self.numRequestedFrames}")
                    self.timelapseTask =  asyncio.ensure_future(self.newScan())
                    asyncio.gather(self.timelapseTask)
                    self.nextScan.emit()
                    while not self.timelapseTask.done():
                        await asyncio.sleep(1)
                    self.tlapseProgVal = int((i+1)/self.numRequestedFrames*100)
                    
                    logger.info(f"[TIMELAPSE]: {self.tlapseProgVal}% - FRAME {i+1}/{self.numRequestedFrames}")
                    if i+1 < self.numRequestedFrames:
                        logger.info(f"[TIMELAPSE]: AWAITING INTERVAL TIMEOUT . . . {self.interval} seconds ")
                        await asyncio.sleep(self.interval) 
                    logger.info(f"[TIMELAPSE]: {self.tlapseProgVal}% FINISHED - FRAMES {i+1}/{self.numRequestedFrames} DONE")
                    self.nextScan.emit()
            await asyncio.sleep(2)
            self.cancelTasks()
            self.device.stop()
            self.timelapseDone = True
            self.numFramesDone = 0 # reset counter for new timelapse if initiated through the GUI
            df = self.results 
            df.to_pickle(f"{self.scanName}_{self.interval}s_{self.numRequestedFrames}.pkl")
            logger.info("TIMELAPSE FINISHED - DATAFRAME EXPORTED")
        except asyncio.exceptions.CancelledError:
            logger.info("CANCELLED TIMELAPSE")        
            self.timelapseFinished.emit()
     

    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """

        logger.info("cancelling previously scheduled tasks")
        try:
            if self.device.avgTask is not None:
                self.continueTimelapse = False
                self.timelapseTask.cancel()
                self.device.avgTask.cancel()
                self.continueTimelapse = False
                self.timelapseDone = True
                self.timelapseFinished.emit()
                self.avgProgVal = 0
                self.tlapseProgVal = 0
                self.numFramesDone = 0
                self.continueTimelapse = False
                if self.tempObsTask is not None:
                    self.tempObsTask.cancel()
        
        except asyncio.exceptions.CancelledError:
            logger.info("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = TheaTimelapse(loop, 'timelapseConfig.yml')
