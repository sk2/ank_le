"""
Generate dynagen configuration files for a network 

Config options
===============

autonetkit.cfg::

    [Dynagen]
        image = /dev/null
        working dir = /home/autonetkit/
        model = 7200
        interfaces = "FastEthernet0/0", "FastEthernet0/1", "FastEthernet1/0", "FastEthernet1/1", "FastEthernet2/0", "FastEthernet2/1"
        [[Slots]]
            slot1 = PA-2FE-TX
            slot2 = PA-2FE-TX
        [[Options]]
            idlepc = 0x6085af60
            ram = 128
        [[Hypervisor]]
            server = 127.0.0.1
            port = 7202

lab.net::

    [[7202]]
        image = /dev/null
        ghostios = True
        chassis = 7200   
		idlepc = 0x6085af60
		ram = 128
		slot1 = PA-2FE-TX
		slot2 = PA-2FE-TX  

can put any ``key = val`` line into the *options* section of the config file.
Same for slots, so ``S0/0 = r2 s0/0`` is also valid.


"""
from mako.lookup import TemplateLookup    

from pkg_resources import resource_filename         
import pkg_resources

import os

import logging
LOG = logging.getLogger("ANK")

import shutil      
import glob
import time
import itertools
import tarfile

import AutoNetkit as ank
#from ank.config import config
from AutoNetkit import config
settings = config.settings          

import pprint   
pp = pprint.PrettyPrinter(indent=4)      

# Check can write to template cache directory
template_cache_dir = config.template_cache_dir

if (os.path.exists(template_cache_dir) 
    and not os.access(template_cache_dir, os.W_OK)):
    LOG.info("Unable to write to cache dir %s, "
             "template caching disabled" % template_cache_dir)
    template_cache_dir = None

template_dir =  resource_filename("AutoNetkit","lib/templates")   
lookup = TemplateLookup(directories=[ template_dir ],
                        module_directory= template_cache_dir,
                        #cache_type='memory',
                        #cache_enabled=True,
                       )
                
import os    

#TODO: add more detailed exception handling to catch writing errors
# eg for each subdir of templates

#TODO: make this a module
#TODO: make this a netkit compiler plugin
#TODO: clear up label vs node id

#TODO: Move these into a netkit helper function*****
def lab_dir():
    #TODO: make use config
    return config.dynagen_dir

def router_conf_dir():
    #TODO: make use config
    #return config.lab_dir
    return os.path.join(lab_dir(), "configs")

def router_conf_file(network, router):
    """Returns filename for config file for router"""
    return "%s.conf" % router.folder_name

def router_conf_path(network, router):
    """ Returns full path to router config file"""
    r_file = router_conf_file(network, router)
    return os.path.join(router_conf_dir(), r_file)


class dynagenCompiler:  
    """Compiler main"""

    def __init__(self, network, igp, services, image, hypervisor_server, hypervisor_port):
        self.network = network
        self.services = services
        self.image = image
        self.hypervisor_server = hypervisor_server
        self.hypervisor_port = hypervisor_port
        self.igp = igp
        self.interface_names = config.settings['Dynagen']['interfaces']
#TODO: allow user to specify these in config
        self.interface_mapping = {"FastEthernet": "f",
                'Ethernet': 'e',
                }
        self.default_weight = 1

    def initialise(self):  
        """Creates lab folder structure"""
        if not os.path.isdir(lab_dir()):
            os.mkdir(lab_dir())
        else:
            for item in glob.iglob(os.path.join(lab_dir(), "*")):
                if os.path.isdir(item):
                    shutil.rmtree(item)           
                else:
                    os.unlink(item)

        if not os.path.isdir(router_conf_dir()):
            os.mkdir(router_conf_dir()) 

        return

    def configure_interfaces(self, device):
        LOG.debug("Configuring interfaces for %s" % self.network.fqdn(device))
        """Interface configuration"""
        lo_ip = self.network.lo_ip(device)
        interfaces = []

        interfaces.append({
            'id':          'lo0',
            'ip':           lo_ip.ip,
            'netmask':      lo_ip.netmask,
            'wildcard':      lo_ip.hostmask,
            'prefixlen':    lo_ip.prefixlen,
            'network':       lo_ip.network,
            'net_ent_title': ank.ip_to_net_ent_title_ios(lo_ip.ip),
            'description': 'Loopback',
        })

        for src, dst, data in self.network.graph.edges(device, data=True):
            subnet = data['sn']
            int_id = self.int_id(data['id'])
            description = 'Interface %s -> %s' % (
                    ank.fqdn(self.network, src), 
                    ank.fqdn(self.network, dst))

