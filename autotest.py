from mininet.log import setLogLevel, info
from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr
from minindn.apps.application import Application
from time import sleep

def main():
    setLogLevel('debug')
    Minindn.cleanUp()
    Minindn.verifyDependencies()

    print("### staring Minindn ###")
    
    ndn = Minindn(topoFile="web.conf")

    ndn.start()
    sleep(10)

    print("### starting NFD ###")
    nfds = AppManager(ndn, ndn.net.hosts, Nfd)
    sleep(10)

    nlsrs = AppManager(ndn, ndn.net.hosts, Nlsr)
    sleep(10)


    consumers = [host for host in ndn.net.hosts if host.name.startswith("con")]
    producers = [host for host in ndn.net.hosts if host.name.startswith("pro")]

    print("### starting Producer ###")
    for producer in producers:
        Application(producer).start("/home/a_coin_fan/code/ndn-dev/producer/bin/ndnput --prefix producer --datasetId 1 --config /home/a_coin_fan/code/ndn-dev/producer/config.ini", "producer.log")
        sleep(10)
    
    print("### starting Consumer ###")
    for consumer in consumers:
        Application(consumer).start("/home/a_coin_fan/code/ndn-dev/consumer/bin/ndnget /producer/1/medium_test.txt -v --no-version-discovery", "consumer.log")
        sleep(5)
        print("### finish sending ##")
    MiniNDNCLI(ndn.net)


main()