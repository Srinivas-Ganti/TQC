import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
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
      
        self.plotDataContainer = {'currentAveragePulseFft': None, 'livePulseFft': None}       # Dictionary for plot items
        self.startOk = False                                                                  # Flag for TDS pulse start time validation
        self.endOk = False                                                                    # Flag for TDS pulse end time validation
        self.avgsOk = False                                                                   # Flag for required pulse averages validation
        self.waferIdOk = False                                                                # Flag for wafer ID validation
        self.sensorIdOk = False                                                               # Flag for sensor ID validation
        self.repeatsOk = False                                                                # Flag for timelapse repeats validation
        self.intervalOK = False                                                               # Flag for timelapse duration validation
        self.tlapseSaveDir = None                                                             # Path for saving timelapse data
        self.classification = None                                                            # Result of TDS pulse classification.
        self.avgTask = None                                                                   # averaging task (manual - button event)
        self.qcAvgTask = None                                                                 # QC averaging task (automatic - cartridge sensing)
        self.timelapseTask = None                                                             # timelapse task (manual)
        self.pulsePeaks = None                                                                # result of peak finding on TDS pulse for classification
        self.qcParams = {}                                                                    # empty dictionary to hold qc parameters
        self.qcComplete = False                                                               # Flag to track qc task completeion
        self.qcResult = None                                                                  # QC result 
        self.qcRunNum = 0                                                                     # tracking inspected sensors
        self.qcRunning = False                                                                # Flag for QC running status
        self.previousClassification = None                                                    # previous classification result 
        self.qcResultsList = []                                                               # empty list to hold accumulated QC data on multiple sensors 


    def initAttribs(self):

        """
            Initialise class attributes for QC, timelapse application with default values.
        """

        self.pulseAmp = None                       # Received pulse data              
        self.avgPulseAmp = None                    # Averaged result
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

        self.isAcquiring = False                   # Flag to check if pulses are being received
        self.pulseLatency = 1                      # time in seconds for processing TDS pulses
        self.currentAverageFft = None              # averaged pulse FFT
        self.frame = None                          # timelapse frame
        self.frames = None                         # list of timelapse frames  
        self.keepRunning = False                   # Flag to keep runnning the processing of TDS pulses

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



#*********************************************************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, 'theaConfig.yml')
