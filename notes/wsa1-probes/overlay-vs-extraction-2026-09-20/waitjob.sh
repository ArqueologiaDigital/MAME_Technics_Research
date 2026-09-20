#!/bin/bash
until ! pgrep -f "wsa1drv/wsa1 wsa1r" >/dev/null; do sleep 5; done
echo DONE
