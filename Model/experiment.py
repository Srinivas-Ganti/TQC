from datetime import datetime
import numpy as np
import os
import sys
import yaml
from PyQt5 import uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pyqtgraph import PlotWidget, graphicsItems, TextItem
from pyqtgraph.graphicsItems.PlotDataItem import PlotDataItem, PlotCurveItem
from scipy import signal as sgnl
import signal

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(baseDir)

from Controller.TQC_controller import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s:%(name)s:%(message)s")

file_handler = logging.FileHandler(os.path.join(logDir, 'experiment.log'))
stream_handler = logging.StreamHandler()

file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(formatter)

stream_handler.setLevel(logging.ERROR)
stream_handler.setFormatter(formatter)


logger.addHandler(file_handler)
logger.addHandler(stream_handler)

        

class Experiment(QWidget):

    configReady = pyqtSignal()
    stopUpstream = pyqtSignal() #  signal to app to stop the controller
    
    def __init__(self, loop, config_file): 

        super().__init__()
        self.loop = loop
        
        self.config_file = config_file
        self.configLoaded = False
        try:
            self.loadConfig()
            self.loadDevice()
            self.device.stop()            # Always begin in "Stop" state
            self.device.resetAveraging()  # Always begin with averaging buffer cleared
            self.stdRefDir = None         # path to std ref dir
            self.lastFile = None          # Full path of the last file being saved
        except AttributeError as a:
            logger.error("Scan Control not found. Please ensure Menlo ScanControl is ON")
            raise a
        except FileNotFoundError as f:
            logger.error("Problem loading config file, check file path")
            raise f
        


    def makeHeader(self, kind = 'default'):

        """Makes a header for the file to be saved"""

        currentDatetime = datetime.now()
        
        if kind == 'default':

            
            header = f"""THEA QC - RAM Group GmbH & Menlo Systems GmbH\nProgram Version 1.05\nAverage over {self.device.scanControl.desiredAverages} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}, Lot number: {self.lotNum}, wafer num: {self.waferId}
            User time axis shift: {self.config['TScan']['begin']*-1}
            Time [ps]              THz Signal [mV]"""  

            filename = f"""{currentDatetime.strftime("%y-%m-%dT%H%M%S")}_T_NIL_RH_NIL_PID_NIL_SN_{self.sensorId}_Reference.txt"""    

        if kind == 'qc':

            header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.05\nAverage over {self.numAvgs} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
            User time axis shift: {self.config['TScan']['begin']*-1}, QC Parameters: {self.qcParams}
            Time [ps]              THz Signal [mV]"""

        filename = f"""{currentDatetime.strftime("%y-%m-%dT%H%M%S")}_T_NIL_RH_NIL_PID_NIL_SN_{self.sensorId}_{self.qcResult}_Reference.txt"""    
        
        return header, filename


    def loadConfig(self):
        
        """
            load and set config paramters
        """

        with open(self.config_file, 'r') as f:
            data = yaml.load(f, Loader= yaml.FullLoader)

        self.config = data
        self.configLoaded = True


    def loadDevice(self):

        """Load ScanControl object"""

        self.device = Device(self.loop)
        self.initialiseModel()
        logger.info("DEVICE LOADED")
    
    
    def initialiseModel(self):

        """Initialse scancontrol with startup measurement parameters"""

        logger.info("Setting ScanControl measurement parameters")
        self.device.resetAveraging()
        self.device.setBegin(self.config['TScan']['begin'])
        self.device.setEnd(float(self.config['TScan']['begin']) + float(self.config['TScan']['window']))
        # self.device.setDesiredAverages(1) # default to single shot unless in averaging task
        

    def saveAverageData(self, data = None, path = "default", headerType = 'default'):
        
        """
            Saves data in the default folder specified in config.
            TimeAxis is offset to start at 0 ps.

            :type data: dict
            :param data: THz data (TDS and FFT)

        """

        if headerType in ['default', 'stdRef']:
            header, filename = self.makeHeader(kind = 'default')
        elif headerType == 'qc':
            header, filename = self.makeHeader(kind = 'qc')
            
            # Note to self: handle exceptions here
        
        if data == 0: 
            data = self.device.avgResult
            logger.info("Saving last averaged result")
        else:
            logger.info("Saving result from received data object")

        try:
            avgAmp = data['amplitude'][0]
            time = data['timeaxis'] - data['timeaxis'][0]  
            tds = np.vstack([time, avgAmp]).T
        except TypeError:
            logger.error("No data to save")
            return

        if path == "default":
            dataFolder = self.config['Export']['saveDir']
        else:
            dataFolder = path
        try:
            todayFolder = f'{datetime.today():%Y-%m-%d}'
            savingFolder = os.path.join(dataFolder, todayFolder)
            if not os.path.isdir(savingFolder):
                os.makedirs(savingFolder)
        
            dataFile = os.path.join(savingFolder, f'{filename}')
            if headerType == 'stdRef':
                self.lastFile = dataFile.split(self.stdRefDir)[1][1:]
            else:
                self.lastFile = filename
            np.savetxt(dataFile, tds, delimiter = '\t' , header = header)
        except:
            logger.error("Invalid file path to export averaging data")


    def calculateFFT(self, time, amp):
        
        """
            Calculate FFT of THz pulse.

            :type time: numpy array
            :param time: timeaxis data of THz pulse
            :type amp: numpy array
            :param amp: Pulse amplitude data.

            :return: frequency axis data and FFT data
            :rtype: numpy array, numpy array

        """        

        t_ser_len = 16384
        T = time[1]-time[0] 
        N = len(time)     
        w = sgnl.tukey(N, alpha = 0.1)   
        amp = w*amp                                        
        pad = t_ser_len - N  
        time = np.append(time, np.zeros(pad))          
        amp = np.append(amp, np.zeros(pad))
      
        N0 = len(time)
        freq = np.fft.fftfreq(N0, T)
        zero_THz_idx = self.find_nearest(freq, 0)[0]
        freq= freq[zero_THz_idx:int(len(freq)/2)]
        FFT = np.fft.fft(amp)/(N0/2)   
        FFT = FFT[zero_THz_idx:int(len(FFT)/2)]     
        FFT = np.abs(FFT)
        return freq, FFT

        
    def find_nearest(self, array, value):        

        """"
        Retrun the index and value of the element in the array that is nearest to the given input value
        
            :type array: numpy array
            :param array: np array in which to search for nearest value.
            :type value: float, or int
            :param value: array element to be compared to this value.

            :return: resulting array index and its value, 
            :rtype: int, float


        """

        array = np.asarray(array)
        idx = (np.abs(array - value)).argmin()
        return idx, array[idx] 

  

#***************************************************************

if __name__ == "__main__":

    """Load experiment configuration, collect averages repeatedly and 
       save data. Data is organized by date and measurement number (counter)"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

   
    experiment = Experiment(loop, 'experiment.yml')
    print(experiment.config)
   
    
    experiment.device.pulseReady.connect(experiment.device.collectAverages)
    experiment.device.dataUpdateReady.connect(experiment.saveAverageData)

    experiment.device.start()

    with loop: 

        sys.exit(loop.run_forever())
        