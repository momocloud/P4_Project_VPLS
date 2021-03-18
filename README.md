# IK2217-P4_Project-Group_4

We have completed all five tasks. The project is done through scripts instead of static configuration files. Auto-arp is set to false.

## Method of starting the program

1. Open a terminal and start P4 program.

   ```shell
   sudo p4run --conf <json file>
   ```

   For example if you want to use the sixth topology, you need to run the command below.

   ```shell
   sudo p4run --conf 06-aries-p4app.json
   ```

2. Open a new terminal and start the python script.

   ```shell
   sudo python routing-controller.py <conf file>
   ```

   For example if you want to use the sixth topology, you need to run the command below.

   ```shell
   sudo python routing-controller.py 06-aries-vpls.conf
   ```

## Method of testing the program

1. Open a new terminal and use the test script.

   ```shell
   sudo <script file>
   ```

   For example if you want to test the sixth topology, you need to run the command below.

   ```shell
   sudo ./test_topology_06.sh 
   ```

2. To test the ecmp function, you can use one script named `ecmp_test.py`.

   Firstly, open a new terminal and control one host as the sender. For example, if you want to use h1 as the sender:

   ```shell
   mx h1
   ```

   Then use the script:

   ```shell
   python ecmp_test.py <destination_ip> <destination_mac_addr> <number_of_random_packets>
   ```

   For example, if you want to send 7 packets to h2 whose ip is 10.0.0.2 and mac is 00:00:0a:00:00:02:

   ```shell
   python ecmp_test.py 10.0.0.2 00:00:0a:00:00:02 7
   ```

   This test script is modified from the ETH tutorial. You can use wireshark during the packet sending process to confirm that ecmp is in effect.
   
## Some files useful

   (control plane api)[./controlplane_api.md]
   
   (data plane api)[./dataplane_api.md]
   
   
