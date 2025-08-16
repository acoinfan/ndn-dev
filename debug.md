# 调试笔记（debug.md）

本文件总结了在本仓库（ndn-dev）调试 NFD / Mininet / ndnclient 时的常见问题、排查步骤和可复现的命令，方便快速定位「ping 通但 NDN 报 NoRoute」等问题。

## 目标
- 给出可复现的最小检查清单
- 列出常用命令与日志位置
- 总结已遇到的问题、根因与修复建议

---

## 环境要点
- Mininet 网络命名空间运行节点（hosts）
- 每个 host 上运行一个 NFD 实例，管理 socket 建议放在 `/run/nfd/<name>.sock`
- 客户端二进制：`client/bin/ndnclient`（以 host 的命名空间中运行）
- 日志位置：`/tmp/ndn/` 下的 `*-nfd.log`, `*-faces.log`, 各 client 的 `*.log`

---

## 快速复现与检查流程（按顺序）
1. 启动 Mininet 拓扑（例如 `manual.py` 或 `ndn-simulator.py`）：
   - 用 sudo: `sudo python3 manual.py` 或 `sudo python3 ndn-simulator.py`
2. 在 Mininet CLI 中先检查 L2/L3：
   - `nodes` / `links`
   - 对每个节点检查接口和地址：`<host> ip addr show`
   - 检查 ARP：`<host> arp -n`
   - 用 ping 验证链路（逐对点）：`<host> ping <peer-IP>`
3. 确认 NFD 启动并 socket 存在：
   - 宿主机：`sudo ls -l /run/nfd` 或 `ss -xl | grep nfd`
   - 在节点命名空间检查：`<host> bash -c 'ls -l /run/nfd || true'`
4. 检查 NFD 日志：`tail -n 200 /tmp/ndn/<host>-nfd.log`
5. 检查 NFD 的 face/route/fib：
   - `export NDN_CLIENT_TRANSPORT="unix:///run/nfd/<name>.sock"`
   - `nfdc face list`
   - `nfdc route list`
   - `nfdc fib list`
6. 若 NFD 上没有对应 udp4:// face：先合并在 host 内执行 face create，再 add route：
   - `export NDN_CLIENT_TRANSPORT="unix:///run/nfd/<name>.sock"; nfdc face create udp4://<peer-ip>:6363; nfdc route add /proX udp4://<peer-ip>:6363`
7. 验证 ndnclient：在 host 内启动并查看 `/tmp/ndn/*.log`，并观察 producer 是否写出 `pro<ID>.ok`，consumer 是否触发并写出对应日志。

---

## 常用诊断命令（拷贝运行）
- 列出 unix sockets（宿主）：
```
sudo ss -xl | grep nfd
```
- 查看 nfd 日志（某 host）:
```
tail -n 200 /tmp/ndn/<host>-nfd.log
```
- 导出 face/route/fib 快照（在节点命名空间）：
```
export NDN_CLIENT_TRANSPORT="unix:///run/nfd/<host>.sock"
nfdc face list > /tmp/ndn/<host>-faces.log
nfdc route list > /tmp/ndn/<host>-routes.log
nfdc fib list > /tmp/ndn/<host>-fib.log
```
- 检查接口/ARP/路由（在 Mininet CLI）:
```
<host> ip addr show
<host> arp -n
<host> ip route show
```
- 抓包（在 host 命名空间）:
```
<host> tcpdump -n -i <if> udp port 6363 or icmp
```

---

## 命令输出如何解读（快速参考）
下面按命令分条说明如何阅读输出、常见异常和快速定位方法。

- `nfdc face list`
   - 作用：列出 NFD 中的 face（传输通道）。
   - 重点看：`remote` / `local` 字段（确认是 `udp4://`/`tcp://` 还是 `fd://`/`unix://`），`counters`（in/out 流量），`flags`（local/permanent/on-demand）。
   - 快速判断：
      - 出现 `udp4://<peer>:6363` 表示存在到远端的网络 face；若只有 `fd://`/`unix://`，说明只是管理/短连接，不是网络面。
      - counters 持续增长说明 face 在传输数据；全为 0 说明没有流量。
   - 常见问题：创建后很快看到 `CLOSING`/`CLOSED`，通常是短期管理连接（nfdc）产生的 fd:// face 或 NFD 在重载 face section。

