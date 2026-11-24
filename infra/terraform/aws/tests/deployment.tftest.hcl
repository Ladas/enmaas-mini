mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_ami" {
    defaults = { id = "ami-0123456789abcdef0" }
  }
}
variables {
  account_id         = "123456789012"
  group              = "demo"
  deployment_id      = "em-demo-012345abcdef"
  ami_id             = "ami-0123456789abcdef0"
  ami_owner_id       = "123456789012"
  availability_zones = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]
  ssh_cidrs          = ["192.0.2.1/32"]
  https_cidrs        = ["192.0.2.1/32"]
  ssh_public_key     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestFixture public-only"
}
run "single_host" {
  command = plan
  assert {
    condition     = length(aws_instance.host) == 1 && length(aws_vpc_security_group_ingress_rule.peer) == 0
    error_message = "Single topology must not create auxiliary hosts or peer rules."
  }
  assert {
    condition     = alltrue([for host in aws_instance.host : host.metadata_options[0].http_tokens == "required" && host.metadata_options[0].http_put_response_hop_limit == 1 && host.root_block_device[0].encrypted])
    error_message = "Hosts require IMDSv2, hop limit one and encrypted disks."
  }
  assert {
    condition     = alltrue([for rule in aws_vpc_security_group_ingress_rule.workstation : rule.cidr_ipv4 == "192.0.2.1/32"])
    error_message = "Workstation ingress must stay restricted."
  }
}
run "full_topology" {
  command = plan
  variables { topology = "full" }
  assert {
    condition     = length(aws_instance.host) == 3 && length(aws_subnet.host) == 3 && length(aws_vpc_security_group_ingress_rule.peer) == 3
    error_message = "Full topology needs three hosts/subnets and exactly three private peer rules."
  }
  assert {
    condition     = alltrue([for rule in aws_vpc_security_group_ingress_rule.peer : rule.cidr_ipv4 == null])
    error_message = "Service-to-service access must use security-group references, not public CIDRs."
  }
  assert {
    condition     = aws_subnet.host["observability"].availability_zone == "eu-central-1c"
    error_message = "Role placement must preserve selected availability zones."
  }
  assert {
    condition     = alltrue([for host in aws_instance.host : host.tags["enmaas:group"] == "demo" && host.volume_tags["enmaas:run"] == "em-demo-012345abcdef"])
    error_message = "Instances and volumes require ownership tags."
  }
}
run "reject_open_ssh" {
  command = plan
  variables { ssh_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.ssh_cidrs]
}
run "reject_open_https" {
  command = plan
  variables { https_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.https_cidrs]
}
run "reject_cross_group_id" {
  command = plan
  variables { deployment_id = "em-foreign-012345abcdef" }
  expect_failures = [var.deployment_id]
}
run "reject_private_key" {
  command = plan
  variables { ssh_public_key = "-----BEGIN PRIVATE KEY-----" }
  expect_failures = [var.ssh_public_key]
}
run "reject_foreign_zone" {
  command = plan
  variables { availability_zones = ["us-east-1a"] }
  expect_failures = [var.availability_zones]
}
run "apply_full_inventory" {
  command = apply
  variables { topology = "full" }
  assert {
    condition     = output.deployment.deployment_id == "em-demo-012345abcdef" && length(output.deployment.hosts) == 3
    error_message = "Applied inventory must retain ownership and all service roles."
  }
  assert {
    condition     = alltrue([for host in output.deployment.hosts : host.ssh_user == "ec2-user" && startswith(host.https_url, "https://")])
    error_message = "Inventory must contain service connection information."
  }
}
run "reject_wrong_account" {
  command = plan
  variables { account_id = "999999999999" }
  expect_failures = [aws_vpc.deployment]
}
