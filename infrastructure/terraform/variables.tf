variable "project_name" {
  type    = string
  default = "pitchcraft"
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "mongodb_atlas_url" {
  type        = string
  description = "MongoDB Atlas connection string"
  sensitive   = true
}

variable "secrets_arn" {
  type        = string
  description = "AWS Secrets Manager ARN prefix for API keys"
}

variable "backend_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}
