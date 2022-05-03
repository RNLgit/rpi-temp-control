from rpi_hardware_pwm import HardwarePWM
import atexit

BOARD = 10
BCM = 11
HW_PWM_MAP = {BOARD: {12: 0, 35: 1},
              BCM: {18: 0, 19: 1}}
AUDIBLE_SPECTRUM = range(20, 20_000)


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


if __name__ == '__main__':
    import argparse
    import time
    type_map = {'board': BOARD, 'bcm': BCM}

    parser = argparse.ArgumentParser(description='Smart control RPI CPU core temperature set point with PWM fan')
    parser.add_argument('-p', '--pin', dest='pin', default=12, type=int,
                        help='The PWM pin number (RPI GPIO board type) controlling the fan')
    parser.add_argument('-b', '--board-type', dest='board_type', default='board', type=str,
                        help=f'RPI pin board type. options: f{list(type_map.keys())}')
    parser.add_argument('-t', '--temperature_min', dest='temperature_min', default=55, type=int,
                        help='Temperature set point (to turn fan on)')
    parser.add_argument('-d', '--duty-cycle', dest='duty_cycle', default=20, type=int,
                        help='Minimum duty cycle can turn fan on from stall')
    parser.add_argument('-f', '--frequency', dest='frequency', default=25_000, type=int,
                        help='PWM frequency. Ideally set frequency outside audible range')
    parser.add_argument('-m', '--temperature_max', dest='temperature_max', default=80, type=int,
                        help='Temperature point that turn fan to full speed')
    parser.add_argument('-s', '--settle_time', dest='settle_time', default=10, type=int,
                        help='After temperature reached min set point, delay time (s) before fan can turn back on')

    ops = parser.parse_args()

    fan_h = NMosPWM(ops.pin, ops.frequency, type_map[ops.board_type])
    atexit.register(fan_h.exit_handler)
    fan_h.start_pwm(ops.duty_cycle)
    time.sleep(3)
