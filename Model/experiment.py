from datetime import datetime
import numpy as np
import os
import sys
import yaml
from PyQt5.QtWidgets import QApplication


baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(baseDir)

from Controller.TQC_controller import *


class Experiment():
    
    def __init__(self, config_file):  

        self.config_file = config_file
        self.loadConfig()
        self.loadDevice()

    
    def loadConfig(self):
        
        """
            load and set config paramters
        """

        with open(self.config_file, 'r') as f:
            data = yaml.load(f, Loader= yaml.FullLoader)

        self.config = data


    def loadDevice(self):

        
        self.device = Device(loop)
        self.initialise()

    
    def initialise(self):

        self.device.resetAveraging()
        self.device.setBegin(self.config['TScan']['begin'])
        self.device.setEnd(float(self.config['TScan']['begin']) + float(self.config['TScan']['window']))
        self.device.setDesiredAverages(self.config['TScan']['numAvgs'])
        

    def saveAverageData(self, data):
        
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
        
        dataFolder = self.config['Export']['saveDir']
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


        

        
        
#***************************************************************

if __name__ == "__main__":

    """Load experiment configuration, collect averages repeatedly and 
       save data. Data is organized by date and measurement number (counter)"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

   
    experiment = Experiment('experiment.yml')
    print(experiment.config)
   
    
    experiment.device.pulseReady.connect(experiment.device.collectAverages)
    experiment.device.dataUpdateReady.connect(experiment.saveAverageData)

    experiment.device.start()

    with loop: 

        sys.exit(loop.run_forever())
        