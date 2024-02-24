
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
        
    def __interpret(self, parameterValue: str, variables: dict) -> str:
        isSensible = False
        if(parameterValue is None):
            return None
        if(isinstance(parameterValue, str)):
            matches = re.findall(_REGEX_CAPTURE_VARIABLE, parameterValue)
            if(len(matches) > 0):
                for match in matches:
                    var = str.strip(match)
                    if(var in variables):
                        parameterValue = parameterValue.replace(f'${{{{{match}}}}}', variables[var].value)
                        if(variables[var].sensitive):
                            isSensible = True
                        self._logger.debug(f"Interpreting variable: {var} -> {variables[var]}")
                    else:
                        parameterValue = parameterValue.replace(f'${{{{{match}}}}}', "")
                        self._logger.debug(f"Variable not found: {var}. Replaced by empty string.")
        return VariableValue(parameterValue, isSensible) 

    def set_backend_config(self, parameters: dict, variables: dict) -> dict:
        # set backend config
        backend_config = {}
        #override configuration with backend configuration
        if(parameters.keys().__contains__('backend')):
            if(parameters['backend'].keys().__contains__('backend_type')):
                variables['tf.backend_type'] = self.__interpret(parameters['backend']['backend_type'], variables)
            if(parameters['backend'].keys().__contains__('arm_access_key')):
                variables['tf.arm_access_key'] = self.__interpret(parameters['backend']['arm_access_key'], variables)
            if(parameters['backend'].keys().__contains__('container_name')):
                variables['tf.container_name'] = self.__interpret(parameters['backend']['container_name'], variables)
            if(parameters['backend'].keys().__contains__('storage_account_name')):
                variables['tf.storage_account_name'] = self.__interpret(parameters['backend']['storage_account_name'], variables)
            if(parameters['backend'].keys().__contains__('key')):
                variables['tf.key'] = self.__interpret(parameters['backend']['key'], variables)
                
        # set backend config for azure
        if(variables['tf.backend_type'].value == 'azurerm'):
            if(not variables.keys().__contains__('tf.arm_access_key')):
                cli = AzureCli()
                cli.run(variables["tf.storage_account_name"].value)
            else:
                os.environ["ARM_ACCESS_KEY"] = variables["tf.arm_access_key"].value
            super().appendVariables({ "tf.arm_access_key": VariableValue(os.environ["ARM_ACCESS_KEY"], True), 'tf.storage_account_name': variables["tf.storage_account_name"], 'tf.container_name': variables["tf.container_name"], 'tf.key': variables["tf.key"] })
            backend_config = {'storage_account_name': variables["tf.storage_account_name"].value, 'container_name': variables["tf.container_name"].value, 'key': variables["tf.key"].value}
            
        return backend_config
    
    def set_tf_var_file(self, variables: dict, parameters: dict) -> str:
        # set terraform var file
        var_file = None
        if(variables.keys().__contains__('tfVarFile')):
            var_file = self.__interpret(variables['tfVarfile'].value, variables).value
        if(parameters.keys().__contains__('tfVarFile')):
            var_file = self.__interpret(parameters['tfVarFile'], variables).value 
        return var_file
    
    def set_tfplan_file(self, variables: dict, parameters: dict) -> str:
        # set terraform var file
        tfplan_file = './terrafom.tfplan'
        if(variables.keys().__contains__('tfplanFile')):
            tfplan_file = self.__interpret(variables['tfplanFile'].value, variables).value
        if(parameters.keys().__contains__('tfplanFile')):
            tfplan_file = self.__interpret(parameters['tfplanFile'], variables).value  
        return tfplan_file

    def __run_terraform(self, command: str, parameters: dict, variables: dict) -> TaskResult:
        # launch terraform command
        backendConfig = self.set_backend_config(parameters, variables)
        
        # set terraform var file
        var_file = self.set_tf_var_file(variables, parameters)              
            
        if(backendConfig != {}):
            result = {}
            tfpath = self.__interpret(parameters['tfPath'], variables).value
            tf = Terraform(working_dir=tfpath, var_file=var_file)
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
    variables = {}   
    vars = ast.literal_eval(__cli_args.variables)
    for key in vars:
        variables[key] = VariableValue(vars[key])
    
    action.invoke(ast.literal_eval(__cli_args.parameters), variables)