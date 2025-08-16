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
    sudo rm -rf /run/nfd/*
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
    
    for i in {0..2}; do
        echo "设置client$i..."
        mkdir -p /tmp/ndn/client$i
        
        # 停止可能存在的NFD进程
        sudo ip netns exec client$i pkill nfd 2>/dev/null || true
        sleep 1
        
        # 创建简单的NFD配置
        cat > /tmp/ndn/client$i/nfd.conf << EOF
face_system
{
  unix
  {
    path /run/nfd/client$i.sock
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
        echo "启动client$i NFD..."
        sudo ip netns exec client$i bash -c "
            mkdir -p /var/lib/ndn/nfd
            nfd --config /tmp/ndn/client$i/nfd.conf > /tmp/ndn/client$i/nfd.log 2>&1 &
        "
        
        # 等待socket文件创建
        echo "等待client$i socket文件..."
        timeout=15
        while [ $timeout -gt 0 ]; do
            if [ -S "/run/nfd/client$i/nfd.sock" ]; then
                echo "client$i NFD启动成功"
                break
            fi
            sleep 1
            timeout=$((timeout-1))
        done
        
        if [ $timeout -eq 0 ]; then
            echo "client$i NFD启动失败，检查日志:"
            cat /tmp/ndn/client$i/nfd.log 2>/dev/null || echo "无日志文件"
        fi
    done
    
    echo "等待所有NFD稳定..."
    sleep 5
}

# 设置NDN路由
setup_ndn_routing() {
    echo "6. 设置NDN路由..."
    
    # 验证所有socket文件存在
    for i in {0..2}; do
        if [ ! -S "/run/nfd/client$i/nfd.sock" ]; then
            echo "错误: client$i NFD未启动"
            return 1
        fi
    done
    
    # 设置跨节点路由
    echo "设置client0路由..."
    sudo ip netns exec client0 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client0/nfd.sock'
        nfdc face create udp4://10.0.1.2:6363
        nfdc face create udp4://10.0.3.2:6363
        nfdc route add /pro1 udp4://10.0.1.2:6363
        nfdc route add /pro2 udp4://10.0.3.2:6363
    "
    
    echo "设置client1路由..."
    sudo ip netns exec client1 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client1/nfd.sock'
        nfdc face create udp4://10.0.1.1:6363
        nfdc face create udp4://10.0.2.2:6363
        nfdc route add /pro0 udp4://10.0.1.1:6363
        nfdc route add /pro2 udp4://10.0.2.2:6363
    "
    
    echo "设置client2路由..."
    sudo ip netns exec client2 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client2/nfd.sock'
        nfdc face create udp4://10.0.2.1:6363
        nfdc face create udp4://10.0.3.1:6363
        nfdc route add /pro0 udp4://10.0.3.1:6363
        nfdc route add /pro1 udp4://10.0.2.1:6363
    "
    
    echo "NDN路由设置完成"
}

# 测试基础NDN功能
test_basic_ndn() {
    echo "7. 测试基础NDN功能..."
    
    # 在client1上启动producer
    sudo ip netns exec client1 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client1/nfd.sock'
        echo 'Hello from client1' | ndnpoke /pro1/test &
    " &
    sleep 2
    
    # 在client0上测试consumer
    result=$(sudo ip netns exec client0 bash -c "
        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client0/nfd.sock'
        timeout 5 ndnpeek /pro1/test 2>/dev/null || echo 'FAILED'
    ")
    
    if [ "$result" = "FAILED" ]; then
        echo "基础NDN测试失败"
        return 1
    else
        echo "基础NDN测试成功: $result"
        return 0
    fi
}

# 显示状态
show_status() {
    echo "8. 显示系统状态..."
    
    for i in {0..2}; do
        echo "--- client$i ---"
        
        # 检查NFD进程
        nfd_pids=$(sudo ip netns exec client$i pgrep nfd 2>/dev/null || echo "无")
        echo "NFD PID: $nfd_pids"
        
        # 检查socket
        if [ -S "/run/nfd/client$i/nfd.sock" ]; then
            echo "Socket: 存在"
            # 显示FIB
            sudo ip netns exec client$i bash -c "
                export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client$i/nfd.sock'
                echo 'FIB条目:'
                nfdc fib list | grep pro || echo '  无producer路由'
            "
        else
            echo "Socket: 不存在"
        fi
        echo ""
    done
}

# 交互式shell
interactive_shell() {
    echo ""
    echo "=== 交互式管理 ==="
    echo "可用命令:"
    echo "  status     - 显示状态"
    echo "  test       - 测试NDN连接"
    echo "  shell <id> - 进入client shell"
    echo "  logs <id>  - 显示NFD日志"
    echo "  cleanup    - 清理并退出"
    echo ""
    
    while true; do
        read -p "ndn> " cmd args
        
        case $cmd in
            "status")
                show_status
                ;;
            "test")
                test_basic_ndn
                ;;
            "shell")
                if [ -n "$args" ]; then
                    echo "进入client$args shell (输入exit退出):"
                    sudo ip netns exec client$args bash -c "
                        export NDN_CLIENT_TRANSPORT='unix:///run/nfd/client$args/nfd.sock'
                        export PS1='client$args# '
                        bash
                    "
                else
                    echo "用法: shell <client_id>"
                fi
                ;;
            "logs")
                if [ -n "$args" ]; then
                    echo "=== client$args NFD日志 ==="
                    cat /tmp/ndn/client$args/nfd.log 2>/dev/null || echo "无日志文件"
                else
                    echo "用法: logs <client_id>"
                fi
                ;;
            "cleanup"|"exit"|"quit")
                cleanup
                exit 0
                ;;
            "help"|"")
                echo "可用命令: status, test, shell <id>, logs <id>, cleanup"
                ;;
            *)
                echo "未知命令: $cmd"
                ;;
        esac
    done
}

# 主函数
main() {
    cleanup
    setup_network
    start_nfd
    
    # 如果NFD启动成功才继续
    success_count=0
    for i in {0..2}; do
        if [ -S "/run/nfd/client$i/nfd.sock" ]; then
            success_count=$((success_count + 1))
        fi
    done
    
    echo "成功启动 $success_count/3 个NFD实例"
    
    if [ $success_count -gt 0 ]; then
        setup_ndn_routing
        test_basic_ndn
        show_status
        interactive_shell
    else
        echo "所有NFD实例启动失败，退出"
        cleanup
        exit 1
    fi
}

# 捕获Ctrl+C
trap cleanup EXIT

main "$@"
