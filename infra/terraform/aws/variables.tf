variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Provide the intended AWS account ID."
  }
}
variable "region" {
  type    = string
  default = "eu-central-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.region)) && !startswith(var.region, "cn-")
    error_message = "Use a commercial AWS region."
  }
}
variable "group" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,7}$", var.group))
    error_message = "Use a 2–8 character lowercase deployment group."
  }
}
variable "deployment_id" {
  type = string
  validation {
    condition     = can(regex("^em-${var.group}-[a-f0-9]{12}$", var.deployment_id))
    error_message = "Deployment ID must contain the group and 12 random hex digits."
  }
}
variable "topology" {
  type    = string
  default = "single"
  validation {
    condition     = contains(["single", "full"], var.topology)
    error_message = "Choose single (gateway) or full (gateway, Keycloak, observability)."
  }
}
variable "ami_id" {
  type = string
  validation {
    condition     = can(regex("^ami-[a-f0-9]{8,17}$", var.ami_id))
    error_message = "Select an exact RHEL x86_64 AMI."
  }
}
variable "ami_owner_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.ami_owner_id))
    error_message = "Supply the verified AMI publisher account."
  }
}
variable "availability_zones" {
  type = list(string)
  validation {
    condition     = length(var.availability_zones) >= 1 && length(var.availability_zones) <= 3 && alltrue([for zone in var.availability_zones : startswith(zone, var.region)])
    error_message = "Choose one to three availability zones in the selected region."
  }
}
variable "vpc_cidr" {
  type    = string
  default = "10.80.0.0/16"
  validation {
    condition     = can(cidrsubnet(var.vpc_cidr, 8, 2)) && endswith(var.vpc_cidr, "/16") && startswith(var.vpc_cidr, "10.")
    error_message = "Use a dedicated private 10.x.0.0/16 network."
  }
}
variable "ssh_cidrs" {
  type = set(string)
  validation {
    condition     = length(var.ssh_cidrs) > 0 && alltrue([for cidr in var.ssh_cidrs : can(cidrnetmask(cidr)) && endswith(cidr, "/32")])
    error_message = "SSH requires explicit workstation IPv4 /32 addresses."
  }
}
variable "https_cidrs" {
  type = set(string)
  validation {
    condition     = length(var.https_cidrs) > 0 && alltrue([for cidr in var.https_cidrs : can(cidrnetmask(cidr)) && endswith(cidr, "/32")])
    error_message = "This initial testing module requires HTTPS restricted to IPv4 /32 addresses."
  }
}
variable "ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa) [A-Za-z0-9+/=]+( [^\\r\\n]+)?$", trimspace(var.ssh_public_key))) && !strcontains(var.ssh_public_key, "PRIVATE KEY")
    error_message = "Supply only an existing SSH public key."
  }
}