- `nfdc route list`
   - 作用：显示 FIB（路由）条目。每条记录包含 `prefix`、`nexthop`、`origin` 等。
   - 快速判断：
      - 若缺少目标前缀（如 `/pro0`），NDN 会报 `NoRoute`。
      - 若 route 存在但 `nexthop` 指向的网络 face 不存在或不可达，Interest 无法发出。

- `ip addr show`
   - 作用：查看本机接口与 IP/掩码。
   - 快速判断：
      - 检查每个链路接口是否有正确的 IP 与子网掩码（点对点建议 `/30` 或 `/31`）。
      - 如果同一主机的多个接口位于同一大网段（如 `/8`），会引起 ARP 与路由混乱，应改为每链路独立子网。

- `arp -n`
   - 作用：查看 ARP 缓存（IP → MAC）。
   - 快速判断：
      - 有 MAC 地址则 L2 可达；若显示 `incomplete`，说明 ARP 请求没有收到回应，通常是接口/子网不匹配或对端未 up。

- `ip route show`
   - 作用：显示内核的 IP 路由表。
   - 快速判断：
      - 确认目标网络为直连（`dev <iface>`）或有合适的下一跳；点对点测试应看到对应的 `/30` 直连路由条目。

综合排查建议：先用 `ip addr show`/`arp -n`/`ip route show` 确保 L2/L3 正常，再检查 `nfdc face list` 与 `nfdc route list`；如果 face 缺失，合并在 host 内一次性执行 `nfdc face create` 再 `nfdc route add`，等待 face 出现并稳定后再启动应用。

---

## 已知问题汇总（本项目调试过程中发现）
1. 接口 IP/掩码配置不正确
   - 早期脚本把多个接口置于同一大网段（如 `/8`），导致 ARP 冲突或 `incomplete` 条目。结果：某些链路 L2/L3 不通，导致对应 NFD face 无法建立。
   - 修复：为每条点对点链路分配独立的 `/30`，并在 `net.start()` 之后 `ip addr flush dev <if>` -> `ip addr add <ip>/30 dev <if>` -> `ip link set <if> up`。

2. NFD 配置文件包含本地二进制不支持的 section（validators、authorizations 等）
   - 结果：nfd 启动失败或报错 `unknown directive` / `no module subscribed`。
   - 修复：使用最小兼容配置，或确保 nfd 二进制包含对应模块；建议使用 `validators { null { } }`（若二进制支持）或直接移除这些 sections。

3. nfdc 管理连接造成短寿命 fd:// face churn
   - 每次单独运行 `nfdc` 命令会建立短期的管理连接（fd://），命令结束即断开，日志可见大量 create -> CLOSING -> CLOSED。
   - 频繁短连接会触发 `Network change detected` 并 reload face section，导致后续 face/route 创建失败。
   - 修复：将多条 nfdc 命令合并为一次在同一 shell 内运行，或使用脚本在 host 内批量运行并等待 face 稳定。

4. face/route 创建的时序问题（race）
   - 在 face 未处于 UP 时就 add route 或启动应用，route 可能不生效或在 reload 后丢失。
   - 修复：创建 face 后轮询 `nfdc face list`，确认 `udp4://...` 存在并稳定后再 `nfdc route add`，再启动应用。

5. Producer/Consumer 同步信号不一致
   - Consumer 等待 `all.ok` 而 producer 只写 `pro<ID>.ok`，导致 consumer 超时或未开始，影响测试流程。
   - 修复：在 producer 写 `pro<ID>.ok` 后同时写 `/tmp/ndn/all.ok`（或让 consumer 等待一组 `pro*.ok`）。

---

## 推荐修复清单（优先级）
1. 在 `ndn-simulator.py` / `manual.py` 中，把每条链路配置为 `/30` 并在 `net.start()` 后设置接口地址（flush -> add -> up）。
2. 让 NFD 配置 conservative：`udp.mcast = no`，移除或使用 `null` validator，增加 `udp.idle_timeout`。
3. 合并并序列化 `nfdc` 操作：先 `face create`（批量），轮询 face list，再 `route add`，最后启动客户端。对每个 host 使用一次 shell 执行多条 nfdc，减少短连接。 
4. 在脚本里增加日志导出：重定向 nfd 到 `/tmp/ndn/<host>-nfd.log`，并周期性写 `nfdc face/route/fib` 到文件。
5. 统一 producer/consumer 的就绪信号（`pro<ID>.ok` + `all.ok` 或 consumers 检测所有 pro*.ok）。

