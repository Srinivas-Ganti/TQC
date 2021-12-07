# %%
from datetime import datetime
from pandas.core.indexes import base

from pandas.core.indexes.base import InvalidIndexError

import matplotlib.pyplot as plt

import numpy as np
import os
import pandas as pd
import sys 
from scipy import signal


from scipy.signal import find_peaks
import yaml as yml

baseDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
configDir = os.path.join(baseDir, "Model")

sys.path.append(baseDir)
sys.path.append(rscDir)
sys.path.append(configDir)

airDir = os.path.join(rscDir, "AirExample")
sensorDir = os.path.join(rscDir, "SensorExample")


from Model.MenloLoader import MenloLoader

# %%
class Test():

    def __init__(self):

        self.mLoader = MenloLoader([]) 
        self.TdsWin = 400
        self.loadConfig()
       
        self.loadAir()
        self.loadRef()
        # self.freq, self.airFFT = self.calculateFFT(self.timeAxis, self.airTDS)
        # _, self.refFFT = self.calculateFFT(self.timeAxis, self.refTDS)
        
    
    def loadAir(self):
        
        self.airFiles = self.config['Temp']['airFileNames']
        src = [os.path.join(airDir, file) for file in self.airFiles]
        self.airTDS = self.mLoader.getTDS(src, [])
        self.timeAxis = self.mLoader.getTDS(src, [])[0]['time']

    def loadRef(self):
        
        self.refFiles = self.config['Temp']['sensorFileNames']
        src = [os.path.join(sensorDir, file) for file in self.refFiles]
        self.refTDS = self.mLoader.getTDS(src, [])


    def loadConfig(self, configFile = os.path.join(configDir,"theaConfig.yml")):

        with open(configFile, 'r') as f:
            configData = yml.load(f, Loader = yml.Loader)
        self.config = configData
        self.configLoaded = True
        if self.configLoaded:
            print("[QC]: Config Loaded")
            print(self.config)


    def calculateFFT(self, time, amp):

        t_ser_len = 16384
        T = time[1]-time[0] 
        time = time - time[0] # start timeseries at 0 ps
        N0 = len(time)
        time = time[:(self.mLoader.find_nearest(time, self.TdsWin)[0])+1]                   
        amp = amp[:(self.mLoader.find_nearest(time, self.TdsWin)[0])+1]
        # amp = amp - self.dcOffset # dc offset correction
        
        N = len(time)     
        w = signal.tukey(N, alpha = 0.1)   
        amp = w*amp                                        
        pad = t_ser_len - N  
        time = np.append(time, np.zeros(pad))          
        amp = np.append(amp, np.zeros(pad))
      
        N0 = len(time)
        freq = np.fft.fftfreq(N0, T)
        zero_THz_idx = self.mLoader.find_nearest(freq, 0)[0]
        freq= freq[zero_THz_idx:int(len(freq)/2)]
        FFT = np.fft.fft(amp)/(N0/2)   
        FFT = FFT[zero_THz_idx:int(len(FFT)/2)]     
        FFT = np.abs(FFT)
        return freq, FFT        

    # %%
t = Test()


def plotTDS(start, end, series):
    plt.figure(figsize=(15,10))
    StartIdx = t.mLoader.find_nearest(t.timeAxis, start)[0]
    EndIdx = t.mLoader.find_nearest(t.timeAxis, end)[0]
    y = series[StartIdx:EndIdx]
    x = t.timeAxis[StartIdx:EndIdx]
    plt.plot(x,y)
    
    return StartIdx, EndIdx


start, end = plotTDS(50,100,t.airTDS[0]['amp'])
x = t.timeAxis[start:end]

# %%
i = 0
distance = 80
prominence = 0.25
width = 19
threshold = 0.005

plt.figure(figsize=(15,10))
plt.suptitle(f"AIR {i}")
x1 = x
y1 = t.airTDS[i]['amp'][start:end]
apeaks0, _ = find_peaks(y1, distance = distance)
apeaks1, _ = find_peaks(y1, prominence= prominence)
apeaks2, _ = find_peaks(y1, width = width)
apeaks3, _ = find_peaks(y1, threshold = threshold)

plt.subplot(2,2,1)
plt.plot(apeaks0, y1[apeaks0], "xr"); plt.plot(y1); plt.legend(['distance'])


plt.subplot(2,2,2)
plt.plot(apeaks1, y1[apeaks1], "ob"); plt.plot(y1); plt.legend(['prominence'])

plt.subplot(2,2,3)
plt.plot(apeaks2, y1[apeaks2], "vg"); plt.plot(y1); plt.legend(['width'])


plt.subplot(2,2,4)
plt.plot(apeaks3, y1[apeaks3], "xk"); plt.plot(y1); plt.legend(['threshold'])
plt.show()
# %%
plt.figure(figsize=(15,10))
plt.suptitle(f"REFERENCE {i}")
x1 = x
y1 = t.refTDS[i]['amp'][start:end]
rpeaks0, _ = find_peaks(y1, distance = distance)
rpeaks1, _ = find_peaks(y1, prominence=prominence)
rpeaks2, _ = find_peaks(y1, width = width)
rpeaks3, _ = find_peaks(y1, threshold = threshold)

plt.subplot(2,2,1)

plt.plot(rpeaks0, y1[rpeaks0], "xr"); plt.plot(y1); plt.legend(['distance'])


plt.subplot(2,2,2)
plt.plot(rpeaks1, y1[rpeaks1], "ob"); plt.plot(y1); plt.legend(['prominence'])

plt.subplot(2,2,3)
plt.plot(rpeaks2, y1[rpeaks2], "vg"); plt.plot(y1); plt.legend(['width'])


plt.subplot(2,2,4)
plt.plot(rpeaks3, y1[rpeaks3], "xk"); plt.plot(y1); plt.legend(['threshold'])
plt.show()

print("DISTANCE: ",apeaks0, "\n", rpeaks0)
print("PROMINENCE: ",len(apeaks1), len(rpeaks1))
print("WIDTH: ",len(apeaks2), len(rpeaks2))
print("THRESHOLD: ",len(apeaks3), len(rpeaks3))

# %%