from hexss import check_packages

check_packages('pandas', 'pymodbus', 'Flask', 'pyserial', auto_install=True, verbose=False)

registers = {
    'ALA01': {
        'name': 'Detailed information of the alarm detected lately 0',
        'address': 0x0500
    },

    'ALA02': {
        'name': 'Detailed information of the alarm detected lately 1',
        'address': 0x0501
    },

    '-': {
        'name': 'Detailed information of the alarm detected lately 2',
        'address': 0x0502
    },

    'ALC0': {
        'name': 'Detailed information of the alarm detected lately 3',
        'address': 0x0503
    },

    'ALT0': {
        'name': 'Detailed information of the alarm detected lately 4',
        'address': 0x0504
    },

    'DRG1': {
        'name': 'Device Control Register 1',
        'address': 0x0D00,
        'signals': [
            {
                'bit_position': 14,
                'signal_symbol': 'SFTY',
                'signal_name': 'Safety speed command',
                'description': 'Safety speed set with the parameter 0: Invalid, 1: Valid'
            },
            {
                'bit_position': 12,
                'signal_symbol': 'SON',
                'signal_name': 'Servo ON command',
                'description': '0: Servo OFF, 1: Servo ON'
            },
            {
                'bit_position': 8,
                'signal_symbol': 'RES',
                'signal_name': 'Alarm reset',
                'description': '0: Normal, “0” -> “1” rise edge: Alarm reset'
            },
            {
                'bit_position': 5,
                'signal_symbol': 'STP',
                'signal_name': 'Pause command',
                'description': '0: Normal, 1: Pause (deceleration stop)'
            },
            {
                'bit_position': 4,
                'signal_symbol': 'HOME',
                'signal_name': 'Home return command',
                'description': '“0” -> “1” rise edge: Home return operation'
            },
            {
                'bit_position': 3,
                'signal_symbol': 'CSTR',
                'signal_name': 'Positioning start',
                'description': '0: Normal, “0” -> “1” rise edge: Positioning start to the target position specified with the position no.'
            },
        ]
    },
    'DRG2': {
        'name': 'Device Control Register 2',
        'address': 0x0D01
    },

    'POSR': {
        'name': 'Position NO. Specification Register',
        'address': 0x0D03,
        'signals': [
            {
                'bit_position': 5,
                'signal_symbol': 'PC32',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 4,
                'signal_symbol': 'PC16',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 3,
                'signal_symbol': 'PC8',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 2,
                'signal_symbol': 'PC4',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 1,
                'signal_symbol': 'PC2',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 0,
                'signal_symbol': 'PC1',
                'signal_name': '-',
                'description': '-'
            },
        ]
    },

    'DSS1': {
        'name': 'Device Status Register',
        'address': 0x9005,
        'signals': [
            {
                'bit_position': 15,
                'signal_symbol': 'EMGS',
                'signal_name': 'Emergency stop status',
                'description': '1: Under emergency stop'
            },
            {
                'bit_position': 14,
                'signal_symbol': 'SFTY',
                'signal_name': 'Safety speed valid',
                'description': '1: Safety speed valid condition'
            },
            {
                'bit_position': 13,
                'signal_symbol': 'PWR',
                'signal_name': 'Controller ready ',
                'description': '1: Controller preparation completed'
            },
            {
                'bit_position': 12,
                'signal_symbol': 'SV',
                'signal_name': 'Servo ready',
                'description': '1: Operation preparation completed (servo ON status)'
            },
            {
                'bit_position': 11,
                'signal_symbol': 'PSFL',
                'signal_name': 'Push & hold missing',
                'description': '1: Push & hold missing'
            },
            {
                'bit_position': 10,
                'signal_symbol': 'ALMH',
                'signal_name': 'Major failure status ',
                'description': '1: Alarm indicating that continuous operation is impossible'
            },
            {
                'bit_position': 9,
                'signal_symbol': 'ALML',
                'signal_name': 'Minor failure status ',
                'description': '1: Alarm indicating that continuous operation is impossible'
            },
            {
                'bit_position': 5,
                'signal_symbol': 'STP',
                'signal_name': 'Pause commanding',
                'description': '1: Pause command being issued'
            },
            {
                'bit_position': 4,
                'signal_symbol': 'HEND',
                'signal_name': 'Home return completion',
                'description': '1: Home return completed'
            },
            {
                'bit_position': 3,
                'signal_symbol': 'PEND',
                'signal_name': 'Position complete',
                'description': '1: Positioning completed'
            },
        ]
    },
    'DSSE': {
        'name': 'Expansion Device Status Register',
        'address': 0x9007,
        'signals': [
            {
                'bit_position': 11,
                'signal_symbol': 'GMHS',
                'signal_name': 'Home returning',
                'description': '1: Home returning'
            },
            {
                'bit_position': 10,
                'signal_symbol': 'PUSH',
                'signal_name': 'Push & hold operating',
                'description': '1: Push & hold operating '
            },
            {
                'bit_position': 5,
                'signal_symbol': 'MOVE',
                'signal_name': 'Moving',
                'description': '1: Moving (including home return, push & hold operation)'
            },
        ]
    },
    'ZONS': {
        'name': 'Zone Status Register',
        'address': 0x9013,
        'signals': [
            {
                'bit_position': 8,
                'signal_symbol': 'PZONE',
                'signal_name': 'Position zone output',
                'description': 'This signal becomes “1” when the current position is within the setting range if individual zone boundaries are set in the position table.'
            },
            {
                'bit_position': 1,
                'signal_symbol': 'ZONE2',
                'signal_name': 'Zone output 2',
                'description': 'This signal becomes “1” when the position is within the setting range of the parameter zone boundary 2.'
            },
            {
                'bit_position': 0,
                'signal_symbol': 'PZON1',
                'signal_name': 'Zone output 1',
                'description': 'This signal becomes “1” when the position is within the setting range of the parameter zone boundary 1.'
            },

        ]
    },
    'POSS': {
        'name': 'Position NO. Status Register',
        'address': 0x9014,
        'signals': [
            {
                'bit_position': 5,
                'signal_symbol': 'PM32',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },
            {
                'bit_position': 4,
                'signal_symbol': 'PM16',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },
            {
                'bit_position': 3,
                'signal_symbol': 'PM8',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },
            {
                'bit_position': 2,
                'signal_symbol': 'PM4',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },
            {
                'bit_position': 1,
                'signal_symbol': 'PM2',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },
            {
                'bit_position': 0,
                'signal_symbol': 'PM1',
                'signal_name': '',
                'description': 'The position complete position no. is output as a 6-bit binary code.'
            },

        ]
    },
    'POSR2': {
        'name': 'Position NO. Specification Register',
        'address': 0x9800,
        'signals': [
            {
                'bit_position': 5,
                'signal_symbol': 'PC32',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 4,
                'signal_symbol': 'PC16',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 3,
                'signal_symbol': 'PC8',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 2,
                'signal_symbol': 'PC4',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 1,
                'signal_symbol': 'PC2',
                'signal_name': '-',
                'description': '-'
            },
            {
                'bit_position': 0,
                'signal_symbol': 'PC1',
                'signal_name': '-',
                'description': '-'
            },
        ]
    },

    'PCMDH': {
        'name': 'Target position coordinate specification register H',
        'address': 0x9900,
    },
    'PCMDL': {
        'name': 'Target position coordinate specification register L',
        'address': 0x9901,
    },

    'INPH': {
        'name': 'Positioning band specification register  H',
        'address': 0x9902,
    },
    'INPL': {
        'name': 'Positioning band specification register  L',
        'address': 0x9903,
    },

    'VCMDH': {
        'name': 'Speed specification register H',
        'address': 0x9904,
    },
    'VCMDL': {
        'name': 'Speed specification register L',
        'address': 0x9905,
    },
    'ACMD': {
        'name': 'Acceleration/deceleration speed specification register',
        'address': 0x9906,
    },
    'PPOW': {
        'name': 'Push-current limiting value',
        'address': 0x9907,
    },
    'CTLF': {
        'name': 'Control flag specification register',
        'address': 0x9908,
    },
}


