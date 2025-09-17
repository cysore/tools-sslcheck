# 部署指南

本文档提供SSL证书监控系统的详细部署说明，包括三种不同的部署方式。

## 部署方式对比

| 特性 | CloudFormation | Terraform | 手动部署 |
|------|----------------|-----------|----------|
| 复杂度 | 低 | 中 | 高 |
| 基础设施管理 | 自动 | 自动 | 手动 |
| 版本控制 | 是 | 是 | 否 |
| 跨云支持 | 否 | 是 | 否 |
| AWS集成 | 最佳 | 良好 | 基本 |
| 推荐场景 | AWS原生项目 | 多云环境 | 快速测试 |

## 前提条件

### 系统要求

- **操作系统**：Linux、macOS或Windows（WSL）
- **Python**：3.9或更高版本
- **AWS CLI**：2.0或更高版本
- **权限**：AWS账户管理员权限或相应的IAM权限

### 必需的AWS权限

部署用户需要以下IAM权限：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:*",
                "iam:*",
                "sns:*",
                "events:*",
                "logs:*",
                "cloudformation:*"
            ],
            "Resource": "*"
        }
    ]
}
```

### 环境准备

1. **安装AWS CLI**：
```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# 下载并安装AWS CLI MSI安装包
```

2. **配置AWS凭证**：
```bash
aws configure
# 输入Access Key ID、Secret Access Key、默认区域和输出格式
```

3. **验证配置**：
```bash
aws sts get-caller-identity
```

## 方式1：CloudFormation部署（推荐）

CloudFormation是AWS原生的基础设施即代码服务，最适合纯AWS环境。

### 步骤1：准备配置文件

```bash
# 复制参数模板
cp cloudformation-parameters.json.example cloudformation-parameters.json

# 编辑参数文件
vim cloudformation-parameters.json
```

参数文件示例：
```json
[
    {
        "ParameterKey": "FunctionName",
        "ParameterValue": "ssl-certificate-monitor"
    },
    {
        "ParameterKey": "ScheduleExpression",
        "ParameterValue": "rate(30 days)"
    },
    {
        "ParameterKey": "DomainsToMonitor",
        "ParameterValue": "example.com,yoursite.com,anotherdomain.org"
    },
    {
        "ParameterKey": "NotificationEmail",
        "ParameterValue": "admin@yourcompany.com"
    },
    {
        "ParameterKey": "LogLevel",
        "ParameterValue": "INFO"
    }
]
```

### 步骤2：部署基础设施

```bash
# 使用部署脚本（推荐）
./deploy-cloudformation.sh

# 或手动部署
aws cloudformation create-stack \
  --stack-name ssl-certificate-monitor \
  --template-body file://cloudformation-template.yaml \
  --parameters file://cloudformation-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### 步骤3：部署Lambda代码

```bash
# 创建部署包
./deploy.sh package

# 更新Lambda代码
aws lambda update-function-code \
  --function-name ssl-certificate-monitor \
  --zip-file fileb://ssl-certificate-monitor.zip
```

### 步骤4：确认邮件订阅

检查您的邮箱，确认SNS订阅邮件。

### 步骤5：测试部署

```bash
# 手动触发测试
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  response.json

# 查看响应
cat response.json
```

## 方式2：Terraform部署

Terraform提供了更灵活的基础设施管理，支持多云环境。

### 步骤1：安装Terraform

```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# 验证安装
terraform version
```

### 步骤2：配置变量

```bash
# 复制变量模板
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# 编辑变量文件
vim terraform/terraform.tfvars
```

变量文件示例：
```hcl
# AWS配置
aws_region = "us-east-1"

# Lambda函数配置
function_name      = "ssl-certificate-monitor"
lambda_timeout     = 180
lambda_memory_size = 256

# 监控配置
domains_to_monitor = [
  "example.com",
  "yoursite.com",
  "anotherdomain.org"
]

# 定时配置
schedule_expression = "rate(30 days)"

# 通知配置
notification_email = "admin@yourcompany.com"

# 日志配置
log_level = "INFO"
```

### 步骤3：初始化和部署

```bash
# 使用部署脚本（推荐）
./deploy-terraform.sh

# 或手动部署
cd terraform
terraform init
terraform plan
terraform apply
```

