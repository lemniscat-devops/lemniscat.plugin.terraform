
import argparse
import ast
import logging
import os
from logging import Logger
from lemniscat.core.contract.engine_contract import PluginCore
from lemniscat.core.model.models import Meta, TaskResult
from lemniscat.core.util.helpers import FileSystem, LogUtil

from lemniscat.plugin.terraform.terraform import Terraform


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

    @staticmethod
    def set_backend_config(variables: dict) -> dict:
        # set backend config
        backend_config = {}
        if(variables['tfBackend'] == 'azurerm'):
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
        backendConfig = self.set_backend_config(variables)
        
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
            elif(command == 'destroy'):
                result = tf.destroy()
            
            if(result[0] != 0):
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