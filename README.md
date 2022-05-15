# rpi-temp-control
[![Python package](https://github.com/RNLgit/rpi-temp-control/actions/workflows/python-package.yml/badge.svg)](
https://github.com/RNLgit/rpi-temp-control/actions/workflows/python-package.yml)

A lightweight service that cools raspberry pi cpu temperature by pwm fan.

**Features** 
 - Background running upon device boot up
 - Linear regulation in temperature range
 - Avoids frequent fan on/off when temperature lingering around set point

---

## Set Up

## Hardware Set-up
Requires MOSFET setup connect to one of hardware control PWM pins.

![Circuit](./image/NMosfet_switch.png)

### Fan Powering:
If using ~ 1W fan, for example [Delta BFB0405HHA-A](https://www.delta-fan.com/products/BFB0405HHA-A.html), it generally 
ok to connect fan positive to RPI 5V rail. However more powerful fan is used or working in full spinning for most of the 
time, using a separate fan power and share the same ground is suggested to avoid RPI under power.

### GPIO Pins:
Many GPIO can set to pwm output, but there're only limited number of pins can use hardware pwm which can set frequency
higher than audible range. Checkout the correct pin to avoid unpleasant noise. e.g. on RPI 4 Model B, PIN 12 & 
35 (Board pin ref) are hardware pwm pins.

## Dependencies
Requires [rpi-hardware-pwm](https://github.com/Pioreactor/rpi_hardware_pwm) to enable pwm frequency that can set beyond
audible range. 

## Avoiding Fan Dead Zone
Each fan have it's own dead zone that pwm can't turn fan on (at low duty cycle, for example 20%), it depend on the pwm frequency and duty cycle set. Tested out
each fan for minimum duty cycle & frequency pair before making the service permenant.

---

# Usage

## Use as package

Threaded control

```Python
from rpictrl import CPUTempController
from RPi.GPIO import BOARD

ctc = CPUTempController(pin_no=12,  freq=25000, pinout_type=BOARD, temp_min=50, temp_max=80, duty_cycle_min=20, duty_cycle_max=100)
ctc.fan_self_test(from_dc=20, to_dc=100)  # test out duty cycle from 20% to 100%
ctc.start_monitor_thread()
```

Fan Access

```Python
from rpictrl import NMosPWM

pwm_fan = NMosPWM(pin_no=12)
pwm_fan.frequency = 30_000  # set pwm frequency
pwm_fan.start(30)  # start fan duty cycle as 30%
pwm_fan.duty_cycle = 40  # change duty cycle to 40%, apply instantly
pwn_fan.frequency = 25_000  # change pwm frequency to 25,000 Hz, apply instantly
pwm_fan.duty_cycle  # query current pwm duty cycle
pwm_fan.frequency  # query current pwm frequency
```

## Use as service upon startup

1. use sudo to install required packages 
   (It may fail to import package if not root pip3)
   ```console
   sudo pip3 install
   ```
2. modify your ```temp-controller/controller.py``` path and args accordingly in 
   ```service/cpu-temp-control.service```
3. ```console
    sudo cp ./cpu-temp-control.service /etc/systemd/system/cpu-temp-control.service
    ```
4. Reload the daemon 
   ```console
   sudo systemctl daemon-reload
   ```
5. Enable service 
   ```console
   sudo systemctl enable cpu-temp-control.service
   ```
6. Start service 
   ```console
   sudo systemctl start cpu-temp-control.service
   ```

- To stop service 
  ```console
  sudo systemctl stop cpu-temp-control.service
  ```

---

# Debugging

- Check service status:
   ```console
   systemctl status cpu-temp-control
   ```
   
- Check previous fan on/off logs:
   ```console
   vi /var/log/syslog
   ```

- Check error traceback from the service
    - get PID of the service 
      ```console
      systemctl status cpu-temp-control | grep -oP '(?<=PID: )[0-9]+'
      ```
    - then get error traceback from PID 
      ```console
      journalctl _PID=$PID
      ```
