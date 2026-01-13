from pulumi import ResourceOptions, export, Config
from pulumi_azure_native import Provider
from pulumi_azure_native.resources import ResourceGroup
from pulumi_azure_native import network
import pulumi_random as random

from pulumi_azure_native import compute


# From: https://learn.microsoft.com/en-us/azure/developer/terraform/hub-spoke-on-prem

onprem_vnet_rg = ResourceGroup("onprem-vnet-rg")

export("onprem_rg", onprem_vnet_rg.name)

onprem_vnet = network.VirtualNetwork("onprem-vnet",
                                     resource_group_name=onprem_vnet_rg.name,
                                     address_space=network.AddressSpaceArgs(
                                         address_prefixes=["192.168.0.0/16"]
                                     )
                                     )


onprem_mgmt = network.Subnet("onprem-mgmt",
                             virtual_network_name=onprem_vnet.name,
                             resource_group_name=onprem_vnet_rg.name,
                             address_prefix="192.168.1.128/25"
                             )

onprem_pip = network.PublicIPAddress("onprem-pip",
                                     resource_group_name=onprem_vnet_rg.name,
                                     public_ip_allocation_method=network.IPAllocationMethod.DYNAMIC
                                     )

onprem_nic = network.NetworkInterface("onprem-nic",
                                      resource_group_name=onprem_vnet_rg.name,
                                      enable_ip_forwarding=True,
                                      ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
                                          name="onprem",
                                          subnet=network.SubnetArgs(
                                              id=onprem_mgmt.id
                                          ),
                                          private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                                          public_ip_address=network.PublicIPAddressArgs(
                                              id=onprem_pip.id
                                          )
                                      )]
                                      )

onprem_nsg = network.NetworkSecurityGroup("onprem_nsg",
                                          resource_group_name=onprem_vnet_rg.name,
                                          security_rules=[network.SecurityRuleArgs(
                                              name="SSH",
                                              priority=1001,
                                              direction=network.SecurityRuleDirection.INBOUND,
                                              access="Allow",
                                              protocol="Tcp",
                                              source_port_range="*",
                                              source_address_prefix="86.27.128.191/32",
                                              destination_address_prefix="*",
                                              destination_port_range="22"
                                          )]
                                          )

onprem_gateway_subnet = network.Subnet("GatewaySubnet",
                                       name="GatewaySubnet",
                                       virtual_network_name=onprem_vnet.name,
                                       resource_group_name=onprem_vnet_rg.name,
                                       address_prefix="192.168.255.224/27",
                                       )

pw = random.RandomPassword("vm-pw", length=20)

export("pw", pw.result)

onprem_vm = compute.VirtualMachine("onprem-vm",
                                   resource_group_name=onprem_vnet_rg.name,
                                   hardware_profile=compute.HardwareProfileArgs(
                                       vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2
                                   ),
                                   storage_profile=compute.StorageProfileArgs(
                                       image_reference=compute.ImageReferenceArgs(
                                           offer="ubuntu-24_04-lts",
                                           publisher="Canonical",
                                           sku="server",
                                           version="latest"
                                       ),
                                       os_disk=compute.OSDiskArgs(
                                           name="myosdisk1",
                                           caching=compute.CachingTypes.READ_WRITE,
                                           create_option="FromImage",
                                           managed_disk=compute.ManagedDiskParametersArgs(
                                               storage_account_type=compute.StorageAccountTypes.STANDARD_LRS
                                           )
                                       ),
                                   ),
                                   os_profile=compute.OSProfileArgs(
                                       computer_name="pk-onprem-vm",
                                       admin_password=pw.result,
                                       admin_username="pk-admin",
                                       linux_configuration=compute.LinuxConfigurationArgs(
                                           disable_password_authentication=False
                                       )
                                   ),
                                   network_profile=compute.NetworkProfileArgs(
                                       network_interfaces=[compute.NetworkInterfaceReferenceArgs(
                                           id=onprem_nic.id
                                       )]
                                   )
                                   )

