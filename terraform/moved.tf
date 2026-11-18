# Preserve prior root-to-module address migrations for resources still in use.
moved {
  from = aws_ecr_repository.app
  to   = module.ecr.aws_ecr_repository.app
}

moved {
  from = aws_ecr_lifecycle_policy.app
  to   = module.ecr.aws_ecr_lifecycle_policy.app
}

moved {
  from = aws_iam_openid_connect_provider.github[0]
  to   = module.github_deploy.aws_iam_openid_connect_provider.github[0]
}

moved {
  from = aws_iam_role.github_deploy
  to   = module.github_deploy.aws_iam_role.github_deploy
}

moved {
  from = aws_iam_policy.github_deploy
  to   = module.github_deploy.aws_iam_policy.github_deploy
}

moved {
  from = aws_iam_role_policy_attachment.github_deploy
  to   = module.github_deploy.aws_iam_role_policy_attachment.github_deploy
}

# ECS/Fargate and ALB are different resource types from EC2 and cannot be state-moved.
# These removals make retirement of the old architecture explicit in Terraform plans.
removed {
  from = module.alb

  lifecycle {
    destroy = true
  }
}

removed {
  from = module.ecs

  lifecycle {
    destroy = true
  }
}

removed {
  from = module.ecs_task_roles

  lifecycle {
    destroy = true
  }
}

removed {
  from = module.networking.aws_security_group.task

  lifecycle {
    destroy = true
  }
}

# Also handle state written before the previous root-to-module migration.
removed {
  from = aws_security_group.task

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_cloudwatch_log_group.app

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_ecs_cluster.main

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_ecs_task_definition.app

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_ecs_service.app

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_iam_role.task_execution

  lifecycle {
    destroy = true
  }
}

removed {
  from = aws_iam_role_policy_attachment.task_execution

  lifecycle {
    destroy = true
  }
}
