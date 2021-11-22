import sys
import os

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(baseDir)

from Model.experiment import *

class TheaQC(Experiment):
    
    def __init__(self, loop = None, configFile = None):
        super().__init__(loop, configFile)
        
    def initialise(self):

        if self.configLoaded:
            pass





#*********************************************************************************

if __name__ == "__main__":

    """Extend functionality of experiment class to include some QC related features"""
    
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    tqc = TheaQC(loop, 'theaConfig.yml')
