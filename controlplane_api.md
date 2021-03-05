# 一些自己定义的控制层的函数

### 定义在`RoutingController`下:

`gen_tunnel(self)`: 生成通道，生成两个属性`name_to_tunnel`和`tunnel_list`存在类里，在init里调用，不用手动调用。

`get_pe_list(self)`: 生成边缘交换机与中间交换机的列表，分别存储类属性`pe_list`与`non_pe_list`中，在init里调用，不用手动调用。

`pe_list`: 一个保存所有边缘交换机的列表属性，用例：
```python
print self.pe_list

# 打印结果：
# [u's1', u's5', u's4']
```

`non_pe_list`: 一个保存所有中间交换机的列表属性，用例：
```python
print self.non_pe_list

# 打印结果：
# [u's3', u's2']
```

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

`get_all_tunnel_ports(self, sw_name)`: 返回sw_name的所有在隧道中的端口列表。用例：
```python
for sw_name in self.topo.get_p4switches().keys():
    print str(sw_name) + ': ' + str(self.get_all_tunnel_ports(sw_name))

# 打印结果：
# s3: [1, 3, 2]
# s2: [1, 3, 2]
# s1: [4, 3]
# s5: [4, 3]
# s4: [4, 3]
```

`get_all_non_tunnel_ports(self, sw_name)`: 返回sw_name的所有不在隧道中的端口列表。用例：
```python
for sw_name in self.topo.get_p4switches().keys():
    print str(sw_name) + ': ' + str(self.get_all_non_tunnel_ports(sw_name))

# 打印结果：
# s3: []
# s2: []
# s1: [1, 2]
# s5: [1, 2]
# s4: [2, 1]
```