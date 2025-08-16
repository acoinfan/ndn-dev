f'ndnclient --config /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini '
f'--directory /home/a_coin_fan/code/ndn-dev/experiments '
f'--filename small_test.txt '
f'--id {i} '
f'--nodes 3 > /tmp/ndn/client{i}.log 2>&1 &'

NDN_CLIENT_TRANSPORT=unix:///run/nfd/client0.sock nfdc face list