output "deployment" {
  description = "Nonsecret infrastructure inventory; not an installation or security qualification receipt."
  value = {
    version       = 1
    cloud         = "aws"
    account_id    = var.account_id
    region        = var.region
    group         = var.group
    deployment_id = var.deployment_id
    topology      = var.topology
    vpc_id        = aws_vpc.deployment.id
    hosts = { for role, host in aws_instance.host : role => {
      public_ip         = host.public_ip
      private_ip        = host.private_ip
      ssh_user          = "ec2-user"
      instance_id       = host.id
      security_group_id = aws_security_group.host[role].id
      https_url         = "https://${host.public_ip}:8443"
    } }
  }
}
