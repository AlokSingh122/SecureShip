# SecureShip

SecureShip is a security-gated delivery example using FastAPI, Docker, GitHub Actions,
Gitleaks, Trivy, Checkov, Terraform, and AWS ECR/EC2.

## Architecture

```text
Internet --HTTP:80--> EC2 public IPv4 --Docker:80->8000--> FastAPI
                              ^
                              | Systems Manager Run Command
                     GitHub Actions (OIDC)
```

One Amazon Linux 2023 `t3.micro` instance runs the container directly on host port 80.
There is no load balancer, TLS, HTTPS redirect, SSH ingress, NAT Gateway, ECS, or
Kubernetes. HTTP is intentionally used only for this non-sensitive learning demo.

## Project structure

```text
secureship/
├── .github/workflows/
│   ├── secure-pipeline.yml
│   └── terraform-check.yml
├── app/
│   ├── __init__.py
│   ├── app.py
│   └── requirements.txt
├── docker/Dockerfile
├── security/
│   ├── __init__.py
│   ├── policy.yaml
│   └── policy_engine.py
├── terraform/
│   ├── modules/
│   │   ├── networking/
│   │   ├── ec2/
│   │   ├── ecr/
│   │   └── github_deploy/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   ├── moved.tf
│   ├── backend.tf
│   ├── terraform.tfvars       # local only; ignored by Git
│   └── example.tfvars
├── tests/
│   ├── test_app.py
│   └── test_policy.py
├── reports/.gitkeep
├── requirements-dev.txt
├── pytest.ini
├── README.md
├── .gitignore
├── .dockerignore
└── .gitleaks.toml
```

The EC2 security group allows configurable TCP/80 ingress (default `0.0.0.0/0`) and has
no TCP/22 rule. The instance uses an encrypted 8-GB gp3 root volume, required IMDSv2,
an EC2 instance profile, Systems Manager, and a 14-day CloudWatch log group. Docker runs
the existing non-root image with `--restart unless-stopped`, its existing health check,
and `-p 80:8000`.

## Security pipeline

Pull requests run pytest, Gitleaks, Trivy filesystem and image scans, Checkov, and the
Python policy gate. Deployment runs only after that job succeeds, on a push or manual
dispatch to `main`. GitHub Actions assumes its IAM role using OIDC; no AWS access-key
secrets are used. It pushes the already-scanned image under the commit SHA, resolves the
immutable ECR digest, deploys that digest through SSM, waits for the SSM command and
container health check, then verifies `/health` and the matching `/version` commit over
HTTP.

The EC2 role has repository-scoped ECR pull access, the AWS-managed
`AmazonSSMManagedInstanceCore` policy, and CloudWatch stream-write access limited to the
application log group. The GitHub role has repository-scoped ECR push access and SSM
`SendCommand` access limited to the configured instance and `AWS-RunShellScript`
document. SSH is not required.

The policy contains expiring Checkov exceptions only for the required public HTTP/public
IPv4 path and the learning environment's log encryption/retention/monitoring cost choices.
All other Checkov failures remain blocking.

## Local checks

Requirements: Python 3.11+, Terraform 1.10+, and Docker.

```powershell
python -m pip install -r requirements-dev.txt -r app/requirements.txt
python -m pytest
terraform -chdir=terraform fmt -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
docker build -f docker/Dockerfile -t secureship:local .
docker run --rm -p 80:8000 secureship:local
```

## AWS deployment

### 1. Prepare Terraform state

The S3 backend is retained in `terraform/backend.tf`, with encryption and native lock
files enabled. Use a dedicated S3 bucket with versioning, server-side encryption, Block
Public Access, a TLS-only bucket policy, and restricted IAM access. The bucket is
provisioned separately and is not removed by `terraform destroy`.

Back up existing state before changing the deployment architecture:

```powershell
terraform -chdir=terraform state pull > pre-ec2.tfstate
```

Keep that file private and out of version control. Initialize the existing backend with
its configuration (use `-migrate-state` only when moving a local state file to S3):