# Interface information for router config
            interfaces.append({
                'id':          int_id,
                'ip':           data['ip'],
                'network':       subnet.network,
                'prefixlen':    subnet.prefixlen,
                'netmask':    subnet.netmask,
                'wildcard':      subnet.hostmask,
                'broadcast':    subnet.broadcast,
                'description':  description,
                'weight':   data.get('weight', self.default_weight),
            })

        return interfaces

    def configure_igp(self, router, igp_graph, ebgp_graph):
        """igp configuration"""
        LOG.debug("Configuring IGP for %s" % self.network.label(router))
#TODO: get area from router
        default_area = 0
        igp_interfaces = []
        if igp_graph.degree(router) > 0:
            # Only start IGP process if IGP links
#TODO: make loopback a network mask so don't have to do "0.0.0.0"
            igp_interfaces.append({ 'id': 'lo0', 'wildcard': router.lo_ip.hostmask,
                'passive': False,
                'network': router.lo_ip.network,
                'area': default_area, 'weight': self.default_weight,
                })
            for src, dst, data in igp_graph.edges(router, data=True):
                int_id = self.int_id(data['id'])
                subnet = self.network.graph[src][dst]['sn']
                description = 'Interface %s -> %s' % (
                        ank.fqdn(self.network, src), 
                        ank.fqdn(self.network, dst))
                igp_interfaces.append({
                    'id':       int_id,
                    'weight':   data.get('weight', self.default_weight),
                    'area':   data.get('area', default_area),
                    'network': str(subnet.network),
                    'description': description,
                    'wildcard':      str(subnet.hostmask),
                    })

# Need to add eBGP edges as passive interfaces
            for src, dst in ebgp_graph.edges(router):
# Get relevant edges from ebgp_graph, and edge data from physical graph
                data = self.network.graph[src][dst]
                int_id = self.int_id(data['id'])
                subnet = self.network.graph[src][dst]['sn']
                description = 'Interface %s -> %s' % (
                    ank.fqdn(self.network, src), 
                    ank.fqdn(self.network, dst))
                igp_interfaces.append({
                    'id':       int_id,
                    'weight':   data.get('weight', self.default_weight),
                    'area':   data.get('area', default_area),
                    'description': description,
                    'passive': True,
                    'network': str(subnet.network),
                    'wildcard':      str(subnet.hostmask),
                    })

        return igp_interfaces

    def configure_bgp(self, router, physical_graph, ibgp_graph, ebgp_graph):
        LOG.debug("Configuring BGP for %s" % self.network.fqdn(router))
        """ BGP configuration"""
#TODO: Don't configure iBGP or eBGP if no eBGP edges
# need to pass correct blank dicts to templates then...

#TODO: put comments in for IOS bgp peerings
        # route maps
        bgp_groups = {}
        route_maps = []
        ibgp_neighbor_list = []
        ibgp_rr_client_list = []
        route_map_groups = {}

        if router in ibgp_graph:
            for src, neigh, data in ibgp_graph.edges(router, data=True):
                route_maps_in = self.network.g_session[neigh][router]['ingress']
                rm_group_name_in = None
                if len(route_maps_in):
                    rm_group_name_in = "rm_%s_in" % neigh.folder_name
                    route_map_groups[rm_group_name_in] = [match_tuple 
                            for route_map in route_maps_in
                            for match_tuple in route_map.match_tuples]

                route_maps_out = self.network.g_session[router][neigh]['egress']
                rm_group_name_out = None
                if len(route_maps_out):
                    rm_group_name_in = "rm_%s_out" % neigh.folder_name
                    route_map_groups[rm_group_name_out] = [match_tuple 
                            for route_map in route_maps_out
                            for match_tuple in route_map.match_tuples]

                description = data.get("rr_dir") + " to " + ank.fqdn(self.network, neigh)
                if data.get('rr_dir') == 'down':
                    ibgp_rr_client_list.append(
                            {
                                'id':  self.network.lo_ip(neigh).ip,
                                'description':      description,
                                'route_maps_in': rm_group_name_in,
                                'route_maps_out': rm_group_name_out,
                                })
                elif (data.get('rr_dir') in set(['up', 'over', 'peer'])
                        or data.get('rr_dir') is None):
                    ibgp_neighbor_list.append(
                            {
                                'id':  self.network.lo_ip(neigh).ip,
                                'description':      description,
                                'route_maps_in': rm_group_name_in,
                                'route_maps_out': rm_group_name_out,
                                })

        bgp_groups['internal_peers'] = {
            'type': 'internal',
            'neighbors': ibgp_neighbor_list
            }
        if len(ibgp_rr_client_list):
            bgp_groups['internal_rr'] = {
                    'type': 'internal',
                    'neighbors': ibgp_rr_client_list,
                    'cluster': self.network.lo_ip(router).ip,
                    }

        if router in ebgp_graph:
            external_peers = []
            for peer in ebgp_graph.neighbors(router):
                route_maps_in = self.network.g_session[peer][router]['ingress']
                rm_group_name_in = None
                if len(route_maps_in):
                    rm_group_name_in = "rm_%s_in" % peer.folder_name
                    route_map_groups[rm_group_name_in] = [match_tuple 
                            for route_map in route_maps_in
                            for match_tuple in route_map.match_tuples]

