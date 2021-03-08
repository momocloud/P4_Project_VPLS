/*************************************************************************
*********************** P A R S E R  *******************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet_1;
    }

    state parse_ethernet_1 {
        packet.extract(hdr.ethernet_1);
        transition select(hdr.ethernet_1.etherType) {
            TYPE_TUNNEL: parse_tunnel;
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_tunnel {
        packet.extract(hdr.tunnel);
        transition parse_ethernet_2;
    }

    state parse_ethernet_2 {
        packet.extract(hdr.ethernet_2);
        transition select(hdr.ethernet_2.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol){
            6 : parse_tcp;
            default: accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    }

}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet_1);
        packet.emit(hdr.cpu);
        packet.emit(hdr.tunnel);
        packet.emit(hdr.ethernet_2);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
        packet.emit(hdr.rtt); 
    }
}
