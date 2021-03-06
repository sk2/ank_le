<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN"
   "http://www.w3.org/TR/html4/strict.dtd">

<html lang="en">
<head>
  <link rel="stylesheet" href=${css_filename} type="text/css">
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
	<title>AutoNetkit Network Summary</title>
</head>
<body>                   
<h1>AutoNetkit Network Summary</h1>        

<h2>Plots</h2>
<ul>
  <li><a href="plot.html">Physical Graph</a></li>     
  <li><a href="ip.html">IP Graph</a></li>
  <li><a href="igp.html">IGP Graph</a></li>
  <li><a href="ibgp.html">iBGP Graph</a></li>
  <li><a href="ebgp.html">eBGP Graph</a></li>
  <li><a href="dns.html">DNS Hierarchy Graph</a></li>     
  <li><a href="dns_auth.html">DNS Authority Graph</a></li>

</ul>

<h2>Network Statistics</h2>
	<table>
		<tr> <th>Total Devices:</th> <td>${network_stats['device_count']}</td> </tr>     
		<tr> <th>Total Routers:</th> <td>${network_stats['router_count']}</td> </tr>     
		<tr> <th>Total Servers:</th> <td>${network_stats['server_count']}</td> </tr>     
		<tr> <th>Total Links:</th> <td>${network_stats['edge_count']}</
			td> </tr>       
		<tr> <th>Autonomous Systems:</th> <td>${network_stats['as_count']}</td> </tr>                         
	</table>

% for asn, as_data in as_stats.items():
<h2>AS${asn}</h2>
	<table>
		<tr> <th>Router</th> <th>Loopback</th> </tr>     
    %for router, loopback in as_data['loopbacks']:
    <tr> <td>${router}</td> <td>${loopback}</ td> </tr>       
      % endfor
  </table>

  % for node, node_data in sorted(as_data['node_list'].items()):
  <h3>${node}</h3>
  ${len(node_data['interface_list'])} interfaces

 <table>
    <tr><td>Interfaces</td><td>iBGP Peers</td><td>eBGP Peers</td></tr>
    <tr><td>
	<table>
    <tr> <th>Neighbour</th> <th>Subnet</th> </tr>     
    %for neigh, subnet in node_data['interface_list']:
    <tr> <td>${neigh}</td> <td>${subnet}</ td> </tr>       
      % endfor
  </table>

</td>
<td>
  
  <table>
    <tr> <th>Neighbour</th> <th>Loopback</th> </tr>     
    %for neigh, subnet in node_data['ibgp_list']:
    <tr> <td>${neigh}</td> <td>${subnet}</ td> </tr>       
      % endfor
    </table>


  </td>
  <td>
  <table>
    <tr> <th>Neighbour</th> <th>Loopback</th> </tr>     
    %for neigh, subnet in node_data['ebgp_list']:
    <tr> <td>${neigh}</td> <td>${subnet}</ td> </tr>       
      % endfor
  </table>
</td>
</tr>




</table>
  % endfor

  <h2>Virtual Nodes</h2>

  % for node, node_data in sorted(as_data['virtual_nodes'].items()):
  <h3>${node}</h3>

    <table>
      <tr> <th>Local IP</th> <th>Neighbour</th> <th>Neighbour IP </th></tr>     
    %for local_ip, remote_ip, destination in node_data['links']:
    <tr> <td>${local_ip}</td> <td>${destination}</ td> <td> ${remote_ip} </td> </tr>       
      % endfor
    </table>

%endfor

  <hr>

%endfor
  
<p>
Generated at ${timestamp} by <a href="http://packages.python.org/AutoNetkit/">AutoNetkit</a>
</body>
</html>
