import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rscDir = os.path.join(baseDir, "Resources")
configDir = os.path.join(baseDir, "config")  # if keeping in same dir as model
sys.path.append(baseDir)
sys.path.append(configDir)

from Model.experiment import *
from Resources import ur
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


class MAXSerialTemp(QWidget):
    
    nextScan = pyqtSignal(str) 

    def __init__(self, loop , configFile = None):

        super().__init__()
        
        self.configFile = configFile
        self.initAttribs()
        self.loadConfig()
        self.initTempSensor()


    def initAttribs(self):
        
        """
        initilaise properties
        """

        self.port = None
        self.config = None
        self.configLoaded = None
        self.serial = None
        self.baudrate = None
        self.lastMessage = None
        self.ackTask = None
        self.temperatures = None
        self.ctr = 0
        self.epoch = 1
        self.keepRunning = False
        self.tempObsTask = None


    def loadConfig(self):
        
        """
            load and set config paramters
        """

        with open(self.configFile, 'r') as f:
            data = yaml.load(f, Loader= yaml.FullLoader)

        self.config = data
        self.configLoaded = True


    def initTempSensor(self):

        """
        Check if sensor works - serial communication
        """

        self.port = self.config['TemperatureSensor']['port']
        self.baudrate = self.config['TemperatureSensor']['baudrate']
        self.timeout = self.config['TemperatureSensor']['timeout']
        self.initSerial()
        self.clearData()


    def initSerial(self):

        """Initialise robot via serial port
        """

        try:
            self.serial = QtSerialPort.QSerialPort(self.port)
            self.serial.setBaudRate(self.baudrate)
            self.serial.open(QIODevice.ReadWrite)
            print("SERIAL PORT OPENED")
        except:
            print("Could not open serial device")


    def clearData(self):

        self.temperatures = np.empty(self.config['TemperatureSensor']['scrollLength'])
        self.temperatures[:] = np.NaN
        self.time = np.linspace(1,(self.epoch+1)*(self.config['TemperatureSensor']['scrollLength']),
                                 self.config['TemperatureSensor']['scrollLength'])

        print("Clearing . . .")


    async def waitOnSerial(self):

        """Reusable block of code to log timeout for Ack
        """
        
        logger.info(f"last message : {self.lastMessage}")
        self.lastMessage = " "      #  clear previous ACK if any
        try:
            self.ackTask = asyncio.create_task(self.waitForAck())
            await asyncio.wait_for(self.ackTask, timeout = self.timeout)
        except asyncio.exceptions.TimeoutError:
            logger.error(f"[ERROR]: ACK not received")
            logger.warning(f"CHECK CONNECTIONS AND TEMPERATURE PROBE")
        except Exception as e:
            raise e
            

    async def waitForAck(self):

        """Wait for ACK from Serial
        """

        while self.lastMessage != 'ACK':
            logger.info("Waiting for ACK")
            await asyncio.sleep(1)
        logger.info("ACK received")


    async def readTemp(self):

        """
        Send command on serial to insert cartridge
        """

        txt = "readTemp\n"
        self.serial.write(txt.encode())
        await self.waitOnSerial()
        
        

if __name__ == "__main__":

    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    t1 = MAXSerialTemp(loop, "../config/timelapseConfig.yml")