### 步骤4：部署Lambda代码

```bash
# 返回项目根目录
cd ..

# 创建部署包
./deploy.sh package

# 获取函数名并更新代码
FUNCTION_NAME=$(cd terraform && terraform output -raw lambda_function_arn | cut -d':' -f7)
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file fileb://ssl-certificate-monitor.zip
```

### 步骤5：验证部署

```bash
# 查看Terraform输出
cd terraform
terraform output

# 测试Lambda函数
cd ..
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  response.json
```

## 方式3：手动部署

手动部署适合快速测试或学习目的，但不推荐用于生产环境。

### 步骤1：创建IAM角色

```bash
# 使用脚本创建角色
./create-iam-role.sh

# 或手动创建
aws iam create-role \
  --role-name ssl-certificate-monitor-role \
  --assume-role-policy-document file://iam-trust-policy.json

aws iam create-policy \
  --policy-name ssl-certificate-monitor-policy \
  --policy-document file://iam-policy.json

aws iam attach-role-policy \
  --role-name ssl-certificate-monitor-role \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/ssl-certificate-monitor-policy
```

### 步骤2：创建SNS主题

```bash
# 创建SNS主题
SNS_TOPIC_ARN=$(aws sns create-topic \
  --name ssl-certificate-alerts \
  --query 'TopicArn' \
  --output text)

# 订阅邮件通知
aws sns subscribe \
  --topic-arn "$SNS_TOPIC_ARN" \
  --protocol email \
  --notification-endpoint your-email@example.com

echo "SNS Topic ARN: $SNS_TOPIC_ARN"
```

### 步骤3：设置环境变量

```bash
# 设置必要的环境变量
export LAMBDA_ROLE_ARN=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ssl-certificate-monitor-role
export SNS_TOPIC_ARN=$SNS_TOPIC_ARN

# 创建.env文件
cat > .env << EOF
DOMAINS=example.com,yoursite.com
SNS_TOPIC_ARN=$SNS_TOPIC_ARN
LOG_LEVEL=INFO
EOF
```

### 步骤4：部署Lambda函数

```bash
# 使用部署脚本
./deploy.sh

# 或手动部署
./deploy.sh package

aws lambda create-function \
  --function-name ssl-certificate-monitor \
  --runtime python3.9 \
  --role "$LAMBDA_ROLE_ARN" \
  --handler ssl_certificate_monitor.lambda_handler.lambda_handler \
  --zip-file fileb://ssl-certificate-monitor.zip \
  --timeout 180 \
  --memory-size 256 \
  --environment Variables="{$(grep -v '^#' .env | grep -v '^$' | sed 's/^/"/; s/$/"/; s/=/":"/g' | tr '\n' ',' | sed 's/,$//')}"
```

### 步骤5：创建定时触发器

```bash
# 创建EventBridge规则
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "rate(30 days)" \
  --description "SSL证书监控定时触发规则"

# 添加Lambda目标
aws events put-targets \
  --rule ssl-certificate-monitor-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):function:ssl-certificate-monitor"

# 授权EventBridge调用Lambda
aws lambda add-permission \
  --function-name ssl-certificate-monitor \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):rule/ssl-certificate-monitor-schedule"
```

## 部署后配置

### 确认邮件订阅

1. 检查您的邮箱
2. 点击SNS订阅确认邮件中的确认链接
3. 确认订阅状态：

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn "$SNS_TOPIC_ARN"
```

### 测试系统

```bash
# 手动触发Lambda函数
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  response.json

# 查看执行结果
cat response.json

# 查看执行日志
aws logs tail /aws/lambda/ssl-certificate-monitor --follow
```

### 验证定时触发

```bash
# 查看EventBridge规则
aws events list-rules --name-prefix ssl-certificate-monitor

# 查看规则目标
aws events list-targets-by-rule --rule ssl-certificate-monitor-schedule
```

## 配置调优

### 性能优化

#### 大量域名优化

如果监控超过20个域名：

```bash
# 增加内存和超时时间
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512 \
  --timeout 600
