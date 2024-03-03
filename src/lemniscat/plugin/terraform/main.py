
import argparse
import ast
import logging
import os
from logging import Logger
import re
from lemniscat.core.contract.engine_contract import PluginCore
from lemniscat.core.model.models import Meta, TaskResult, VariableValue
from lemniscat.core.util.helpers import FileSystem, LogUtil
from lemniscat.plugin.terraform.azurecli import AzureCli

from lemniscat.plugin.terraform.terraform import Terraform

_REGEX_CAPTURE_VARIABLE = r"(?:\${{(?P<var>[^}]+)}})"

class Action(PluginCore):

    def __init__(self, logger: Logger) -> None:
        super().__init__(logger)
        plugin_def_path = os.path.abspath(os.path.dirname(__file__)) + '/plugin.yaml'
        manifest_data = FileSystem.load_configuration_path(plugin_def_path)
        self.meta = Meta(
            name=manifest_data['name'],
            description=manifest_data['description'],
            version=manifest_data['version']
        )
        
    def set_backend_config(self) -> dict:
        # set backend config
        backend_config = {}
        #override configuration with backend configuration
        if(self.parameters.keys().__contains__('backend')):
            if(self.parameters['backend'].keys().__contains__('backend_type')):
                self.variables['tf.backend_type'] = VariableValue(self.parameters['backend']['backend_type'])
            if(self.parameters['backend'].keys().__contains__('arm_access_key')):
                self.variables['tf.arm_access_key'] = VariableValue(self.parameters['backend']['arm_access_key'])
            if(self.parameters['backend'].keys().__contains__('container_name')):
                self.variables['tf.container_name'] = VariableValue(self.parameters['backend']['container_name'])
            if(self.parameters['backend'].keys().__contains__('storage_account_name')):
                self.variables['tf.storage_account_name'] = VariableValue(self.parameters['backend']['storage_account_name'])
            if(self.parameters['backend'].keys().__contains__('key')):
                self.variables['tf.key'] = VariableValue(self.parameters['backend']['key'])
                
        # set backend config for azure
        if(self.variables['tf.backend_type'].value == 'azurerm'):
            if(not self.variables.keys().__contains__('tf.arm_access_key') or self.variables["tf.arm_access_key"].value is None or len(self.variables["tf.arm_access_key"].value) == 0):
                cli = AzureCli()
                cli.run(self.variables["tf.storage_account_name"].value)
            else:
                os.environ["ARM_ACCESS_KEY"] = self.variables["tf.arm_access_key"].value
            super().appendVariables({ "tf.arm_access_key": VariableValue(os.environ["ARM_ACCESS_KEY"], True), 'tf.storage_account_name': self.variables["tf.storage_account_name"], 'tf.container_name': self.variables["tf.container_name"], 'tf.key': self.variables["tf.key"] })
            backend_config = {'storage_account_name': self.variables["tf.storage_account_name"].value, 'container_name': self.variables["tf.container_name"].value, 'key': self.variables["tf.key"].value}
            
        return backend_config
    
    def set_tf_var_file(self) -> str:
        # set terraform var file
        var_file = None
        if(self.variables.keys().__contains__('tfVarFile')):
            var_file = self.variables['tfVarfile'].value
        if(self.parameters.keys().__contains__('tfVarFile')):
            var_file = self.parameters['tfVarFile'] 
        return var_file
    
    def set_tfplan_file(self) -> str:
        # set terraform var file
        tfplan_file = './terrafom.tfplan'
        if(self.variables.keys().__contains__('tfplanFile')):
            tfplan_file = self.variables['tfplanFile'].value
        if(self.parameters.keys().__contains__('tfplanFile')):
            tfplan_file = self.parameters['tfplanFile']  
        return tfplan_file

    def __run_terraform(self) -> TaskResult:
        # launch terraform command
        backendConfig = self.set_backend_config()
        
        # set terraform var file
        var_file = self.set_tf_var_file()              
        
        # set terraform command    
        command = self.parameters['action']
            
        if(backendConfig != {}):
            result = {}
            tfpath = self.parameters['tfPath']
            tf = Terraform(working_dir=tfpath, var_file=var_file)
            if(command == 'init'):
                result = tf.init(backend_config=backendConfig)
            elif(command == 'plan'):        
                result = tf.plan(out=self.set_tfplan_file())
            elif(command == 'apply'):
                result = tf.apply(dir_or_plan=self.set_tfplan_file())
                if(result[0] == 0):
                    if(self.parameters.keys().__contains__('prefixOutput')):
                        outputs = tf.output(prefix=self.parameters['prefixOutput'])
                    else:
                        outputs = tf.output()
                    super().appendVariables(outputs)
            elif(command == 'destroy'):
                result = tf.destroy()
            
            if(result[0] != 0 and result[0] != 2):
                return TaskResult(
                    name=f'Terraform {command}',
                    status='Failed',
                    errors=result[2])
            else:
                return TaskResult(
                    name=f'Terraform {command}',
                    status='Completed',
                    errors=[])
        else:
            self._logger.error(f'No backend config found')
            
            return TaskResult(
                name=f'Terraform {command}',
                status='Failed',
                errors=[0x0001])
        

    def invoke(self, parameters: dict = {}, variables: dict = {}) -> TaskResult:
        super().invoke(parameters, variables)
        self._logger.debug(f'Command: {self.parameters["action"]} -> {self.meta}')
        task = self.__run_terraform()
        return task
    
    def test_logger(self) -> None:
        self._logger.debug('Debug message')
        self._logger.info('Info message')
        self._logger.warning('Warning message')
        self._logger.error('Error message')
        self._logger.critical('Critical message')

def __init_cli() -> argparse:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--parameters', required=True, 
        help="""(Required) Supply a dictionary of parameters which should be used. The default is {}
        """
    )
    parser.add_argument(
        '-v', '--variables', required=True, help="""(Optional) Supply a dictionary of variables which should be used. The default is {}
        """
    )                
    return parser
        
if __name__ == "__main__":
    logger = LogUtil.create()
    action = Action(logger)
    __cli_args = __init_cli().parse_args()
    variables = {}   
    vars = ast.literal_eval(__cli_args.variables)
    for key in vars:
        variables[key] = VariableValue(vars[key])
    
    action.invoke(ast.literal_eval(__cli_args.parameters), variables)