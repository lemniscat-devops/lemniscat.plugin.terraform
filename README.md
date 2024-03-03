# lemniscat.plugin.terraform
A terraform plugin for lemniscat

## Description
This plugin provides a terraform plugin for lemniscat. It allows you to run terraform commands from within lemniscat.
> [!NOTE] 
> This plugin allow only for the moment Azure backend.

## Usage
### Pre-requisites
To use this plugin, you need to have terraform installed on your machine. You can install terraform from [here](https://www.terraform.io/downloads.html).
In order to use this plugin, you need to add plugin into the required section of your manifest file.

```yaml
requirements:
  - name: lemniscat.plugin.terraform
    version: 0.2.0
```

### Run terraform init command with Storage Account Access Key
```yaml 
- task: terraform
  displayName: 'Terraform init'
  steps:
    - pre
  parameters:
    action: init
    tfPath: ${{ tfPath }}
    backend:
      backend_type: azurerm
      storage_account_name: ${{ storage_account_name }}
      container_name: tfstate
      arm_access_key: ${{ arm_access_key }}
      key: terraform.tfstate
```

### Run terraform init command with Service Principal

If you want to use Service Principal to to get the storage account access key, you can use the following configuration.
First you need to create a Service Principal and assign it to the storage account. You can use the following command to create a Service Principal.
```bash
az ad sp create-for-rbac --name <ServicePrincipalName> --role contributor --scopes /subscriptions/<subscription_id>/resourceGroups/<resource_group_name>/providers/Microsoft.Storage/storageAccounts/<storage_account_name>
```
Then store the output in environment variables.
- `ARM_SUBSCRIPTION_ID` : The subscription ID that you want to use
- `ARM_CLIENT_ID` : The client ID of the service principal
- `ARM_CLIENT_SECRET` : The client secret of the service principal
- `ARM_TENANT_ID` : The tenant ID of the service principal

Then you can use the following configuration to run terraform init command. 

```yaml
- task: terraform
  displayName: 'Terraform init'
  steps:
    - pre
  parameters:
    action: init
    tfPath: ${{ tfPath }}
    backend:
      backend_type: azurerm
      storage_account_name: ${{ storage_account_name }}
      container_name: tfstate
      key: terraform.tfstate
```


### Run terraform plan command
```yaml
- task: terraform
  displayName: 'Terraform plan'
  steps:
    - pre
  parameters:
    action: plan
    tfPath: ${{ tfPath }}
    tfVarFile: ${{ tfVarsPath }}/vars.tfvars
    tfplanFile: ${{ tfPath }}/terrafom.tfplan
```

### Run terraform apply command
```yaml
- task: terraform
  displayName: 'Terraform apply'
  steps:
    - run
  parameters:
    action: apply
    tfPath: ${{ tfPath }}
    tfplanFile: ${{ tfPath }}/terrafom.tfplan
```

### Run terraform destroy command
```yaml
- task: terraform
  displayName: 'Terraform destroy'
  steps:
    - run
  parameters:
    action: destroy
    tfPath: ${{ tfPath }}
    tfVarFile: ${{ tfVarsPath }}/vars.tfvars
```

## Inputs

### Parameters
- `action` : The action to be performed. It can be `init`, `plan`, `apply` or `destroy`.
- `tfPath` : The path to the terraform main file.
- `tfVarFile` : The path to the terraform variable file.
- `tfplanFile` : The path to the terraform plan file.
- [`backend`](#Backend) : The backend configuration. It contains the following fields.
- `prefixOutput` : The prefix to be added to the output of the terraform command. It is optional. For example, if you have a terraform output `resource_group_name` and you want to add a prefix `tf` to it, you can set `prefixOutput` to `tf`. Then the output will be `tf.resource_group_name`.

### Backend
- `backend_type` : The type of the backend. It can be `azurerm` only for the moment. Must be provided if `tf.backend_type` isn't in the lemniscat bag of variables.
- `storage_account_name` : The name of the storage account. Only required if `backend_type` is `azurerm`. Must be provided if `tf.storage_account_name` isn't in the lemniscat bag of variables.
- `container_name` : The name of the container. Only required if `backend_type` is `azurerm`. Must be provided if `tf.container_name` isn't in the lemniscat bag of variables.
- `arm_access_key` : The access key of the storage account. Only required if `backend_type` is `azurerm`. Must be provided if `tf.arm_access_key` isn't in the lemniscat bag of variables or if environment variables `ARM_SUBSCRIPTION_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET` and `ARM_TENANT_ID` are not set.
- `key` : The name of the state file. Must be provided if `tf.key` isn't in the lemniscat bag of variables.

## Outputs

You can push variables to the lemniscat runtime in order to be used after by other tasks. All the outpus defined in the terraform output file will be pushed to the lemniscat runtime. The sensitive outputs will be send to the lemniscat runtime as secret.

If you want to add a prefix to the output, you can use the `prefixOutput` parameter.
For example, if you have a terraform output `resource_group_name` and you want to add a prefix `tf` to it, you can set `prefixOutput` to `tf`. Then the output will be `tf.resource_group_name`.