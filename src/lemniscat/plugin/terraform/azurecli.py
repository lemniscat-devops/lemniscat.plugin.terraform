# -*- coding: utf-8 -*-
# above is for compatibility of python2.7.11

import logging
import os
import subprocess, sys   
from lemniscat.core.util.helpers import LogUtil
import re

try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.setLoggerClass(LogUtil)
log = logging.getLogger(__name__.replace('lemniscat.', ''))

class AzureCli:
    def __init__(self):
        pass
    
    def cmd(self, cmds, **kwargs):
        outputVar = {}
        capture_output = kwargs.pop('capture_output', True)
        is_env_vars_included = kwargs.pop('is_env_vars_included', False)
        if capture_output is True:
            stderr = subprocess.PIPE
            stdout = subprocess.PIPE
        else:
            stderr = sys.stderr
            stdout = sys.stdout
            
        environ_vars = {}
        if is_env_vars_included:
            environ_vars = os.environ.copy()

        p = subprocess.Popen(cmds, stdout=stdout, stderr=stderr,
                             cwd=None)
        
        while p.poll() is None:
            if(p.stdout is not None):
                lines = p.stdout.readlines()
                for line in lines:
                    ltrace = line.decode('utf-8').rstrip('\r\n')
                    m = re.match(r"^\[lemniscat\.pushvar\] (?P<key>\w+)=(?P<value>.*)", str(ltrace))
                    if(not m is None):
                        outputVar[m.group('key').strip()] = m.group('value').strip()
                        if(m.group('key').strip() == "arm_access_key"):
                            os.environ["ARM_ACCESS_KEY"] = m.group('value').strip()
                    else:
                        log.info(f'  {ltrace}')
            if(p.stderr is not None):
                errors = p.stderr.readlines()
                for error in errors:
                    ltrace = error.decode("utf-8").rstrip("\r\n")
                    if(ltrace.startswith("ERROR:")):
                        log.error(f'  {ltrace}')
                    else:
                        log.warning(f'  {ltrace}')
                          
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
        self.append_loginCommand()
        return self.cmd(['pwsh', '-Command', f'$result = az storage account keys list -n {storage_account_name} --query "[0].value" -o tsv; Write-Host "[lemniscat.pushvar] arm_access_key=$result"'], capture_output=True)