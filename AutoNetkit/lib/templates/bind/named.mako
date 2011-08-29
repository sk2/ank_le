options {
    	allow-query { "any"; };
};   


//zone for each AS
zone "${domain}." IN {
	type master;
	file "/etc/bind/db.${domain}";  
	allow-query { "any"; };
};      
                 
   
## Entries
% for e in entry_list:
zone "${e['identifier']}.in-addr.arpa" {
	type master; 
	file "${e['bind_dir']}/db.${e['identifier']}";        
	allow-query { "any"; };
};	     
%endfor
       

	// prime the server with knowledge of the root servers
zone "." {
        type hint;
        file "/etc/bind/db.root";       
	};
                             



%if logging:
logging {
category "default" { "debug"; };
category "general" { "debug"; };
category "database" { "debug"; };
category "security" { "debug"; };
category "config" { "debug"; };
category "resolver" { "debug"; };
category "xfer-in" { "debug"; };
category "xfer-out" { "debug"; };
category "notify" { "debug"; };
category "client" { "debug"; };
category "unmatched" { "debug"; };
category "network" { "debug"; };
category "update" { "debug"; };
category "queries" { "debug"; };
category "dispatch" { "debug"; };
category "dnssec" { "debug"; };
category "lame-servers" { "debug"; };
channel "debug" {
file "/tmp/nameddbg" versions 2 size 50m;
print-time yes;
print-category yes;
};
};          
%endif      