---

## 快速复查示例（整体顺序）
1. net.start()
2. 为 link 接口配置 /30 地址并 `ip link set up`（验证 ping 成功）
3. 启动所有 NFD，等待 unix sockets
4. 在每个 host 内批量执行：
   ```bash
   export NDN_CLIENT_TRANSPORT="unix:///run/nfd/<host>.sock"; \
   nfdc face create udp4://<peer1>:6363; nfdc face create udp4://<peer2>:6363; \
   nfdc route add /proX udp4://<peer1>:6363; nfdc route add /proY udp4://<peer2>:6363
   ```
5. 轮询 `nfdc face list`，等待 udp4 faces UP
6. 启动 producers，等待 `pro*.ok` → 写 `all.ok`
7. 启动 consumers → 验证 `/tmp/ndn/*.log` 与 `nfdc face|route` 的流量计数

---

## 附：常见命令片段
- 清理旧进程/文件：
```
sudo pkill -f nfd || true
sudo pkill -f ndnclient || true
sudo rm -rf /tmp/ndn/* /run/nfd/*
```
- 在脚本内等待 socket 出现（示例）：
```
deadline=$((SECONDS+10))
while [ $SECONDS -lt $deadline ]; do
  [ -S /run/nfd/client0.sock ] && break
  sleep 0.2
done
```

---

如果你愿意，我可以：
- 把上面的最佳实践直接应用为 `ndn-simulator.py` 的补丁（自动实现 /30 配置、合并 nfdc、等待 face/up 并导出日志）；或
- 只生成一个更详细的 `README-debug.md` 包含 exact commands 用于 CI/自动化测试。 

请选择下一步（我可以直接修改文件并运行快速检查）。

---

## 常见失败示例（命令 → 失败结果 → 成因 → 修复）

下面收集若干在构建 Mininet + NFD 实验网络时经常遇到的失败例子。每条包含：执行的命令／操作、典型的失败输出、根因分析和可行的修复办法。

### 示例 1 — 错误的 Mininet API 参数导致 TypeError
命令/操作：在脚本中用错误参数调用 addIntf

```bash
# 错误示例（会触发 TypeError）
node.addIntf(intf=someIntf, inf='h1-eth0')
```

失败输出（典型）：

```
TypeError: addIntf() got an unexpected keyword argument 'inf'
```

成因：使用了不存在或拼写错误的关键字参数；Mininet 的 API 要求不同的参数签名。

修复：使用正确的 API；通常用 `net.addLink(h1, h2)` 创建链路，或者在需要时传入正确的参数名，例如 `setIP('10.0.0.1/30', intf='h1-eth0')`。把接口/IP 的设置放在 `net.start()` 之后以避免被覆盖。

---

### 示例 2 — 把多条链路放到同一子网导致 ARP/路由冲突（pingall 丢包）
命令/操作：给主机的多个接口分配同一网络（例如都用 10.0.0.0/8）

```bash
# 不要这样：多个接口都在 10.0.0.0/8
h1.setIP('10.0.0.1/8', intf='h1-eth0')
h1.setIP('10.0.0.2/8', intf='h1-eth1')
```

失败输出（典型）：

```
*** Ping: testing ping reachability
h1 -> h2: x% dropped
*** Results: 100% dropped
```

成因：主机内的多个接口处于同一 L3 子网时，内核在做 ARP/出接口选择时会混淆（选择错误的网卡发送 ARP/数据包），导致 ARP 表和流量走向错误。

修复：把每条点对点链路放在独立子网（推荐 /30 或 /31），或者在主机上配置策略路由；常见做法是在 `net.start()` 后为每个链路分配 /30 地址并确保各接口属于不同网段。

示例正确做法：

```bash
# 为每对点对点链路使用 /30
h1.setIP('10.0.1.1/30', intf='h1-eth0')
h2.setIP('10.0.1.2/30', intf='h2-eth0')
```

---

### 示例 3 — 启动 NFD 时遇到配置文件中未知/不支持的指令，NFD 退出
命令/操作：使用包含未编译进二进制的模块或新语法的 `nfd.conf`

```bash
# 启动 NFD（示意）
nfd --config /tmp/nfd.conf
```

失败输出（典型）：

