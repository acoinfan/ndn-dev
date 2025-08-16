from mininet.net import Mininet
from mininet.node import Host
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from time import sleep
import os
import importlib.util
import sys
import datetime
import shutil
import threading

net = Mininet(link=TCLink)
h1 = net.addHost('h1')
h2 = net.addHost('h2')
h3 = net.addHost('h3')

net.addLink(h1, h2, bw=100)
net.addLink(h1, h3, bw=100)

net.start()

# 为每条链路设置独立子网（推荐使用 /30）
h1.setIP('10.0.1.1/30', intf='h1-eth0')
h2.setIP('10.0.1.2/30', intf='h2-eth0')

h1.setIP('10.0.2.1/30', intf='h1-eth1')
h3.setIP('10.0.2.2/30', intf='h3-eth0')

print('h1 interfaces: %s\n' % h1.intfNames())
print('h1 IPs:\n%s\n' % h1.cmd('ip addr show'))
print('h2 IPs:\n%s\n' % h2.cmd('ip addr show'))
print('h3 IPs:\n%s\n' % h3.cmd('ip addr show'))

# 如果你希望 h2 <-> h3 互通（通过 h1 路由），开启转发并添加路由：
# h1.cmd('sysctl -w net.ipv4.ip_forward=1')
# h2.cmd('ip route add 10.0.2.0/30 via 10.0.1.1')
# h3.cmd('ip route add 10.0.1.0/30 via 10.0.2.1')

CLI(net)

net.stop()