# Now need to update the sequence numbers for the flattened route maps

                route_maps_out = self.network.g_session[router][peer]['egress']
                rm_group_name_out = None
                if len(route_maps_out):
                    rm_group_name_out = "rm_%s_out" % peer.folder_name
                    route_map_groups[rm_group_name_out] = [match_tuple 
                            for route_map in route_maps_out
                            for match_tuple in route_map.match_tuples]

                peer_ip = physical_graph[peer][router]['ip'] 

                external_peers.append({
                    'id': peer_ip, 
                    'route_maps_in': rm_group_name_in,
                    'route_maps_out': rm_group_name_out,
                    'peer_as': self.network.asn(peer)})
            bgp_groups['external_peers'] = {
                    'type': 'external', 
                    'neighbors': external_peers}

# Ensure only one copy of each route map, can't use set due to list inside tuples (which won't hash)
# Use dict indexed by name, and then extract the dict items, dict hashing ensures only one route map per name
        community_lists = {}
        prefix_lists = {}
        node_bgp_data = self.network.g_session.node.get(router)
        if node_bgp_data:
            community_lists = node_bgp_data.get('tags')
            prefix_lists = node_bgp_data.get('prefixes')
        policy_options = {
                'community_lists': community_lists,
                'prefix_lists': prefix_lists,
                'route_maps': route_map_groups,
                }

        return (bgp_groups, policy_options)

    def configure_ios(self):
        """ Configures IOS"""
        LOG.info("Configuring IOS")
        ios_template = lookup.get_template("cisco/ios.mako")
        ank_version = pkg_resources.get_distribution("AutoNetkit").version
        date = time.strftime("%Y-%m-%d %H:%M", time.localtime())

        physical_graph = self.network.graph
        igp_graph = ank.igp_graph(self.network)
        ibgp_graph = ank.get_ibgp_graph(self.network)
        ebgp_graph = ank.get_ebgp_graph(self.network)

        for router in self.network.routers():
            #check interfaces feasible
#TODO: make in_degree a property eg link_count
            asn = self.network.asn(router)
            network_list = []
            lo_ip = self.network.lo_ip(router)

            interfaces = self.configure_interfaces(router)
            igp_interfaces = self.configure_igp(router, igp_graph,ebgp_graph)
            (bgp_groups, policy_options) = self.configure_bgp(router, physical_graph, ibgp_graph, ebgp_graph)

            # advertise AS subnet
            adv_subnet = self.network.ip_as_allocs[asn]
            if not adv_subnet in network_list:
                network_list.append(adv_subnet)

            juniper_filename = router_conf_path(self.network, router)
            with open( juniper_filename, 'wb') as f_jun:
                f_jun.write( ios_template.render(
                    hostname = router.rtr_folder_name,
                    username = 'autonetkit',
                    interfaces=interfaces,
                    igp_interfaces=igp_interfaces,
                    igp_protocol = self.igp,
# explicit protocol
                    use_isis = self.igp == 'isis',
                    asn = asn,
                    lo_ip=lo_ip,
                    #TODO: make router have property "identifier" which maps to lo_ip
                    router_id = lo_ip.ip,
                    network_list = network_list,
                    bgp_groups = bgp_groups,
                    policy_options = policy_options,
                    ank_version = ank_version,
                    date = date,
                    ))

    
    def int_id(self, interface_id):
        #TODO: try/except in case index not found
        try:
            return self.interface_names[interface_id]
        except IndexError:
            LOG.warn("Unable to allocate interface_id %s, defined"
                    " interfaces: %s. Using first interface of %s" % ( interface_id, 
                        ", ".join("%s: %s" % (index, id) for index, id in enumerate(self.interface_names)),
                        self.interface_names[0]))
            return self.interface_names[0]

    def dynagen_interface_name(self, interface_id):
        """ FastEthernet1/0 -> f1/0"""
