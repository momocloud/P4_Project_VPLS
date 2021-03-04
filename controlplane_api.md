# 一些自己定义的控制层的函数

### 定义在`RoutingController`下:

`gen_tunnel()`: 生成通道，生成两个属性存在类里，在init里，不用写。

`name_to_tunnel`: 一个保存sw_name与tunnel的字典。用例：
```python
print self.name_to_tunnel

# 打印结果: 
# {(u's1', u's4'): [(u's1', u's3', u's4'), (u's1', u's2', u's4')],
#  (u's1', u's5'): [(u's1', u's3', u's5'), (u's1', u's2', u's5')],
#  (u's5', u's4'): [(u's5', u's3', u's4'), (u's5', u's2', u's4')]}
```

`tunnel_list`: 一个所有tunnel的列表。用例：
```python
print self.tunnel_list

# 打印结果: 
# [(u's1', u's3', u's5'), (u's1', u's2', u's5'), (u's1', u's3', u's4'), (u's1', u's2', u's4'), (u's5', u's3', u's4'), (u's5', u's2', u's4')]
```

`get_tunnel_ports(self, tunnel, sw_name)`: 返回sw_name的交换机连接tunnel的端口号列表。用例：
```python
for sw_name in self.topo.get_p4switches().keys():
    for tunnel in self.tunnel_list:
        if sw_name in tunnel:
            print str(sw_name) + '-' + str(tunnel) + ': ' + str(self.get_tunnel_ports(tunnel, sw_name))

# 打印结果: 
# s3-(u's1', u's3', u's5'): [1, 3]
# s3-(u's1', u's3', u's4'): [1, 2]
# s3-(u's5', u's3', u's4'): [3, 2]
# s2-(u's1', u's2', u's5'): [1, 3]
# s2-(u's1', u's2', u's4'): [1, 2]
# s2-(u's5', u's2', u's4'): [3, 2]
# s1-(u's1', u's3', u's5'): [4]
# s1-(u's1', u's2', u's5'): [3]
# s1-(u's1', u's3', u's4'): [4]
# s1-(u's1', u's2', u's4'): [3]
# s5-(u's1', u's3', u's5'): [4]
# s5-(u's1', u's2', u's5'): [3]
# s5-(u's5', u's3', u's4'): [4]
# s5-(u's5', u's2', u's4'): [3]
# s4-(u's1', u's3', u's4'): [4]
# s4-(u's1', u's2', u's4'): [3]
# s4-(u's5', u's3', u's4'): [4]
# s4-(u's5', u's2', u's4'): [3]
```

`get_pwid(self, sw_name)`: 返回sw_name的交换机端口对应的pw_id，是一个字典。用例：
```python
for sw_name in self.topo.get_p4switches().keys():
    print str(sw_name) + ': ' + str(self.get_pwid(sw_name))

# 打印结果:
# s3: {}
# s2: {}
# s1: {1: 1, 2: 2}
# s5: {1: 2, 2: 2}
# s4: {1: 1, 2: 2}
```