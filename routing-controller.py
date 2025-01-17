from p4utils.utils.topology import Topology
from p4utils.utils.sswitch_API import SimpleSwitchAPI
from scapy.all import Ether, sniff, Packet, BitField
from multiprocessing import Pool
import threading
import json
import ipaddress
import itertools

class CpuHeader(Packet):
    name = 'CpuPacket'
    fields_desc = [BitField('macAddr', 0, 48), BitField('tunnel_id', 0, 16), BitField('pw_id_or_ingress_port', 0, 16)]

class RttHeader(Packet):
    name = 'RttPacket'
    fields_desc = [BitField('customer_id',0,16), BitField('ip_addr_src', 0, 32), BitField('ip_addr_dst', 0, 32), BitField('rtt',0,48)]

class EventBasedController(threading.Thread):
    def __init__(self, params):
        super(EventBasedController, self).__init__()
        self.topo = Topology(db="topology.db")
        self.sw_name = params["sw_name"]
        self.cpu_port_intf = params["cpu_port_intf"]
        self.thrift_port = params["thrift_port"]
        self.id_to_switch = params["id_to_switch"]
        self.whole_controller = params["whole_controller"]
        self.controller = SimpleSwitchAPI(thrift_port)
        self.ecmp_group_count = 1

    def run(self):
        sniff(iface=self.cpu_port_intf, prn=self.recv_msg_cpu)

    def recv_msg_cpu(self, pkt):
        print "received packet at " + str(self.sw_name) + " controller"

        packet = Ether(str(pkt))

        if packet.type == 0x1234:
            cpu_header = CpuHeader(packet.payload)
            self.process_packet([(cpu_header.macAddr, cpu_header.tunnel_id, cpu_header.pw_id_or_ingress_port)]) ### change None with the list of fields from the CPUHeader that you defined
        elif packet.type == 0x5678:
            rtt_header = RttHeader(packet.payload)
            self.process_packet_rtt([(rtt_header.customer_id,rtt_header.ip_addr_src,rtt_header.ip_addr_dst,rtt_header.rtt)])

    def process_packet(self, packet_data):
        for macAddr, tunnel_id, pw_id_or_ingress_port in packet_data:
            if self.topo.get_hosts_connected_to(self.sw_name) == []:
                self.controller.table_add('l2_learning_tunnel', 'NoAction', [str(macAddr), str(pw_id_or_ingress_port)], [])
                return
            # non-tunnel packets
            if tunnel_id == 0:
                egress_spec = pw_id_or_ingress_port
                self.controller.table_add('l2_learning_non_tunnel', 'NoAction', [str(macAddr), str(egress_spec)], [])
                pw_id = self.whole_controller.get_pwid(self.sw_name)[egress_spec]
                # direct_forward_without_tunnel
                for ingress_port in self.whole_controller.get_all_non_tunnel_ports(self.sw_name):
                    if ingress_port == egress_spec or self.whole_controller.get_pwid(self.sw_name)[ingress_port] != pw_id:
                        continue
                    else:
                        self.controller.table_add('direct_forward_without_tunnel', 'direct_forward_without_tunnel_act', [str(ingress_port), str(macAddr)], [str(egress_spec)])
                # decap_forward_with_tunnel
                self.controller.table_add('decap_forward_with_tunnel', 'decap_forward_with_tunnel_act', [str(macAddr), str(pw_id)], [str(egress_spec)])
                
            # tunnel packets
            else:
                pw_id = pw_id_or_ingress_port
                self.controller.table_add('l2_learning_tunnel', 'NoAction', [str(macAddr), str(pw_id)], [])
                tunnel = self.whole_controller.tunnel_list[tunnel_id - 1]

                # encap_forward_with_tunnel
                for ingress_port in self.whole_controller.get_all_non_tunnel_ports(self.sw_name):
                    if self.whole_controller.get_pwid(self.sw_name)[ingress_port] != pw_id:
                        continue
                    else:
                        egress_spec = self.whole_controller.get_tunnel_ports(tunnel, self.sw_name)[0]
                        self.controller.table_add('encap_forward_with_tunnel', 'encap_forward_with_tunnel_act', [str(ingress_port), str(macAddr)], [str(egress_spec), str(tunnel_id), str(pw_id)])
                # # ecmp
                the_other_pe = self.sw_name
                for pe_pair in self.whole_controller.name_to_tunnel.keys():
                    if tunnel in self.whole_controller.name_to_tunnel[pe_pair]:
                        for pe in pe_pair:
                            if pe == self.sw_name:
                                continue
                            else:
                                the_other_pe = pe
                tunnel_l = self.whole_controller.name_to_tunnel.get((self.sw_name, the_other_pe), None)
                if tunnel_l == None:
                    tunnel_l = self.whole_controller.name_to_tunnel[(the_other_pe, self.sw_name)]
                if len(tunnel_l) > 1:
                    for ingress_port in self.whole_controller.get_all_non_tunnel_ports(self.sw_name):
                        if self.whole_controller.get_pwid(self.sw_name)[ingress_port] != pw_id:
                            continue
                        else:
                            self.controller.table_add('ecmp_group', 'ecmp_group_act', [str(ingress_port), str(macAddr)], [str(self.ecmp_group_count), str(len(tunnel_l))])
                    for hash_value in range(len(tunnel_l)):
                        tunnel_ecmp = tunnel_l[hash_value]
                        tunnel_id_ecmp = self.whole_controller.tunnel_list.index(tunnel_ecmp) + 1
                        egress_spec = self.whole_controller.get_tunnel_ports(tunnel_ecmp, self.sw_name)[0]
                        self.controller.table_add('ecmp_forward', 'encap_forward_with_tunnel_act', [str(self.ecmp_group_count), str(hash_value)], [str(egress_spec), str(tunnel_id_ecmp), str(pw_id)])
                    self.ecmp_group_count += 1

    def process_packet_rtt(self, packet_data):
        for customer_id, ip_addr_src, ip_addr_dst, rtt in packet_data:
            print("Customer_id: " + str(customer_id))
            print("SourceIP: " +  str(ipaddress.IPv4Address(ip_addr_src)))
            print("DestinationIP: " + str(ipaddress.IPv4Address(ip_addr_dst)))
            print("RTT: " + str(rtt))