onprem_vpn_gw1_pip = network.PublicIPAddress("onprem-vpn-gw1-pip",
                                             resource_group_name=onprem_vnet_rg.name,
                                             public_ip_allocation_method=network.IPAllocationMethod.DYNAMIC
                                             )

onprem_vpn_gateway = network.VirtualNetworkGateway("onprem-vpn-gateway",
                                                   resource_group_name=onprem_vnet_rg.name,
                                                   gateway_type=network.VirtualNetworkGatewayType.VPN,
                                                   vpn_type=network.VpnType.ROUTE_BASED,
                                                   active_active=False,
                                                   enable_bgp=False,
                                                   sku=network.VirtualNetworkGatewaySkuArgs(
                                                       name="VpnGw1",
                                                       tier="VpnGw1"
                                                   ),
                                                   ip_configurations=[network.VirtualNetworkGatewayIPConfigurationArgs(
                                                       name="vnetGatewayConfig",
                                                       public_ip_address=network.SubResourceArgs(
                                                           id=onprem_vpn_gw1_pip.id
                                                       ),
                                                       private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                                                       subnet=network.SubResourceArgs(
                                                           id=onprem_gateway_subnet.id
                                                       )
                                                   )]
                                                   )


# From: https://learn.microsoft.com/en-us/azure/developer/terraform/hub-spoke-hub-network

hub_vnet_rg = ResourceGroup("hub-vnet-rg")

export("hub_vnet_rg", hub_vnet_rg.name)

hub_vnet = network.VirtualNetwork("hub-vnet",
                                  resource_group_name=hub_vnet_rg.name,
                                  address_space=network.AddressSpaceArgs(
                                      address_prefixes=["10.0.0.0/16"]
                                  )
                                  )



hub_mgmt = network.Subnet("hub-mgmt",
                          resource_group_name=hub_vnet_rg.name,
                          virtual_network_name=hub_vnet.name,
                          address_prefixes=["10.0.0.64/27"]
                          )

hub_dmz = network.Subnet("hub-dmz",
                         resource_group_name=hub_vnet_rg.name,
                         virtual_network_name=hub_vnet.name,
                         address_prefixes=["10.0.0.32/27"]
                         )

hub_nic = network.NetworkInterface("hub-nic",
                                   resource_group_name=hub_vnet_rg.name,
                                   enable_ip_forwarding=True,
                                   ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
                                       name="hub",
                                       subnet=network.SubnetArgs(
                                           id=hub_mgmt.id
                                       ),
                                       private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC
                                   )]
                                   )

hub_vm = compute.VirtualMachine("hub-vm",
                                resource_group_name=hub_vnet_rg.name,
                                hardware_profile=compute.HardwareProfileArgs(
                                    vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2
                                ),
                                storage_profile=compute.StorageProfileArgs(
                                    image_reference=compute.ImageReferenceArgs(
                                        offer="ubuntu-24_04-lts",
                                        publisher="Canonical",
                                        sku="server",
                                        version="latest"
                                    ),
                                    os_disk=compute.OSDiskArgs(
                                        caching=compute.CachingTypes.READ_WRITE,
                                        create_option="FromImage",
                                        managed_disk=compute.ManagedDiskParametersArgs(
                                            storage_account_type=compute.StorageAccountTypes.STANDARD_LRS
                                        )
                                    ),
                                ),
                                os_profile=compute.OSProfileArgs(
                                    computer_name="pk-onprem-vm",
                                    admin_password=pw.result,
                                    admin_username="pk-admin",
                                    linux_configuration=compute.LinuxConfigurationArgs(
                                        disable_password_authentication=False
                                    )
                                ),
                                network_profile=compute.NetworkProfileArgs(
                                    network_interfaces=[compute.NetworkInterfaceReferenceArgs(
                                        id=hub_nic.id
                                    )]
                                )
                                )

hub_vpn_gateway1_pip = network.PublicIPAddress("hub-vpn-gatway1-pip",
                                               resource_group_name=hub_vnet_rg.name,
                                               public_ip_allocation_method=network.IPAllocationMethod.DYNAMIC
                                               )

