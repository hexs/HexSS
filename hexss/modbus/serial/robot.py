import json
import math
import time
from typing import List, Optional, Dict, Any
from hexss import check_packages
from hexss.numpy import split_int32_to_uint16, int16, int32
from hexss.num import unpack_16bit, pack_16bit

check_packages('pandas', 'pymodbus==3.8.6', 'Flask', 'pyserial', auto_install=True)

from pymodbus.client import ModbusSerialClient
from hexss.serial import get_comport
from hexss.constants.terminal_color import *

# --- Register data definition ---
# https://www.intelligentactuator.com/pdf/controller-manuals/MODBUS(ME0162-10B).pdf (page 36/388)
REGISTERS: Dict[int, Dict[str, Any]] = {
    # 4.3.3 Detail of Modbus Status Registers (page 62/388)
    0x0100: {
        'symbol': 'EMGS', 'name': 'EMG status', 'description': '',
        'signals': {}
    },
    0x0101: {
        'symbol': 'SFTY', 'name': 'Safety speed enabled status', 'description': '',
        'signals': {}
    },
    0x0102: {
        'symbol': 'PWR', 'name': 'Controller ready status', 'description': '',
        'signals': {}
    },
    0x0103: {
        'symbol': 'SV', 'name': 'Servo ON status', 'description': '',
        'signals': {}
    },
    0x0104: {
        'symbol': 'PSFL', 'name': 'Missed work part in push-motion operation', 'description': '',
        'signals': {}
    },
    0x0105: {
        'symbol': 'ALMH', 'name': 'Major failure status', 'description': '',
        'signals': {}
    },
    0x0106: {
        'symbol': 'ALML', 'name': 'Minor failure status', 'description': '',
        'signals': {}
    },
    0x0107: {
        'symbol': 'ABER', 'name': 'Absolute error status', 'description': '',
        'signals': {}
    },
    0x0108: {
        'symbol': 'BKRL', 'name': 'Brake forced-release status', 'description': '',
        'signals': {}
    },
    0x010A: {
        'symbol': 'STP', 'name': 'Pause status', 'description': '',
        'signals': {}
    },
    0x010B: {
        'symbol': 'HEND', 'name': 'Home return status', 'description': '',
        'signals': {}
    },
    0x010C: {
        'symbol': 'PEND', 'name': 'Position complete status', 'description': '',
        'signals': {}
    },
    0x010D: {
        'symbol': 'CEND', 'name': 'Load cell calibration complete', 'description': '',
        'signals': {}
    },
    0x010E: {
        'symbol': 'CLBS', 'name': 'Load cell calibration status', 'description': '',
        'signals': {}
    },

    # 4.3.2 Details of Modbus Registers (page 35/388)
    0x0500: {
        'name': 'Alarm detail code', 'symbol': 'ALA0', 'description': '0x0500 Alarm detail code | 0x0501 Alarm address',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm detail code {1 << i}'} for i in reversed(range(16))
        }
    },
    0x0501: {
        'name': 'Alarm address', 'symbol': 'ALA0', 'description': '-',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm address {1 << i}'} for i in reversed(range(16))
        }
    },
    0x0503: {
        'name': 'Alarm code', 'symbol': 'ALC0', 'description': '-',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm code {1 << i}'} for i in reversed(range(16))
        }
    },
    0x0504: {
        'name': 'Alarm occurrence time', 'symbol': 'ALT0', 'description': '-',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm occurrence time {1 << i + 16}'} for i in reversed(range(16))
        }
    },
    0x0505: {
        'name': 'Alarm occurrence time', 'symbol': 'ALT0', 'description': '-',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm occurrence time {1 << i}'} for i in reversed(range(16))
        }
    },
    0x0D00: {
        'name': 'Device Control Register 1', 'symbol': 'DRG1', 'description': '',
        'signals': {
            15: {'symbol': 'EMG', 'name': 'EMG operation specification',
                 'description': '0: Emergency stop not actuated\n1: Emergency stop actuated\nChanging this bit to 1 will switch the controller to the emergency stop mode. Take note that the drive source will not be cut off. (The ALM LED on the controller will not illuminate.)'},
            14: {'symbol': 'SFTY', 'name': 'Safety speed command',
                 'description': '0: Disable safety speed\n1: Enable safety speed\nChanging this bit to 1 will limit the speeds of all movement commands to the speed specified by user parameter No. 35, "Safety speed."'},
            12: {'symbol': 'SON', 'name': 'Servo ON command', 'description': '0: Servo OFF, 1: Servo ON'},
            8: {'symbol': 'ALRS', 'name': 'Alarm reset',
                'description': '0: Normal\n1: Alarm will reset\n0->1 rise edge: Alarm reset'},
            7: {'symbol': 'BKRL', 'name': 'Brake forced-release',
                'description': '0: Normal\n1: Forcibly release brake'},
            5: {'symbol': 'STP', 'name': 'Pause command', 'description': '0: Normal, 1: Pause (deceleration stop)'},
            4: {'symbol': 'HOME', 'name': 'Home return command',
                'description': '0->1 rise edge: Home return operation'},
            3: {'symbol': 'CSTR', 'name': 'Positioning start',
                'description': '0: Normal\n0->1 rise edge: Positioning start to the target position specified with the position no.'}
        }
    },
    0x0D01: {
        'name': 'Device Control Register 2', 'symbol': 'DRG2', 'description': '',
        'signals': {
            # 15: Cannot be used
            14: {'symbol': 'JISL', 'name': 'Jog/inch switching', 'description': '0: Jog\n1: Inching'},
            # 13: Cannot be used
            # 12: Cannot be used
            11: {'symbol': 'MOD', 'name': 'Teaching mode',
                 'description': '0: Normal operation mode\n1: Teaching mode'},
            10: {'symbol': 'TEAC', 'name': 'Position data load',
                 'description': '0: Normal\n1: Position data load command'},
            9: {'symbol': 'JOG+', 'name': 'Jog+', 'description': '0: Normal\n1: Jog+ command'},
            8: {'symbol': 'JOG-', 'name': 'Jog-', 'description': '0: Normal\n1: Jog- command '},
            7: {'symbol': 'ST7', 'name': 'Start position 7', 'description': ''},
            6: {'symbol': 'ST6', 'name': 'Start position 6', 'description': ''},
            5: {'symbol': 'ST5', 'name': 'Start position 5', 'description': ''},
            4: {'symbol': 'ST4', 'name': 'Start position 4', 'description': ''},
            3: {'symbol': 'ST3', 'name': 'Start position 3', 'description': ''},
            2: {'symbol': 'ST2', 'name': 'Start position 2', 'description': ''},
            1: {'symbol': 'ST1', 'name': 'Start position 1', 'description': ''},
            0: {'symbol': 'ST0', 'name': 'Start position 0', 'description': ''}
        }
    },
    0x0D03: {
        'name': 'Position NO. Specification Register', 'symbol': 'POSR',
        'description': 'Data of program number command registers',
        'signals': {9: {'symbol': 'PC512', 'name': 'Position command bit 512', 'description': '-'},
                    8: {'symbol': 'PC256', 'name': 'Position command bit 256', 'description': '-'},
                    7: {'symbol': 'PC128', 'name': 'Position command bit 128', 'description': '-'},
                    6: {'symbol': 'PC64', 'name': 'Position command bit 64', 'description': '-'},
                    5: {'symbol': 'PC32', 'name': 'Position command bit 32', 'description': '-'},
                    4: {'symbol': 'PC16', 'name': 'Position command bit 16', 'description': '-'},
                    3: {'symbol': 'PC8', 'name': 'Position command bit 8', 'description': '-'},
                    2: {'symbol': 'PC4', 'name': 'Position command bit 4', 'description': '-'},
                    1: {'symbol': 'PC2', 'name': 'Position command bit 2', 'description': '-'},
                    0: {'symbol': 'PC1', 'name': 'Position command bit 1', 'description': '-'}
                    }
    },
    0x1000: {'name': 'Target position 0', 'symbol': 'PCMD0'},
    0x1001: {'name': 'Target position 0', 'symbol': 'PCMD0'},
    0x1002: {'name': 'Positioning band 0', 'symbol': 'INP0'},
    0x1003: {'name': 'Positioning band 0', 'symbol': 'INP0'},
    0x1004: {'name': 'Speed command 0', 'symbol': 'VCMD0'},
    0x1005: {'name': 'Speed command 0', 'symbol': 'VCMD0'},
    0x1006: {'name': 'Individual zone boundary + 0', 'symbol': 'ZNMP0'},
    0x1007: {'name': 'Individual zone boundary + 0', 'symbol': 'ZNMP0'},
    0x1008: {'name': 'Individual zone boundary - 0', 'symbol': 'ZNLP0'},
    0x1009: {'name': 'Individual zone boundary - 0', 'symbol': 'ZNLP0'},
    0x100A: {'name': 'Acceleration command 0', 'symbol': 'ACMD0'},
    0x100B: {'name': 'Deceleration command 0', 'symbol': 'DCMD0'},
    0x100C: {'name': 'Push-current limiting value 0', 'symbol': 'PPOW0'},
    0x100D: {'name': 'Load current threshold 0', 'symbol': 'LPOW0'},
    0x100E: {'name': 'Control flag specification 0', 'symbol': 'CTLF0'},

    # 4000 to 83FF: Reserved for system
    0x8400: {
        'name': 'Total moving count', 'symbol': 'TLMC', 'description': '-', 'signals': {}
    },
    0x8401: {
        'name': 'Total moving count', 'symbol': 'TLMC', 'description': '-', 'signals': {}
    },
    0x8402: {
        'name': 'Total moving distance', 'symbol': 'ODOM', 'description': '-', 'signals': {}
    },
    0x8403: {
        'name': 'Total moving distance', 'symbol': 'ODOM', 'description': '-', 'signals': {}
    },
    0x8422: {
        'name': 'Current time', 'symbol': 'TIMN', 'description': 'PCON-CA/CFA/CB/CFB only', 'signals': {}
    },
    0x842E: {
        'name': 'Total FAN driving time', 'symbol': 'TFAN', 'description': 'PCON-CFA/CFB only', 'signals': {}
    },
    0x9000: {
        'name': 'Current Position Register', 'symbol': 'PNOW', 'description': '', 'signals': {}
    },
    0x9001: {
        'name': 'Current Position Register', 'symbol': 'PNOW', 'description': '', 'signals': {}
    },
    0x9002: {
        'name': 'Present Alarm Code Register', 'symbol': 'ALMC', 'description': '', 'signals': {}
    },
    0x9003: {
        'name': 'Input Port Register', 'symbol': 'DIPM', 'description': '', 'signals': {}
    },
    0x9004: {
        'name': 'Output Port Register', 'symbol': 'DOPM', 'description': '', 'signals': {}
    },
    0x9005: {
        'name': 'Device Status 1 Register', 'symbol': 'DSS1', 'description': '-', 'signals': {
            15: {'symbol': 'EMGS', 'name': 'Emergency status',
                 'description': '0: Emergency stop not actuated\n1: Emergency stop actuated'},
            14: {'symbol': 'SFTY', 'name': 'Safety speed enabled status',
                 'description': '0: Safety status disabled\n1: Safety status enabled '},
            13: {'symbol': 'PWR', 'name': 'Controller ready status',
                 'description': '0: Controller busy\n1: Controller ready'},
            12: {'symbol': 'SV', 'name': 'Servo ON status', 'description': '0: Servo OFF\n1: Servo ON'},
            11: {'symbol': 'PSFL', 'name': 'Push & hold missing',
                 'description': '0: Normal\n1: Missed work part in push-motion operation'},
            10: {'symbol': 'ALMH', 'name': 'Major failure status',
                 'description': '0: Normal\n1: Major failure alarm present'},
            9: {'symbol': 'ALML', 'name': 'Minor failure status',
                'description': '0: Normal\n1: Major failure alarm present'},
            8: {'symbol': 'ABER', 'name': 'Absolute error status',
                'description': '0: Normal\n1: Absolute error present'},
            7: {'symbol': 'BKRL', 'name': 'Brake forced-release status',
                'description': '0: Brake actuated\n1: Brake released'},
            5: {'symbol': 'STP', 'name': 'Pause status', 'description': '0: Normal\n1: Pause command active'},
            4: {'symbol': 'HEND', 'name': 'Home return completion status',
                'description': '0: Home return not yet complete\n1: Home return complete'},
            3: {'symbol': 'PEND', 'name': 'Position complete status',
                'description': '0: Positioning not yet complete\n1: Position complete'},
            2: {'symbol': 'CEND', 'name': 'Load cell calibration complete',
                'description': '0: Calibration not yet complete\n1: Calibration complete'},
            1: {'symbol': 'CLBS', 'name': 'Load cell calibration status',
                'description': '0: Calibration not yet complete\n1: Calibration complete'}
        }
    },
    0x9006: {
        'name': 'Device Status 2 Register', 'symbol': 'DSS2', 'description': '-', 'signals': {
            15: {'symbol': 'ENBS', 'name': 'Enable',
                 'description': '0: Disable condition(Operation Stop, Servo OFF)\n1: Enable condition (normal operation)'},
            13: {'symbol': 'LOAD', 'name': 'Load output judgment status',
                 'description': '0: Normal\n1: Load output judgment'},
            12: {'symbol': 'TRQS', 'name': 'Torque level status', 'description': '0: Normal\n1: Torque level achieved'},
            11: {'symbol': 'MODS', 'name': 'Teaching mode status',
                 'description': '0: Normal operation mode\n1: Teaching mode'},
            10: {'symbol': 'TEAC', 'name': 'Position-data load command status',
                 'description': '0: Normal\n1: Position data load complete'},
            9: {'symbol': 'JOG+', 'name': 'Jog+ status', 'description': '0: Normal\n1: Jog+ command active'},
            8: {'symbol': 'JOG-', 'name': 'Jog- status', 'description': '0: Normal\n1: Jog- command active'},
            7: {'symbol': 'PE7', 'name': 'Position complete 7', 'description': '-'},
            6: {'symbol': 'PE6', 'name': 'Position complete 6', 'description': '-'},
            5: {'symbol': 'PE5', 'name': 'Position complete 5', 'description': '-'},
            4: {'symbol': 'PE4', 'name': 'Position complete 4', 'description': '-'},
            3: {'symbol': 'PE3', 'name': 'Position complete 3', 'description': '-'},
            2: {'symbol': 'PE2', 'name': 'Position complete 2', 'description': '-'},
            1: {'symbol': 'PE1', 'name': 'Position complete 1', 'description': '-'},
            0: {'symbol': 'PE0', 'name': 'Position complete 0', 'description': '-'}
        }
    },
    0x9007: {
        'name': 'Expansion Device Status Register', 'symbol': 'DSSE', 'description': '-', 'signals': {
            15: {'symbol': 'EMGP', 'name': 'Emergency stop status',
                 'description': '0: Emergency stop not actuated\n1: Emergency stop actuated\n'},
            14: {'symbol': 'MPUV', 'name': 'Motor voltage low status',
                 'description': '0: Normal\n1: Motor drive source cut off'},
            13: {'symbol': 'RMDS', 'name': 'Operation mode status', 'description': '0: AUTO mode\n1: MANU mode'},
            11: {'symbol': 'GMHS', 'name': 'Home returning', 'description': '0: Normal\n1: Home returning'},
            10: {'symbol': 'PUSH', 'name': 'Push & hold operating',
                 'description': '0: Normal\n1: Push & hold operating '},
            9: {'symbol': 'PSNS', 'name': 'Excitation detection status',
                'description': '0: Excitation detection not yet complete\n1: Excitation detection complete'},
            8: {'symbol': 'PMSS', 'name': 'PIO/Modbus switching status',
                'description': '0: PIO commands enabled\n1: PIO command disabled'},
            5: {'symbol': 'MOVE', 'name': 'Moving',
                'description': '0: Stopped\n1: Moving (including home return, push & hold operation)'}
        }
    },
    0x9008: {
        'name': 'System Status Register', 'symbol': 'STAT', 'description': '-', 'signals': {
            31: {'symbol': 'BATL', 'name': 'Absolute Battery Voltage Drop (for SCON only)',
                 'description': '0: In normal condition\n1: Battery voltage drop'},
            17: {'symbol': 'ASOF', 'name': 'Auto servo OFF', 'description': '0: Normal\n1: Auto servo OFF'},
            16: {'symbol': 'AEEP', 'name': 'Nonvolatile memory being accessed',
                 'description': '0: Normal\n1: Nonvolatile memory being accessed'},
            4: {'symbol': 'RMDS', 'name': 'Operation mode status', 'description': '0: AUTO mode\n1: MANU mode '},
            3: {'symbol': 'HEND', 'name': 'Home return completion status',
                'description': '0: Home return not yet complete\n1: Home return completion'},
            2: {'symbol': 'SV', 'name': 'Servo status', 'description': '0: Servo OFF\n1: Servo ON'},
            1: {'symbol': 'SON', 'name': 'Servo command status', 'description': '0: Servo OFF\n1: Servo ON'},
            0: {'symbol': 'MPOW', 'name': 'Drive source ON', 'description': '0: Drive source cut off\n1: Normal'}
        }
    },
    0x9009: {
        'name': 'System Status Register', 'symbol': 'STAT', 'description': '-', 'signals': {
            31: {'symbol': 'BATL', 'name': 'Absolute Battery Voltage Drop (for SCON only)',
                 'description': '0: In normal condition\n1: Battery voltage drop'},
            17: {'symbol': 'ASOF', 'name': 'Auto servo OFF', 'description': '0: Normal\n1: Auto servo OFF'},
            16: {'symbol': 'AEEP', 'name': 'Nonvolatile memory being accessed',
                 'description': '0: Normal\n1: Nonvolatile memory being accessed'},
            4: {'symbol': 'RMDS', 'name': 'Operation mode status', 'description': '0: AUTO mode\n1: MANU mode '},
            3: {'symbol': 'HEND', 'name': 'Home return completion status',
                'description': '0: Home return not yet complete\n1: Home return completion'},
            2: {'symbol': 'SV', 'name': 'Servo status', 'description': '0: Servo OFF\n1: Servo ON'},
            1: {'symbol': 'SON', 'name': 'Servo command status', 'description': '0: Servo OFF\n1: Servo ON'},
            0: {'symbol': 'MPOW', 'name': 'Drive source ON', 'description': '0: Drive source cut off\n1: Normal'}
        }
    },
    0x900A: {
        'name': 'Current speed monitor register', 'symbol': 'VNOW', 'description': '', 'signals': {}
    },
    0x900B: {
        'name': 'Current speed monitor register', 'symbol': 'VNOW', 'description': '', 'signals': {}
    },
    0x900C: {
        'name': 'Current ampere monitor register', 'symbol': 'CNOW', 'description': '', 'signals': {}
    },
    0x900D: {
        'name': 'Current ampere monitor register', 'symbol': 'CNOW', 'description': '', 'signals': {}
    },
    0x900E: {
        'name': 'Deviation monitor register', 'symbol': 'DEVI', 'description': '', 'signals': {}
    },
    0x900F: {
        'name': 'Deviation monitor register', 'symbol': 'DEVI', 'description': '', 'signals': {}
    },
    0x9010: {
        'name': 'System timer register', 'symbol': 'STIM', 'description': '',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm occurrence time {1 << i + 16}'} for i in reversed(range(16))
        }
    },
    0x9011: {
        'name': 'System timer register', 'symbol': 'STIM', 'description': '',
        'signals': {
            i: {'symbol': '-', 'name': f'Alarm occurrence time {1 << i}'} for i in reversed(range(16))
        }
    },
    0x9012: {
        'name': 'Special input port register', 'symbol': 'SIPM', 'description': '', 'signals': {
            14: {'symbol': 'NP', 'name': 'Command pulse NP signal status',
                 'description': 'This bit indicates the status of the command pulse NP signal.'},
            12: {'symbol': 'PP', 'name': 'Command pulse PP signal status',
                 'description': 'This bit indicates the status of the command pulse PP signal.'},
            8: {'symbol': 'MDSW', 'name': 'Mode switch status', 'description': '0: AUTO mode \n1: MANU mode'},
            4: {'symbol': 'BLCT', 'name': 'Belt breakage sensor', 'description': '0: Belt broken\n1: Normal'},
            3: {'symbol': 'HMCK', 'name': 'Home-check sensor monitor', 'description': '0: Sensor OFF\n1: Sensor ON'},
            2: {'symbol': 'OT', 'name': 'Overtravel sensor monitor', 'description': '0: Sensor OFF\n1: Sensor ON'},
            1: {'symbol': 'CREP', 'name': 'Creep sensor monitor', 'description': '0: Sensor OFF\n1: Sensor ON'},
            0: {'symbol': 'LS', 'name': 'Limit sensor monitor', 'description': '0: No alarm\n1: Alarm occurred'}
        }
    },
    0x9013: {
        'name': 'Zone Status Register', 'symbol': 'ZONS', 'description': '-', 'signals': {
            14: {'symbol': 'LS2', 'name': 'Limit sensor output monitor 2',
                 'description': '0: Out of range\n1: In range\n'},
            13: {'symbol': 'LS1', 'name': 'Limit sensor output monitor 1',
                 'description': '0: Out of range\n1: In range\n'},
            12: {'symbol': 'LS0', 'name': 'Limit sensor output monitor 0',
                 'description': '0: Out of range\n1: In range\n'},
            8: {'symbol': 'PZ', 'name': 'Position zone output monitor',
                'description': '0: Out of range\n1: In range\n'},
            1: {'symbol': 'Z2', 'name': 'Zone output monitor 2', 'description': '0: Out of range\n1: In range\n'},
            0: {'symbol': 'P1', 'name': 'Zone output monitor 1', 'description': '0: Out of range\n1: In range\n'}
        }
    },
    0x9014: {
        'name': 'Position NO. Status Register', 'symbol': 'POSS', 'description': '-',
        'signals': {
            9: {'symbol': 'PM512', 'name': 'Position complete number status bit 512'},
            8: {'symbol': 'PM256', 'name': 'Position complete number status bit 256'},
            7: {'symbol': 'PM128', 'name': 'Position complete number status bit 128'},
            6: {'symbol': 'PM64', 'name': 'Position complete number status bit 64'},
            5: {'symbol': 'PM32', 'name': 'Position complete number status bit 32'},
            4: {'symbol': 'PM16', 'name': 'Position complete number status bit 16'},
            3: {'symbol': 'PM8', 'name': 'Position complete number status bit 8'},
            2: {'symbol': 'PM4', 'name': 'Position complete number status bit 4'},
            1: {'symbol': 'PM2', 'name': 'Position complete number status bit 2'},
            0: {'symbol': 'PM1', 'name': 'Position complete number status bit 1'}
        }
    },
    0x9015: {
        'name': 'Expansion system status registers', 'symbol': 'SSSE',
        'description': 'Position movement command register details', 'signals': {
            11: {'symbol': 'ALMC', 'name': 'Cold start level alarm',
                 'description': '0: Normal\n1: Cold level start alarm in occurrence'},
            8: {'symbol': 'RTC', 'name': 'RTC (calendar) function use',
                'description': '0: RTC function not used\n1: RTC function used'}
        }
    },
    0x9020: {
        'name': 'Overload level monitors', 'symbol': 'OLLV', 'description': '', 'signals': {}
    },
    0x9021: {
        'name': 'Overload level monitors', 'symbol': 'OLLV', 'description': '', 'signals': {}
    },
    0x9022: {
        'name': 'Press program alarm code', 'symbol': 'ALMP', 'description': '', 'signals': {}
    },
    0x9023: {
        'name': 'Press program alarm generated program No.', 'symbol': 'ALMP', 'description': '',
        'signals': {}
    },
    0x9024: {
        'name': 'Press program status register', 'symbol': 'PPST', 'description': '',
        'signals': {
            14: {'symbol': 'WAIT', 'name': 'Waiting', 'description': '-'},
            13: {'symbol': 'RTRN', 'name': 'While in returning operation', 'description': '-'},
            12: {'symbol': 'DCMP', 'name': 'While in depression operation', 'description': '-'},
            11: {'symbol': 'PSTP', 'name': 'Pressurize during the stop', 'description': '-'},
            10: {'symbol': 'PRSS', 'name': 'While in pressurizing operation', 'description': '-'},
            9: {'symbol': 'SERC', 'name': 'While in probing operation', 'description': '-'},
            8: {'symbol': 'APRC', 'name': 'While in approaching operation', 'description': '-'},
            4: {'symbol': 'MPHM', 'name': 'Program home return during the movement', 'description': '-'},
            3: {'symbol': 'PALM', 'name': 'Program alarm', 'description': '-'},
            2: {'symbol': 'PCMP', 'name': 'Program finished in normal condition', 'description': '-'},
            1: {'symbol': 'PRUN', 'name': 'While in executing program', 'description': '-'},
            0: {'symbol': 'PORG', 'name': 'Program home position', 'description': '-'}
        }
    },
    0x9025: {
        'name': 'Press program judgement status register', 'symbol': 'PPJD', 'description': '',
        'signals': {
            5: {'symbol': 'LJNG', 'name': 'Load judgement NG',
                'description': '0: Load judgment not conducted\n1: Load judgement NG'},
            4: {'symbol': 'LJOK', 'name': 'Load judgement OK',
                'description': '0: Load judgment not conducted\n1: Load judgement OK'},
            3: {'symbol': 'PJNG', 'name': 'Position (distance) judgement NG',
                'description': '0: Position (distance) judgment not conducted\n1: Position (distance) judgement NG'},
            2: {'symbol': 'PJOK', 'name': 'Position (distance) judgement OK',
                'description': '0: Position (distance) judgment not conducted\n1: Position (distance) judgement OK'},
            1: {'symbol': 'JDNG', 'name': 'Total judgement NG',
                'description': '0: Total judgement not conducted\n1: Total judgement NG'},
            0: {'symbol': 'JDOK', 'name': 'Total judgement OK',
                'description': '0: Total judgement not conducted\n1: Total judgement OK'}
        }
    },
    0x9800: {
        'name': 'Position NO. Specification Register', 'symbol': 'POSR2',
        'description': 'Position movement command register details',
        'signals': {9: {'symbol': 'PC512', 'name': 'Position command bit 512', 'description': '-'},
                    8: {'symbol': 'PC256', 'name': 'Position command bit 256', 'description': '-'},
                    7: {'symbol': 'PC128', 'name': 'Position command bit 128', 'description': '-'},
                    6: {'symbol': 'PC64', 'name': 'Position command bit 64', 'description': '-'},
                    5: {'symbol': 'PC32', 'name': 'Position command bit 32', 'description': '-'},
                    4: {'symbol': 'PC16', 'name': 'Position command bit 16', 'description': '-'},
                    3: {'symbol': 'PC8', 'name': 'Position command bit 8', 'description': '-'},
                    2: {'symbol': 'PC4', 'name': 'Position command bit 4', 'description': '-'},
                    1: {'symbol': 'PC2', 'name': 'Position command bit 2', 'description': '-'},
                    0: {'symbol': 'PC1', 'name': 'Position command bit 1', 'description': '-'}
                    }
    },
    0x9900: {
        'name': 'Target position coordinate specification register', 'symbol': 'PCMD', 'description': '-',
        'signals': {}
    },
    0x9901: {
        'name': 'Target position coordinate specification register', 'symbol': 'PCMD', 'description': '-',
        'signals': {}
    },
    0x9902: {
        'name': 'Positioning band specification register', 'symbol': 'INPH', 'description': '-',
        'signals': {}
    },
    0x9903: {
        'name': 'Positioning band specification register', 'symbol': 'INPL', 'description': '-',
        'signals': {}
    },
    0x9904: {
        'name': 'Speed specification register H', 'symbol': 'VCMDH', 'description': '-',
        'signals': {}
    },
    0x9905: {
        'name': 'Speed specification register L', 'symbol': 'VCMDL', 'description': '-',
        'signals': {}
    },
    0x9906: {
        'name': 'Acceleration/deceleration speed specification register', 'symbol': 'ACMD', 'description': '-',
        'signals': {}
    },
    0x9907: {
        'name': 'Push-current limiting value', 'symbol': 'PPOW', 'description': '-',
        'signals': {}
    },
    0x9908: {
        'name': 'Control flag specification register', 'symbol': 'CTLF', 'description': '-',
        'signals': {}
    }
}

