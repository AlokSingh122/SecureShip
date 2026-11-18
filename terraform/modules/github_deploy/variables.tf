variable "project_name" {
  type = string
}

variable "github_repository" {
  type = string
}

variable "github_repository_owner_id" {
  type = string
}

variable "github_repository_id" {
  type = string
}

variable "create_oidc_provider" {
  type = bool
}

variable "aws_region" {
  type = string
}

variable "ecr_repository_arn" {
  type = string
}

variable "ec2_instance_arn" {
  type = string
}
