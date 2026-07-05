terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "random_password" "vm_admin" {
  length  = 24
  special = false
}

resource "random_string" "kv_suffix" {
  length  = 8
  numeric = true
  special = false
  upper   = false
}

resource "random_string" "storage_suffix" {
  length  = 8
  numeric = true
  special = false
  upper   = false
}

# --- Resource Group ---

resource "azurerm_resource_group" "main" {
  name     = "CLOUD-DASHBOARD-DEMO"
  location = "westus3"
}

# --- VNet ---

resource "azurerm_virtual_network" "main" {
  name                = "demo-vnet"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.0.0.0/16"]
}

# --- Subnet ---

resource "azurerm_subnet" "main" {
  name                 = "default"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.0/24"]
}

# --- NSG ---

resource "azurerm_network_security_group" "main" {
  name                = "demo-nsg"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "SSH"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# --- Public IP ---

resource "azurerm_public_ip" "main" {
  name                = "demo-vmPublicIP"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

# --- NIC ---

resource "azurerm_network_interface" "main" {
  name                = "demo-vmVMNic"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.main.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.main.id
  }
}

resource "azurerm_network_interface_security_group_association" "main" {
  network_interface_id      = azurerm_network_interface.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

# --- Key Vault ---

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "demo" {
  name                = "demo-kv-${random_string.kv_suffix.result}"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
}

# --- VM ---

resource "azurerm_linux_virtual_machine" "main" {
  name                = "demo-vm"
  location            = "westus3"
  resource_group_name = azurerm_resource_group.main.name
  size                = "Standard_D2ds_v6"
  admin_username      = "azureuser"
  admin_password      = random_password.vm_admin.result
  disable_password_authentication = false
  network_interface_ids = [
    azurerm_network_interface.main.id,
  ]

  os_disk {
    name                 = "demo-vm_OsDisk_1"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}

# --- Storage Account ---

resource "azurerm_storage_account" "main" {
  name                     = "demostorage${random_string.storage_suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = "westus3"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  access_tier              = "Hot"
}
