# -*- coding: utf-8 -*-
"""
Query
"""
__author__ = "\n".join(['Simon Knight'])
#    Copyright (C) 2009-2011 by Simon Knight, Hung Nguyen

import networkx as nx
import AutoNetkit as ank
import logging
LOG = logging.getLogger("ANK")
#TODO: only import what is needed
from pyparsing import *
import operator

graph = nx.read_gpickle("condensed_west_europe.pickle")
#print graph.nodes(data=True)

##### parser
# Node selection syntax

attribute = Word(alphas, alphanums+'_').setResultsName("attribute")
#TODO: check how evaluation examples on pyparsing work out which comparison/operator is used

lt = Literal("<").setResultsName("<")
le = Literal("<=").setResultsName("<=")
eq = Literal("=").setResultsName("=")
ne = Literal("!=").setResultsName("!=")
ge = Literal(">=").setResultsName(">=")
gt = Literal(">").setResultsName(">")

opn = {
        '<': operator.lt,
        '<=': operator.le,
        '=': operator.eq,
        '>=': operator.ge,
        '>': operator.gt,
        '&': set.intersection,
        '|': set.union,
        }

# Both are of comparison to access in same manner when evaluating
comparison = (lt | le | eq | ne | ge | gt).setResultsName("comparison")
stringComparison = (eq | ne).setResultsName("comparison")
#
#quoted string is already present
integer = Word(nums).setResultsName("value").setParseAction(lambda t: int(t[0]))

#TODO: allow parentheses? - should be ok as pass to the python parser

boolean_and = Literal("&").setResultsName("&")
boolean_or = Literal("|").setResultsName("|")
boolean = (boolean_and | boolean_or).setResultsName("boolean")

numericQuery = Group(attribute + comparison + integer).setResultsName( "numericQuery")

stringValues = (Word(alphanums) | quotedString.setParseAction(removeQuotes)).setResultsName("value")

stringQuery =  Group(attribute + stringComparison + stringValues).setResultsName( "stringQuery")

singleQuery = numericQuery | stringQuery
query = singleQuery + ZeroOrMore(boolean + singleQuery)

tests = [
        'Network = ACOnet & asn = 1853 & Latitude < 50',
        'Network = ACOnet & Longitude < 14',
        'asn = 680 & label = HAN',
        'Network = GEANT',
        'Network = GEANT & Country = Greece',
        'Network = GEANT & Latitude > 55',
        'Network = GEANT & type = "Fully Featured"',
        ]

def evaluate(stack):
    if len(stack) == 1:
        return set(stack.pop())
    else:
        a = set(stack.pop())
        op = stack.pop()
        return opn[op](a, evaluate(stack))



for test in tests:
    print "--------------------------"
    print test
    result = query.parseString(test)
    #print result.dump()

    def comp_fn_string(token, n):
        return opn[token.comparison](graph.node[n].get(token.attribute), token.value)

    def comp_fn_numeric(token, n):
        return opn[token.comparison](float(graph.node[n].get(token.attribute)), token.value)

    stack = []

    for token in result:
        if token in boolean:
            stack.append(token)
            continue

# different function depending on value type: numeric or string

        if isinstance(token.value, str):
            comp_fn = comp_fn_string
        if isinstance(token.value, int):
            comp_fn = comp_fn_numeric
       
        if comp_fn:
            #TODO: change to generator expressions and evaluate as sets in the evaluate function
            result_set = set(n for n in graph if token.attribute in graph.node[n] and comp_fn(token, n) )
            stack.append(result_set)

    final_set = evaluate(stack)
    #print final_set
    print ", ".join(graph.node[n].get('label') for n in final_set)


# can set parse action to be return string?

#TODO: create function from the parsed result
# eg a lambda, and then apply this function to the nodes in the graph
# eg G.node[n].get(attribute) = "quotedstring"  operator 