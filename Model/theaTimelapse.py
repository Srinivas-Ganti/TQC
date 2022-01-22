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

from scipy.signal import find_peaks


class TheaTimelapse(Experiment):

    
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
        
        self.currentFrame = None                   # current frame to be saved
        self.numData = None                        # progress ctr for timelapse         
        self.filesize = None                       # filesize in kB , +1 kB for safety 
        self.maxStorage = None                     # maximum allocated data storage loaded from config file
        self.maxFrames = None                      # Upper limit for frames viz maxStorage
        self.numFramesDone = 0                     # variable to mark timelapse progress 
        self.timelapseTask = None
        self.continueTimelapse = None               # flag to control/ suspend aqcuisition

    def checkSessionStorage(self):

        """Compute maximum allowable frames to be saved"""

        self.maxFrames = int(ur(self.maxStorage).m_as('kB')/ur(self.filesize).m_as('kB'))


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
        #self.tlapseProgVal = self.numRequestedFrames/self.maxFrames*100  # check later
        await asyncio.sleep(0.1)
        
 

    @asyncSlot()
    async def startAveraging(self, numAvgs = None):

        """
            AsyncSlot coroutine to initiate the averaging task. Buttons are partially disabled during the process. 
        """                
        await asyncio.sleep(0.1)
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
            header = f"""THEA TIMELAPSE - RAM Group GmbH, powered by Menlo Systems\nProgram Version 0.2\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_{self.currentFrame}"""
            exportPath = os.path.join(self.exportPath, base_name)
            data_file = os.path.join(exportPath.replace("/","\\") +'.txt')
            print(data_file)
            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            

    @asyncSlot()
    async def nextFrame(self):

        """Do a new scan"""

        self.device.resetAveraging()
        await self.startAveraging()
        self.numFramesDone +=1



    @asyncSlot()
    async def timelapseStart(self):

        try:
            self.continueTimelapse = True
            if self.numRequestedFrames == 0:     
                self.numRequestedFrames = self.maxFrames
            for i in range(self.numRequestedFrames):
                if self.continueTimelapse:       
                    print(f"[TIMELAPSE]: FRAME {i+1}/{self.numRequestedFrames}")
                
                    self.timelapseTask =  asyncio.ensure_future(self.nextFrame())
                    
                    asyncio.gather(self.timelapseTask)
                    while not self.timelapseTask.done():
                        await asyncio.sleep(1)
                    self.tlapseProgVal = int((i+1)/self.numRequestedFrames*100)
                    print(f"[TIMELAPSE]: {self.tlapseProgVal}% - FRAME {i+1}/{self.numRequestedFrames}")

                    if i+1 < self.numRequestedFrames:
                        print(f"[TIMELAPSE]: AWAITING INTERVAL TIMEOUT . . . {self.interval} seconds ")
                        await asyncio.sleep(self.interval) 
                    print(f"[TIMELAPSE]: {self.tlapseProgVal}% FINISHED - FRAMES {i+1}/{self.numRequestedFrames} DONE")

        except asyncio.exceptions.CancelledError:
            print("CANCELLED TIMELAPSE")        

            
  

    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """
        print("cancelling tasks")
        try:
            if self.device.avgTask is not None:
                self.device.avgTask.cancel()
                self.timelapseTask.cancel()
                print("Averaging cancelled")
                self.avgProgVal = 0
                self.tlapseProgVal = 0
                self.numFramesDone = 0
                self.continueTimelapse = False
        
        except CancelledError:
            print("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = TheaTimelapse(loop, 'timelapseConfig.yml')
