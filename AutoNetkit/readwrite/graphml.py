# -*- coding: utf-8 -*-
"""
Graphml
"""
__author__ = "\n".join(['Simon Knight'])
#    Copyright (C) 2009-2011 by Simon Knight, Hung Nguyen

__all__ = ['load_graphml']

import networkx as nx
import itertools
import pprint
import AutoNetkit as ank
import os

#TODO: make work with network object not self.ank
#TODO: split into smaller (not exported) functions
import logging
LOG = logging.getLogger("ANK")

config = ank.config
settings = config.settings

def load_graphml(net_file, default_asn = 1):
    """
    Loads a network from Graphml into AutoNetkit.
    """
    default_device_type = 'router'
    path, filename = os.path.split(net_file)
    net_name = os.path.splitext(filename)[0]
    # get full path
    path =  os.path.abspath(path)
    pickle_dir = path + os.sep + "cache"
    if not os.path.isdir(pickle_dir):
        os.mkdir(pickle_dir)
    pickle_file = "{0}/{1}.pickle".format(pickle_dir, net_name)
#TODO: re-enable pickle
    if (False and os.path.isfile(pickle_file) and
        os.stat(net_file).st_mtime < os.stat(pickle_file).st_mtime):
        # Pickle file exists, and source_file is older
        input_graph = nx.read_gpickle(pickle_file)
    else:
        # No pickle file, or is outdated
        input_graph = nx.read_graphml(net_file)
        nx.write_gpickle(input_graph, pickle_file)

    nodes_with_H_set = sum(1 for n in input_graph if input_graph.node[n].get('H'))
    if nodes_with_H_set == len(input_graph):
#all nodes have H set, apply graph products
        LOG.info("All nodes in graph %s have H attribute set, applying graph product" % net_name)
        input_graph = ank.graph_product(net_file)
        print "input graph is", input_graph
        if not input_graph:
            LOG.warn("Unable to load graph %s" % net_file)
            return
# remap ('a', 2) -> 'a2'
        nx.relabel_nodes(input_graph, 
                dict( (n, "%s_%s" % (n[0], n[1])) for n in input_graph), copy=False)

# a->z for renaming
# try intially for a, b, c, d
    letters = (chr(x) for x in range(97,123)) 

# set any blank labels to be letter for gh-122
    empty_label_nodes = [n for n, d in input_graph.nodes(data=True) if not d.get("label")]
    if len(empty_label_nodes) > 26:
# use aa, ab, ac, etc
        single_letters = list(letters)
        letters = ("%s%s" % (a, b) for a in single_letters for b in single_letters)
    mapping = dict( (n, letters.next()) for n in empty_label_nodes)
    input_graph = nx.relabel_nodes(input_graph, mapping)
   
    # set label if unset
    for node, data in input_graph.nodes(data=True):
        if 'label' not in data:
            input_graph.node[node]['label'] = node
        if 'device_type' not in data:
            input_graph.node[node]['device_type'] = default_device_type 
            LOG.debug("Setting device_type for %s to %s" % ( 
                input_graph.node[node]['label'], default_device_type) )

    # check each node has an ASN allocated
    for node, data in input_graph.nodes_iter(data=True):
        if not 'asn' in data:
            LOG.debug("No asn set for node %s using default of %s" % 
                     (data['label'],
                      default_asn))
            input_graph.node[node]['asn'] = default_asn
        else:
            input_graph.node[node]['asn'] = int(data['asn']) # ensure is integer

    # Convert to single-edge and then back to directed, to ensure edge in both
    # directions
    #TODO: Document this that assume bi-directional

    input_graph = nx.Graph(input_graph)
    input_graph = input_graph.to_directed()
    
    return input_graph
