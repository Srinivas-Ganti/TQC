import sys
import os

baseDirC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
controllerDir = os.path.join(baseDirC, "Controller")
MenloAPIDir = os.path.join(controllerDir, "Menlo")

sys.path.append(controllerDir)
sys.path.append(MenloAPIDir)


import asyncio
from asyncio.exceptions import CancelledError
from asyncqt import QEventLoop, asyncSlot
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget

from Menlo.scancontrolclient import ScanControlClient, ScanControlStatus


class Device(QWidget):

    dataUpdateReady = pyqtSignal(object)
    pulseReady = pyqtSignal(object)
    
    """Controller class for Menlo TeraSmart Spectrometer"""

    def __init__(self, loop):

        """ Create and initialise scanControl instance. Connection needs to be established before anything else happens"""
        super().__init__()

        if isinstance(loop, QEventLoop):
            self.client = ScanControlClient(loop = loop)
            self.connect()
            self.scanControl = self.client.scancontrol
            self.isAcquiring = False                   # Flag to check if pulses are being received
            self.keepRunning = False                   # Flag to keep runnning the processing of TDS pulses
            self.pulseReady = self.scanControl.pulseReady
            self.pulseData = None
            self.avgTask = None                        # averaging task 
            self.status = None
            self.pulseReady.connect(self.processPulses)   
            self.scanControl.statusChanged.connect(self._statusChanged) 
            print("DEVICE INITIALISED")
        else:
            print("CLIENT ERROR:")


    def __str__(self):
        
        return "A device object to control Menlo TeraSmart, Device is a subclass of QWidget"


    @asyncSlot()
    async def _statusChanged(self, status):

        """
            AsyncSlot Coroutine to indicate ScanControl Staus.
        """        

        strStatus = str(ScanControlStatus(status).name)
        self.status = strStatus
        if not self.status == "Acquiring":
            self.isAcquiring = False
        else:
            self.isAcquiring = True


    def setBegin(self, begin):

        """
            Set TDS pulse start time (ps)

            :type begin: int/ float
            :param begin: TDS pulse start time

        """
        
        if type(begin) is int or type(begin) is float:
            self.scanControl.setBegin(begin)
        else:
            print(f"[ERROR]: InputError: 'begin' should be a numeric value in picoseconds, got {type(begin)} instead.\n")

    
    def setDesiredAverages(self, desiredAvgs):

        """
            Set required averages.

            :type desiredAvgs: int
            :param desiredAvgs: required number of TDS pulse averages in scan.
        """        

        if desiredAvgs >= 0:
            self.numAvgs = desiredAvgs
            self.scanControl.setDesiredAverages(desiredAvgs)
        else:
            "[ERROR]: InputError: 'num_avgs' should be positve integer value or zero "


    def setEnd(self, end):

        """
            Set TDS pulse end time (ps).

            :type end: int/ float
            :param end: TDS pulse end time
        """

        if type(end) is int or type(end) is float:
            self.scanControl.setEnd(end)
        else:
            print(f"[ERROR]: InputError: 'end' should be a numeric value in picoseconds, got {type(end)} instead.\n")


    @asyncSlot()
    async def collectAveragesRepeatedly(self, data):

        """
            Print out pulse information and emit final average as signal.

            :type data: dict
            :param data: data dictionary with THz pulse information
        """
        asyncio.sleep(0.01)
        if self.scanControl.currentAverages > 0:
            self.pulseData = data
        print(f"Averaging: {self.scanControl.currentAverages}/{self.scanControl.desiredAverages}\r")
        if self.scanControl.currentAverages==self.scanControl.desiredAverages:
            avgData = data 
            self.resetAveraging()
            self.dataUpdateReady.emit(avgData)


    @asyncSlot()
    async def doAvgTask(self):

        """Perform averaging task and emit final result as signal"""

        await asyncio.sleep(0.01)
        
        if self.avgTask is not None:
            self.resetAveraging()

            if not self.isAcquiring:
                self.start()            

            # print(f"Averaging: {self.scanControl.currentAverages}/{self.scanControl.desiredAverages}\r")
            if self.scanControl.currentAverages==self.scanControl.desiredAverages:
                avgData = self.pulseData
                self.resetAveraging()
                self.dataUpdateReady.emit(avgData)
                    

    def resetAveraging(self):

        """
            Reset scancontrol averages
        """

        print("> [SCANCONTROL] Resetting averages")
        self.scanControl.resetAveraging()


    @asyncSlot()    
    async def start(self):

        """
            AsyncSlot Coroutine to open the detector and begin acquiring THz pulse data.
        """

        try:
            
            await self.scanControl.start()
            print("> [SCANCONTROL] Opening Detector") 
            
            self.isAcquiring = True    
            print("> [SCANCONTROL] Receiving Pulses . . . ")   

            if self.avgTask is not None and self.avgTask.done():
                self.setDesiredAverages(1)

            print("Default/ non task avgs set to single shot")

        except AttributeError:
            print("> [ERROR] InitalisationError: Menlo ScanControl is not ready. Please follow normal startup using Menlo ScanControl before launching the QC app")


    @asyncSlot()    
    async def stop(self):

        """
            AsyncSlot Coroutine to stop acquiring THz pulses. 
        """

        print("***********/ */ */ STOPPING */ */ */  ************")
        
        await self.scanControl.stop()
        
        self.isAcquiring = False
        self.keepRunning = False


    def connect(self):

        """
            Connect to TeraSmart
        """
        try:
            self.client.connect()
        except ConnectionRefusedError:
             print("""> [ERROR] ConnectionRefused: Please ensure ScanControl is active, Check laser ON, 
                         Antenna voltage should be enabled for correct operation""")


    def done(self, data):

        print("**********************Averaging Done**************************")
        print(data)


    @asyncSlot()
    async def processPulses(self, data):

        self.pulseData = data

#*********************************************************************************************************************


if __name__ == "__main__":

    """
        Collect averages repeatedly.
    """


    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    dev = Device(loop)
    

    # Connections are only for example, not hardcoded into the controller class
    dev.pulseReady.connect(dev.collectAveragesRepeatedly) 
    dev.dataUpdateReady.connect(dev.done)
    
    # Test of repeated averaging
    dev.setDesiredAverages(10)              
    dev.start()

    with loop: 

        sys.exit(loop.run_forever())
        