# --- Normalize and preprocess register data ---
for reg in REGISTERS.values():
    reg.setdefault('description', '-')
    for bit, sig in reg.get('signals', {}).items():
        sig.setdefault('description', '-')


class Signal:
    EMG = 15
    SFTY = 14  # Safety speed
    SON = 12  # Servo On
    ALRS = 8  # Alarm Reset
    BKRL = 7
    STP = 5  # Pause
    HOME = 4  # Home
    CSTR = 3
    MOVE = 5

    def __init__(self, bit: int, symbol: str, name: str, description: str = '-'):
        self.bit = bit
        self.symbol = symbol
        self.name = name
        self.description = description

    def __repr__(self):
        return f"Signal({self.bit}, {self.symbol})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'bit': self.bit,
            'symbol': self.symbol,
            'name': self.name,
            'description': self.description
        }


class Register:
    def __init__(
            self, address: List[int], symbol: str, name: str, signals: Dict[int, Signal], description: str = '-',
            client: Optional[ModbusSerialClient] = None, slave_id: Optional[int] = None
    ):
        """
        address example = [36872, 36873]
        symbol example  = STAT
        signals example = {31: Signal(15, BATL), 17: Signal(1, ASOF), ..., 1: Signal(1, SON), 0: Signal(0, MPOW)}
        """
        self.address = address
        self.symbol = symbol
        self.name = name
        self.signals = signals
        self.description = description
        self.values: List[int] = [0 for _ in address]
        self.value: Optional[int] = None
        self.client = client
        self.id = slave_id

    def __repr__(self):
        addr_str = ', '.join(f'0x{a:04X}' for a in self.address)
        return f"Register({self.symbol}, [{addr_str}], {self.value})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'symbol': self.symbol,
            'name': self.name,
            'signals': {bit: sig.to_dict() for bit, sig in self.signals.items()},
            'description': self.description,
            'values': self.values,
            'value': self.value,
        }

    def read(self) -> Optional[List[int]]:
        resp = self.client.read_input_registers(self.address[0], count=len(self.address), slave=self.id + 1)
        if resp.isError():
            print(f"Error reading SLAVE {self.id} @ 0x{self.address[0]:04X}: {resp}")
            self.value = None
            return None
        self.values = resp.registers
        self.value = unpack_16bit(self.values)
        return self.values

    def write(self, values: List[int]) -> bool:
        resp = self.client.write_registers(self.address[0], values=values, slave=self.id + 1)
        if resp.isError():
            print(f"Error writing SLAVE {self.id} @ 0x{self.address[0]:04X}: {resp}")
            return False
        return True

    def read_value(self) -> Optional[int]:
        self.read()
        return self.value

    def write_value(self, value: int) -> None:
        self.write(pack_16bit(value, len(self.address)))

    def get_bit(self, bit: int) -> bool:
        self.read()
        segment = 0 if bit >= 16 else -1
        shift = bit - 16 if bit >= 16 else bit
        return bool(self.values[segment] & (1 << shift))

    def set_bit(self, bit: int) -> None:
        if self.read() is None:
            return
        segment = 0 if bit >= 16 else -1
        shift = bit - 16 if bit >= 16 else bit
        new = self.values.copy()
        new[segment] |= (1 << shift)
        if new != self.values:
            self.write(new)

    def reset_bit(self, bit: int) -> None:
        if self.read() is None:
            return
        segment = 0 if bit >= 16 else -1
        shift = bit - 16 if bit >= 16 else bit
        new = self.values.copy()
        new[segment] &= ~(1 << shift)
        if new != self.values:
            self.write(new)


