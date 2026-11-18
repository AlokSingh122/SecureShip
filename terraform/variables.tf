variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix used for SecureShip AWS resources."
  type        = string
  default     = "secureship"
}

variable "github_repository" {
  description = "GitHub repository allowed to deploy, as OWNER/REPOSITORY."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like OWNER/REPOSITORY."
  }
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub owner ID used in the OIDC subject."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must contain only digits."
  }
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID used in the OIDC subject."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "github_repository_id must contain only digits."
  }
}

variable "create_github_oidc_provider" {
  description = "Set false if this AWS account already has the GitHub OIDC provider."
  type        = bool
  default     = true
}

variable "ec2_instance_type" {
  description = "EC2 instance type used for the single application host."
  type        = string
  default     = "t3.micro"
}

variable "allowed_http_cidr" {
  description = "IPv4 CIDR permitted to access the application over HTTP."
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrnetmask(var.allowed_http_cidr))
    error_message = "allowed_http_cidr must be a valid IPv4 CIDR."
  }
}