hub_nva_rg = ResourceGroup("hub-nva-rg")

export("hub_nva_rg", hub_nva_rg.name)

hub_gateway_rt = network.RouteTable("hub-gateway-rt",
                                    resource_group_name=hub_nva_rg.name,
                                    disable_bgp_route_propagation=False,
                                    routes=[
                                        network.RouteArgs(
                                            name="toHub",
                                            address_prefix="10.0.0.0/16",
                                            next_hop_type=network.RouteNextHopType.VNET_LOCAL
                                        ),
                                        network.RouteArgs(
                                            name="toSpoke1",
                                            address_prefix="10.1.0.0/16",
                                            next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
                                            next_hop_ip_address="10.0.0.36"
                                        ),
                                        network.RouteArgs(
                                            name="toSpoke2",
                                            address_prefix="10.2.0.0/16",
                                            next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
                                            next_hop_ip_address="10.0.0.36"
                                        )
                                    ],
                                    opts=ResourceOptions(ignore_changes=["properties.etag", "properties.routes[*].etag"])
                                    )

spoke1_rt = network.RouteTable("spoke1-rt",
    resource_group_name=hub_nva_rg.name,
    disable_bgp_route_propagation=False,
    routes=[
        network.RouteArgs(
            name="toSpoke2",
            address_prefix="10.2.0.0/16",
            next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
            next_hop_ip_address="10.0.0.36"
        ),
        network.RouteArgs(
            name="default",
            address_prefix="0.0.0.0/0",
            next_hop_type=network.RouteNextHopType.VNET_LOCAL
        )
    ],
    opts=ResourceOptions(ignore_changes=["properties.etag", "properties.routes[*].etag"])
)

spoke2_rt = network.RouteTable("spoke2-rt",
    resource_group_name=hub_nva_rg.name,
    disable_bgp_route_propagation=False,
    routes=[
        network.RouteArgs(
            name="toSpoke1",
            address_prefix="10.1.0.0/16",
            next_hop_type=network.RouteNextHopType.VIRTUAL_APPLIANCE,
            next_hop_ip_address="10.0.0.36"
        ),
        network.RouteArgs(
            name="default",
            address_prefix="0.0.0.0/0",
            next_hop_type=network.RouteNextHopType.VNET_LOCAL
        )
    ],
    opts=ResourceOptions(ignore_changes=["properties.etag", "properties.routes[*].etag", "etag", "routes[*].etag"])
)

hub_gateway_subnet = network.Subnet("hub-gateway-subnet",
                                    subnet_name="GatewaySubnet",
                                    resource_group_name=hub_vnet_rg.name,
                                    virtual_network_name=hub_vnet.name,
                                    address_prefixes=["10.0.255.224/27"],
                                    route_table=network.RouteTableArgs(
                                        id=hub_gateway_rt.id
                                    )
                                    )

hub_vnet_gateway = network.VirtualNetworkGateway("hub-vpn-gateway",
                                                 resource_group_name=hub_vnet_rg.name,
                                                 gateway_type=network.VirtualNetworkGatewayType.VPN,
                                                 vpn_type=network.VpnType.ROUTE_BASED,
                                                 active_active=False,
                                                 enable_bgp=False,
                                                 sku=network.VirtualNetworkGatewaySkuArgs(
                                                     name="VpnGw1",
                                                     tier="VpnGw1"
                                                 ),
                                                 ip_configurations=[network.VirtualNetworkGatewayIPConfigurationArgs(
                                                     name="vnetGatewayConfig",
                                                     public_ip_address=network.SubResourceArgs(
                                                         id=hub_vpn_gateway1_pip.id
                                                     ),
                                                     private_ip_allocation_method=network.IPAllocationMethod.DYNAMIC,
                                                     subnet=network.SubResourceArgs(
                                                         id=hub_gateway_subnet.id
                                                     )
                                                 )]
                                                 )

shared_key = random.RandomUuid("shared-key")

