from rpi_hardware_pwm import HardwarePWM
from threading import Thread, Event
import subprocess
import atexit

BOARD = 10
BCM = 11
HW_PWM_MAP = {BOARD: {12: 0, 35: 1},
              BCM: {18: 0, 19: 1}}
AUDIBLE_SPECTRUM = range(20, 20_000)
RPI_TEMP_CMD = ['vcgencmd', 'measure_temp']


class Controller(object):
    def start_pwm(self, duty_cycle: int):
        raise NotImplementedError

    def set_frequency(self, frequency: int):
        raise NotImplementedError

    def set_duty_cycle(self, duty_cycle: int):
        raise NotImplementedError

    def stop_pwm(self):
        raise NotImplementedError

    def exit_handler(self):
        self.stop_pwm()
        print('Fan control stopped')

    def __del__(self):
        try:
            self.stop_pwm()
        except:
            pass


class NMosPWM(Controller):
    def __init__(self, pin_no, frequency=25_000, pinout_type=BOARD):
        if pin_no not in HW_PWM_MAP[pinout_type].keys():
            raise ValueError(f'RPI pin {pin_no} not support hardware pwm')
        self.__frequency = frequency
        self.__duty_cycle = None
        self.is_stopped = True
        self.pwm = HardwarePWM(pwm_channel=HW_PWM_MAP[pinout_type][pin_no], hz=self.__frequency)

    @property
    def frequency(self):
        return self.__frequency

    @frequency.setter
    def frequency(self, value):
        self.set_frequency(value)

    @property
    def duty_cycle(self):
        return self.__duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        self.set_duty_cycle(value)

    def set_frequency(self, frequency: int):
        if frequency <= 0:
            raise ValueError('frequency need to be positive non-zero int')
        self.pwm.change_frequency(frequency)
        self.__frequency = frequency

    def set_duty_cycle(self, duty_cycle: int):
        if not 0 <= duty_cycle <= 100:
            raise ValueError('Duty cycle can only be non negative int from 0 to 100')
        self.pwm.change_duty_cycle(duty_cycle)
        self.__duty_cycle = duty_cycle

    def start_pwm(self, duty_cycle: int):
        if not 0 <= duty_cycle <= 100:
            raise ValueError('Duty cycle can only be non negative int from 0 to 100')
        self.pwm.start(duty_cycle)
        self.__duty_cycle = duty_cycle
        self.is_stopped = False

    def stop_pwm(self):
        self.pwm.stop()
        self.is_stopped = True


class CPUTempController(Thread, NMosPWM):
    def __init__(self, **kwargs):
        for key, arg in kwargs.items():
            setattr(self, key, arg)
        super(CPUTempController, self).__init__(pin_no=self.pin_no, frequency=self.frequency,
                                                pinout_type=self.pinout_type)
        for key, arg in kwargs.items():
            setattr(self, key, arg)

    @staticmethod
    def get_cpu_temp(round_to=2) -> float:
        """
        get current RPI cpu temperature
        Unit in deg C
        :param round_to: round result to decimal points
        """
        result = subprocess.Popen(RPI_TEMP_CMD, stdout=subprocess.PIPE)
        result = result.stdout.read().decode('ascii')
        temp = result.split('=')[1][0:4]  # will get temp=52^C
        return round(float(temp), round_to)

    def fan_self_test(self):
        if self.is_stopped:
            self.start_pwm(20)
            time.sleep(3)
            self.stop_pwm()

    def linear_duty_cycle(self):
        if not hasattr(self, 'temp_max') or not hasattr(self, 'temp_min'):
            raise ValueError('need to specify temp_mim and temp_max for linear duty cycle calc')
        dc = (self.duty_cycle_max - self.duty_cycle_min) / (self.temp_max - self.temp_min) * \
             (self.get_cpu_temp() - self.duty_cycle_min) + self.duty_cycle_min
        return int(dc) if dc >= self.duty_cycle_min else 0

    def run(self):
        pass


if __name__ == '__main__':
    import argparse
    import time
    type_map = {'board': BOARD, 'bcm': BCM}

    parser = argparse.ArgumentParser(description='Smart control RPI CPU core temperature set point with PWM fan')
    parser.add_argument('-p', '--pin', dest='pin', default=12, type=int,
                        help='The PWM pin number (RPI GPIO board type) controlling the fan')
    parser.add_argument('-b', '--board-type', dest='board_type', default='board', type=str,
                        help=f'RPI pin board type. options: f{list(type_map.keys())}')
    parser.add_argument('-d', '--duty-cycle', dest='duty_cycle', default=20, type=int,
                        help='Minimum duty cycle can turn fan on from stall')
    parser.add_argument('--duty-cycle-max', dest='duty_cycle_max', default=100, type=int,
                        help='max duty cycle fan can run')
    parser.add_argument('-f', '--frequency', dest='frequency', default=25_000, type=int,
                        help='PWM frequency. Ideally set frequency outside audible range')
    parser.add_argument('-t', '--temperature_min', dest='temp_min', default=55, type=int,
                        help='Temperature set point (to turn fan on)')
    parser.add_argument('-m', '--temperature_max', dest='temp_max', default=85, type=int,
                        help='Temperature point that turn fan to full speed')
    parser.add_argument('-s', '--settle_time', dest='settle_time', default=10, type=int,
                        help='After temperature reached min set point, delay time (s) before fan can turn back on')

    ops = parser.parse_args()

    ctc = CPUTempController(pin_no=ops.pin, frequency=ops.frequency, pinout_type=type_map[ops.board_type],
                            temp_min=ops.temp_min, temp_max=ops.temp_max, duty_cycle_min=ops.duty_cycle,
                            duty_cycle_max=ops.duty_cycle_max, settle_time=ops.settle_time)
    atexit.register(ctc.exit_handler)
    ctc.fan_self_test()
