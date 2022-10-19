from cmath import nan
import sys
import os

from numpy import double



baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
viewDir = os.path.join(baseDir, "View")
uiDir = os.path.join(viewDir, "Designer")
configDir = os.path.join(viewDir, "config")

sys.path.append(baseDir)
sys.path.append(modelDir)
sys.path.append(viewDir)
sys.path.append(configDir)
sys.path.append(uiDir)

from Model.TemperatureSensor import *
from Model import ur

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s:%(name)s:%(message)s")

file_handler = logging.FileHandler(os.path.join(logDir, 'App.log'))
stream_handler = logging.StreamHandler()

file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)



class TempTimelapseWindow(QMainWindow):

    """
    THEA Timelapse GUI Main window class for low temperature measurements
    """

    def __init__(self, experiment = None):

        super().__init__()
        self.experiment = experiment
        self.initUI()
        self.openSerial()
    
    
    def mouseMoved(self, evt):

        """
            Track mouse movement on data plot in plot units (arb.dB vs THz)

            :type evt: pyqtSignal 
            :param evt: Emitted when the mouse cursor moves over the scene. Contains scene cooridinates of the mouse cursor.

        """

        pos = evt
        if self.livePlot_2.sceneBoundingRect().contains(pos):
            mousePoint = self.livePlot_2.plotItem.vb.mapSceneToView(pos)
            x = float("{0:.3f}".format(mousePoint.x()))
            y = float("{0:.3f}".format(mousePoint.y()))
            self.xyLabel_2.setText(f"last cursor position: {x, y}")

   
    def plotTemp(self, line):

        """Plot temperature
        """

        if "deg C" in line:

            self.experiment.ctr += 1
            temp = line.split("deg")[0]
            self.lblTempBig.setText(f"Cold finger Temp: {temp} C")  

            def correctData():
                self.experiment.temperatures = np.append(self.experiment.temperatures, double(line.split("deg")[0]))
                self.experiment.temperatures = np.roll(self.experiment.temperatures, 1)
                self.experiment.temperatures = np.delete(self.experiment.temperatures, -1)
                flipped = np.flip(self.experiment.temperatures)
                return flipped
                                
            if self.experiment.ctr != self.experiment.config['TemperatureSensor']['scrollLength']:
                nanidx = self.experiment.ctr
                flipped = correctData()
                self.data = np.append(flipped[len(flipped)-nanidx:], flipped[:len(flipped)-nanidx])      
            
            else:
                self.experiment.ctr = 1
                self.experiment.epoch+=1
                self.experiment.clearData()
                self.xmin = self.xmin + self.experiment.config['TemperatureSensor']['scrollLength']
                self.xmax = self.xmax + self.experiment.config['TemperatureSensor']['scrollLength']
                self.experiment.time = np.linspace(self.xmin,self.xmax,self.experiment.config['TemperatureSensor']['scrollLength'])
                self.livePlot_2.setXRange(self.xmin, self.xmax)
                

                
                flipped = correctData()
                
                nanidx =  self.experiment.ctr
                self.data = self.experiment.temperatures
                print(self.data)
                
                
            self.plotT.curve.setData(self.experiment.time,self.data)
            self.plotT.curve.setPen(color = self.colorLivePulse, width = self.averagePlotLineWidth)
            

    def connectEvents(self):
        
        """
            Connect GUI object and validator signals to respective methods.
        """
      
        self.experiment.serial.readyRead.connect(self.receive)
        self.experiment.nextScan.connect(self.plotTemp)
        self.livePlot_2.scene().sigMouseMoved.connect(self.mouseMoved)
        self.btnStartTemp.clicked.connect(self.startObs)
        self.btnStopTemp.clicked.connect(self.stopObs)


    def openSerial(self):
        
        """Open serial port for communication with QC robot"""

        
        self.experiment.serial.open(QIODevice.ReadWrite)


    def initUI(self):

        """
            Initialise UI from design file
        """

        uic.loadUi("../View/Designer/periodicMeasurementUI.ui", self)
        self.setWindowTitle("THEA Timelapse")
        #self.disableButtons()
        #self.initAttribs()
        self.connectEvents()

        self.colorLivePulse = (255,255,0, 180)
        self.livePlot_2.setLabel('left', 'Temperature (C)')
        self.livePlot_2.setLabel('bottom', 'Observations - 1/Sampling Rate (sec)')
        self.livePlot_2.setTitle("""Temperature historical""", color = 'g', size = "45 pt")   
        self.livePlot_2.showGrid(x = True, y = True)
        self.TplotDataContainer = {}
        self.averagePlotLineWidth = 2

        self.labelValue = TextItem('', **{'color': '#FFF'})
        self.labelValue.setPos(QPointF(4,-100))

        self.lEditTdsStart.setAlignment(Qt.AlignCenter) 
        self.lEditTdsEnd.setAlignment(Qt.AlignCenter) 
        self.lEditTdsAvgs.setAlignment(Qt.AlignCenter) 
        self.livePlot_2.addItem(self.labelValue)
        self.scroll = QScrollBar(Qt.Horizontal)
        self.xmin = 1
        self.xmax = self.experiment.config['TemperatureSensor']['scrollLength'] 
        self.plotT = self.livePlot_2.plot(self.experiment.temperatures)
        self.livePlot_2.setXRange(self.xmin, self.xmax)
        self.livePlot_2.setYRange(50, -100)
        self.lblTempBig.setText("Cold Finger temp. (C): --")


    @asyncSlot()
    async def receive(self):

        """Receive messages on serial port and redirect to message box"""

        
        while self.experiment.serial.canReadLine():
            
            codec = QTextCodec.codecForName("UTF-8")
            line = codec.toUnicode(self.experiment.serial.readLine()).strip()
            print(line)
            
            if "deg C" in line:
                self.experiment.nextScan.emit(line)
                
            self.experiment.lastMessage = line
            await asyncio.sleep(0)


    @asyncSlot()
    async def startObs(self):
      
        self.experiment.keepRunning = True
        self.experiment.clearData()
        while self.experiment.keepRunning:
            self.experiment.tempObsTask =  asyncio.ensure_future(self.experiment.readTemp())
            asyncio.gather(self.experiment.tempObsTask)
            while not self.experiment.tempObsTask.done():
                await asyncio.sleep(1/self.experiment.config['TemperatureSensor']['samplingRate'])


    @asyncSlot()
    async def stopObs(self):
        self.experiment.keepRunning = False
        try:
            self.experiment.tempObsTask.cancel()
            self.experiment.ackTask.cancel()
            self.epoch = 1
            self.ctr = 0
            self.experiment.clearData()
            self.lblTempBig.setText(f"Cold finger Temp (C): --")    
            self.xmin = 1
            self.xmax = self.experiment.config['TemperatureSensor']['scrollLength'] 
            self.livePlot_2.setXRange(self.xmin, self.xmax)
            self.experiment.time = np.linspace(1,self.experiment.config['TemperatureSensor']['scrollLength'],
                                               self.experiment.config['TemperatureSensor']['scrollLength'])
        except asyncio.exceptions.CancelledError:
            print("Cancelled Observation")



#******************************************************************************************

if __name__ == '__main__':
    
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = MAXSerialTemp(loop, '../config/timelapseConfig.yml')
    win = TempTimelapseWindow(ttl)
    win.show()

    with loop:
        sys.exit(loop.run_forever())


    

