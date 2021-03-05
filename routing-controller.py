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
    ### define your own CPU header

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
        self.controller = SimpleSwitchAPI(thrift_port)

    def run(self):
        sniff(iface=self.cpu_port_intf, prn=self.recv_msg_cpu)

    def recv_msg_cpu(self, pkt):
        print "received packet at " + str(self.sw_name) + " controller"

        packet = Ether(str(pkt))

        if packet.type == 0x1234:
            cpu_header = CpuHeader(packet.payload)
            self.process_packet([(None)]) ### change None with the list of fields from the CPUHeader that you defined
        elif packet.type == 0x5678:
            rtt_header = RttHeader(packet.payload)
            self.process_packet_rtt([(rtt_header.customer_id,rtt_header.ip_addr_src,rtt_header.ip_addr_dst,rtt_header.rtt)])

    def process_packet(self, packet_data):
        ### write your learning logic here
        ### use exercise 04-Learning as a reference point
        pass

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
        ### logic to be executed at the start-up of the topology
        ### hint: compute ECMP paths here
        ### use exercise 08-Simple Routing as a reference

        # PE Part
        for pe in self.pe_list:
            for ingress_port in self.get_pwid(pe).keys():
                pw_id = self.get_pwid(pe)[ingress_port]

                # encap_forward_with_tunnel
                for another_pe in self.pe_list:
                    if pe == another_pe:
                        continue
                    else:
                        for host in self.topo.get_hosts_connected_to(another_pe):
                            if self.get_pwid(another_pe)[self.topo.node_to_node_port_num(another_pe, host)] != pw_id:
                                continue
                            else:
                                dst_mac = self.topo.get_host_mac(host)
                                tunnel_l = self.name_to_tunnel.get((pe, another_pe), None)
                                if tunnel_l is None:
                                    tunnel_l = self.name_to_tunnel[another_pe, pe]
                                tunnel = tunnel_l[0]
                                tunnel_id = self.tunnel_list.index(tunnel) + 1
                                egress_spec = self.get_tunnel_ports(tunnel, pe)[0]
                                self.controllers[pe].table_add('encap_forward_with_tunnel', 'encap_forward_with_tunnel_act', [str(ingress_port), str(dst_mac)], [str(egress_spec), str(tunnel_id), str(pw_id)])

                # direct_forward_without_tunnel
                for host in self.topo.get_hosts_connected_to(pe):
                    if self.topo.node_to_node_port_num(pe, host) == ingress_port or self.get_pwid(pe)[self.topo.node_to_node_port_num(pe, host)] != pw_id:
                        continue
                    else:
                        dst_mac = self.topo.get_host_mac(host)
                        egress_spec = self.topo.node_to_node_port_num(pe, host)
                        self.controllers[pe].table_add('direct_forward_without_tunnel', 'direct_forward_without_tunnel_act', [str(ingress_port), str(dst_mac)], [str(egress_spec)])

            # decap_forward_with_tunnel
            for host in self.topo.get_hosts_connected_to(pe):
                dst_mac = self.topo.get_host_mac(host)
                egress_spec = self.topo.node_to_node_port_num(pe, host)
                pw_id = self.get_pwid(pe)[egress_spec]
                self.controllers[pe].table_add('decap_forward_with_tunnel', 'decap_forward_with_tunnel_act', [str(dst_mac), str(pw_id)], [str(egress_spec)])

            # encap_multicast_egress_decap
            for port in self.get_all_tunnel_ports(pe):
                self.controllers[pe].table_add('encap_multicast_egress_decap', 'NoAction', [str(port)], [])

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
        
             # encap_multicast_egress_decap
            for port in self.get_all_tunnel_ports(non_pe):
                self.controllers[non_pe].table_add('encap_multicast_egress_decap', 'NoAction', [str(port)], [])


        print '=====tunnel_list below====='
        print self.tunnel_list
        print '=========='
        print self.non_pe_list



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
        thread = EventBasedController(params )
        thread.setName('MyThread ' + str(sw_name))
        thread.daemon = True
        thread_list.append(thread)
        thread.start()
    for thread in thread_list:
        thread.join()
    print ("Thread has finished")