class RoutingController(object): 

    def __init__(self, vpls_conf_file):

        self.topo = Topology(db="topology.db")
        self.cpu_ports = {x:self.topo.get_cpu_port_index(x) for x in self.topo.get_p4switches().keys()}
        self.controllers = {}
        self.vpls_conf_file = vpls_conf_file
        self.name_to_tunnel = {}
        self.tunnel_list = []
        self.pe_list = []
        self.non_pe_list = []
        self.init()

    def init(self):
        self.connect_to_switches()
        self.reset_states()
        self.add_mirror()
        self.extract_customers_information()
        self.gen_tunnel()
        self.get_pe_list()
        self.switch_to_id = {sw_name:self.get_switch_id(sw_name) for sw_name in self.topo.get_p4switches().keys()}
        self.id_to_switch = {self.get_switch_id(sw_name):sw_name for sw_name in self.topo.get_p4switches().keys()}

    def add_mirror(self):
        for sw_name in self.topo.get_p4switches().keys():
            self.controllers[sw_name].mirroring_add(100, self.cpu_ports[sw_name])    
        
    def extract_customers_information(self):
        with open(self.vpls_conf_file) as json_file:
            self.vpls_conf = json.load(json_file)

    def reset_states(self):
        [controller.reset_state() for controller in self.controllers.values()]

    def connect_to_switches(self):
        for p4switch in self.topo.get_p4switches():
            thrift_port = self.topo.get_thrift_port(p4switch)
            self.controllers[p4switch] = SimpleSwitchAPI(thrift_port)

    def get_switch_id(self, sw_name):
        return "{:02x}".format(self.topo.get_p4switches()[sw_name]["sw_id"])

    def gen_tunnel(self):
        pe_switchs = []
        for swname in self.topo.get_p4switches().keys():
            if len(self.topo.get_hosts_connected_to(swname)) != 0:
                pe_switchs.append(swname)
        pe_pair = list(itertools.combinations(pe_switchs, 2))
        name_to_tunnel = {}
        tunnel_list = []
        for item in pe_pair:
            sub_tunnels = self.topo.get_shortest_paths_between_nodes(item[0], item[1])
            for sub_tunnel in sub_tunnels:
                if 'sw-cpu' in sub_tunnel:
                    sub_tunnels.remove(sub_tunnel)
            for sub_tunnel in sub_tunnels:
                tunnel_list.append(sub_tunnel)
            name_to_tunnel.update({item: sub_tunnels})
        self.name_to_tunnel = name_to_tunnel
        self.tunnel_list = tunnel_list

    def get_tunnel_ports(self, tunnel, sw_name): 
        ports = []
        if tunnel.index(sw_name) == 0:
            ports.append(self.topo.node_to_node_port_num(sw_name, tunnel[1]))
        elif tunnel.index(sw_name) == len(tunnel) - 1:
            ports.append(self.topo.node_to_node_port_num(sw_name, tunnel[len(tunnel) - 2]))
        else:
            index = tunnel.index(sw_name)
            ports.append(self.topo.node_to_node_port_num(sw_name, tunnel[index - 1]))
            ports.append(self.topo.node_to_node_port_num(sw_name, tunnel[index + 1]))
        return ports

    def get_all_tunnel_ports(self, sw_name):
        ports = []
        for tunnel in self.tunnel_list:
            if sw_name in tunnel:
                ports_t = self.get_tunnel_ports(tunnel, sw_name)
                for port in ports_t:
                    if not port in ports:
                        ports.append(port)
        return ports

    def get_port_tunnels(self, port, sw_name):
        tunnels = []
        for tunnel in self.tunnel_list:
            if sw_name in tunnel:
                if port in self.get_tunnel_ports(tunnel, sw_name):
                    tunnels.append(tunnel)
        return tunnels

    def get_all_non_tunnel_ports(self, sw_name):
        ports = []
        for host in self.topo.get_hosts_connected_to(sw_name):
            ports.append(self.topo.node_to_node_port_num(sw_name, host))
        return ports

    def get_pwid(self, sw_name):
        pwid_dic = {}
        for host in self.topo.get_hosts_connected_to(sw_name):
            if self.vpls_conf['hosts'][host] == 'A':
                pwid_dic.update({self.topo.node_to_node_port_num(sw_name, host): 1})
            elif self.vpls_conf['hosts'][host] == 'B':
                pwid_dic.update({self.topo.node_to_node_port_num(sw_name, host): 2})
        return pwid_dic

    def get_pe_list(self):
        for sw_name in self.topo.get_p4switches().keys():
            if len(self.topo.get_hosts_connected_to(sw_name)) > 0 :
                self.pe_list.append(sw_name)
            elif len(self.topo.get_hosts_connected_to(sw_name)) == 0 :
                self.non_pe_list.append(sw_name)

    def process_network(self):
        # PE Part
        for pe in self.pe_list:
            # group_id = 0
            for ingress_port in self.get_pwid(pe).keys():
                pw_id = self.get_pwid(pe)[ingress_port]

            # multicast
            tunnel_handle_num = 0
            for tunnel_port in self.get_all_tunnel_ports(pe):
                for tunnel in self.get_port_tunnels(tunnel_port, pe):
                    tunnel_id = self.tunnel_list.index(tunnel) + 1
                    node_port = []
                    node_port.append(tunnel_port)
                    self.controllers[pe].mc_node_create(tunnel_id, node_port)
                    tunnel_handle_num += 1
            for tunnel_port in self.get_all_tunnel_ports(pe):
                for tunnel in self.get_port_tunnels(tunnel_port, pe):
                    tunnel_id = self.tunnel_list.index(tunnel) + 1
                    node_port = []
                    node_port.append(tunnel_port)
                    self.controllers[pe].mc_node_create(tunnel_id, node_port)
                    
            non_tunnel_ports_1 = []
            non_tunnel_ports_2 = []
            for non_tunnel_port in self.get_all_non_tunnel_ports(pe):
                if self.get_pwid(pe)[non_tunnel_port] == 1:
                    non_tunnel_ports_1.append(non_tunnel_port)
                elif self.get_pwid(pe)[non_tunnel_port] == 2:
                    non_tunnel_ports_2.append(non_tunnel_port)
            for index in range(4):
                self.controllers[pe].mc_mgrp_create(index + 1)
            for index in range(2):
                self.controllers[pe].mc_node_create(0, non_tunnel_ports_1)
                self.controllers[pe].mc_node_create(0, non_tunnel_ports_2)

            for index in range(tunnel_handle_num):
                self.controllers[pe].mc_node_associate(1, index)
                self.controllers[pe].mc_node_associate(2, index + tunnel_handle_num)
            self.controllers[pe].mc_node_associate(1, tunnel_handle_num * 2)
            self.controllers[pe].mc_node_associate(2, tunnel_handle_num * 2 + 1)
            self.controllers[pe].mc_node_associate(3, tunnel_handle_num * 2 + 2)
            self.controllers[pe].mc_node_associate(4, tunnel_handle_num * 2 + 3)

            for ingress_port in self.get_all_non_tunnel_ports(pe):
                pw_id = self.get_pwid(pe)[ingress_port]
                self.controllers[pe].table_add('get_pwid', 'get_pwid_act', [str(ingress_port)], [str(pw_id)])
                if pw_id == 1:
                    self.controllers[pe].table_add('encap_multicast', 'encap_multicast_act', [str(ingress_port)], ['1', str(pw_id)])
                elif pw_id == 2:
                    self.controllers[pe].table_add('encap_multicast', 'encap_multicast_act', [str(ingress_port)], ['2', str(pw_id)])
            self.controllers[pe].table_add('decap_multicast', 'decap_multicast_act', ['1'], ['3'])
            self.controllers[pe].table_add('decap_multicast', 'decap_multicast_act', ['2'], ['4'])

        # non_PE Part
        for non_pe in self.non_pe_list:
            tunnel_l = []
            tunnel_id_l = []
            for tunnel in self.tunnel_list:
                if non_pe in tunnel:
                    tunnel_l.append(tunnel)
                    tunnel_id_l.append(self.tunnel_list.index(tunnel) + 1)
            for index in range(len(tunnel_l)):
                tunnel = tunnel_l[index]
                tunnel_id = tunnel_id_l[index]
                ports = self.get_tunnel_ports(tunnel, non_pe)
                self.controllers[non_pe].table_add('direct_forward_with_tunnel', 'direct_forward_with_tunnel_act', [str(ports[0]), str(tunnel_id)], [str(ports[1])])
                self.controllers[non_pe].table_add('direct_forward_with_tunnel', 'direct_forward_with_tunnel_act', [str(ports[1]), str(tunnel_id)], [str(ports[0])])

        print '=====tunnel_list below====='
        print self.tunnel_list

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print "Error: vpls.conf file missing"
        sys.exit()
    vpls_conf_file = sys.argv[1]
    controller = RoutingController(vpls_conf_file)
    controller.process_network()
    thread_list = []
    for sw_name in controller.topo.get_p4switches().keys():
        cpu_port_intf = str(controller.topo.get_cpu_port_intf(sw_name).replace("eth0", "eth1"))
        thrift_port = controller.topo.get_thrift_port(sw_name)
        id_to_switch = controller.id_to_switch
        params ={}
        params["sw_name"] = sw_name
        params["cpu_port_intf"]= cpu_port_intf 
        params["thrift_port"]= thrift_port
        params["id_to_switch"]= id_to_switch
        params["whole_controller"] = controller
        thread = EventBasedController(params )
        thread.setName('MyThread ' + str(sw_name))
        thread.daemon = True
        thread_list.append(thread)
        thread.start()
    for thread in thread_list:
        thread.join()
    print ("Thread has finished")
