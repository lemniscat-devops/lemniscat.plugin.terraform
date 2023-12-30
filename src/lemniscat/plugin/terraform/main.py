
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

    def __run_terraform(self, command: str, parameters: dict, variables: dict) -> TaskResult:
        # launch terraform command
        backendConfig = self.set_backend_config(variables)
        if(backendConfig != {}):
            result = {}
            tf = Terraform(working_dir=parameters['tfPath'])
            if(command == 'init'):
                result = tf.init(backend_config=backendConfig)
            elif(command == 'plan'):
                result = tf.plan(backend_config=backendConfig)
            elif(command == 'apply'):
                result = tf.apply(backend_config=backendConfig)
            elif(command == 'destroy'):
                result = tf.destroy(backend_config=backendConfig)
            
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
        
if __name__ == "__main__":
    print("Hello World")
    logger = LogUtil.create()
    action = Action(logger)
    action.invoke({ 'action': 'init', 'tfPath': 'C:\DEV\Onepoint\Smartplace\Product.AzureStorage\src\/terraform' }, { 'tfBackend': 'azurerm', 'arm_access_key': '08CMLob4mDzjqYY9lfGoAOOtoeUXdliKzAN9su1FpPndpsHAGIPIb+If6mOD4dFuStEuMowHvMDR+ASto3+ZqA==', 'storage_account_name': 'stcfsoplab', 'container_name': 'tfstates', 'key': 'loremipsum.tfstate'})