hub_onprem_conn = network.VirtualNetworkGatewayConnection("hub-onprem-conn",
                                                          resource_group_name=hub_vnet_rg.name,
                                                          connection_type=network.VirtualNetworkGatewayConnectionType.VNET2_VNET,
                                                          routing_weight=1,
                                                          virtual_network_gateway1=network.VirtualNetworkGatewayArgs(
                                                              id=hub_vnet_gateway.id
                                                          ),
                                                          virtual_network_gateway2=network.VirtualNetworkGatewayArgs(
                                                              id=onprem_vpn_gateway.id
                                                          ),
                                                          shared_key=shared_key.result
                                                          )

onprem_hub_conn = network.VirtualNetworkGatewayConnection("onprem-hub-conn",
                                                          resource_group_name=onprem_vnet_rg.name,
                                                          connection_type=network.VirtualNetworkGatewayConnectionType.VNET2_VNET,
                                                          routing_weight=1,
                                                          virtual_network_gateway1=network.VirtualNetworkGatewayArgs(
                                                              id=onprem_vpn_gateway.id
                                                          ),
                                                          virtual_network_gateway2=network.VirtualNetworkGatewayArgs(
                                                              id=hub_vnet_gateway.id
                                                          ),
                                                          shared_key=shared_key.result
                                                          )


# From: https://learn.microsoft.com/en-us/azure/developer/terraform/hub-spoke-hub-nva

hub_nva_nic = network.NetworkInterface("hub-nva-nic",
                                       resource_group_name=hub_nva_rg.name,
                                       enable_ip_forwarding=True,
                                       ip_configurations=[network.NetworkInterfaceIPConfigurationArgs(
                                           name="hub-nva",
                                           subnet=network.SubnetArgs(
                                               id=hub_dmz.id
                                           ),
                                           private_ip_address="10.0.0.36",
                                           private_ip_allocation_method=network.IPAllocationMethod.STATIC
                                       )],
                                       )


hub_nva_vm = compute.VirtualMachine("hub-nva-vm",
                                    resource_group_name=hub_nva_rg.name,
                                    hardware_profile=compute.HardwareProfileArgs(
                                        vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2
                                    ),
                                    storage_profile=compute.StorageProfileArgs(
                                        image_reference=compute.ImageReferenceArgs(
                                            offer="ubuntu-24_04-lts",
                                            publisher="Canonical",
                                            sku="server",
                                            version="latest"
                                        ),
                                        os_disk=compute.OSDiskArgs(
                                            caching=compute.CachingTypes.READ_WRITE,
                                            create_option="FromImage",
                                            managed_disk=compute.ManagedDiskParametersArgs(
                                                storage_account_type=compute.StorageAccountTypes.STANDARD_LRS
                                            )
                                        ),
                                    ),
                                    os_profile=compute.OSProfileArgs(
                                        computer_name="pk-hum-nva-vm",
                                        admin_password=pw.result,
                                        admin_username="pk-admin",
                                        linux_configuration=compute.LinuxConfigurationArgs(
                                            disable_password_authentication=False
                                        )
                                    ),
                                    network_profile=compute.NetworkProfileArgs(
                                        network_interfaces=[compute.NetworkInterfaceReferenceArgs(
                                            id=hub_nva_nic.id
                                        )]
                                    )
                                    )

compute.VirtualMachineExtension("enable-routes",
                                vm_name=hub_nva_vm.name,
                                publisher="Microsoft.Azure.Extensions",
                                resource_group_name=hub_nva_rg.name,
                                type="CustomScript",
                                type_handler_version="2.0",
                                settings={
                                    "fileUris": [
                                        "https://raw.githubusercontent.com/lonegunmanb/reference-architectures/refs/heads/master/scripts/linux/enable-ip-forwarding.sh"
                                    ],
                                    "commandToExecute": "bash enable-ip-forwarding.sh"
                                }
                                )


# From: https://learn.microsoft.com/en-us/azure/developer/terraform/hub-spoke-spoke-network

spoke1_vnet_rg = ResourceGroup("spoke1-vnet-rg")

export("spoke1_vnet_rg", spoke1_vnet_rg.name)

