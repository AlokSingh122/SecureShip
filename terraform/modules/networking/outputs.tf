output "public_subnet_id" {
  value = sort(data.aws_subnets.public.ids)[0]
}

output "vpc_id" {
  value = data.aws_vpc.default.id
}