```

#### 网络优化

```bash
# 如果遇到网络超时，可以调整SSL检查器超时
# 在代码中修改 SSLCertificateChecker 的 timeout 参数
```

### 监控配置

#### 设置CloudWatch告警

```bash
# 创建Lambda错误告警
aws cloudwatch put-metric-alarm \
  --alarm-name "SSL-Monitor-Errors" \
  --alarm-description "SSL证书监控Lambda函数错误" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=FunctionName,Value=ssl-certificate-monitor \
  --evaluation-periods 1
```

#### 设置日志保留

```bash
# 设置日志保留期
aws logs put-retention-policy \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --retention-in-days 14
```

## 更新和维护

### 更新Lambda代码

```bash
# 重新打包
./deploy.sh package

# 更新函数代码
aws lambda update-function-code \
  --function-name ssl-certificate-monitor \
  --zip-file fileb://ssl-certificate-monitor.zip
```

### 更新配置

```bash
# 更新环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"newdomain.com,example.com",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts",
    "LOG_LEVEL":"DEBUG"
  }'
```

### 更新定时规则

```bash
# 修改执行频率
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "rate(7 days)" \
  --description "SSL证书监控定时触发规则"
```

## 卸载系统

### CloudFormation卸载

```bash
# 使用脚本卸载
./deploy-cloudformation.sh delete

# 或手动删除
aws cloudformation delete-stack --stack-name ssl-certificate-monitor
```

### Terraform卸载

```bash
# 使用脚本卸载
./deploy-terraform.sh destroy

# 或手动销毁
cd terraform
terraform destroy
```

### 手动卸载

```bash
# 删除Lambda函数
aws lambda delete-function --function-name ssl-certificate-monitor

# 删除EventBridge规则
aws events remove-targets --rule ssl-certificate-monitor-schedule --ids "1"
aws events delete-rule --name ssl-certificate-monitor-schedule

# 删除SNS主题
aws sns delete-topic --topic-arn "$SNS_TOPIC_ARN"

# 删除IAM角色和策略
aws iam detach-role-policy \
  --role-name ssl-certificate-monitor-role \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/ssl-certificate-monitor-policy

aws iam delete-role --role-name ssl-certificate-monitor-role
aws iam delete-policy \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/ssl-certificate-monitor-policy

# 删除日志组
aws logs delete-log-group --log-group-name /aws/lambda/ssl-certificate-monitor
```

## 故障排除

### 常见部署问题

#### 权限不足

**错误**：`AccessDenied` 或 `UnauthorizedOperation`

**解决**：
```bash
# 检查当前用户权限
aws sts get-caller-identity

# 确保用户具有必要的IAM权限
aws iam list-attached-user-policies --user-name your-username
```

#### 资源已存在

**错误**：`ResourceAlreadyExistsException`

**解决**：
```bash
# 检查现有资源
aws lambda list-functions --query 'Functions[?FunctionName==`ssl-certificate-monitor`]'

# 删除现有资源或使用不同名称
```

#### 区域不匹配

**错误**：资源在错误的AWS区域

**解决**：
```bash
# 检查当前区域
aws configure get region

# 设置正确的区域
aws configure set region us-east-1
```

### 运行时问题

#### Lambda超时

**症状**：函数执行超时

**解决**：
```bash
# 增加超时时间
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --timeout 300
```

#### 内存不足

**症状**：内存使用超限

**解决**：
```bash
# 增加内存分配
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512
```

#### 网络连接问题

**症状**：无法连接到目标域名

**解决**：
1. 检查域名是否可访问
2. 验证DNS解析
3. 检查防火墙设置

### 获取帮助

如果遇到部署问题：

1. 查看CloudWatch日志
2. 检查AWS服务状态
3. 参考AWS文档
4. 提交GitHub Issue

## 最佳实践

### 安全最佳实践

1. **最小权限原则**：仅授予必要的IAM权限
2. **定期轮换凭证**：定期更新AWS访问密钥
3. **监控访问**：启用CloudTrail记录API调用
4. **加密传输**：确保所有通信使用HTTPS

### 运维最佳实践

1. **监控告警**：设置CloudWatch告警
2. **日志管理**：定期清理旧日志
3. **备份配置**：保存配置文件到版本控制
4. **文档更新**：保持部署文档最新

### 成本优化

1. **合理配置**：根据实际需求设置内存和超时
2. **日志保留**：设置合理的日志保留期
3. **定期审查**：定期检查资源使用情况
4. **标签管理**：使用标签跟踪成本