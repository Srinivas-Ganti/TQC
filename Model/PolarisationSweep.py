import sys
import os


from pyqtgraph.exporters import ImageExporter
baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
viewDir = os.path.join(baseDir, "View")
# configDir = os.path.join(baseDir, "Model")  # if keeping in same dir as model
sys.path.append(baseDir)
sys.path.append(viewDir)

from Model.experiment import *
from Resources import ur
from MenloLoader import MenloLoader
import pandas as pd
from PyQt5 import QtSerialPort

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


class TheaPolSweep(Experiment):

    polSweepFinished = pyqtSignal()
    nextScan = pyqtSignal() 
    

    def __init__(self, loop = None, configFile = None):
        
        super().__init__(loop, configFile)
        self.initialise()
        

    def initialise(self):

        """
            Initialise experiment parameters
        """


        if self.configLoaded:
            self.initAttribs()
            self.initResources()
            
            self.mLoader = MenloLoader([])          # fileLoader object
            self.TdsWin = self.config['TScan']['window']
            self.exportPath = self.config['Export']['saveDir']
          
            self.loadRobotConfig()
            self.initRobot()


    def initRobot(self):

        """Initialise robot via serial port"""

        try:
            self.serial = QtSerialPort.QSerialPort(self.port)
            self.serial.setBaudRate(self.baudrate)
        except:
            print("Could not open serial device")


    def loadRobotConfig(self):

        """Load serial port config for robot"""

        if self.configLoaded:
            self.port = self.config['Robots']['port']
            self.baudrate = self.config['Robots']['baudrate']
            self.angle1Lim = self.config['Robots']['angle1Lim']
            self.angle2Lim = self.config['Robots']['angle2Lim']
            self.timeout = self.config['Robots']['timeout']
            self.angRes = self.config['Robots']['angRes']

    def initResources(self):

        """
            Initialise class attributes for timelapse with default values.
        """

        self.startOk = False                                  # Flag for TDS pulse start time validation
        self.endOk = False                                    # Flag for TDS pulse end time validation
        self.avgsOk = False                                   # Flag for required pulse averages validation
        self.angle1Ok = False                                 # Flag for angle1 input validity 
        self.framesOk = False                               # Flag for timelapse interval validation
        self.angle2Ok = False                                 # Flag for angle2 input validity 
        self.srcTDS = []                                      # list to store tds dictionaries
        self.dtlist = []                                      # list to store datetime information  
        self.port = None                                      # Serial port name
        self.baudrate = None                                  # baudrate for serial communication  
        self.serial = None                                    # Serial object to communicate with robots
        self.lastMessage = None 
        self.angle1Lim = None                                # angle 1 limit
        self.angle2Lim = None                                # angle 2 limit  
        self.angle1 = None                                   # angle 1 set pt
        self.angle2 = None                                   # angle2 set pt


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
        self.polSweepProgVal = 0                     # counter for timelapse progress bar     
        self.numAvgs = None                        # number of set averages
        self.startTime = None                      # TDS pulse start time (ps)
        self.endTime = None                        # TDS pulse end time (ps)
   
        self.numRequestedFrames = None             # frames requested by user 
        self.requestedAngle = None                 # track the holder angle requested by user during scan
        self.actualAngle = None
        self.tdsParams = {}                        # Empty dictionary to hold TDS pulse parameters
        self.currentAverageFft = None              # averaged pulse FFT
        
        self.currentFrame = None                   # current frame to be saved
        self.numData = None                        # progress ctr for timelapse         
        self.numFramesDone = 0                     # variable to mark timelapse progress 
        self.polSweepTask = None
        self.continuePolSweep = None              # flag to control/ suspend aqcuisition
        self.timelapseDone = False                 # flag to control progress
        self.results = pd.DataFrame()                      # this will be the resulting dataFrame
        self.GIFSourceNames = []                   # names of files to make a GIF out of
        self.timeout = None
        self.ackTask = None                         # wait for ack with timeout
        self.scanName = None

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
       
        if numAvgs == None:            
            self.device.setDesiredAverages(self.numAvgs)
            print(f"default averaginig: {self.numAvgs}")
        else:
            self.device.setDesiredAverages(numAvgs)
            print(f"special averaginig: {numAvgs}")
                
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

            header = f"""THEA Phi Scan - RAM Group GmbH, powered by Menlo Systems\nProgram Version 0.2\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}, Phi: {self.actualAngle:03f}
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_{self.scanName}_data{self.numFramesDone+1:04d}"""
            exportPath = os.path.join(self.exportPath, base_name)
            data_file = os.path.join(exportPath.replace("/","\\") +'.txt')
            print(f"EXPORTED: {data_file}")
            df = pd.DataFrame.from_dict({'frameNum': f"data{self.numFramesDone+1:04d}" , 'datetime': currentDatetime, 'time':self.timeAxis, 'amp':self.pulseAmp, 'freq' : self.freq, 'FFT': self.FFT}, orient='index')
            df = df.transpose()
            self.results = pd.concat([self.results, df], axis = 0).reset_index(drop = True)
            
            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            self.numFramesDone +=1
            
            print(self.results.tail())

            

    @asyncSlot()
    async def newScan(self):

        """Do a new scan"""

        self.device.resetAveraging()
        await self.startAveraging()
        


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


    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """
        logger.warning("cancelling tasks")
        try:
           
                         
            
            if self.device.avgTask is not None:
                self.device.avgTask.cancel()
                self.device.avgTask.cancelled()
                logger.info("Averaging cancelled")

          
                
            if self.ackTask is not None:
                logger.info("Cancelling Ack timer")
                self.ackTask.cancel()   
                self.ackTask.cancelled()

            await self.device.stop()
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.warning("Shutting down tasks")


    def homeRobot(self):

        """Send command on serial to insert cartridge"""

        txt = "home\n"
        self.serial.write(txt.encode())

    def rotateHolder(self, angle):

        """Send command on serial to insert cartridge"""
        
        if angle == self.angle1:     
            txt = f"rot+{angle:2f}\n"
        else:
            txt = f"rot-{angle:.2f}\n"
        self.serial.write(txt.encode())


    def goHome(self):

        txt = f"rot+{abs(self.sweepArray[-1]):3f}\n"
        self.serial.write(txt.encode())


    async def getPosition(self):

        """Send command on serial to insert cartridge"""
        
        txt = "pos\n"
        self.serial.write(txt.encode())
        await asyncio.sleep(0.5)
        print(self.lastMessage)
        self.currentPosition = self.lastMessage

    @asyncSlot()
    async def polSweepStart(self):

        try:
            self.results = pd.DataFrame()
            self.polSweepDone = False
            self.continuePolSweep = True
            self.GIFSourceNames = [] 
            self.polSweepFinished.emit()   # emit this to check validity of the btn states

            self.homeRobot()
            await self.waitOnRobot()
            logger.info("Homing complete. . .")
            
            for i in range(len(self.sweepArray)):
                if i == 0:
                    self.requestedAngle =  self.sweepArray[i]
                else:
                    self.requestedAngle = abs(self.sweepArray[i-1] - self.sweepArray[i])
                self.actualAngle = self.sweepArray[i]
                print(f"Scan {i}/{len(self.sweepArray)}")
                self.rotateHolder(self.requestedAngle)
                await self.waitOnRobot()
                await self.getPosition()
            
                self.polSweepTask =  asyncio.ensure_future(self.newScan())
                asyncio.gather(self.polSweepTask)

                while not self.polSweepTask.done():
                    await asyncio.sleep(1)

                self.polSweepProgVal = int((i+1)/len(self.sweepArray)*100)
                print(f"Pol. sweep progress: {self.polSweepProgVal} %")
                self.nextScan.emit()
                await asyncio.sleep(0.1)
               
                
                
            #         
            self.cancelTasks()
            await self.device.stop()
            self.polSweepDone = True
            self.continuePolSweep = False
            self.numFramesDone = 0 # reset counter for new timelapse if initiated through the GUI
            self.polSweepFinished.emit()
            await asyncio.sleep(1)
            self.goHome()
            df = self.results 
            df.to_pickle(f"{self.scanName}_{self.angle1}_{self.angle2}_{self.numRequestedFrames}.pkl")
            print("SCAN COMPLETED AND DATAFRAME EXPORTED")


        except asyncio.exceptions.CancelledError:
            print("CANCELLED TIMELAPSE")        

    
    async def waitForAck(self):

        """Wait for ACK from Robot"""

        while self.lastMessage != 'ACK':
            logger.info("Waiting for ACK")
            await asyncio.sleep(1)
        logger.info("ACK received")


    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """

        print("cancelling previously scheduled tasks")
        try:
            if self.device.avgTask is not None:
                
                self.polSweepTask.cancel()
                self.device.avgTask.cancel()
                self.continuePolSweep = False
                self.polSweepDone = True
                self.polSweepFinished.emit()
                self.avgProgVal = 0
                self.polSweepProgVal = 0
                self.numFramesDone = 0
                
        except asyncio.exceptions.CancelledError:
            print("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = TheaPolSweep(loop, 'polSweepConfig.yml')