class Signal:
    def __init__(self, bit_position, signal_symbol, signal_name, description):
        self.bit_position = bit_position
        self.signal_symbol = signal_symbol
        self.signal_name = signal_name
        self.description = description
        self.value = None


class Register:
    def __init__(self, name, address, signals=None):
        self.name = name
        self.address = address
        self.signals = [Signal(**signal) for signal in signals] if signals else None
        self.value = None


class Registers:
    registers_list = [
        'ALA01',
        'ALA02',
        'ALC0',
        'ALT0',
        'DRG1',
        'DRG2',
        'POSR',
        'DSS1',
        'DSSE',
        'ZONS',
        'POSS',
        'POSR2',
        'PCMDH',
        'PCMDL',
        'INPH',
        'INPL',
        'VCMDH',
        'VCMDL',
        'ACMD',
        'PPOW',
        'CTLF'
    ]
    ALA01: Register = None
    ALA02: Register = None
    ALC0: Register = None
    ALT0: Register = None
    DRG1: Register = None
    DRG2: Register = None
    POSR: Register = None
    DSS1: Register = None
    DSSE: Register = None
    ZONS: Register = None
    POSS: Register = None
    POSR2: Register = None
    PCMDH: Register = None
    PCMDL: Register = None
    INPH: Register = None
    INPL: Register = None
    VCMDH: Register = None
    VCMDL: Register = None
    ACMD: Register = None
    PPOW: Register = None
    CTLF: Register = None

    def __init__(self, registers_dict):
        for key, value in registers_dict.items():
            setattr(self, key, Register(name=value['name'], address=value['address'], signals=value.get('signals')))

    def get_register_by_name(self, name):
        return getattr(self, name, None)


all_registers = Registers(registers)
