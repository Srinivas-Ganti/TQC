from this import d
from PyQt5.QtWidgets import QApplication, QWidget
import sys
import os
from numpy import double

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelDir = os.path.join(baseDir, "Model")
# configDir = os.path.join(baseDir, "config")  # if keeping in same dir as model
sys.path.append(baseDir)
sys.path.append(modelDir)
# sys.path.append(configDir)

from Model.PolarisationSweep import *

class PolDataViewerWindow(QMainWindow):

    def __init__(self, configFile):
        super().__init__()
        self.initUI()
        self.phi = None
        self.config_file = configFile
        self.scanName = None
        #self.loadConfig()
        #self.loadData()

    
    def loadConfig(self):
        
        """
            load and set config paramters
        """

        with open(self.config_file, 'r') as f:
            data = yaml.load(f, Loader= yaml.FullLoader)

        self.config = data
        self.configLoaded = True


    def initUI(self):

        uic.loadUi("../View/Designer/polDataViewerUI.ui", self)
        self.setWindowTitle("THEA PolDataViewer")
        self.initAttribs()
        self.connectEvents()
        self.setAcceptDrops(True)
        self.livePlot.setLabel('left', 'Transmission Intensity (dB)')
        self.livePlot.setLabel('bottom', 'Frequency (THz)')
        self.livePlot.setTitle("""Transmission FFT""", color = 'g', size = "45 pt")   
        self.livePlot.showGrid(x = True, y = True)
        self.labelValue = TextItem('', **{'color': '#FFF'})
        self.labelValue.setPos(QPointF(4,-100))
        self.livePlot.addItem(self.labelValue)
        self.exporter = ImageExporter(self.livePlot.scene())   # Exporter for creating plot images
        self.exporter.parameters()['width'] = 500


    def initAttribs(self):

        self.height = 500
        self.width = 570
        self.left = 10
        self.top = 40      
        self.labelValue = None         #LabelItem to display timelapse frames on plot
        self.setGeometry(self.left, self.top, self.width, self.height)   
        self.livePlot.setXRange(0,3.5, padding = 0)
        self.livePlot.setYRange(-250, -105, padding = 0)
        self.colorLivePulse = (66,155,184, 145)
        self.colorlivePulseBackground = (66,155,184,145)
        self.livePlotLineWidth = 1
        self.averagePlotLineWidth = 1.5
        self.plotDataContainer = {f'Data1': None}       # Dictionary for plot items


    def connectEvents(self):
        self.livePlot.scene().sigMouseMoved.connect(self.mouseMoved)
        self.lEditPhi.editingFinished.connect(self.validateEditPhi)
    

    def loadData(self):

        self.sampleDF = pd.read_pickle(self.config['Data']['Sample'])
        self.referenceDF = pd.read_pickle(self.config['Data']['Reference'])



    def validateEditPhi(self):

        
        """
            Validate user input for Requested Frames of the timelapse
        """ 
        
        validationRule = QDoubleValidator(-120,120,3)
        print(validationRule.validate(self.lEditPhi.text(),120))
        if validationRule.validate(self.lEditPhi.text(),
                                   120)[0] == QValidator.Acceptable:
            print(f"Phi input ACCEPTED")
            
        else:
            print(f"> [WARNING]:Invalid angle.")
            
            self.phi =0
            self.lEditPhi.setText(str(self.phi))


    def plot(self, x, y):

        """
            Plot data on existing plot widget.

            :type x: numpy array
            :param x: frequency axis data
            :type y: numpy array
            :param y: Pulse FFT data.

            :return: plot data.
            :rtype: PlotWidget.plot  

        """   

        return self.livePlot.plot(x,y)

    
    def mouseMoved(self, evt):

        """
            Track mouse movement on data plot in plot units (arb.dB vs THz)

            :type evt: pyqtSignal 
            :param evt: Emitted when the mouse cursor moves over the scene. Contains scene cooridinates of the mouse cursor.

        """

        pos = evt
        if self.livePlot.sceneBoundingRect().contains(pos):
            mousePoint = self.livePlot.plotItem.vb.mapSceneToView(pos)
            x = float("{0:.3f}".format(mousePoint.x()))
            y = float("{0:.3f}".format(mousePoint.y()))
            self.xyLabel.setText(f"last cursor position: {x, y}")


if __name__ =="__main__":
    app = QApplication(sys.argv)
    win = PolDataViewerWindow('../config/polDataViewerConfig.yml')
    win.show()
    app.exec()
    


