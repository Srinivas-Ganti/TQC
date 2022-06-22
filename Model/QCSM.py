
from transitions import Machine, State
import enum 
import asyncio
from time import sleep
from transitions.extensions import AsyncMachine, GraphMachine
import random



class QCStates(enum.Enum):

    OFF=  0
    ON = 1
    HOME = 1.1
    EJECT1 = 1.2
    INSERT1 = 1.3
    EJECT2 = 1.4
    INSERT2 = 1.5
    NOACK = 3.1
    NOCHIP = 3.2
    CRASH = 3.3
    UNKNOWN = 3.4
    ERROR = 3.5

class QCRobotApp:
    def __init__(self):

        self.qc_state = QCStates.OFF # start from off state
        self.was_homed = False       # assume the machine is not homed

    def prepare_qc(self):
        print("Preparing QC app")
 
    async def command_poweron(self):
        print("sending command : poweron")
        await asyncio.sleep(1)
        self

    async def command_poweroff(self):
        print("sending command : poweroff")

    async def command_insert_cartridges(self):
        print("sending action command : insert")

    async def command_eject_Cartridges(self):
        print("sending action command : eject")

    async def command_goto_align1(self):
        print("sending move command : align 1")

    async def command_goto_align2(self):
        print("sending move command : align 2")

    async def command_homeRobot(self):
        print("sending home command")


    async def quickscan(self):
        print("Starting quick scan")
        await asyncio.sleep(1) # a short duration scan
        print("Quick Scan completed")

    async def fullscan(self):

        print("Starting full scan")
        await asyncio.sleep(5) # a longer duration scan
        print("Full Scan completed")

    def compareResult(self):

        sleep(0.1)  # blocking calculation
        k = random.randint(0, 1)
        if k == 0:
            print("QC FAIL")
        else:
            print("QC PASS")

        sleep(0.5) # blocking file write and results update


    async def waitOnRobot(self):
        print("waiting for ack . . .")
        await asyncio.sleep(1) # robot operating correctly responds in about 1 sec

 
        


        





tPowerOn = dict(trigger = 'poweron', source = QCStates.OFF, dest = QCStates.ON, before = "command_poweron")
tHome =  dict(trigger = 'homeRobot', source = QCStates.ON, dest = QCStates.HOME, after = "home")
transitions = [tPowerOn, tHome]
# transitions = [tPowerOn,
#                ['poweroff', '*', QCStates.OFF], 
#                ['home', QCStates.ON, QCStates.HOME],
#                ['turnTabl', QCStates.HOME, QCStates.EJECT1],
#                ['turnTabl', QCStates.EJECT2, QCStates.EJECT1],
#                ['turnTabl', QCStates.EJECT1, QCStates.EJECT2],
#                ['eject2', QCStates.INSERT2, QCStates.EJECT2],
#                ['eject1', QCStates.INSERT1, QCStates.EJECT1],
#                ['insert2', QCStates.EJECT2, QCStates.INSERT2],
#                ['insert1', QCStates.EJECT1, QCStates.INSERT1],
#                ['error', '*', QCStates.ERROR]]


if __name__ == "__main__":
    model = QCRobotApp()
    m = AsyncMachine(model, states = QCStates, transitions = transitions , initial = QCStates.OFF, auto_transitions= False)
    asyncio.get_event_loop().run_until_complete(m.model.poweron())
    # m.get_graph().draw('QC statemachine.png', prog='dot')
