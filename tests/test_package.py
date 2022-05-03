import pytest
from rpi_hardware_pwm import HardwarePWMException
from rpictrl import *


def test_dependencies():
    try:
        NMosPWM(pin_no=12)
    except HardwarePWMException:
        pass
