# 自定义网络拓扑配置文件
# 你可以在这里定义任意复杂的网络拓扑和链路属性

# 绝对路径
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 节点配置
nodes = {
    'consumer1': {'ip': '10.0.0.1/24', 'type': 'consumer'},
    'producer1': {'ip': '10.0.0.2/24', 'type': 'producer'},
}

# 链路配置
links = {
    # 链路名称: 配置参数
    'consumer1-producer1': {
        'nodes': ('consumer1', 'producer1'),    # 链路连接的节点
        'bw': 100,                              # 带宽 (Mbps)
        'delay': '0ms',                         # 延迟
        'loss': 0,                              # 丢包率 (%)
        'max_queue_size': 10000000,                  # 最大队列大小 (字节)
        'use_htb': True,                        # 使用 HTB 队列调度
        'jitter': None                          # 抖动 (可选)
    }
}

# 应用配置
applications = {
    'producer1': {
        'prefix': 'producer1',
        'config_file': os.path.join(PROJECT_ROOT, 'exp-proconfig.ini'),
        'directory': os.path.join(PROJECT_ROOT, 'experiments/1')
    }
}

# 路由配置
routes = {
    # 节点名称: [(前缀, 下一跳)]
    'consumer1': [('/producer1', 'udp4://10.0.0.2:6363')],
}

# 测试配置
tests = [
    {
        'name': 'multi_test',
        'consumer': ['consumer1'],
        'config': os.path.join(PROJECT_ROOT, 'exp-conconfig.ini'),
        'interest': '/producer1/testfile_6442450.txt',
        'description': 'temp'
    },
    
    # 你可以添加更多测试
    # {
    #     'name': 'large_file_test',
    #     'consumer': 'consumer',
    #     'interest': '/producer/1/large_test.txt',  # NDN interest 路径建议保持原格式
    #     'description': '大文件传输测试'
    # },
    
    # {
    #     'name': 'binary_test',
    #     'consumer': 'consumer',
    #     'interest': '/producer/1/binary_test.dat',  # NDN interest 路径建议保持原格式
    #     'description': '二进制文件测试'
    # }
]
