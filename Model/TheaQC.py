import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
# configDir  = os.path.join(baseDir, "Config") # use only if making a separate config dir
configDir = os.path.join(baseDir, "Model")  # if keeping in same dir as model
sys.path.append(baseDir)

from Model.experiment import *
from MenloLoader import MenloLoader


class TheaQC(Experiment):
    
    def __init__(self, loop = None, configFile = None):
        
        super().__init__(loop, configFile)
        self.initialise()
        

    def initialise(self):

        if self.configLoaded:
            self.initAttribs()
            self.initResources()
            self.mLoader = MenloLoader([])          # fileLoader object
            self.TdsWin = self.config['TScan']['window']


    def initResources(self):

        """
            Initialise class attributes for QC application with default values.
        """
      

        self.startOk = False                                  # Flag for TDS pulse start time validation
        self.endOk = False                                    # Flag for TDS pulse end time validation
        self.avgsOk = False                                   # Flag for required pulse averages validation
        self.waferIdOk = False                                # Flag for wafer ID validation
        self.sensorIdOk = False                               # Flag for sensor ID validation
        self.repeatsOk = False                                # Flag for timelapse repeats validation
        self.intervalOK = False                               # Flag for timelapse duration validation
        self.tlapseSaveDir = None                             # Path for saving timelapse data
        self.classification = "Sensor"                            # Result of TDS pulse classification.
        
        self.qcAvgTask = None                                 # QC averaging task (automatic - cartridge sensing)
        self.timelapseTask = None                             # timelapse task (manual)
        self.pulsePeaks = None                                # result of peak finding on TDS pulse for classification
        self.qcParams = {}                                    # empty dictionary to hold qc parameters
        self.qcComplete = False                               # Flag to track qc task completeion
        self.qcResult = None                                  # QC result 
        self.qcRunNum = 0                                     # tracking inspected sensors
        self.qcRunning = False                                # Flag for QC running status
        self.previousClassification = None                    # previous classification result 
        self.qcResultsList = []                               # empty list to hold accumulated QC data on multiple sensors 
        self.stdRef = None                                    # Standard reference data for QC  

    def initAttribs(self):

        """
            Initialise class attributes for QC, timelapse application with default values.
        """

        self.pulseAmp = None                       # Received pulse data              
        
        self.timeAxis = None                       # time data 
        self.timelapseRunning = False              # Flag to check if timelapse is running
        self.TdsWin = None                         # TDS windowing duration (ps)
        self.dcOffsetFile = None                   # DC offset file path
        self.dcOffset = None                       # DC background correction data
        self.FFT = None                            # FFT of the current pulse data
        self.freq = None                           # frequency (THz)
        self.configLoaded = False                  # Flag to check if config is loaded
        self.avgProgVal = 0                        # counter for averaging progress bar
        self.tlapseProgVal = 0                     # counter for timelapse progress bar
        self.tscans = []                           # empty list to contain the timelapse scan data
        self.numAvgs = None                        # number of set averages
        self.startTime = None                      # TDS pulse start time (ps)
        self.endTime = None                        # TDS pulse end time (ps)
        self.repeatNum = None                      # number of repeated aquisitions in the timelapse
        self.interval = None                       # time interval between aquisitions for timelapse
        self.waferId = None                        # QC wafer ID
        self.sensorId = None                       # QC sensor ID
        self.tdsParams = {}                        # Empty dictionary to hold TDS pulse parameters


        self.pulseLatency = 1                      # time in seconds for processing TDS pulses
        self.currentAverageFft = None              # averaged pulse FFT
        self.frame = None                          # timelapse frame
        self.frames = None                         # list of timelapse frames  
        

        self.chipsPerWafer = None                  # Parameter to trigger wafer ID change (not used)
        self.classificationDistance = None         # Pulse peak fitting parameters for classification- distance (see scipy.find_peaks())
        self.classificationProminence = None
        self.classificationWidth = None
        self.classificationThreshold = None
        self.stdRef = None                         # Standard reference TDS pulse data


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
        self.chipsPerWafer = self.config['QC']['chipsPerWafer']
        qcSaveDir = self.config['QC']['qcSaveDir']
        if qcSaveDir is None or not os.path.isdir(qcSaveDir):
            self.qcSaveDir = os.path.join(baseDir, "qcData")
            print(f"Setting default directory for qcData at: {self.qcSaveDir}")
        else:
            self.qcSaveDir = qcSaveDir
            print(f"QC data will be saved in: {self.qcSaveDir}")


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
        # self.classifyTDS()                            # Live Cartridge sensing
        # self.sensorUpdateReady.emit()
        self.freq, self.FFT = self.calculateFFT(self.timeAxis,self.pulseAmp)
        
        await asyncio.sleep(0.1)
        
 
    @asyncSlot()
    async def measureStandardRef(self):

        """Measure standard reference for QC and update config file."""
        await asyncio.sleep(1)
        while not self.device.avgTask.done():
            await asyncio.sleep(0.5)
        if self.device.avgTask.done():
            rawExportData = np.vstack([self.timeAxis, self.pulseAmp]).T
            currentDatetime = datetime.now()
            header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.04\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}
    Time [ps]              THz Signal [mV]"""
            base_name = f"""{currentDatetime.strftime("%d%m%yT%H%M%S")}_WID_{self.waferId}_SN_{self.sensorId}_STANDARD_Reference"""
            refPath = os.path.join(rscDir,"StandardReferences", base_name)
            data_file = os.path.join(refPath.replace("/","\\") +'.txt')
            print(data_file)
            np.savetxt(data_file, rawExportData, header = header, delimiter = '\t' )  
            
            newStdRef = data_file.split('/')[-1]
            self.config['QC']['stdRefFileName'] = newStdRef
            with open(os.path.join(configDir,"theaConfig.yml"), 'w') as f:
                f.write(yaml.dump(self.config, default_flow_style = False))
            
            self.loadConfig()
            self.initialise()
            self.loadStandardRef()
            print("STD REF LOADED")
            

    @asyncSlot()
    async def startAveraging(self):

        """
            AsyncSlot coroutine to initiate the averaging task. Buttons are partially disabled during the process. 
        """                
        self.device.setDesiredAverages(self.tdsParams['numAvgs'])
        await asyncio.sleep(0.1)
        if self.device.avgTask is not None and  self.device.avgTask.done():
                self.device.avgTask = None
                

        await asyncio.sleep(0.01)
        self.device.keepRunning = True
        self.device.avgTask = asyncio.ensure_future(self.device.doAvgTask())
        await asyncio.gather(self.device.avgTask)
        

    def loadStandardRef(self):

        """
            Load Standard Reference file for comparative QC
        """


        refPath = os.path.join(rscDir,"StandardReferences", self.config['QC']['stdRefFilePath'])
        print(refPath)
        try:
            stdRefData = MenloLoader([refPath]).data
            self.stdRef = stdRefData
            print("Standard reference loaded")
            print(self.stdRef)
        except:
            print(f"[ERROR]: FileNotFound. No resource file called {self.config['QC']['stdRefFilePath']}")


    @asyncSlot()
    async def cancelTasks(self):

        """
            Cancel async tasks. (software stop)
        """
        print("cancelling tasks")
        try:
            if self.timelapseTask is not None:
                print("CANCELLING TLAPSE TASK")
                self.timelapseTask.cancel()

            if self.device.avgTask is not None:
                self.device.avgTask.cancel()
                print("Averaging cancelled")
            if self.qcAvgTask is not None:
                print("QC cancelled")
                self.qcAvgTask.cancel()                
        except CancelledError:
            print("Shutting down tasks")


#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, 'theaConfig.yml')
