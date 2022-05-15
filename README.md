# rpi-temp-control
[![Python package](https://github.com/RNLgit/rpi-temp-control/actions/workflows/python-package.yml/badge.svg)](
https://github.com/RNLgit/rpi-temp-control/actions/workflows/python-package.yml)

A lightweight service that cools raspberry pi cpu temperature by pwm fan.

## Hardware Set-up
Requires MOSFET setup connect to one of hardware control PWM pins

![Circuit](./image/NMosfet_switch.png)

###GPIO Pins:
Many GPIO can set to pwm output, but there're only limited number of pins can use hardware pwm which can set frequency
higher than audible range. Checkout the correct pin to avoid unpleasant noise. e.g. on RPI 4 Model B, PIN 12 & 
35 (Board pin ref) are hardware pwm pins.

## Dependencies
Requires [rpi-hardware-pwm](https://github.com/Pioreactor/rpi_hardware_pwm) to enable pwm frequency that can set beyond
audible range. 

# Setup Temp Control Upon Startup

1. use sudo to install required packages 
   (It may fail to import package if not root pip3)
   ```console
   sudo pip3 install
   ```
2. modify your ```temp-controller/controller.py``` path according to your local in 
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

# Debugging

- Check service status:
   ```console
   systemctl status cpu-temp-control
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
