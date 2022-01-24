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
from scipy import signal


baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(baseDir)

from Controller.TQC_controller import *


class Experiment(QWidget):

    configReady = pyqtSignal()
    
    def __init__(self, loop, config_file): 

        super().__init__()
        self.loop = loop
        
        self.config_file = config_file
        self.configLoaded = False
        self.loadConfig()
        self.loadDevice()
        self.device.stop()            # Always begin in "Stop" state
        self.device.resetAveraging()  # Always begin with averaging buffer cleared
        

    def loadConfig(self):
        
        """
            load and set config paramters
        """

        with open(self.config_file, 'r') as f:
            data = yaml.load(f, Loader= yaml.FullLoader)

        self.config = data
        self.configLoaded = True


    def loadDevice(self):

        self.device = Device(self.loop)
        self.initialiseModel()
        print("DEVICE LOADED")
    
    
    def initialiseModel(self):

        print("INITIALISING FROM BASE EXPERIMENT")
        self.device.resetAveraging()
        self.device.setBegin(self.config['TScan']['begin'])
        self.device.setEnd(float(self.config['TScan']['begin']) + float(self.config['TScan']['window']))
        # self.device.setDesiredAverages(1) # default to single shot unless in averaging task
        

    def saveAverageData(self, data, path = "default"):
        
        """
            Saves data in the default folder specified in config.
            TimeAxis is offset to start at 0 ps.

            :type data: dict
            :param data: THz data (TDS and FFT)

        """

        currentDatetime = datetime.now()
        avgAmp = data['amplitude'][0]
        time = data['timeaxis'] - data['timeaxis'][0]  
        tds = np.vstack([time, avgAmp]).T

        header = f"""THEA QC - RAM Group GmbH, powered by Menlo Systems\nProgram Version 1.05\nAverage over {self.device.scanControl.desiredAverages} waveforms. Start: {self.config['TScan']['begin']} ps, Timestamp: {currentDatetime.strftime('%Y-%m-%dT%H:%M:%S')}
    User time axis shift: {self.config['TScan']['begin']*-1}
    Time [ps]              THz Signal [mV]"""    
        
        if path == "default":
            dataFolder = self.config['Export']['saveDir']
        else:
            dataFolder = path
        try:
            todayFolder = f'{datetime.today():%Y-%m-%d}'
            savingFolder = os.path.join(dataFolder, todayFolder)
            if not os.path.isdir(savingFolder):
                os.makedirs(savingFolder)

            filename = self.config['Export']['filename']
            baseName = filename.split('.')[0]
            ext = filename.split('.')[-1]
            i = 1
            while os.path.isfile(os.path.join(savingFolder, f'{baseName}_{i:04d}.{ext}')):
                i+=1
            dataFile = os.path.join(savingFolder, f'{baseName}_{i:04d}.{ext}')
            np.savetxt(dataFile, tds, header = header)
        except:
            print("Invalid file path to export averaging data")


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
        w = signal.tukey(N, alpha = 0.1)   
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
        