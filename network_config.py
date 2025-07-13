# 自定义网络拓扑配置文件
# 你可以在这里定义任意复杂的网络拓扑和链路属性

# 节点配置
nodes = {
    'consumer': {
        'ip': '10.0.0.1/24',
        'type': 'consumer'
    },
    'producer': {
        'ip': '10.0.0.2/24', 
        'type': 'producer'
    },
    # 你可以添加更多节点
    # 'relay1': {
    #     'ip': '10.0.0.3/24',
    #     'type': 'relay'
    # },
    # 'producer2': {
    #     'ip': '10.0.0.4/24',
    #     'type': 'producer'
    # }
}

# 链路配置
links = {
    # 链路名称: 配置参数
    'consumer-producer': {
        'nodes': ('consumer', 'producer'),
        'bw': 500,           # 带宽 (Mbps)
        'delay': '0ms',    # 延迟
        'loss': 0,          # 丢包率 (%)
        'max_queue_size': 100,
        'use_htb': True,    # 使用 HTB 队列调度
        'jitter': None      # 抖动 (可选)
    },
    
    # 你可以添加更多链路
    # 'consumer-relay1': {
    #     'nodes': ('consumer', 'relay1'),
    #     'bw': 100,
    #     'delay': '5ms',
    #     'loss': 0.5,
    #     'max_queue_size': 2000,
    #     'use_htb': True
    # },
    
    # 'relay1-producer': {
    #     'nodes': ('relay1', 'producer'),
    #     'bw': 50,
    #     'delay': '20ms',
    #     'loss': 2,
    #     'max_queue_size': 1500,
    #     'use_htb': True
    # },
    
    # 'consumer-producer2': {
    #     'nodes': ('consumer', 'producer2'),
    #     'bw': 20,
    #     'delay': '50ms',
    #     'loss': 5,
    #     'max_queue_size': 500,
    #     'use_htb': True
    # }
}

# 应用配置
applications = {
    'producer': {
        'prefix': 'producer',
        'config_file': '/home/a_coin_fan/code/ndn-dev-wsl/exp-proconfig.ini',
        'directory': '/home/a_coin_fan/code/ndn-dev-wsl/experiments/1'
    },
    
    # 你可以添加更多应用
    # 'producer2': {
    #     'prefix': 'producer2',
    #     'dataset_id': 2,
    #     'config_file': '/home/a_coin_fan/code/ndn-dev/producer/config.ini'
    # }
}

# 路由配置
routes = {
    # 节点名称: [(前缀, 下一跳)]
    'consumer': [
        ('/producer', 'udp4://10.0.0.2:6363'),
        # ('/producer2', 'udp4://10.0.0.4:6363')
    ],
    
    'producer': [
        ('/consumer', 'udp4://10.0.0.1:6363')
    ],
    
    # 'relay1': [
    #     ('/producer', 'udp4://10.0.0.2:6363'),
    #     ('/consumer', 'udp4://10.0.0.1:6363')
    # ]
}

# 测试配置
tests = [
    {
        'name': 'basic_test',
        'consumer': 'consumer',
        'config': '/home/a_coin_fan/code/ndn-dev-wsl/exp-conconfig.ini',
        'interest': '/producer/small_test.txt',
        'description': '基本的生产者-消费者测试'
    },
    
    # 你可以添加更多测试
    # {
    #     'name': 'large_file_test',
    #     'consumer': 'consumer',
    #     'interest': '/producer/1/large_test.txt',
    #     'description': '大文件传输测试'
    # },
    
    # {
    #     'name': 'binary_test',
    #     'consumer': 'consumer',
    #     'interest': '/producer/1/binary_test.dat',
    #     'description': '二进制文件测试'
    # }
]