class Registers:
    # ADDRESS_DATA = {}
    # for addr, meta in REGISTERS.items():
    #     symbol = meta['symbol']
    #     if symbol not in ADDRESS_DATA:
    #         ADDRESS_DATA[symbol] = []
    #     ADDRESS_DATA[symbol].append(addr)
    # for k, v in ADDRESS_DATA.items():
    #     # print(f"'{k}': [", ', '.join([f"0x{vv:04X}" for vv in v]), '],')
    #     print(f'{k}: Register = None')
    ADDRESS_DATA = {
        # 'EMGS': [0x0100],
        # 'SFTY': [0x0101],
        # 'PWR': [0x0102],
        # 'SV': [0x0103],
        # 'PSFL': [0x0104],
        # 'ALMH': [0x0105],
        # 'ALML': [0x0106],
        # 'ABER': [0x0107],
        # 'BKRL': [0x0108],
        # 'STP': [0x010A],
        # 'HEND': [0x010B],
        # 'PEND': [0x010C],
        # 'CEND': [0x010D],
        # 'CLBS': [0x010E],
        # 'ALA0': [0x0500, 0x0501],
        # 'ALC0': [0x0503],
        # 'ALT0': [0x0504, 0x0505],
        'DRG1': [0x0D00],
        'DRG2': [0x0D01],
        'POSR': [0x0D03],
        # 'TLMC': [0x8400, 0x8401],
        # 'ODOM': [0x8402, 0x8403],
        # 'TIMN': [0x8422],
        # 'TFAN': [0x842E],
        'PNOW': [0x9000, 0x9001],
        # 'ALMC': [0x9002],
        # 'DIPM': [0x9003],
        # 'DOPM': [0x9004],
        'DSS1': [0x9005],
        'DSS2': [0x9006],
        'DSSE': [0x9007],
        'STAT': [0x9008, 0x9009],
        # 'VNOW': [0x900A, 0x900B],
        # 'CNOW': [0x900C, 0x900D],
        # 'DEVI': [0x900E, 0x900F],
        # 'STIM': [0x9010, 0x9011],
        'SIPM': [0x9012],
        'ZONS': [0x9013],
        'POSS': [0x9014],
        'SSSE': [0x9015],
        # 'OLLV': [0x9020, 0x9021],
        # 'ALMP': [0x9022, 0x9023],
        'PPST': [0x9024],
        'PPJD': [0x9025],
        'POSR2': [0x9800],
        'PCMD': [0x9900, 0x9901],
        'INP': [0x9902, 0x9903],
        'VCMD': [0x9904, 0x9905],
        # 'ACMD': [0x9906],
        # 'PPOW': [0x9907],
        # 'CTLF': [0x9908],
    }

    EMGS: Register = None
    SFTY: Register = None
    PWR: Register = None
    SV: Register = None
    PSFL: Register = None
    ALMH: Register = None
    ALML: Register = None
    ABER: Register = None
    BKRL: Register = None
    STP: Register = None
    HEND: Register = None
    PEND: Register = None
    CEND: Register = None
    CLBS: Register = None
    ALA0: Register = None
    ALC0: Register = None
    ALT0: Register = None
    DRG1: Register = None
    DRG2: Register = None
    POSR: Register = None
    TLMC: Register = None
    ODOM: Register = None
    TIMN: Register = None
    TFAN: Register = None
    PNOW: Register = None
    ALMC: Register = None
    DIPM: Register = None
    DOPM: Register = None
    DSS1: Register = None
    DSS2: Register = None
    DSSE: Register = None
    STAT: Register = None
    VNOW: Register = None
    CNOW: Register = None
    DEVI: Register = None
    STIM: Register = None
    SIPM: Register = None
    ZONS: Register = None
    POSS: Register = None
    SSSE: Register = None
    OLLV: Register = None
    ALMP: Register = None
    PPST: Register = None
    PPJD: Register = None
    POSR2: Register = None
    PCMD: Register = None
    INP: Register = None
    VCMD: Register = None
    ACMD: Register = None
    PPOW: Register = None
    CTLF: Register = None


