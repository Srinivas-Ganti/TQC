from theaTimelapse import *

baseDir =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
guiDir =  os.path.join(baseDir, "View")
sys.path.append(baseDir)
sys.path.append(guiDir)

from View.timelapseWindow import *

app = QApplication(sys.argv)    
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

ttl = TheaTimelapse(loop, '../Model/timelapseConfig.yml')
win = TimelapseMainWindow(ttl)
win.show()

with loop:
    sys.exit(loop.run_forever())


