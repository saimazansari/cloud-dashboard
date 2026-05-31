terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstate181199"
    container_name       = "tfstate"
    key                  = "cloud-dashboard.tfstate"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "location" {
  type        = string
  default     = "eastus"
  description = "Azure region"
}

variable "resource_group_name" {
  type        = string
  default     = "cloud-dashboard-demo"
  description = "Primary resource group name"
}

variable "vnet_name" {
  type        = string
  default     = "demo-vnet"
  description = "Virtual Network name"
}

variable "vnet_address_space" {
  type        = list(string)
  default     = ["10.0.0.0/16"]
  description = "VNet address space"
}

variable "deploy_vnet" {
  type        = bool
  default     = true
  description = "Deploy Virtual Network"
}

variable "deploy_nsg" {
  type        = bool
  default     = true
  description = "Deploy Network Security Group"
}

variable "deploy_key_vault" {
  type        = bool
  default     = true
  description = "Deploy Key Vault"
}

variable "deploy_storage" {
  type        = bool
  default     = true
  description = "Deploy Storage Account"
}

variable "environment" {
  type        = string
  default     = "demo"
  description = "Environment tag"
}

variable "nsg_name" {
  type        = string
  default     = "demo-nsg"
  description = "Network Security Group name"
}

variable "storage_account_name" {
  type        = string
  default     = ""
  description = "Storage account name (auto-generated if empty)"
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_virtual_network" "demo" {
  count               = var.deploy_vnet ? 1 : 0
  name                = var.vnet_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = var.vnet_address_space

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_subnet" "default" {
  count                = var.deploy_vnet ? 1 : 0
  name                 = "default"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.demo[0].name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "demo" {
  count               = var.deploy_nsg ? 1 : 0
  name                = var.nsg_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowSSH"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "random_id" "suffix" {
  byte_length = 3
}

resource "azurerm_key_vault" "demo" {
  count                      = var.deploy_key_vault ? 1 : 0
  name                       = "kv-${var.environment}-${random_id.suffix.hex}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_storage_account" "demo" {
  count                    = var.deploy_storage ? 1 : 0
  name                     = var.storage_account_name != "" ? var.storage_account_name : "st${var.environment}${random_id.suffix.hex}"
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

data "azurerm_client_config" "current" {}

output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "vnet_id" {
  value = var.deploy_vnet ? azurerm_virtual_network.demo[0].id : null
}

output "vnet_name" {
  value = var.deploy_vnet ? azurerm_virtual_network.demo[0].name : null
}

output "nsg_id" {
  value = var.deploy_nsg ? azurerm_network_security_group.demo[0].id : null
}

output "key_vault_uri" {
  value = var.deploy_key_vault ? azurerm_key_vault.demo[0].vault_uri : null
}

output "storage_account_name" {
  value = var.deploy_storage ? azurerm_storage_account.demo[0].name : null
}
