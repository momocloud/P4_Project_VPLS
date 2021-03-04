/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

//My includes 
#include "include/headers.p4"
#include "include/parsers.p4"

const bit<16> L2_LEARN_ETHER_TYPE = 0x1234;
const bit<16> RTT_ETHER_TYPE = 0x5678;

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    // basic forward 
    //       |
    //       | 
    //       v
    
    action drop() {
        mark_to_drop(standard_metadata);
    }

    action direct_forward_without_tunnel_act(egressSpec_t port) {
        // 转发
        standard_metadata.egress_spec = port;
    }

    action decrease_ipv4_ttl() {
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action encap_forward_with_tunnel_act(egressSpec_t port, tunnel_id_t tunnel_id, pw_id_t pw_id) {
        // 报头设置有效
        hdr.ethernet_2.setValid();
        hdr.tunnel.setValid();

        hdr.ethernet_2 = hdr.ethernet_1;

        // 封装隧道头
        hdr.ethernet_1.etherType = TYPE_TUNNEL;
        hdr.tunnel.tunnel_id = tunnel_id;
        hdr.tunnel.pw_id = pw_id;

        // 转发
        standard_metadata.egress_spec = port;
    }

    action direct_forward_with_tunnel_act(egressSpec_t port) {
        // 转发
        standard_metadata.egress_spec = port;
    }

    action decap_forward_with_tunnel_act(egressSpec_t port) {
        // 拆包
        hdr.ethernet_1.etherType = hdr.ethernet_2.etherType;
        hdr.ethernet_2.setInvalid();
        hdr.tunnel.setInvalid();

        // 转发
        standard_metadata.egress_spec = port;
    }

    table direct_forward_without_tunnel {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ethernet_1.dstAddr: exact;
        }
        actions = { direct_forward_without_tunnel_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table direct_forward_with_tunnel {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.tunnel.tunnel_id: exact;
        }
        actions = { direct_forward_with_tunnel_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table encap_forward_with_tunnel {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ethernet_1.dstAddr: exact;
        }
        actions = { encap_forward_with_tunnel_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table decap_forward_with_tunnel {
        key = {
            hdr.ethernet_1.dstAddr: exact;
            hdr.tunnel.pw_id: exact;
        }
        actions = { decap_forward_with_tunnel_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table table_ipv4 {
        key = {}
        actions = { decrease_ipv4_ttl; NoAction; }
        size = 1024;
        default_action = decrease_ipv4_ttl;
    }

    // ecmp 
    //   |
    //   | 
    //   v

    action ecmp_group_act(bit<14> ecmp_group_id, bit<16> num_nhops){
        hash(meta.ecmp_hash, HashAlgorithm.crc16, (bit<1>)0,
	                { hdr.ipv4.srcAddr,
	                  hdr.ipv4.dstAddr,
                      hdr.tcp.srcPort,
                      hdr.tcp.dstPort,
                      hdr.ipv4.protocol},
	                                                        num_nhops);

	    meta.ecmp_group_id = ecmp_group_id;
    }

    table ecmp_group {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ethernet_1.dstAddr: exact;
        }
        actions = { ecmp_group_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table ecmp_forward {
        key = {
            meta.ecmp_group_id: exact;
            meta.ecmp_hash: exact;
        }
        actions = { encap_forward_with_tunnel_act; NoAction; }
        default_action = NoAction;
    }

    // multicast
    //     |
    //     |
    //     v

    action encap_multicast_act(bit<16> mcast_grp, pw_id_t pw_id) {
        standard_metadata.mcast_grp = mcast_grp;
        hdr.ethernet_2.setValid();
        hdr.tunnel.setValid();

        hdr.ethernet_2 = hdr.ethernet_1;

        // 封装隧道头
        hdr.ethernet_1.etherType = TYPE_TUNNEL;
        hdr.tunnel.tunnel_id = 0;
        hdr.tunnel.pw_id = pw_id;
    }

    action decap_multicast_act(bit<16> mcast_grp) {
        hdr.ethernet_1.etherType = hdr.ethernet_2.etherType;
        hdr.ethernet_2.setInvalid();
        hdr.tunnel.setInvalid();
        standard_metadata.mcast_grp = mcast_grp;
    }

    action direct_multicast_act(bit<16> mcast_grp) {
        standard_metadata.mcast_grp = mcast_grp;
    }

    table encap_multicast {
        key = { standard_metadata.ingress_port: exact; }
        actions = { encap_multicast_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table decap_multicast {
        key = { hdr.tunnel.pw_id: exact; }
        actions = { decap_multicast_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    table direct_multicast {
        key = { standard_metadata.ingress_port: exact; }
        actions = { direct_multicast_act; NoAction; }
        size = 1024;
        default_action = NoAction;
    }

    apply {
        if (hdr.tunnel.isValid()) {
            if (hdr.tunnel.tunnel_id != 0) {
                direct_forward_with_tunnel.apply();
                decap_forward_with_tunnel.apply();
            } else {
                direct_multicast.apply();
                decap_multicast.apply();   
            }
        } else {
            if (direct_forward_without_tunnel.apply().hit){}
            else if (hdr.tcp.isValid() && ecmp_group.apply().hit) { ecmp_forward.apply(); }
            else if (encap_forward_with_tunnel.apply().hit) {}
            else { encap_multicast.apply(); }
        }
        if (hdr.ipv4.isValid()) {
            table_ipv4.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    
    action drop_2(){
        mark_to_drop(standard_metadata);
    }

    action encap_multicast_egress_decap_act() {
        hdr.ethernet_1.etherType = hdr.ethernet_2.etherType;
        hdr.ethernet_2.setInvalid();
        hdr.tunnel.setInvalid();
    }

    table encap_multicast_egress_decap {
        key = { standard_metadata.egress_port: exact; }
        actions = { encap_multicast_egress_decap_act; NoAction; }
        size = 1024;
        default_action = encap_multicast_egress_decap_act;
    }

    apply {
        if (hdr.tunnel.isValid()) {
            encap_multicast_egress_decap.apply();
        }
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
	update_checksum(
	    hdr.ipv4.isValid(),
            { hdr.ipv4.version,
	          hdr.ipv4.ihl,
              hdr.ipv4.dscp,
              hdr.ipv4.ecn,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
              hdr.ipv4.hdrChecksum,
              HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

//switch architecture
V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
