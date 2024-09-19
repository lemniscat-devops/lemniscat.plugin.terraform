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


class AwsCli:
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
        self.cmd(['pwsh', '-Command', f"aws configure set aws_access_key_id {os.environ['AWS_ACCESS_KEY_ID']}"], capture_output=True)
        self.cmd(['pwsh', '-Command', f"aws configure set aws_secret_access_key {os.environ['AWS_SECRET_ACCESS_KEY']}"], capture_output=True)
        self.cmd(['pwsh', '-Command', f"aws configure set region {os.environ['AWS_DEFAULT_REGION']}"], capture_output=True)
        self.cmd(['pwsh', '-Command', f"aws sts get-session-token --duration-seconds 28800"], capture_output=True)
        
    def run(self):
        log.info('Logging to AWS...')
        self.append_loginCommand()
        log.info('Logged to AWS.')

