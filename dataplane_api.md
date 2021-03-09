# 数据层表集合

| Tabel                         | Keys                                          | Actions                                                      |
| ----------------------------- | ----------------------------------------------| ------------------------------------------------------------ |
| encap_forward_with_tunnel     | ingress_port, dst_addr                        | encap_forward_with_tunnel_act(egress_spec, tunnel_id, pw_id) |
| decap_forward_with_tunnel     | dst_addr, pw_id                               | decap_forward_with_tunnel_act(egress_spec)                   |
| direct_forward_without_tunnel | ingress_port, dst_addr                        | direct_forward_without_tunnel_act(egress_spec)               |
| direct_forward_with_tunnel    | ingress_port, tunnel_id                       | direct_forward_with_tunnel_act(egress_spec)                  |
| ecmp_group                    | ingress_port, dstAddr                         | ecmp_group_act(group_id, num_nhops)                          |
| ecmp_forward                  | group_id, hash                                | encap_forward_with_tunnel_act(egress_spec, tunnel_id, pw_id) |
| encap_multicast               | ingress_port                                  | encap_multicast_act(mcast_grp, pw_id)                        |
| decap_multicast               | pw_id                                         | decap_multicast_act(mcast_grp)                               |
| smac                          | src_addr, ingress_port                        | NoAction()                                                   |
| no_learning                   | mac_addr, tunnel_id, pw_id_or_ingress_port    | drop_2()                                                     |
