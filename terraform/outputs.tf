output "aws_region" {
  value = var.aws_region
}

output "ecr_repository_name" {
  value = module.ecr.repository_name
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ec2_instance_id" {
  value = module.ec2.instance_id
}

output "ec2_instance_arn" {
  value = module.ec2.instance_arn
}

output "ec2_public_ip" {
  value = module.ec2.public_ip
}

output "ec2_log_group_name" {
  value = module.ec2.log_group_name
}

output "github_deploy_role_arn" {
  value = module.github_deploy.role_arn
}
