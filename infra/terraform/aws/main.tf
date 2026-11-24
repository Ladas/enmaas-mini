data "aws_caller_identity" "current" {}
data "aws_ami" "rhel" {
  owners = [var.ami_owner_id]
  filter {
    name   = "image-id"
    values = [var.ami_id]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "name"
    values = ["RHEL-*"]
  }
}

locals {
  tags = {
    "enmaas:group"   = var.group
    "enmaas:run"     = var.deployment_id
    "enmaas:purpose" = "terraform-test"
  }
  definitions = {
    gateway       = { instance_type = "m7i.2xlarge", volume_gib = 150, index = 0 }
    keycloak      = { instance_type = "m7i.large", volume_gib = 50, index = 1 }
    observability = { instance_type = "m7i.xlarge", volume_gib = 100, index = 2 }
  }
  hosts = { for role, settings in local.definitions : role => settings if var.topology == "full" || role == "gateway" }
  public_rules = { for pair in setproduct(keys(local.hosts), concat(
    [for cidr in sort(tolist(var.ssh_cidrs)) : { port = 22, cidr = cidr }],
    [for cidr in sort(tolist(var.https_cidrs)) : { port = 8443, cidr = cidr }]
  )) : "${pair[0]}-${pair[1].port}-${replace(pair[1].cidr, "/", "_")}" => { role = pair[0], port = pair[1].port, cidr = pair[1].cidr } }
  peers = var.topology == "full" ? {
    gateway_issuer = { source = "gateway", destination = "keycloak", port = 8443 }
    obs_issuer     = { source = "observability", destination = "keycloak", port = 8443 }
    telemetry      = { source = "gateway", destination = "observability", port = 24443 }
  } : {}
}

resource "aws_vpc" "deployment" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = var.deployment_id })
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == var.account_id
      error_message = "AWS caller is outside the intended account."
    }
  }
}
resource "aws_internet_gateway" "deployment" {
  vpc_id = aws_vpc.deployment.id
  tags   = merge(local.tags, { Name = var.deployment_id })
}
resource "aws_subnet" "host" {
  for_each                = local.hosts
  vpc_id                  = aws_vpc.deployment.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value.index)
  availability_zone       = var.availability_zones[each.value.index % length(var.availability_zones)]
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${var.deployment_id}-${each.key}" })
}
resource "aws_route_table" "deployment" {
  vpc_id = aws_vpc.deployment.id
  tags   = merge(local.tags, { Name = var.deployment_id })
}
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.deployment.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.deployment.id
}
resource "aws_route_table_association" "host" {
  for_each       = local.hosts
  subnet_id      = aws_subnet.host[each.key].id
  route_table_id = aws_route_table.deployment.id
}
resource "aws_security_group" "host" {
  for_each    = local.hosts
  name        = "${var.deployment_id}-${each.key}"
  description = "EnMaaS ${each.key}: restricted browser and SSH, explicit private peers"
  vpc_id      = aws_vpc.deployment.id
  tags        = merge(local.tags, { Name = "${var.deployment_id}-${each.key}" })
}
resource "aws_vpc_security_group_ingress_rule" "workstation" {
  for_each          = local.public_rules
  security_group_id = aws_security_group.host[each.value.role].id
  cidr_ipv4         = each.value.cidr
  from_port         = each.value.port
  to_port           = each.value.port
  ip_protocol       = "tcp"
  tags              = local.tags
}
resource "aws_vpc_security_group_ingress_rule" "peer" {
  for_each                     = local.peers
  security_group_id            = aws_security_group.host[each.value.destination].id
  referenced_security_group_id = aws_security_group.host[each.value.source].id
  from_port                    = each.value.port
  to_port                      = each.value.port
  ip_protocol                  = "tcp"
  tags                         = local.tags
}
resource "aws_vpc_security_group_egress_rule" "outbound" {
  for_each          = local.hosts
  security_group_id = aws_security_group.host[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  tags              = local.tags
}
resource "aws_key_pair" "deployment" {
  key_name   = var.deployment_id
  public_key = trimspace(var.ssh_public_key)
  tags       = merge(local.tags, { Name = var.deployment_id })
}
resource "aws_instance" "host" {
  for_each                    = local.hosts
  ami                         = data.aws_ami.rhel.id
  instance_type               = each.value.instance_type
  subnet_id                   = aws_subnet.host[each.key].id
  vpc_security_group_ids      = [aws_security_group.host[each.key].id]
  associate_public_ip_address = true
  key_name                    = aws_key_pair.deployment.key_name
  monitoring                  = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = each.value.volume_gib
    delete_on_termination = true
  }
  tags        = merge(local.tags, { Name = "${var.deployment_id}-${each.key}" })
  volume_tags = merge(local.tags, { Name = "${var.deployment_id}-${each.key}" })
  depends_on  = [aws_route.internet, aws_route_table_association.host]
}