# remove any numbers
        numbers = set("0123456789")
        interface_name = "".join(itertools.takewhile(lambda x: x not in numbers, interface_id))
        interface_number = interface_id.replace(interface_name, "")
        try:
            retval = "%s%s" % (self.interface_mapping[interface_name], interface_number)
        except KeyError:
            LOG.warn("No Dynagen lab.net interface mapping defined for interface type %s" % interface_name)
        return retval

    def configure_dynagen(self):  
        """Generates dynagen specific configuration files."""
        LOG.info("Configuring Dynagen")

        # Location of IOS binary

        # Set up routers
        lab_template = lookup.get_template("dynagen/topology.mako")

        # Counter starting at 2000, eg 2000, 2001, 2002, etc
        console_ports = itertools.count(2000)

        #NOTE this must be a full path!
        server_config_dir = os.path.join(config.settings['Dynagen']['working dir'], lab_dir())
        working_dir ="/tmp"

        #TODO: need nice way to map ANK graph into feasible hardware graph

#TODO: see what chassis is used for
        chassis = config.settings['Dynagen']['model']
        model = config.settings['Dynagen']['model']
        slots = config.settings['Dynagen']['Slots']
        options = config.settings['Dynagen']['Options']

        # ugly alias
#TODO: remove this
        graph = self.network.graph

        all_router_info = {}

        #TODO: make this use dynagen tagged nodes
        for router in sorted(self.network.routers()):
            router_info = {}

            data = graph.node[router]
            router_info['hostname'] = router.fqdn

            rtr_console_port = console_ports.next()
            router_info['console'] =  rtr_console_port
            self.network.graph.node[router]['dynagen_console_port'] = rtr_console_port
            #TODO: tidy this up - want relative reference to config dir
            rtr_conf_file = os.path.join("configs", "%s.conf" % router.folder_name)
            #router_info['cnfg'] = rtr_conf_file
            # Absolute configs for remote dynagen deployment
#TODO: make this dependent on remote host - if localhost then don't use
# and if do use, then 
            rtr_conf_file_with_path = os.path.join(server_config_dir, rtr_conf_file)
            #router_info['cnfg'] = os.path.abspath(rtr_conf_file_with_path)
            router_info['cnfg'] = rtr_conf_file_with_path

            # Max of 3 connections out
            # todo: check symmetric
            router_links = []
            router_info['slot1'] = "NM-4E"
            for src, dst, data in sorted(graph.edges(router, data=True)):
                if dst.is_router:
                    # Src is node, dst is router connected to. Link data in data
                    local_id = data['id']
                    remote_id = graph.edge[dst][src]['id']
                    local_cisco_id = self.dynagen_interface_name(self.int_id(local_id))
                    remote_cisco_id = self.dynagen_interface_name(self.int_id(remote_id))
                    remote_hostname = ank.fqdn(self.network, dst)
                    router_links.append( (local_cisco_id, remote_cisco_id,
                                            remote_hostname))

            # Store links
            router_info['links'] = router_links

            # and store info
            all_router_info[router] = router_info

        #pprint.pprint(all_router_info)
        lab_file = os.path.join(lab_dir(), "lab.net")
        with open( lab_file, 'wb') as f_lab:
            f_lab.write( lab_template.render(
                image = self.image,
                hypervisor_port = self.hypervisor_port,
                hypervisor_server = self.hypervisor_server,
                all_router_info = all_router_info,   
                working_dir = working_dir,
                chassis = chassis,
                model = model,
                slots = slots,
                options = options,
                ))

        return


    def configure(self):
        self.configure_dynagen()
        self.configure_ios()
# create .tgz
        tar_filename = "dynagen_%s.tar.gz" % time.strftime("%Y%m%d_%H%M",
                time.localtime())
        tar = tarfile.open(os.path.join(config.ank_main_dir,
            tar_filename), "w:gz")
        tar.add(lab_dir())
        self.network.compiled_labs['dynagen'] = tar_filename
        tar.close()