```powershell
terraform -chdir=terraform init `
  -backend-config="bucket=YOUR-STATE-BUCKET" `
  -backend-config="key=secureship/terraform.tfstate" `
  -backend-config="region=ap-south-1" `
  -backend-config="encrypt=true" `
  -backend-config="use_lockfile=true"
```

### 2. Configure and apply Terraform

```powershell
Copy-Item terraform\example.tfvars terraform\terraform.tfvars
```

Set `github_repository` in `terraform/terraform.tfvars`. Optionally narrow
`allowed_http_cidr` to your own IPv4 CIDR; GitHub-hosted runners also need to reach port
80 for the workflow smoke test, so use a runner with a permitted egress IP if narrowing
this value.

Review the architecture transition before applying:

```powershell
terraform -chdir=terraform plan
```

`terraform/moved.tf` preserves the old ECR and GitHub OIDC role address migrations. It
also explicitly retires the prior ECS/Fargate, ALB, task-role, and task security-group
resources; those AWS resources cannot be state-moved into EC2. Review the plan for the
expected retirement and EC2 creation before approving:

```powershell
terraform -chdir=terraform apply
```

The EC2 instance initially installs Docker and SSM but does not run an unscanned
bootstrap image. The first application container is deployed only by the passing
security-gated workflow.

### 3. Configure GitHub environment variables and deploy

Create/use the GitHub `production` environment and set these environment variables. From
the repository root, GitHub CLI can load their values from Terraform outputs:

```powershell
gh variable set AWS_ROLE_ARN --env production --body "$(terraform -chdir=terraform output -raw github_deploy_role_arn)"
gh variable set AWS_REGION --env production --body "$(terraform -chdir=terraform output -raw aws_region)"
gh variable set ECR_REPOSITORY --env production --body "$(terraform -chdir=terraform output -raw ecr_repository_name)"
gh variable set EC2_INSTANCE_ID --env production --body "$(terraform -chdir=terraform output -raw ec2_instance_id)"
gh variable set EC2_PUBLIC_IP --env production --body "$(terraform -chdir=terraform output -raw ec2_public_ip)"
gh variable set EC2_LOG_GROUP --env production --body "$(terraform -chdir=terraform output -raw ec2_log_group_name)"
```

Push the changes to `main`, or start the pipeline after setting the variables:

```powershell
gh workflow run secure-pipeline.yml --ref main
gh run list --workflow secure-pipeline.yml
```

The GitHub IAM role trust policy accepts only this repository's `production` environment.
Configure that environment to allow deployment from `main` only. Do not add long-lived
AWS keys to GitHub.

## Verification

The deployment workflow performs these checks after SSM reports success. Run them
manually from a network allowed by `allowed_http_cidr`:

```powershell
$ip = terraform -chdir=terraform output -raw ec2_public_ip
curl.exe --fail "http://$ip/health"
curl.exe --fail "http://$ip/version"
```

The version response's `git_sha` should match the commit deployed by the workflow. The
container's Docker health check also probes `http://127.0.0.1:8000/health`.

## Cost and cleanup

For `ap-south-1`, an always-running Linux `t3.micro`, an 8-GB gp3 volume, and one public
IPv4 address are roughly **US$12/month before taxes, data transfer, and log/image storage**
at common on-demand rates. Actual prices, free-tier/credit eligibility, and instance
availability vary; check the AWS pricing pages for the account and region. CloudWatch
logs and ECR storage add usage-based charges. No NAT Gateway or load balancer is created.

Remove the application infrastructure while retaining the separately-managed state
bucket:

```powershell
terraform -chdir=terraform destroy
```

This removes the EC2 instance, security group, instance role/profile, log group, ECR
repository and GitHub deployment resources owned by this Terraform state, including the
retired architecture. It can remove a GitHub OIDC provider only if this stack created it;
set `create_github_oidc_provider = false` when the provider is shared. Keep the versioned
state bucket unless it is dedicated to this project and you have intentionally removed
all protected state versions and lock objects.
