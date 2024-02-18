
import argparse
import ast
import logging
import os
from logging import Logger
import re
from lemniscat.core.contract.engine_contract import PluginCore
from lemniscat.core.model.models import Meta, TaskResult
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
        
    def __interpret(self, parameterValue: str, variables: dict) -> str:
        if(script is None):
            return None
        if(isinstance(script, str)):
            matches = re.findall(_REGEX_CAPTURE_VARIABLE, script)
            if(len(matches) > 0):
                for match in matches:
                    var = str.strip(match)
                    if(var in variables):
                        script = script.replace(f'${{{{{match}}}}}', variables[var])
                        self._logger.debug(f"Interpreting variable: {var} -> {variables[var]}")
                    else:
                        script = script.replace(f'${{{{{match}}}}}', "")
                        self._logger.debug(f"Variable not found: {var}. Replaced by empty string.")
        return parameterValue 

    def set_backend_config(self, parameters: dict, variables: dict) -> dict:
        # set backend config
        backend_config = {}
        #override configuration with backend configuration
        if(parameters.keys().__contains__('backend')):
            if(parameters['backend'].keys().__contains__('backend_type')):
                variables['backend_type'] = self.__interpret(parameters['backend']['backend_type'], variables)
            if(parameters['backend'].keys().__contains__('arm_access_key')):
                variables['arm_access_key'] = self.__interpret(parameters['backend']['arm_access_key'], variables)
            if(parameters['backend'].keys().__contains__('container_name')):
                variables['container_name'] = self.__interpret(parameters['backend']['container_name'], variables)
            if(parameters['backend'].keys().__contains__('storage_account_name')):
                variables['storage_account_name'] = self.__interpret(parameters['backend']['storage_account_name'], variables)
            if(parameters['backend'].keys().__contains__('key')):
                variables['key'] = self.__interpret(parameters['backend']['key'], variables)
                
        # set backend config for azure
        if(variables['backend_type'] == 'azurerm'):
            if(not variables.keys().__contains__('arm_access_key')):
                cli = AzureCli()
                cli.run(variables["storage_account_name"])
            else:
                os.environ["ARM_ACCESS_KEY"] = variables["arm_access_key"]
            backend_config = {'storage_account_name': variables["storage_account_name"], 'container_name': variables["container_name"], 'key': variables["key"]}
            
        return backend_config
    
    @staticmethod
    def set_tf_var_file(variables: dict, parameters: dict) -> str:
        # set terraform var file
        var_file = None
        if(variables.keys().__contains__('tfVarFile')):
            var_file = variables['tfVarfile']
        if(parameters.keys().__contains__('tfVarFile')):
            var_file = parameters['tfVarFile']   
        return var_file
    
    @staticmethod
    def set_tfplan_file(variables: dict, parameters: dict) -> str:
        # set terraform var file
        tfplan_file = './terrafom.tfplan'
        if(variables.keys().__contains__('tfplanFile')):
            tfplan_file = variables['tfplanFile']
        if(parameters.keys().__contains__('tfplanFile')):
            tfplan_file = parameters['tfplanFile']   
        return tfplan_file

    def __run_terraform(self, command: str, parameters: dict, variables: dict) -> TaskResult:
        # launch terraform command
        backendConfig = self.set_backend_config(parameters, variables)
        
        # set terraform var file
        var_file = self.set_tf_var_file(variables, parameters)              
            
        if(backendConfig != {}):
            result = {}
            tf = Terraform(working_dir=parameters['tfPath'], var_file=var_file)
            if(command == 'init'):
                result = tf.init(backend_config=backendConfig)
            elif(command == 'plan'):        
                result = tf.plan(out=self.set_tfplan_file(variables, parameters))
            elif(command == 'apply'):
                result = tf.apply(dir_or_plan=self.set_tfplan_file(variables, parameters))
                if(result[0] == 0):
                    if(parameters.keys().__contains__('prefixOutput')):
                        outputs = tf.output(prefix=parameters['prefixOutput'])
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
        self._logger.debug(f'Command: {parameters["action"]} -> {self.meta}')
        task = self.__run_terraform(parameters['action'], parameters, variables)
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
    action.invoke(ast.literal_eval(__cli_args.parameters), ast.literal_eval(__cli_args.variables))