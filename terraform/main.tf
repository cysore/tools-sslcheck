# SSL证书监控系统 - Terraform配置

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 变量定义
variable "aws_region" {
  description = "AWS区域"
  type        = string
  default     = "us-east-1"
}

variable "function_name" {
  description = "Lambda函数名称"
  type        = string
  default     = "ssl-certificate-monitor"
}

variable "schedule_expression" {
  description = "定时触发表达式"
  type        = string
  default     = "rate(30 days)"
}

variable "domains_to_monitor" {
  description = "要监控的域名列表"
  type        = list(string)
  default     = ["example.com", "test.org"]
}

variable "notification_email" {
  description = "接收通知的邮箱地址"
  type        = string
  default     = "admin@example.com"
}

variable "log_level" {
  description = "日志级别"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "日志级别必须是 DEBUG, INFO, WARNING, 或 ERROR 之一。"
  }
}

variable "lambda_timeout" {
  description = "Lambda函数超时时间（秒）"
  type        = number
  default     = 180
}

variable "lambda_memory_size" {
  description = "Lambda函数内存大小（MB）"
  type        = number
  default     = 256
}

# SNS主题
resource "aws_sns_topic" "ssl_alerts" {
  name         = "ssl-certificate-alerts"
  display_name = "SSL证书过期警报"
  
  tags = {
    Name        = "SSL Certificate Alerts"
    Environment = "production"
    Project     = "ssl-certificate-monitor"
  }
}

# SNS订阅
resource "aws_sns_topic_subscription" "email_notification" {
  topic_arn = aws_sns_topic.ssl_alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# Lambda执行角色
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.function_name}-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "${var.function_name}-execution-role"
    Project = "ssl-certificate-monitor"
  }
}

# Lambda基本执行策略
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# SNS发布策略
resource "aws_iam_role_policy" "sns_publish_policy" {
  name = "${var.function_name}-sns-publish"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.ssl_alerts.arn
      }
    ]
  })
}

# CloudWatch日志组
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 14

  tags = {
    Name    = "${var.function_name}-logs"
    Project = "ssl-certificate-monitor"
  }
}

# Lambda函数
resource "aws_lambda_function" "ssl_monitor" {
  function_name = var.function_name
  role         = aws_iam_role.lambda_execution_role.arn
  handler      = "ssl_certificate_monitor.lambda_handler.lambda_handler"
  runtime      = "python3.9"
  timeout      = var.lambda_timeout
  memory_size  = var.lambda_memory_size
  description  = "SSL证书过期监控系统"

  # 占位符代码 - 实际部署时会被替换
  filename         = "placeholder.zip"
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  environment {
    variables = {
      DOMAINS       = join(",", var.domains_to_monitor)
      SNS_TOPIC_ARN = aws_sns_topic.ssl_alerts.arn
      LOG_LEVEL     = var.log_level
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.sns_publish_policy,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = {
    Name    = var.function_name
    Project = "ssl-certificate-monitor"
  }
}

# 占位符ZIP文件
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "placeholder.zip"
  source {
    content = <<EOF
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Please deploy the actual code using the deployment script.'
    }
EOF
    filename = "lambda_function.py"
  }
}

# EventBridge规则
resource "aws_cloudwatch_event_rule" "schedule_rule" {
  name                = "${var.function_name}-schedule"
  description         = "SSL证书监控定时触发规则"
  schedule_expression = var.schedule_expression
  state              = "ENABLED"

  tags = {
    Name    = "${var.function_name}-schedule"
    Project = "ssl-certificate-monitor"
  }
}

# EventBridge目标
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.schedule_rule.name
  target_id = "SSLMonitorTarget"
  arn       = aws_lambda_function.ssl_monitor.arn
}

# Lambda权限（允许EventBridge调用）
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ssl_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule_rule.arn
}

# 输出
output "lambda_function_arn" {
  description = "Lambda函数ARN"
  value       = aws_lambda_function.ssl_monitor.arn
}

output "sns_topic_arn" {
  description = "SNS主题ARN"
  value       = aws_sns_topic.ssl_alerts.arn
}

output "schedule_rule_arn" {
  description = "EventBridge规则ARN"
  value       = aws_cloudwatch_event_rule.schedule_rule.arn
}

output "execution_role_arn" {
  description = "Lambda执行角色ARN"
  value       = aws_iam_role.lambda_execution_role.arn
}