def _populate_registers(client: Optional[ModbusSerialClient] = None, slave_id: Optional[int] = None) -> Registers:
    reg_obj = Registers()
    for symbol, addrs in Registers.ADDRESS_DATA.items():
        name = None
        description = None
        signals = {}
        for i, addr in enumerate(addrs):
            meta = REGISTERS[addr]
            name = name or meta['name']
            description = description or meta['description']
            for bit, sig in meta.get('signals', {}).items():
                signals[(len(addrs) - 1 - i) * 16 + bit] = Signal(
                    bit=bit,
                    symbol=sig['symbol'],
                    name=sig['name'],
                    description=sig.get('description', '-')
                )
        setattr(
            reg_obj,
            symbol,
            Register(addrs, symbol, name, signals, description, client, slave_id)
        )
    return reg_obj


class Slave:
    def __init__(self, client: ModbusSerialClient, slave_id: int):
        self.id = slave_id
        self.client = client
        self.registers: Registers = _populate_registers(self.client, self.id)

    def read_register(self, address: int, count: int = 1) -> Optional[int]:
        resp = self.client.read_input_registers(address, count=count, slave=self.id + 1)
        if resp.isError():
            print(f"Error reading SLAVE {self.id} @ 0x{address:04X}: {resp}")
            return None
        values = resp.registers
        value = 0
        for v in values:
            value = (value << 16) | v
        value = int16(value) if count == 1 else int32(value)
        return value

    def update_registers(self) -> None:
        for symbol in Registers.ADDRESS_DATA.keys():
            getattr(self.registers, symbol).read()

    def alarm_reset(self) -> None:
        self.registers.DRG1.set_bit(Signal.ALRS)
        self.registers.DRG1.reset_bit(Signal.ALRS)

    def servo(self, on: bool) -> None:
        if on:
            self.registers.DRG1.set_bit(Signal.SON)
        else:
            self.registers.DRG1.reset_bit(Signal.SON)

    def pause(self, pause: bool) -> None:
        if pause:
            self.registers.DRG1.set_bit(Signal.STP)
        else:
            self.registers.DRG1.reset_bit(Signal.STP)

    def home(self, alarm_reset: bool = False, servo_on: bool = False, unpause: bool = False) -> None:
        if alarm_reset: self.alarm_reset()
        if servo_on: self.servo(True)
        if unpause: self.pause(False)
        self.registers.DRG1.set_bit(Signal.HOME)
        self.registers.DRG1.reset_bit(Signal.HOME)

    def move(self, position: int) -> None:
        self.registers.PCMD.write(split_int32_to_uint16(position).tolist())

    def move_to(self, row: int) -> None:
        self.registers.POSR2.write([row])

    def wait(
            self,
            error_emergency: bool = True,
            error_servo_off: bool = True,
            error_paused: bool = False
    ) -> Optional[str]:
        while self.is_moving():
            if self.is_emergency() and error_emergency:
                return 'emergency'
            if self.is_servo_off() and error_servo_off:
                return 'servo off'
            if self.is_paused() and error_paused:
                return 'paused'
        return None

    def is_moving(self) -> bool:
        return bool(self.registers.DSSE.get_bit(Signal.MOVE))

    def is_paused(self) -> bool:
        return bool(self.registers.DSS1.get_bit(Signal.STP))

    def is_servo_on(self) -> bool:
        return bool(self.registers.DSS1.get_bit(Signal.SON))

    def is_servo_off(self) -> bool:
        return not self.is_servo_on()

    def is_emergency(self) -> bool:
        return bool(self.registers.DSS1.get_bit(Signal.EMG))

    def get_current_position(self) -> int:
        self.registers.PNOW.read()
        return self.registers.PNOW.value

    def get_target_position(self, row: Optional[int] = None) -> int:
        if row is None:
            self.registers.PCMD.read()
            return self.registers.PCMD.value
        else:
            return self.read_register(0x1000 + 16 * row, count=2)

    def set_target_position(self, pos: int) -> None:
        self.registers.PCMD.write_value(pos)

    def get_distance(self, row: Optional[int] = None) -> int:
        return abs(self.get_target_position(row) - self.get_current_position())


