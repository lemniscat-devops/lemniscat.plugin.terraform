# -*- coding: utf-8 -*-
# above is for compatibility of python2.7.11

import logging
import os
import subprocess, sys 
from queue import Queue
import threading  
from lemniscat.core.util.helpers import LogUtil
import re

try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

def enqueue_stream(stream, queue, type):
    for line in iter(stream.readline, b''):
        queue.put(str(type) + line.decode('utf-8').rstrip('\r\n'))

def enqueue_process(process, queue):
    process.wait()
    queue.put('x')

logging.setLoggerClass(LogUtil)
log = logging.getLogger(__name__.replace('lemniscat.', ''))

class AzureCli:
    def __init__(self):
        pass
    
    def cmd(self, cmds, **kwargs):
        outputVar = {}
        capture_output = kwargs.pop('capture_output', True)
        stderr = subprocess.PIPE
        stdout = subprocess.PIPE

        p = subprocess.Popen(cmds, stdout=stdout, stderr=stderr,
                             cwd=None) 
        q = Queue()
        to = threading.Thread(target=enqueue_stream, args=(p.stdout, q, 1))
        te = threading.Thread(target=enqueue_stream, args=(p.stderr, q, 2))
        tp = threading.Thread(target=enqueue_process, args=(p, q))
        te.start()
        to.start()
        tp.start()
        
        if(capture_output is True):
            while True:
                line = q.get()
                if line[0] == 'x':
                    break
                if line[0] == '2':  # stderr
                    if(line[1:].startswith("ERROR:")):
                        log.error(f'  {line[1:]}')
                    else:
                        log.warning(f'  {line[1:]}')
                if line[0] == '1':
                    ltrace = line[1:]
                    m = re.match(r"^\[lemniscat\.pushvar\] (?P<key>\w+)=(?P<value>.*)", str(ltrace))
                    if(not m is None):
                        outputVar[m.group('key').strip()] = m.group('value').strip()
                        if(m.group('key').strip() == "arm_access_key"):
                            log.info('Set ARM_ACCESS_KEY environment variable.')
                            os.environ["ARM_ACCESS_KEY"] = m.group('value').strip()
                    else:
                        log.info(f'  {ltrace}')

        tp.join()
        to.join()
        te.join()
                          
        out, err = p.communicate()
        ret_code = p.returncode

        if capture_output is True:
            out = out.decode('utf-8')
            err = err.decode('utf-8')
        else:
            out = None
            err = None

        return ret_code, out, err, outputVar
    
    def append_loginCommand(self):
        self.cmd(['pwsh', '-Command', "az config unset core.allow_broker"], capture_output=False)
        self.cmd(['pwsh', '-Command', f"az login --service-principal -u {os.environ['ARM_CLIENT_ID']} -p {os.environ['ARM_CLIENT_SECRET']} --tenant {os.environ['ARM_TENANT_ID']}"], capture_output=False)
        self.cmd(['pwsh', '-Command', f"az account set --subscription {os.environ['ARM_SUBSCRIPTION_ID']}"], capture_output=False)
        
    def run(self, storage_account_name):
        log.info('Logging to Azure...')
        self.append_loginCommand()
        log.info('Getting storage account key...')
        self.cmd(['pwsh', '-Command', f"az configure --defaults group="], capture_output=False)
        return self.cmd(['pwsh', '-Command', f'$result = az storage account keys list -n {storage_account_name} --query "[0].value" -o tsv; Write-Host "[lemniscat.pushvar] arm_access_key=$result"'], capture_output=True)