spoke1_vnet = network.VirtualNetwork("spoke1-vnet",
    resource_group_name=spoke1_vnet_rg.name,
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.1.0.0/16"]
    )
)

spoke1_mgmt = network.Subnet("spoke1-mgmt",
                             resource_group_name=spoke1_vnet_rg.name,
                             virtual_network_name=spoke1_vnet.name,
                             address_prefixes=["10.1.0.64/27"],
                            #  route_table=network.RouteTableArgs(
                            #      id=spoke1_rt.id
                            #  )
                             )

spoke1_workload = network.Subnet("spoke1-workload",
                             resource_group_name=spoke1_vnet_rg.name,
                             virtual_network_name=spoke1_vnet.name,
                             address_prefixes=["10.1.1.0/24"],
                             route_table=network.RouteTableArgs(
                                 id=spoke1_rt.id
                             )
                             )

spoke1_hub_peer = network.VirtualNetworkPeering("spoke1-hub-peer",
    resource_group_name=spoke1_vnet_rg.name,
    virtual_network_name=spoke1_vnet.name,
    remote_virtual_network=network.SubResourceArgs(
        id=hub_vnet.id
    ),
    allow_virtual_network_access=True,
    allow_forwarded_traffic=True,
    allow_gateway_transit=False,
    use_remote_gateways=True,
    opts=ResourceOptions(depends_on=[hub_vnet_gateway])
)

hub_spoke1_peer = network.VirtualNetworkPeering("hub-spoke1-peer",
    resource_group_name=hub_vnet_rg.name,
    virtual_network_name=hub_vnet.name,
    remote_virtual_network=network.SubResourceArgs(
        id=spoke1_vnet.id
    ),
    allow_virtual_network_access=True,
    allow_forwarded_traffic=True,
    allow_gateway_transit=True,
    use_remote_gateways=False,
    opts=ResourceOptions(depends_on=[hub_vnet_gateway])
)

# spoke2_vnet_rg = ResourceGroup("spoke2-vnet-rg")

# spoke2_vnet = network.VirtualNetwork("spoke2-vnet",
#     resource_group_name=spoke2_vnet_rg.name,
#     address_space=network.AddressSpaceArgs(
#         address_prefixes=["10.2.0.0/16"]
#     )
# )

# spoke2_mgmt = network.Subnet("spoke2-mgmt",
#                              resource_group_name=spoke2_vnet_rg.name,
#                              virtual_network_name=spoke2_vnet.name,
#                              address_prefixes=["10.2.0.64/27"],
#                              route_table=network.RouteTableArgs(
#                                  id=spoke2_rt.id
#                              )
#                              )

# spoke2_workload = network.Subnet("spoke2-workload",
#                              resource_group_name=spoke2_vnet_rg.name,
#                              virtual_network_name=spoke2_vnet.name,
#                              address_prefixes=["10.2.1.0/24"],
#                              route_table=network.RouteTableArgs(
#                                  id=spoke2_rt.id
#                              )
#                              )

# spoke2_hub_peer = network.VirtualNetworkPeering("spoke2-hub-peer",
#     resource_group_name=spoke2_vnet_rg.name,
#     virtual_network_name=spoke2_vnet.name,
#     remote_virtual_network=network.SubResourceArgs(
#         id=hub_vnet.id
#     ),
#     allow_virtual_network_access=True,
#     allow_forwarded_traffic=True,
#     allow_gateway_transit=False,
#     use_remote_gateways=True,
#     opts=ResourceOptions(depends_on=[hub_vnet_gateway])
# )

# hub_spoke2_peer = network.VirtualNetworkPeering("hub-spoke2-peer",
#     resource_group_name=hub_vnet_rg.name,
#     virtual_network_name=hub_vnet.name,
#     remote_virtual_network=network.SubResourceArgs(
#         id=spoke2_vnet.id
#     ),
#     allow_virtual_network_access=True,
#     allow_forwarded_traffic=True,
#     allow_gateway_transit=True,
#     use_remote_gateways=False,
#     opts=ResourceOptions(depends_on=[hub_vnet_gateway])
# )