class Robot:
    def __init__(
            self,
            comport: str,
            baudrate: int = 38400,
            timeout: float = 0.05,
            slaves: Optional[dict] = None,
    ) -> None:
        self.client = ModbusSerialClient(port=comport, baudrate=baudrate, timeout=timeout)
        self.slaves: Dict[int, Slave] = {}
        if slaves is None:
            slaves = {
                "0": {"min_max_position": [0, 40000]},
            }
        for id, slave in slaves.items():
            self.slaves[int(id)] = Slave(self.client, int(id))

    def close(self) -> None:
        if self.client:
            self.client.close()

    def update_registers(self, slave_id: Optional[int] = None, show_results: bool = False) -> None:
        def showbin(n):
            if n is None:
                return "| -- | -- |"
            b = f"{n:032b}"
            left = b[:16]
            right = b[16:]
            left_grouped = ' '.join([left[i:i + 4] for i in range(0, 16, 4)])
            right_grouped = ' '.join([right[i:i + 4] for i in range(0, 16, 4)])
            return f"| {left_grouped} | {right_grouped} |"

        for id, slave in self.slaves.items():
            if slave_id and slave_id != slave.id:
                continue
            slave.update_registers()
            if show_results:
                txt = ''
                # print(f"{CYAN}Slave {slave.id} registers:{END}")
                txt += f"{CYAN.BOLD}Slave {slave.id} registers:{END}\n"
                for symbol in Registers.ADDRESS_DATA.keys():
                    reg = getattr(slave.registers, symbol)
                    # print(f"\t{CYAN}{reg}{END}")
                    # print(f'\t{YELLOW}{showbin(reg.value)}{END}')
                    # txt += f"\t{CYAN}{reg.symbol}{END}\n"
                    txt += f'\t{YELLOW}{showbin(reg.value)} {CYAN}{reg.symbol}: {reg.value}{END}\n'
                print(txt)

    def to_json(self, slave_id: Optional[int] = None, just_vals: bool = False) -> str:
        # get all self.slaves if slave_id is None
        result: Dict[str, Any] = {}
        for id, slave in self.slaves.items():
            if slave_id and slave_id != slave.id:
                continue
            reg_dict = {}
            reg_just_val_dict = {}
            for symbol in Registers.ADDRESS_DATA.keys():
                reg: Register = getattr(slave.registers, symbol)
                # print(symbol) # STAT
                # print(reg) # Register(STAT, (0x9008, 0x9009), 524319)
                # print(reg.signals) # {31: Signal(15, BATL), 17: Signal(1, ASOF), ..., 1: Signal(1, SON), 0: Signal(0, MPOW)}

                signals_dict = {}
                for bit, sig in reg.signals.items():
                    bit_val = (reg.value >> bit) & 1 if reg.value is not None else None
                    sig_info = sig.to_dict()
                    sig_info['value'] = bit_val
                    signals_dict[bit] = sig_info
                reg_dict[symbol] = {
                    'address': reg.address,
                    'symbol': reg.symbol,
                    'name': reg.name,
                    'description': reg.description,
                    'val': reg.value,
                    'signals': signals_dict
                }
                reg_just_val_dict[symbol] = {'val': reg.value}
            result[f"Slave {slave.id}"] = reg_just_val_dict if just_vals else reg_dict
        return json.dumps(result, indent=4)

    def alarm_reset(self) -> None:
        for id, slave in self.slaves.items():
            slave.alarm_reset()

    def servo(self, on: bool = True) -> None:
        for id, slave in self.slaves.items():
            slave.servo(on)

    def pause(self, pause: bool = True) -> None:
        for id, slave in self.slaves.items():
            slave.pause(pause)

    def home(self, alarm_reset: bool = False, servo_on: bool = False, unpause: bool = False) -> None:
        for id, slave in self.slaves.items():
            slave.home(alarm_reset, servo_on, unpause)

    def move_to(self, row: int):
        for id, slave in self.slaves.items():
            slave.move_to(row)

    def wait(
            self,
            error_emergency: bool = True,
            error_servo_off: bool = True,
            error_paused: bool = False
    ) -> Optional[str]:
        while self.is_any_moving():
            if self.is_any_emergency() and error_emergency:
                return 'emergency'
            if self.is_any_servo_off() and error_servo_off:
                return 'servo off'
            if self.is_any_paused() and error_paused:
                return 'paused'
        return None

    def get_distance(self, row: Optional[int] = None):
        return math.sqrt(sum((slave.get_distance(row)) ** 2 for slave in self.slaves.values()))

    def is_any_moving(self) -> bool:
        return any(slave.is_moving() for slave in self.slaves.values())

    def is_any_paused(self) -> bool:
        return any(slave.is_paused() for slave in self.slaves.values())

    def is_any_servo_off(self) -> bool:
        return not all(slave.is_servo_on() for slave in self.slaves.values())

    def is_any_emergency(self) -> bool:
        return any(slave.is_emergency() for slave in self.slaves.values())