```
nfd: error: unknown directive 'validators'
nfd: fatal: configuration parse error
```

成因：`nfd.conf` 中使用了当前 NFD 二进制不支持的配置项（例如某些 validator、plugin、或编译选项缺失）。不同发行版/版本的 NFD 支持的 conf 语法可能不同。

修复：生成或使用与本地 NFD 版本兼容的最小配置文件；移除不支持的段，或在编译/安装时启用需要的模块。调试方法：逐步注释配置段并重启，或查看 nfd 的错误日志以定位不支持的指令。

---

### 示例 4 — 在脚本中频繁运行 `nfdc` 导致大量短生命周期的管理连接（出现许多 fd:// faces，NFD 不稳定）
命令/操作：对每个对等点单独在循环里调用 `nfdc face create`，并且每次都创建新的控制连接

```bash
# 脚本中对每个 peer 都单独调用 nfdc（示意）
for peer in $peers; do
  nfdc face create udp4://$peer
done
```

失败输出（典型）：

```
# 在 nfdc face list 中可以看到很多 fd://... 条目
FaceId: 12
  RemoteURI: fd://12345
  ...
nfd log: incoming connection from manager fd 12345
nfd log: closed connection fd 12345
```

成因：每次调用 `nfdc`（或其它管理客户端）都会建立一个短连接到 nfd 的管理接口，nfd 记录为 fd:// face。大量短连接会产生“面/描述符”抖动，影响稳定性。

修复：
- 在每台主机里用一次性 shell 批量执行多条 nfdc 命令，减少建立/关闭管理连接的次数；
- 或者用支持复用连接的控制工具/API；
- 给 nfd 足够的时间处理 face 建立，并在脚本中加入小的延迟和重试逻辑。

示例（批量）：

```bash
# 在 host 的命名空间中运行一次 shell，里面执行多条 nfdc
ip netns exec ns-host bash -c "nfdc face create udp4://10.0.1.2 && nfdc route add /prefix udp4://10.0.1.2"
```

---

### 示例 5 — 先添加路由再确保 face 已就绪，出现 NoRoute
命令/操作：脚本先执行 `nfdc route add`，但对端 face 尚未处于 UP 状态

```bash
nfdc route add /example udp4://10.0.2.2
# 立即启动 consumer
./consumer --fetch /example
```

失败输出（典型）：

```
Consumer: Interest dropped: NoRoute
```

成因：虽然 FIB 中有条目，但对应的 face 还在建立中或处于 DOWN/可疑状态，NFD 无法把 Interest 发到目标。

修复：在添加路由前，先创建 face 并轮询 `nfdc face list`，确认 RemoteURI 对应的 face 处于 UP，再执行 `nfdc route add`。

示例轮询（伪代码）：

```bash
# 等待 face 出现在列表并且状态为 UP（超时后报错）
until nfdc face list | grep 'udp4://10.0.2.2'; do sleep 0.2; done
nfdc route add /example udp4://10.0.2.2
```

---

### 示例 6 — 试图连接不存在的 NFD UNIX socket（socket 文件缺失或路径错误）
命令/操作：客户端或 nfdc 指定了不正确的 manager socket

```bash
export NFD_MANAGER="unix:///run/nfd/hostA.sock"
nfdc status
```

失败输出（典型）：

```
Failed to connect to manager: No such file or directory
```

成因：NFD 还没启动、未创建 socket，或者启动时使用了不同路径，权限不足也会导致连接失败。

修复：确保在目标命名空间中以正确参数启动 NFD（例如 `nfd --manager unix:/run/nfd/hostA.sock`），确认 `/run/nfd` 存在并有合适权限，脚本启动顺序应先 `start nfd` 再执行 nfdc 或客户端连接。

---

### 示例 7 — 生产者/消费者同步信号不一致，消费者永远等待
命令/操作：消费者脚本等待 `all.ok`，生产者只写 `pro<ID>.ok`

```bash
# consumer.sh 等待 all.ok
while [ ! -f all.ok ]; do sleep 0.5; done
# producers 只写 pro1.ok, pro2.ok
```

失败输出（典型）：

```
# consumer 一直阻塞在等待阶段，后续没有请求发送
```

成因：用于同步的就绪文件名称在生产者和消费者间不一致，导致消费者永远等待。

