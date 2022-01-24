import sys 
import os

topDir = os.path.dirname(os.path.abspath(__file__))
configDir = os.path.join(topDir, "config")
guiDir =  os.path.join(topDir, "View")
guiDir =  os.path.join(guiDir, "Designer")
modelDir =  os.path.join(topDir, "Model")
sys.path.append(topDir)
sys.path.append(guiDir)
sys.path.append(modelDir)

from View.timelapseWindow import *

if __name__ == "__main__":
    app = QApplication(sys.argv)    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ttl = TheaTimelapse(loop, 'config/timelapseConfig.yml')
    win = TimelapseMainWindow(ttl)
    win.show()

    with loop:
        sys.exit(loop.run_forever())