if __name__ == "__main__":
    comport = get_comport(
        'ATEN USB to Serial',
        'IAI USB to UART Bridge Controller',
        'USB-Serial Controller',
        'USB Serial Port'
    )
    print(f"Using COM port: {comport}\n")
    robot = Robot(comport=comport, baudrate=38400, )

    robot.client.connect()

    # test convert registers to json
    robot.update_registers()
    print(robot.to_json())

    # setup slave and reset alarm
    slave = robot.slaves[0]
    slave.alarm_reset()

    # on servo
    if robot.is_any_servo_off():
        robot.alarm_reset()
        robot.servo(True)

    # unpause
    if robot.is_any_paused():
        robot.pause(False)

    # test move and wait (1)
    slave.move_to(0)
    while slave.is_moving(): pass

    # test move and wait (2)
    slave.home()
    status = slave.wait()
    if status: print(f'{RED}{status}{END}')

    # test move and wait (3)
    stop = False
    for pos in [40000, 0, 40000, 0, 40000]:
        print(pos)
        slave.move(pos)

        # status = slave.wait()
        # if status: print(f'{RED}{status}{END}')
        # if status == 'servo off':
        #     stop = True
        #     break
        # if stop:
        #     break
        # time.sleep(0.5)

        ... or ...

        while True:
            slave.registers.PNOW.read()
            slave.registers.PCMD.read()
            print(f'{slave.registers.PNOW.value} -> {slave.registers.PCMD.value} | dist={slave.get_distance()}')

            if not slave.is_moving():
                break
            while slave.is_paused():
                pass
            if not slave.is_servo_on():
                stop = True
                break
        if stop:
            break
        time.sleep(0.5)

    robot.close()
