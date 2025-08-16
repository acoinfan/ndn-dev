#!/bin/bash

# 手动NDN网络搭建脚本

echo "=== 手动搭建NDN网络 ==="

# 清理之前的设置
cleanup() {
    echo "清理网络命名空间..."
    sudo ip netns delete client0 2>/dev/null || true
    sudo ip netns delete client1 2>/dev/null || true
    sudo ip netns delete client2 2>/dev/null || true
    sudo pkill -f nfd
    sudo rm -rf /tmp/ndn/*
}

# 创建网络拓扑
setup_network() {
    echo "1. 创建网络命名空间..."
    sudo ip netns add client0
    sudo ip netns add client1  
    sudo ip netns add client2

    echo "2. 创建veth对..."
    # client0 <-> client1
    sudo ip link add veth0-1 type veth peer name veth1-0
    sudo ip link set veth0-1 netns client0
    sudo ip link set veth1-0 netns client1

    # client1 <-> client2
    sudo ip link add veth1-2 type veth peer name veth2-1
    sudo ip link set veth1-2 netns client1
    sudo ip link set veth2-1 netns client2

    # client2 <-> client0
    sudo ip link add veth2-0 type veth peer name veth0-2
    sudo ip link set veth2-0 netns client2
    sudo ip link set veth0-2 netns client0

    echo "3. 配置IP地址..."
    # client0
    sudo ip netns exec client0 ip addr add 10.0.1.1/24 dev veth0-1
    sudo ip netns exec client0 ip addr add 10.0.3.1/24 dev veth0-2
    sudo ip netns exec client0 ip link set veth0-1 up
    sudo ip netns exec client0 ip link set veth0-2 up
    sudo ip netns exec client0 ip link set lo up

    # client1
    sudo ip netns exec client1 ip addr add 10.0.1.2/24 dev veth1-0
    sudo ip netns exec client1 ip addr add 10.0.2.1/24 dev veth1-2
    sudo ip netns exec client1 ip link set veth1-0 up
    sudo ip netns exec client1 ip link set veth1-2 up
    sudo ip netns exec client1 ip link set lo up

    # client2
    sudo ip netns exec client2 ip addr add 10.0.2.2/24 dev veth2-1
    sudo ip netns exec client2 ip addr add 10.0.3.2/24 dev veth2-0
    sudo ip netns exec client2 ip link set veth2-1 up
    sudo ip netns exec client2 ip link set veth2-0 up
    sudo ip netns exec client2 ip link set lo up

    echo "4. 配置路由..."
    # client0路由
    sudo ip netns exec client0 ip route add 10.0.2.0/24 via 10.0.1.2 dev veth0-1
    
    # client1路由  
    sudo ip netns exec client1 ip route add 10.0.3.0/24 via 10.0.2.2 dev veth1-2
    
    # client2路由
    sudo ip netns exec client2 ip route add 10.0.1.0/24 via 10.0.3.1 dev veth2-0

    echo "网络拓扑创建完成"
}

# 启动NFD实例
start_nfd() {
    echo "5. 启动NFD实例..."
    
    # 为每个namespace创建NFD配置
    for i in {0..2}; do
        mkdir -p /tmp/ndn/client$i
        
        echo "启动client$i NFD..."
        # 检查NFD是否已存在
        if sudo ip netns exec client$i pgrep nfd > /dev/null 2>&1; then
            echo "NFD已在client$i中运行，强制重启..."
            sudo ip netns exec client$i pkill nfd 2>/dev/null || true
            sleep 2
        fi
        
        # 创建简单的配置文件
        cat > /tmp/ndn/client$i/nfd.conf << EOF
face_system
{
  unix
  {
    path /tmp/ndn/client$i/nfd.sock
  }
  tcp
  {
    listen yes
    port 6363
    enable_v4 yes
    enable_v6 no
  }
  udp
  {
    port 6363
    enable_v4 yes
    enable_v6 no
    mcast no
  }
}
rib
{
  localhost_security
  {
    trust-anchor
    {
      type any
    }
  }
}
authorizations
{
  authorize
  {
    certfile any
    privileges
    {
      faces
      fib
      cs
      strategy-choice
    }
  }
}
EOF
        
        # 启动NFD
        echo "启动NFD进程..."
        sudo ip netns exec client$i bash -c "
            mkdir -p /var/lib/ndn/nfd
            mkdir -p /var/log/ndn
            nfd --config /tmp/ndn/client$i/nfd.conf > /tmp/ndn/client$i/nfd.log 2>&1 &
        "
        sleep 3
            
            # 等待socket文件出现
            echo "等待client$i socket文件创建..."
            timeout=30
            while [ $timeout -gt 0 ]; do
                if [ -S "/tmp/ndn/client$i/nfd.sock" ]; then
                    echo "client$i socket文件已创建"
                    break
                fi
                sleep 1
                timeout=$((timeout-1))
            done
            
            if [ $timeout -eq 0 ]; then
                echo "错误: client$i socket文件创建超时"
                echo "检查NFD日志:"
                cat /tmp/ndn/client$i/nfd.log
                
                # 尝试用默认配置启动
                echo "尝试使用默认配置启动NFD..."
                sudo ip netns exec client$i pkill nfd 2>/dev/null || true
                sleep 2
                
                # 使用最小配置
                cat > /tmp/ndn/client$i/nfd-minimal.conf << EOF
face_system
{
  unix
  {
    path /tmp/ndn/client$i/nfd.sock
  }
  tcp
  {
    listen yes
    port 6363
    enable_v4 yes
    enable_v6 no
  }
  udp
  {
    port 6363
    enable_v4 yes
    enable_v6 no
    mcast no
  }
}
EOF
                
                sudo ip netns exec client$i nfd --config /tmp/ndn/client$i/nfd-minimal.conf > /tmp/ndn/client$i/nfd-minimal.log 2>&1 &
                sleep 5
                
                if [ ! -S "/tmp/ndn/client$i/nfd.sock" ]; then
                    echo "最小配置也失败，显示日志:"
                    cat /tmp/ndn/client$i/nfd-minimal.log
                    return 1
                else
                    echo "使用最小配置成功启动client$i"
                fi
            fi
        fi
    done
    
    echo "等待所有NFD实例稳定..."
    sleep 5
}

# 设置NDN路由
setup_ndn_routing() {
    echo "6. 设置NDN路由..."
    
    # 验证socket文件存在
    for i in {0..2}; do
        if [ ! -S "/tmp/ndn/client$i/nfd.sock" ]; then
            echo "错误: /tmp/ndn/client$i/nfd.sock 不存在"
            return 1
        fi
    done
    
    # client0的路由设置
    echo "设置client0路由..."
    sudo ip netns exec client0 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client0/nfd.sock'
        echo '创建face到client1...'
        nfdc face create udp4://10.0.1.2:6363
        echo '创建face到client2...'
        nfdc face create udp4://10.0.3.2:6363
        echo '添加路由到/pro1...'
        nfdc route add /pro1 udp4://10.0.1.2:6363
        echo '添加路由到/pro2...'
        nfdc route add /pro2 udp4://10.0.3.2:6363
    "
    
    # client1的路由设置  
    echo "设置client1路由..."
    sudo ip netns exec client1 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client1/nfd.sock'
        nfdc face create udp4://10.0.1.1:6363
        nfdc face create udp4://10.0.2.2:6363
        nfdc route add /pro0 udp4://10.0.1.1:6363
        nfdc route add /pro2 udp4://10.0.2.2:6363
    "
    
    # client2的路由设置
    echo "设置client2路由..."
    sudo ip netns exec client2 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client2/nfd.sock'
        nfdc face create udp4://10.0.2.1:6363
        nfdc face create udp4://10.0.3.1:6363
        nfdc route add /pro0 udp4://10.0.3.1:6363
        nfdc route add /pro1 udp4://10.0.2.1:6363
    "
    
    echo "NDN路由设置完成"
}

# 测试基础NDN功能
test_basic_ndn() {
    echo "测试基础NDN功能..."
    
    # 在client1上启动一个简单的producer
    echo "在client1上启动producer..."
    sudo ip netns exec client1 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client1/nfd.sock'
        echo 'Hello from client1' | ndnpoke /pro1/test &
    " &
    
    sleep 2
    
    # 在client0上测试consumer
    echo "在client0上测试consumer..."
    result=$(sudo ip netns exec client0 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client0/nfd.sock'
        timeout 5 ndnpeek /pro1/test 2>/dev/null || echo 'TIMEOUT'
    ")
    
    if [ "$result" != "TIMEOUT" ] && [ -n "$result" ]; then
        echo "基础NDN测试成功: $result"
        return 0
    else
        echo "基础NDN测试失败: $result"
        return 1
    fi
}

# 启动客户端应用
start_clients() {
    echo "7. 启动客户端应用..."
    
    # 创建测试文件
    for i in {0..2}; do
        mkdir -p /tmp/ndn/client$i/files
        echo "Hello from client$i - test content" > /tmp/ndn/client$i/files/test.txt
        
        # 创建一个配置文件（如果不存在）
        if [ ! -f "/home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini" ]; then
            mkdir -p /home/a_coin_fan/code/ndn-dev
            cat > /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini << EOF
[DEFAULT]
pipeline_type = aimd
save_file = true
verbose = true
EOF
        fi
    done
    
    # 检查客户端程序是否存在
    if [ ! -f "/home/a_coin_fan/code/ndn-dev/client/bin/ndnclient" ]; then
        echo "警告: ndnclient程序不存在，只运行基础测试"
        return 0
    fi
    
    # 启动客户端应用
    for i in {0..2}; do
        echo "启动client$i应用..."
        
        sudo ip netns exec client$i bash -c "
            export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client$i/nfd.sock'
            cd /home/a_coin_fan/code/ndn-dev/client
            ./bin/ndnclient \
                --directory /tmp/ndn/client$i/files \
                --filename test.txt \
                --id $i \
                --nodes 3 \
                --config /home/a_coin_fan/code/ndn-dev/exp-clientconfig.ini \
                > /tmp/ndn/client$i/app.log 2>&1 &
        "
        sleep 2
    done
    
    echo "所有客户端应用已启动"
}

# 测试连接
test_connectivity() {
    echo "8. 测试连接..."
    
    echo "网络连通性测试:"
    for i in {0..2}; do
        for j in {0..2}; do
            if [ $i -ne $j ]; then
                case $i$j in
                    "01") target_ip="10.0.1.2" ;;
                    "02") target_ip="10.0.3.2" ;;
                    "10") target_ip="10.0.1.1" ;;
                    "12") target_ip="10.0.2.2" ;;
                    "20") target_ip="10.0.3.1" ;;
                    "21") target_ip="10.0.2.1" ;;
                esac
                result=$(sudo ip netns exec client$i ping -c 1 -W 1 $target_ip 2>/dev/null | grep "1 received" || echo "FAIL")
                echo "client$i -> client$j ($target_ip): $result"
            fi
        done
    done
    
    echo ""
    echo "NFD状态检查:"
    for i in {0..2}; do
        echo "--- client$i ---"
        sudo ip netns exec client$i bash -c "
            export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client$i/nfd.sock'
            echo 'FIB表:'
            nfdc fib list | grep -E '(pro|nexthops)' || echo '无相关路由'
            echo 'Face列表:'
            nfdc face list | grep -E '(udp4|remote)' || echo '无UDP face'
        "
    done
    
    echo ""
    # 运行基础NDN测试
    if test_basic_ndn; then
        echo "基础NDN功能正常"
    else
        echo "基础NDN功能有问题，检查配置"
    fi
}

# 交互式管理
interactive_shell() {
    echo ""
    echo "=== 交互式管理 ==="
    echo "可用命令:"
    echo "1. status - 查看状态"
    echo "2. logs - 查看日志" 
    echo "3. test - 重新测试连接"
    echo "4. simple_test - 简单NDN测试"
    echo "5. shell <client_id> - 进入客户端shell"
    echo "6. debug <client_id> - 调试特定客户端"
    echo "7. cleanup - 清理并退出"
    echo ""
    
    while true; do
        read -p "ndn-manual> " cmd args
        
        case $cmd in
            "status")
                echo "=== 系统状态 ==="
                for i in {0..2}; do
                    echo "--- client$i ---"
                    
                    # 检查namespace是否存在
                    if sudo ip netns exec client$i echo "OK" 2>/dev/null; then
                        echo "Namespace: 存在"
                    else
                        echo "Namespace: 不存在"
                        continue
                    fi
                    
                    # 检查NFD进程
                    nfd_pids=$(sudo ip netns exec client$i pgrep nfd 2>/dev/null || echo "无")
                    echo "NFD PID: $nfd_pids"
                    
                    # 检查socket文件
                    if [ -S "/tmp/ndn/client$i/nfd.sock" ]; then
                        echo "Socket: 存在"
                    else
                        echo "Socket: 不存在"
                    fi
                    
                    # 检查应用进程
                    app_pids=$(sudo ip netns exec client$i pgrep -f ndnclient 2>/dev/null | wc -l)
                    echo "应用进程数: $app_pids"
                done
                ;;
            "simple_test")
                test_basic_ndn
                ;;
            "logs")
                echo "=== 日志文件 ==="
                for i in {0..2}; do
                    echo "--- client$i logs ---"
                    if [ -f "/tmp/ndn/client$i/nfd.log" ]; then
                        echo "NFD日志 (最后5行):"
                        tail -5 "/tmp/ndn/client$i/nfd.log"
                    fi
                    if [ -f "/tmp/ndn/client$i/app.log" ]; then
                        echo "应用日志 (最后5行):"
                        tail -5 "/tmp/ndn/client$i/app.log"
                    fi
                    echo ""
                done
                ;;
            "debug")
                if [ -n "$args" ]; then
                    echo "=== client$args 调试信息 ==="
                    sudo ip netns exec client$args bash -c "
                        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client$args/nfd.sock'
                        echo '=== NFD状态 ==='
                        nfdc status report
                        echo '=== Face列表 ==='
                        nfdc face list
                        echo '=== FIB表 ==='
                        nfdc fib list
                        echo '=== 路由表 ==='
                        nfdc route list
                    "
                else
                    echo "用法: debug <client_id>"
                fi
                ;;
            "test")
                test_connectivity
                ;;
            "shell")
                if [ -n "$args" ]; then
                    echo "进入client$args shell (输入exit退出):"
                    sudo ip netns exec client$args bash -c "
                        export NDN_CLIENT_TRANSPORT='unix:///tmp/ndn/client$args/nfd.sock'
                        export PS1='client$args# '
                        bash
                    "
                else
                    echo "用法: shell <client_id>"
                fi
                ;;
            "cleanup"|"exit"|"quit")
                cleanup
                exit 0
                ;;
            "help"|"")
                echo "可用命令: status, logs, debug <id>, test, simple_test, shell <id>, cleanup"
                ;;
            *)
                echo "未知命令: $cmd"
                ;;
        esac
    done
}

# 主执行流程
main() {
    cleanup
    setup_network
    
    if ! start_nfd; then
        echo "NFD启动失败，退出"
        cleanup
        exit 1
    fi
    
    setup_ndn_routing
    start_clients
    sleep 5
    test_connectivity
    interactive_shell
}

# 捕获Ctrl+C
trap cleanup EXIT

main "$@"