data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_ssm_parameter" "amazon_linux_2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "app" {
  name        = "${var.project_name}-ec2"
  description = "HTTP application access; no SSH ingress"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP application traffic"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_http_cidr]
  }

  egress {
    description = "HTTPS access for ECR, SSM, and package repositories"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-ec2"
    Project = var.project_name
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ec2/${var.project_name}"
  retention_in_days = 14
}

data "aws_iam_policy_document" "instance_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.project_name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.instance_assume_role.json

  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "instance_permissions" {
  statement {
    sid       = "EcrAuthorization"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PullApplicationImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.ecr_repository_arn]
  }

  statement {
    sid = "WriteContainerLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }
}

resource "aws_iam_role_policy" "instance_permissions" {
  name   = "${var.project_name}-ec2-runtime"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance_permissions.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project_name}-ec2"
  role = aws_iam_role.instance.name
}

resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.amazon_linux_2023.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.app.name
  ebs_optimized               = true
  user_data_replace_on_change = true
  user_data                   = <<-USERDATA
    #!/bin/bash
    set -euo pipefail

    dnf install -y docker awscli-2 curl
    systemctl enable --now amazon-ssm-agent
    systemctl enable --now docker
  USERDATA

  root_block_device {
    encrypted             = true
    volume_size           = 8
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm_core,
    aws_iam_role_policy.instance_permissions,
  ]

  tags = {
    Name    = var.project_name
    Project = var.project_name
  }
}