修复：采用一致的就绪协议：要么让每个生产者在就绪时也写一个全局 `all.ok`，要么修改消费者逻辑为当检测到任意 `pro*.ok` 时继续，或者使用更可靠的同步手段（socket/管道/systemd socket/简单 HTTP 健康检查）。

---

### 示例 8 — 单台主机上接口属于混合子网（一个 /8 与另一个 /30），导致路由/ARP 问题
命令/操作：在 Mininet prompt 中查看某主机（如 `pro0`）的接口信息

```text
mininet> pro0 ip addr show
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: pro0-eth0@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc htb state UP group default qlen 1000
    link/ether 1e:58:c4:31:df:0f brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 10.0.0.1/8 brd 10.255.255.255 scope global pro0-eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::1c58:c4ff:fe31:df0f/64 scope link 
       valid_lft forever preferred_lft forever
3: pro0-eth1@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc htb state UP group default qlen 1000
    link/ether 76:06:2f:0f:39:ed brd ff:ff:ff:ff:ff:ff link-netnsid 1
    inet 10.2.0.2/30 scope global pro0-eth1
       valid_lft forever preferred_lft forever
```

问题描述：`pro0` 的两个物理/虚拟接口分别在不同的子网，其中 `pro0-eth0` 被错误配置为一个宽松的 `/8`（10.0.0.1/8），而 `pro0-eth1` 在一个点对点的 `/30`（10.2.0.2/30）。这种不一致会引起本机内核在出接口选择、ARP 请求和源地址选择时发生冲突或混淆，表现为无法到达邻居、ping 丢包或流量走到错误的接口。

诊断要点：
- 用 `ip addr show` 确认每个接口的地址与掩码。注意是否有过宽的网段（/8, /16）覆盖了其他点对点子网。 
- 用 `ip route` / `ip route show table main` 检查路由表，确认内核如何选择出接口。 
- 用 `arp -n` 或 `ip neigh` 检查 ARP/邻居表是否在对应接口上学习到正确 MAC。 
- 检查 `rp_filter`（反向路径过滤）设置：`sysctl net.ipv4.conf.all.rp_filter` 及每个接口的 `net.ipv4.conf.<if>.rp_filter`，若启用且路由混乱，会导致丢包。

快速修复步骤（在 Mininet 命名空间内执行）：

```bash
# 进入 pro0 命名空间（在 Mininet 提示或外部 shell 中）
mininet> pro0 bash
# 或者：ip netns exec <pro0-namespace> bash

# 查看当前路由与邻居
ip addr show
ip route show
ip neigh show

# 把错误的 /8 地址移除并按点对点 /30 重新添加
sudo ip addr flush dev pro0-eth0
sudo ip addr add 10.0.1.1/30 dev pro0-eth0
# 确保另一端对应接口也在相同 /30 网段（在对应主机上执行）

# 可选：临时关闭 rp_filter（测试用）
sudo sysctl -w net.ipv4.conf.all.rp_filter=0
sudo sysctl -w net.ipv4.conf.default.rp_filter=0
sudo sysctl -w net.ipv4.conf.pro0-eth0.rp_filter=0
sudo sysctl -w net.ipv4.conf.pro0-eth1.rp_filter=0

# 重新检查
ip addr show
ip route show
ping -c 3 <peer-address>
```

长期建议：
- 在 Mininet 拓扑脚本中，避免把不同链路分配到同一个大网段；为每条点对点链路使用 /30 或 /31。将所有接口/IP 的设置放在 `net.start()` 之后执行，或使用 `link.intf1.config(ip=...)` 风格的 API，确保不会被 Mininet 覆盖。 
- 若必须在同一主机上保留多个同网段接口，考虑使用策略路由（`ip rule` + `ip route`）或明确设置源地址策略；但这通常超出简单实验的复杂度，应尽量避免。

调试时的快速检查清单：
- `ip addr` 是否有过宽网段（/8、/16）覆盖其它接口？
- `ip route` 是否把流量路由到了错误的接口？
- `ip neigh`/`arp -n` 是否在正确的接口上有对应的 MAC？
- `rp_filter` 是否阻止了正常的流量？

以上案例已写入本文件，便于复现与教学。

