module "networking" {
  source = "./modules/networking"
}

module "ecr" {
  source       = "./modules/ecr"
  project_name = var.project_name
}

module "ec2" {
  source             = "./modules/ec2"
  project_name       = var.project_name
  vpc_id             = module.networking.vpc_id
  subnet_id          = module.networking.public_subnet_id
  instance_type      = var.ec2_instance_type
  allowed_http_cidr  = var.allowed_http_cidr
  ecr_repository_arn = module.ecr.repository_arn
}

module "github_deploy" {
  source                     = "./modules/github_deploy"
  project_name               = var.project_name
  github_repository          = var.github_repository
  github_repository_owner_id = var.github_repository_owner_id
  github_repository_id       = var.github_repository_id
  create_oidc_provider       = var.create_github_oidc_provider
  aws_region                 = var.aws_region
  ecr_repository_arn         = module.ecr.repository_arn
  ec2_instance_arn           = module.ec2.instance_arn
}
