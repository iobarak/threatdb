#!/usr/bin/python

#####
##### RST Threat Database add-on for Splunk Enterprise
##### Copyright (c) 2016 RST Cloud
##### https://www.rstcloud.net/
##### 
##### Author: Nikolay Arefiev
##### Contributor: Yury Sergeev
##### 

import sys
import re
import redis
from netaddr import *

avail_threattypes = [
               "emergingthreats", "binarydefense", "alienvaultreputation", 
               "sslipblacklist", "ransomwaretracker", 
               "blocklistdessh", "blocklistdeapache", "blocklistdebots", 
               "cinsscore", "sblam", "stopforumspam", 
               "atlasattacks", "atlasfastflux", "atlasphishing", "atlasscans",
               "myip","botvrij", "darklist", "labssnort", "openbl"
               ]

if len(sys.argv) != 4:
    print "Usage: python threatuploader.py (ipdb|domaindb) filetype filepath"
    print "available filetypes: "
    sys.exit(1)

db_type = sys.argv[1]
threatfile_type = sys.argv[2]
threatfile_path = sys.argv[3]

if threatfile_type not in avail_threattypes:
    print "available filetypes: ["+", ".join(avail_threattypes)+"]"
    sys.exit(1)

redis_server = '127.0.0.1'
redis_port = 6379
redis_ipdb = 0
redis_domaindb=1

# TTL of entry in the database
threat_ttl=172800 # 48 hours

def threatscore_calc(threttype):
    out=0
    # AlienVailt DB threat types
    if threttype == 'Malicious Host':
        out=20
    if threttype == 'Scanning Host':
        out=5
    if threttype == 'Spamming Host':
        out=10
    return str(out) 

# Upload parsed data to Redis
# rpipe - redis-py pipeline object
# ltype - 'ip'|'net'
# lobj - ip address| CIDR
# thsource - threat source
# thtype - threat category
# thscore - threat score
# thttl - TTL of key in Redis
def upload2redis(rpipe, ltype, lobj, thsource, thtype, thscore, thttl):
    try:
        # Add the key to redis (ip|net:IPaddress|CIDR) => List [ThreatSource1:score1, ThreatSource2:score1] 
        rpipe.sadd(ltype+':'+lobj, "%s:%s:%s" % (thsource, thtype, str(thscore))).expire(ltype+':'+lobj,thttl)
        # Add to index 'net:index'=> Set [CIDR]
        if ltype == 'net':
            rpipe.sadd('net:index',lobj)
    except:
        print 'status=error, message="Cant insert data to Redis"'
        sys.exit(1)

# Parse simple feeds with IPs single column and comments rows 
def simpleparser(file_path, red, threatscore, threattype, current_threatsource):
    red_pipe = red.pipeline()
    iplist_object = open(file_path, "r")    
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '' or line[0] == '#':
            continue
        try:    
            IPAddress(line)
            line_type='ip'
        except AddrFormatError:
            continue
        except ValueError:
            try:
                IPNetwork(line)
                line_type='net'
            except AddrFormatError:
                continue
            except ValueError:
                continue 

        upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)
        
    red_pipe.execute()
    iplist_object.close()
        
def parse_emergingthreats(file_path, red):
    threatscore = 10
    threattype = 'Compromised IP'
    
    red_pipe = red.pipeline()
    iplist_object = open(file_path, "r")
    current_threatsource=''
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '':
            continue
        # Parse Feodo
        if line == '# Feodo':
            current_threatsource = 'Feodo'
            continue
        if line == '# Zeus':
            current_threatsource = 'Zeus'
            continue
        if line == '# Spyeye':
            current_threatsource = 'Spyeye'
            continue
        if line == '# Palevo':
            current_threatsource = 'Palevo'
            continue
        if line == '#Spamhaus DROP Nets':
            current_threatsource = 'Spamhaus DROP Nets'
            continue
        if line == '#Dshield Top Attackers':
            current_threatsource = 'Dshield Top Attackers'
            continue            
        try:    
            IPAddress(line)
            line_type='ip'
        except AddrFormatError:
            continue
        except ValueError:
            try:
                IPNetwork(line)
                line_type='net'
            except AddrFormatError:
                continue
            except ValueError:
                continue 
            
        upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)

    red_pipe.execute()
    iplist_object.close()
    
def parse_binarydefense(fp, rd):
    simpleparser(fp, rd, 10, 'Compromised IP', 'Binarydefense.com')   
    
def parse_alienvaultreputation(file_path, red):
    threattype = ''
    
    red_pipe = red.pipeline()
    iplist_object = open(file_path, "r")    
    current_threatsource='AlienVault.com'
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '' or line[0] == '#':
            continue
        linetemp = line.split('#', 1)
        line = linetemp[0].strip()
        threattype = linetemp[1].split(';',1)[0].strip()
        threatscore = threatscore_calc(threattype)
        try:    
            IPAddress(line)
            line_type='ip'
        except AddrFormatError:
            continue
        except ValueError:
            try:
                IPNetwork(line)
                line_type='net'
            except AddrFormatError:
                continue
            except ValueError:
                continue 
        
        upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)
    
    red_pipe.execute()
    iplist_object.close()
    