以下是正常运行的结果
```text
mininet> pro0 ip addr show
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: pro0-eth0@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc htb state UP group default qlen 1000
    link/ether 56:e2:bb:c5:7f:4d brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 10.1.0.2/30 scope global pro0-eth0
       valid_lft forever preferred_lft forever
3: pro0-eth1@if2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc htb state UP group default qlen 1000
    link/ether 32:a4:b2:9c:73:7d brd ff:ff:ff:ff:ff:ff link-netnsid 1
    inet 10.2.0.2/30 scope global pro0-eth1
       valid_lft forever preferred_lft forever
```

---

### 示例 9 — ARP 表显示 (incomplete)（10.1.0.2 (incomplete) on con1to0-eth0）
命令/操作：在 Mininet 提示下运行 ARP 查看

```text
mininet> con1to0 arp -n
Address                  HWtype  HWaddress           Flags Mask            Iface
10.1.0.2                         (incomplete)                              con1to0-eth0
10.0.0.1                 ether   ee:76:c2:34:59:d8   C                     con1to0-eth0
```

问题描述：某个邻居地址（10.1.0.2）显示为 `(incomplete)`，说明本机尝试做 ARP 解析但尚未收到对方的 ARP 回复，或者 ARP 请求被过滤/发送到了错误的接口。

常见成因：
- 对端没有在同一子网（IP/掩码不匹配），因此不会响应 ARP；
- 本机发出 ARP 请求但因为接口绑定/路由选择错误而走到了错误的物理接口；
- 对端命名空间/接口未启用或链路没有正确连接；
- 防火墙或 netfilter/rp_filter 拦截了 ARP/ICMP 流量（较少见）。

诊断步骤：
- `ip addr show` 检查本机和对端接口 IP 与掩码；
- 在对端执行 `ip addr`/`ip link` 确认接口存在且 UP；
- 从本机用 `arping -I <iface> <peer-IP>` 强制在指定接口发送 ARP 请求；
- 检查交换/链接两端的链路状态（`ip link`, `ethtool`）、以及 Mininet 是否把正确接口连接到期望的对端；
- 临时关闭 rp_filter 以排除路径过滤问题：`sysctl net.ipv4.conf.<if>.rp_filter=0`。

修复建议：
- 确保两端接口在同一点对点子网（/30 或 /31）；
- 如果发现 IP 在不同网段，重新 `ip addr flush` 并按 /30 重新设置；
- 在脚本中把 IP 配置放在 `net.start()` 后，避免被 Mininet 覆盖；
- 如果使用命名空间外工具操作接口，注意用 `ip netns exec` 在正确命名空间内运行。

以下是正常运行应有的结果：
```text
mininet> con1to0 arp -n
Address                  HWtype  HWaddress           Flags Mask            Iface
10.1.0.2                 ether   56:e2:bb:c5:7f:4d   C                     con1to0-eth0
```

---

### 示例 10 — `nfdc face list` 中出现 UDP face 且本地/远端地址不一致或为不同子网（提示源地址选择问题）
命令/操作：在 `pro0` 命名空间用 `NFD_CLIENT_TRANSPORT` 指向本地 unix socket，然后列出 face

```text
mininet> pro0 NDN_CLIENT_TRANSPORT=unix:///run/nfd/pro0.sock nfdc face list
...
faceid=258 remote=udp4://10.1.0.1:6363 local=udp4://10.0.0.1:6363 expires=96s ... flags={non-local on-demand point-to-point}
...
```

问题描述：看到一个 UDP face，其 `remote=10.1.0.1` 而 `local=10.0.0.1`。如果本机实际应该和 `10.2.0.x` 网段通信，这说明 NFD 在建立 UDP face 时使用了错误的本地源地址（源地址选择来自内核路由/接口配置），从而导致对端把回复发向不同地址或创建了意外的 fd:// face 映射。

常见成因：
- 本机有多个接口且 IP/路由配置不当（比如有 /8 覆盖），内核选择了错误的源地址；
- 在非目标命名空间中执行 nfdc（或用错误的环境变量/manager socket），导致 face 创建命名空间/源地址不匹配；
- 对端收到带有非预期源地址的数据后，会对该地址建立临时 face（fd:// 或新 UDP face），造成双向不对称。

诊断步骤：
- 在本机和对端都运行 `ip addr` 与 `ip route`，确认用于这条 UDP face 的源/目的 IP 是同一链路的两个地址；
- 检查 `nfd` 日志和 face counters（`nfdc face list` 的 counters 部分）看是否有丢包/拒绝；
- 用 `tcpdump -n -i <iface> udp port 6363`（在对应命名空间内）观察实际发送的源 IP 和目的 IP；
- 确认 `nfdc` 的上下文是在正确的命名空间（`mininet> pro0 ...` 或 `ip netns exec ...`）。

