from rpi_hardware_pwm import HardwarePWM
from threading import Thread, Event
import subprocess
import time
import signal
import atexit
from collections import deque
import logging
import os

BOARD = 10
BCM = 11
HW_PWM_MAP = {BOARD: {12: 0, 35: 1},
              BCM: {18: 0, 19: 1}}
AUDIBLE_SPECTRUM = range(20, 20_000)
RPI_TEMP_CMD = ['vcgencmd', 'measure_temp']

logger = logging.getLogger('cpu-temp-control')
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'INFO'))


class Controller(object):
    def start_pwm(self, duty_cycle: int) -> None:
        raise NotImplementedError

    def set_frequency(self, frequency: int) -> None:
        raise NotImplementedError

    def set_duty_cycle(self, duty_cycle: int) -> None:
        raise NotImplementedError

    def stop_pwm(self) -> None:
        raise NotImplementedError

    def exit_handler(self) -> None:
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
    def frequency(self) -> int:
        return self.__frequency

    @frequency.setter
    def frequency(self, value):
        self.set_frequency(value)

    @property
    def duty_cycle(self) -> int:
        return self.__duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        self.set_duty_cycle(value)

    def set_frequency(self, frequency: int) -> None:
        if frequency <= 0:
            raise ValueError('frequency need to be positive non-zero int')
        self.pwm.change_frequency(frequency)
        self.__frequency = frequency

    def set_duty_cycle(self, duty_cycle: int) -> None:
        if not 0 <= duty_cycle <= 100:
            raise ValueError('Duty cycle can only be non negative int from 0 to 100')
        self.pwm.change_duty_cycle(duty_cycle)
        if duty_cycle == 0:
            self.is_stopped = True
        self.__duty_cycle = duty_cycle

    def start_pwm(self, duty_cycle: int) -> None:
        if not 0 <= duty_cycle <= 100:
            raise ValueError('Duty cycle can only be non negative int from 0 to 100')
        self.pwm.start(duty_cycle)
        self.__duty_cycle = duty_cycle
        self.is_stopped = False

    def stop_pwm(self) -> None:
        self.pwm.stop()
        self.is_stopped = True


class CPUTempController(NMosPWM):
    """
    Main cpu temperature controller object. Init this object to get threaded fan control.

    e.g.
    CPUTempController(pin_no=12, freq=25000, pinout_type=10, temp_min=50, temp_max=80, duty_cycle_min=20,
        duty_cycle_max=100, settle_time=5)
    """
    def __init__(self, **kwargs):
        for key, arg in kwargs.items():
            setattr(self, key, arg)
        super(CPUTempController, self).__init__(pin_no=self.pin_no, frequency=self.freq, pinout_type=self.pinout_type)
        for key, arg in kwargs.items():
            setattr(self, key, arg)
        if 'temp_q_size' not in kwargs:
            setattr(self, 'temp_q_size', 10)  # temperature queue size that stores past n temperature samples
        if 'polling_interval' not in kwargs:
            setattr(self, 'polling_interval', 1)  # cpu temperature measuring interval
        self.temp_q = deque(maxlen=self.temp_q_size)  # queue that store past temperatures for control decision
        self.job = Thread
        self.ramping = False
        signal.signal(signal.SIGTERM, self.stop_monitor)
        signal.signal(signal.SIGINT, self.stop_monitor)

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

    @classmethod
    def linear_duty_cycle(cls, temp_now: float, temp_min: float, temp_max: float, dc_min: int, dc_max: int) -> int:
        """
        Algorithm to calculate two points linear duty cycle
        :param temp_now: current temp
        :param temp_min: min temperature to kick in control
        :param temp_max: max temperature need full control
        :param dc_min: min duty cycle can turn on device under control, matches temp_min
        :param dc_max: max duty cycle at temp_max and above
        :return:
        """
        dc = (dc_max - dc_min) / (temp_max - temp_min) * (temp_now - temp_min) + dc_min
        return int(dc) if dc >= dc_min else 0

    def fan_self_test(self, from_dc=20, to_dc=50, interval=0.2) -> None:
        """
        Perform a self test for debugging purposes
        """
        if self.is_stopped:
            self.start_pwm(0)
            for i in range(from_dc, to_dc + 1):
                self.duty_cycle= i
                time.sleep(interval)
            self.stop_pwm()
        logger.info(f'Fan self test from {from_dc} to {to_dc} done')

    def calc_dc_cpu(self, cpu_temp: float) -> int:
        if not hasattr(self, 'temp_max') or not hasattr(self, 'temp_min'):
            raise ValueError('need to specify temp_mim and temp_max for linear duty cycle calc')
        return self.linear_duty_cycle(temp_now=cpu_temp, temp_min=self.temp_min, temp_max=self.temp_max,
                                      dc_min=self.duty_cycle_min, dc_max=self.duty_cycle_max)

    @property
    def is_lingering(self) -> bool:
        """
        lingering is a state that temperature hovering around the temperature set point. Fan should preserve previous
        action in this state.
        """
        if any([i <= self.temp_min for i in self.temp_q]) and any([i > self.temp_min for i in self.temp_q]):
            return True
        return False

    @property
    def d2temperature(self) -> float:
        """
        Calculate second order derivative of past 3 samples. Second order derivative implies temperature increasing
        trend.
        """
        pass

    def fan_manager(self) -> None:
        """
        Applying fan on off control strategy
        """
        self.temp_q.append(self.get_cpu_temp())
        if len(self.temp_q) < self.temp_q.maxlen or self.is_lingering:
            return
        new_dc = self.calc_dc_cpu(self.temp_q[-1])
        if new_dc != self.duty_cycle:  # saving duty cycle assignment when duty cycle no change
            self.duty_cycle = new_dc

    def stop_monitor(self) -> None:
        logger.warning('Stopping fan control')
        self.stop_pwm()
        if hasattr(self.job, 'stop'):
            self.job.stop()

    def start_monitor_thread(self) -> None:
        self.start_pwm(0)
        self.job = MonitorJob(self)
        self.job.start()
        logger.info('CPU temperature monitor job started. monitoring temperautre...')


class MonitorJob(Thread):
    def __init__(self, controller: CPUTempController):
        """
        https://medium.com/greedygame-engineering/an-elegant-way-to-run-periodic-tasks-in-python-61b7c477b679
        """
        super(MonitorJob, self).__init__()
        self.daemon = True
        self.stopped = Event()
        self.controller = controller

    def stop(self) -> None:
        self.stopped.set()
        self.join()

    def run(self) -> None:
        while not self.stopped.wait(self.controller.polling_interval):
            self.controller.fan_manager()


if __name__ == '__main__':
    import argparse
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

    ops = parser.parse_args()

    ctc = CPUTempController(pin_no=ops.pin, freq=ops.frequency, pinout_type=type_map[ops.board_type],
                            temp_min=ops.temp_min, temp_max=ops.temp_max, duty_cycle_min=ops.duty_cycle,
                            duty_cycle_max=ops.duty_cycle_max)
    logger.info('Shiny new CPU controller created')
    atexit.register(ctc.exit_handler)
    ctc.fan_self_test()
    ctc.start_monitor_thread()
    ctc.job.join()