def parse_sslipblacklist(file_path, red):
    threatscore = 5
    threattype = ''
    
    red_pipe = red.pipeline()     
    iplist_object = open(file_path, "r")    
    current_threatsource='SSLBL.abuse.ch'
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '' or line[0] == '#':
            continue
        linetemp = line.split(',')
        line = linetemp[0].strip()
        threattype = linetemp[2].strip()

        try:    
            IPAddress(line)
            line_type='ip'
        except AddrFormatError:
            continue
        except ValueError:
            try:
                IPNetwork(line)
                line_type='net'
            except AddrFormatError:
                continue
            except ValueError:
                continue 

        upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)
    
    red_pipe.execute()
    iplist_object.close()

def parse_ransomwaretracker(fp, rd):
    simpleparser(fp, rd, 10, 'Compromised IP', 'Ransomwaretracker.abuse.ch')   
    
def parse_blocklistdessh(fp, rd):
    simpleparser(fp, rd, 20, 'SSH attacks','Blocklist.de')
    
def parse_blocklistdeapache(fp, rd):
    simpleparser(fp, rd, 10, 'Apache attacks','Blocklist.de')

def parse_blocklistdebots(fp, rd):
    simpleparser(fp, rd, 10, 'Bad bots','Blocklist.de')

def parse_cinsscore(fp, rd):
    simpleparser(fp, rd, 10, 'Compromised IP','CINSScore.com')
    
def parse_sblam(fp, rd):
    simpleparser(fp, rd, 5, 'Web Form Spammer IP','Sblam.com')
    
def parse_stopforumspam(fp, rd):
    simpleparser(fp, rd, 5, 'Web Form Spammer IP','Stopforumspam.com')
   
def parse_arboratlas(file_path, red, threatscore, threattype):
    red_pipe = red.pipeline()
    
    iplist_object = open(file_path, "r")    
    current_threatsource='ATLAS.Arbor.net'
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '':
            continue
        regip = re.match('^([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}).*', row)
        if regip is not None:
            line = regip.group(1)
            try:    
                IPAddress(line)
                line_type='ip'
            except AddrFormatError:
                continue
            except ValueError:
                try:
                    IPNetwork(line)
                    line_type='net'
                except AddrFormatError:
                    continue
                except ValueError:
                    continue 
            upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)

    red_pipe.execute()
    iplist_object.close()
    
def parse_atlasattacks(fp, rd):
    parse_arboratlas(fp, rd, 20, 'Malicious Host')
def parse_atlasfastflux(fp, rd):
    parse_arboratlas(fp, rd, 10, 'Fast flux hosting')
def parse_atlasphishing(fp, rd):
    parse_arboratlas(fp, rd, 10, 'Phishing Host')
def parse_atlasscans(fp, rd):
    parse_arboratlas(fp, rd, 10, 'Scanning Host')

def parse_myip(file_path, red):
    threatscore = 10
    threattype = 'Bad bots'
    red_pipe = red.pipeline()
    
    iplist_object = open(file_path, "r")    
    current_threatsource='MYIP.ms'
    for row in iplist_object:
        line_type=''
        line = row[:-1]
        if line == '':
            continue
        regip = re.match('^([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}).*', row)
        if regip is not None:
            line = regip.group(1)
            try:    
                IPAddress(line)
                line_type='ip'
            except AddrFormatError:
                continue
            except ValueError:
                try:
                    IPNetwork(line)
                    line_type='net'
                except AddrFormatError:
                    continue
                except ValueError:
                    continue 
            upload2redis(red_pipe, line_type, line, current_threatsource, threattype, threatscore, threat_ttl)
            
    red_pipe.execute()
    iplist_object.close()
 
def parse_botvrij(fp, rd):
    simpleparser(fp, rd, 20, 'Malicious Host', 'Botvrij.eu')
    
def parse_darklist(fp, rd):
    simpleparser(fp, rd, 20, 'SSH attacks', 'Darklist.de')
    
def parse_labssnort(fp, rd):
    simpleparser(fp, rd, 20, 'Malicious Host', 'Labs.snort.org')
 
def parse_openbl(fp, rd):
    simpleparser(fp, rd, 10, 'Web attacks', 'OpenBL.org')
        
def make_redisconn(conn_db):
    try:
        redis_pool = redis.ConnectionPool(host=redis_server, port=redis_port, db=conn_db)
        redis_conn = redis.Redis(connection_pool=redis_pool)
	redis_conn.ping()
    except:
        print 'status=error, message="Redis connection error '+redis_server+':'+str(redis_port)+'"'
        sys.exit(1)
    return redis_conn

def main():
    if db_type == 'ipdb':
        red = make_redisconn(redis_ipdb)

        method_name = 'parse_'+threatfile_type
        method = globals().get(method_name)
        if not method:
            print 'status=error, message="'+method_name+' method not exist"'
            sys.exit(1)
        method(threatfile_path, red)
            
        print 'status=done, threatsource='+threatfile_type+', message="UploadedIntoDB"'

    if db_type == 'domaindb':
        print 'status=error, message="domaindb is not implemented yet"'

main()
sys.exit(0)