修复建议：
- 修正接口 IP 并确保 routing/source selection 正确（移除不必要的大网段，如 /8）；
- 在目标命名空间中创建 face，使得内核从正确接口选择源地址；例如：
  - `ip netns exec pro0 nfdc face create udp4://10.2.0.2`（在 pro0 命名空间里用对端正确的地址创建 face）；
- 可指定本地绑定（部分实现/工具支持）或通过临时路由规则确保从期望接口发出数据；
- 批量创建 face 并在添加 route 前等待 face 成为 UP，避免路由/face 的时序错位。

正确结果:
```text
mininet> pro0 NDN_CLIENT_TRANSPORT=unix:///run/nfd/pro0.sock nfdc face list
faceid=1 remote=internal:// local=internal:// congestion={base-marking-interval=100ms default-threshold=65536B} mtu=8800 counters={in={0i 15d 0n 6630B} out={42i 0d 0n 3074B}} flags={local permanent point-to-point local-fields}
faceid=254 remote=contentstore:// local=contentstore:// mtu=8800 counters={in={0i 0d 0n 0B} out={0i 0d 0n 0B}} flags={local permanent point-to-point}
faceid=255 remote=null:// local=null:// mtu=8800 counters={in={0i 0d 0n 0B} out={0i 0d 0n 0B}} flags={local permanent point-to-point}
faceid=256 remote=fd://22 local=unix:///run/nfd/pro0.sock congestion={base-marking-interval=100ms default-threshold=65536B} mtu=8800 counters={in={41i 1d 0n 2861B} out={1i 14d 0n 6630B}} flags={local on-demand point-to-point local-fields congestion-marking}
faceid=257 remote=fd://23 local=unix:///run/nfd/pro0.sock congestion={base-marking-interval=100ms default-threshold=65536B} mtu=8800 counters={in={1i 2d 0n 12870B} out={2i 1d 0n 330B}} flags={local on-demand point-to-point congestion-marking}
faceid=260 remote=fd://24 local=unix:///run/nfd/pro0.sock congestion={base-marking-interval=100ms default-threshold=65536B} mtu=8800 counters={in={1i 0d 0n 43B} out={0i 0d 0n 0B}} flags={local on-demand point-to-point congestion-marking}
```
---

### 示例 11 — 路由表中有过宽路由（10.0.0.0/8 dev con2to0-eth0 src 10.2.0.1），导致子网遮蔽与错误源地址选择
命令/操作：在 `con2to0` 上查看路由表

```text
mininet> con2to0 ip route show
10.0.0.0/8 dev con2to0-eth0 proto kernel scope link src 10.2.0.1
```

问题描述：路由表包含 `10.0.0.0/8`，这会匹配大量 10.x.x.x 地址空间，覆盖原本应属于其他点对点子网的路由，从而让内核把发往小网段的流量错误地走到 `con2to0-eth0`，并把源地址选择为该接口的 `10.2.0.1`。

成因：在配置地址时误用了大掩码（/8、/16 等），或脚本在多处给同一主机的不同接口分配了重叠子网地址。

诊断与修复：
- 使用 `ip addr` 找出哪些接口有重叠的 10.0.0.0 网段；
- 对出问题的接口执行 `ip addr flush dev <if>`（移除所有链路），然后按点对点 /30 重建；

示例修复命令：

```bash
# 在 con2to0 命名空间内
ip addr flush dev con2to0-eth0
ip addr add 10.2.0.1/30 dev con2to0-eth0
# 确认其它主机的对应接口属于同一 /30
```

后续建议：在 Topology 脚本中生成地址时避免使用单一大网段覆盖所有链路；为每条链路分配独立的 /30，或使用地址池按链路索引分配。这样可以避免内核路由/ARP 的歧义和 NFD UDP face 使用错误源地址的问题。

正确结果：
```text
mininet> con2to0 ip route show
10.2.0.0/30 dev con2to0-eth0 proto kernel scope link src 10.2.0.1
```
---

以上三例已追加到本文件，包含诊断命令与可即时执行的修复步骤，便于在实际 Mininet + NFD 实验中快速定位与修复子网/ARP 与 NFD face 相关的问题。
