# SSL证书监控系统

一个基于AWS Lambda的自动化SSL证书过期监控系统，能够定期检查您的网站SSL证书状态，并在证书即将过期时通过SNS发送通知。

## 功能特性

- 🔍 **自动检查**：每30天自动检查SSL证书状态
- 📧 **智能通知**：仅在证书即将过期（30天内）或已过期时发送通知
- 🛡️ **错误处理**：完善的网络错误处理和重试机制
- 📊 **详细报告**：包含证书过期时间、颁发者、剩余天数等详细信息
- 🔧 **灵活配置**：支持环境变量配置，易于管理
- 📈 **批量处理**：支持同时监控多个域名
- 🔒 **安全设计**：输入验证、敏感信息保护等安全措施

## 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  EventBridge    │───▶│  Lambda Function │───▶│  SNS Topic      │
│  (定时触发)      │    │  (SSL检查器)      │    │  (邮件通知)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │  CloudWatch Logs │
                       │  (执行日志)       │
                       └──────────────────┘
```

## 快速开始

### 前提条件

- AWS账户和已配置的AWS CLI
- Python 3.9+
- 有效的邮箱地址用于接收通知

### 1. 克隆项目

```bash
git clone <repository-url>
cd ssl-certificate-monitor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板：

```bash
cp .env.template .env
```

编辑 `.env` 文件，设置您的配置：

```bash
# 必需配置
DOMAINS=example.com,yoursite.com,anotherdomain.org
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts

# 可选配置
LOG_LEVEL=INFO
```

### 4. 部署系统

详细的部署指南请参考 [DEPLOYMENT.md](DEPLOYMENT.md)

选择以下任一部署方式：

#### 方式1：使用CloudFormation（推荐）

最适合AWS原生环境，提供完整的基础设施管理：

```bash
# 1. 配置参数
cp cloudformation-parameters.json.example cloudformation-parameters.json
# 编辑参数文件，设置域名和邮箱

# 2. 一键部署
./deploy-cloudformation.sh

# 3. 确认邮件订阅
# 检查邮箱并确认SNS订阅
```

#### 方式2：使用Terraform

适合多云环境和基础设施即代码管理：

```bash
# 1. 配置变量
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# 编辑变量文件

# 2. 部署基础设施
./deploy-terraform.sh

# 3. 确认邮件订阅
```

#### 方式3：手动部署

适合快速测试和学习：

```bash
# 1. 创建IAM角色和SNS主题
./create-iam-role.sh

# 2. 设置环境变量
export LAMBDA_ROLE_ARN=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ssl-certificate-monitor-role
export SNS_TOPIC_ARN=$(aws sns create-topic --name ssl-certificate-alerts --query 'TopicArn' --output text)

# 3. 部署Lambda函数
./deploy.sh

# 4. 创建定时触发器
aws events put-rule --name ssl-certificate-monitor-schedule --schedule-expression "rate(30 days)"
aws events put-targets --rule ssl-certificate-monitor-schedule --targets "Id"="1","Arn"="$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.FunctionArn' --output text)"
```

### 5. 验证部署

```bash
# 测试Lambda函数
aws lambda invoke --function-name ssl-certificate-monitor --payload '{}' response.json
cat response.json
```

## 配置说明

### 环境变量配置

### 必需配置

| 变量名 | 必需 | 描述 | 示例 | 验证规则 |
|--------|------|------|------|----------|
| `DOMAINS` | 是 | 要监控的域名列表（逗号分隔） | `example.com,test.org` | 有效域名格式，不含协议和路径 |
| `SNS_TOPIC_ARN` | 是 | SNS主题ARN | `arn:aws:sns:us-east-1:123456789012:alerts` | 有效的SNS ARN格式 |

### 可选配置

| 变量名 | 必需 | 默认值 | 描述 | 可选值 |
|--------|------|--------|------|--------|
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### 环境变量设置示例

```bash
# 在Lambda控制台设置
DOMAINS=example.com,yoursite.com,anotherdomain.org
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts
LOG_LEVEL=INFO

# 在.env文件中设置（本地测试）
DOMAINS=example.com,test.org
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts
LOG_LEVEL=DEBUG

# 使用AWS CLI设置
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com,yoursite.com,test.org",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts",
    "LOG_LEVEL":"INFO"
  }'
```

### 域名配置详细说明

系统支持多种域名输入格式，会自动清理和标准化：

```bash
# ✅ 支持的格式（会自动清理）
DOMAINS="example.com,www.test.org,https://mysite.net,another.com:443,site.com/path"

# 系统会自动转换为
DOMAINS="example.com,test.org,mysite.net,another.com,site.com"

# ❌ 不支持的格式
DOMAINS="192.168.1.1,localhost,*.example.com"  # IP地址、本地域名、通配符
```

### 日志级别说明

| 级别 | 输出内容 | 适用场景 |
|------|----------|----------|
| `DEBUG` | 详细的调试信息，包括每个步骤 | 开发和故障排除 |
| `INFO` | 基本执行信息和结果 | 生产环境（推荐） |
| `WARNING` | 警告和非致命错误 | 最小化日志输出 |
| `ERROR` | 仅错误信息 | 仅关注错误 |

### 支持的域名格式

系统会自动清理和标准化域名格式：

```bash
# 支持的输入格式
https://example.com      # 自动移除协议
www.example.com         # 自动移除www前缀
example.com:443         # 自动移除端口号
example.com/path        # 自动移除路径
```

### 定时配置

默认每30天执行一次检查。可以通过修改EventBridge规则来调整：

```bash
# 每天检查
rate(1 day)

# 每周检查
rate(7 days)

# 每月1号上午9点检查
cron(0 9 1 * ? *)
```

## 使用指南

### 查看执行日志

```bash
# 查看最近的日志
aws logs tail /aws/lambda/ssl-certificate-monitor --follow

# 查看特定时间段的日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --start-time 1640995200000
```

### 手动触发检查

```bash
# 手动执行检查
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  response.json
```

### 更新域名列表

```bash
# 更新环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"newdomain.com,example.com",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts",
    "LOG_LEVEL":"INFO"
  }'
```

### 更新Lambda代码

```bash
# 重新打包并部署
./deploy.sh package
aws lambda update-function-code \
  --function-name ssl-certificate-monitor \
  --zip-file fileb://ssl-certificate-monitor.zip
```

## 通知示例

当发现即将过期的证书时，您会收到类似以下内容的邮件：

```
主题: ⚠️ SSL证书提醒: 2个证书即将过期

SSL证书过期监控报告
==============================
检查时间: 2024-01-15 09:00:00

⚠️ 即将过期证书 (30天内):

• example.com
  过期时间: 2024-02-10 23:59:59
  剩余天数: 26 天
  颁发者: Let's Encrypt

• test.org
  过期时间: 2024-02-05 12:30:00
  剩余天数: 21 天
  颁发者: DigiCert Inc

建议操作:
1. 立即续期已过期的证书
2. 计划续期即将过期的证书
3. 更新证书后重新部署相关服务

此消息由SSL证书监控系统自动发送。
```

## 故障排除

详细的故障排除指南请参考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### 常见问题快速解决

#### 1. Lambda函数超时

**症状**：函数执行超时，部分域名未检查完成

**快速解决**：
```bash
# 增加超时时间到5分钟
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --timeout 300

# 同时增加内存以提高性能
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512
```

#### 2. 域名解析失败

**症状**：日志中显示DNS解析错误

**快速解决**：
```bash
# 验证域名格式
echo "example.com,test.org" | tr ',' '\n' | while read domain; do
  nslookup "$domain" && echo "✓ $domain 可解析" || echo "✗ $domain 解析失败"
done

# 更新正确的域名列表
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"corrected-domain.com,example.com",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts"
  }'
```

#### 3. SNS通知未收到

**症状**：证书过期但未收到邮件通知

**快速解决**：
```bash
# 检查并重新确认订阅
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts

# 重新订阅邮件通知
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# 测试SNS发送
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts \
  --message "测试消息" \
  --subject "SSL监控测试"
```

#### 4. 权限错误

**症状**：Lambda函数无法发送SNS消息

**快速解决**：
```bash
# 检查当前IAM角色权限
aws iam get-role-policy \
  --role-name ssl-certificate-monitor-role \
  --policy-name ssl-certificate-monitor-policy

# 如果权限不足，重新应用策略
aws iam put-role-policy \
  --role-name ssl-certificate-monitor-role \
  --policy-name ssl-certificate-monitor-policy \
  --policy-document file://iam-policy.json
```

#### 5. 配置验证失败

**症状**：Lambda函数启动时配置验证错误

**快速解决**：
```bash
# 检查当前环境变量
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor \
  --query 'Environment.Variables'

# 设置完整的环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com,test.org",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts",
    "LOG_LEVEL":"INFO"
  }'
```

### 调试模式

启用详细日志记录：

```bash
# 设置DEBUG日志级别
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts",
    "LOG_LEVEL":"DEBUG"
  }'
```

### 性能优化

#### 大量域名优化

如果需要监控大量域名（>50个）：

1. **增加内存和超时时间**：
```bash
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512 \
  --timeout 900
```

2. **考虑分批部署**：
将域名分组，创建多个Lambda函数分别监控。

## 运维指南

### 日常维护

#### 监控系统健康

```bash
# 检查最近执行状态
aws logs tail /aws/lambda/ssl-certificate-monitor --since 1h

# 查看执行统计
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "REPORT" \
  --start-time $(date -d '7 days ago' +%s)000

# 检查错误日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "ERROR" \
  --start-time $(date -d '24 hours ago' +%s)000
```

#### 更新域名列表

```bash
# 添加新域名
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com,newdomain.com,test.org",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts",
    "LOG_LEVEL":"INFO"
  }'

# 验证更新
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor \
  --query 'Environment.Variables.DOMAINS'
```

#### 更新通知设置

```bash
# 添加新的邮件订阅者
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts \
  --protocol email \
  --notification-endpoint new-admin@company.com

# 查看所有订阅者
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:123456789012:ssl-certificate-alerts
```

#### 调整检查频率

```bash
# 改为每周检查
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "rate(7 days)"

# 改为每月1号上午9点检查
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "cron(0 9 1 * ? *)"
```

### 系统升级

#### 更新Lambda代码

```bash
# 1. 获取最新代码
git pull origin main

# 2. 重新打包
./deploy.sh package

# 3. 更新函数代码
aws lambda update-function-code \
  --function-name ssl-certificate-monitor \
  --zip-file fileb://ssl-certificate-monitor.zip

# 4. 验证更新
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  response.json && cat response.json
```

#### 更新基础设施

```bash
# CloudFormation方式
aws cloudformation update-stack \
  --stack-name ssl-certificate-monitor \
  --template-body file://cloudformation-template.yaml \
  --parameters file://cloudformation-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM

# Terraform方式
cd terraform && terraform plan && terraform apply
```

### 备份和恢复

#### 配置备份

```bash
# 备份Lambda配置
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor > lambda-config-backup.json

# 备份环境变量
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor \
  --query 'Environment.Variables' > env-vars-backup.json

# 备份EventBridge规则
aws events describe-rule \
  --name ssl-certificate-monitor-schedule > eventbridge-rule-backup.json
```

#### 配置恢复

```bash
# 恢复环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables="$(cat env-vars-backup.json)"

# 恢复定时规则
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "$(cat eventbridge-rule-backup.json | jq -r '.ScheduleExpression')"
```

## 开发指南

### 本地开发环境

```bash
# 1. 克隆项目
git clone <repository-url>
cd ssl-certificate-monitor

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 如果存在

# 4. 设置环境变量
cp .env.template .env
# 编辑 .env 文件
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试文件
python -m pytest tests/test_ssl_checker.py -v

# 运行特定测试方法
python -m pytest tests/test_ssl_checker.py::TestSSLCertificateChecker::test_check_valid_certificate -v

# 生成代码覆盖率报告
python -m pytest tests/ --cov=ssl_certificate_monitor --cov-report=html
open htmlcov/index.html  # 查看覆盖率报告
```

### 本地测试

```bash
# 测试单个域名检查
python -c "
from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker
checker = SSLCertificateChecker()
result = checker.check_certificate('example.com')
print(f'域名: {result.domain}')
print(f'过期时间: {result.expiry_date}')
print(f'剩余天数: {result.days_until_expiry}')
"

# 测试完整流程（需要设置环境变量）
python -c "
import os
os.environ['DOMAINS'] = 'example.com'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
from ssl_certificate_monitor.lambda_handler import lambda_handler
result = lambda_handler({}, None)
print(result)
"
```

### 项目结构

```
ssl-certificate-monitor/
├── ssl_certificate_monitor/          # 主要代码
│   ├── __init__.py
│   ├── lambda_handler.py             # Lambda入口点
│   ├── models.py                     # 数据模型
│   ├── interfaces.py                 # 服务接口
│   └── services/                     # 服务实现
│       ├── ssl_checker.py            # SSL证书检查
│       ├── domain_config.py          # 域名配置管理
│       ├── sns_notification.py       # SNS通知服务
│       ├── logger.py                 # 日志服务
│       ├── error_handler.py          # 错误处理
│       ├── expiry_calculator.py      # 过期计算
│       └── config_validator.py       # 配置验证
├── tests/                            # 测试代码
│   ├── test_ssl_checker.py
│   ├── test_domain_config.py
│   ├── test_sns_notification.py
│   ├── test_logger.py
│   ├── test_error_handler.py
│   ├── test_config_validator.py
│   ├── test_lambda_handler.py
│   ├── test_integration.py
│   └── test_performance_security.py
├── terraform/                        # Terraform配置
├── deploy.sh                         # 部署脚本
├── deploy-cloudformation.sh          # CloudFormation部署
├── deploy-terraform.sh               # Terraform部署
├── cloudformation-template.yaml      # CloudFormation模板
├── requirements.txt                  # Python依赖
├── requirements-lambda.txt           # Lambda专用依赖
└── README.md                         # 项目文档
```

### 添加新功能

1. **创建服务接口**：在 `interfaces.py` 中定义接口
2. **实现服务类**：在 `services/` 目录下创建实现
3. **编写测试**：在 `tests/` 目录下添加测试
4. **集成到主流程**：在 `lambda_handler.py` 中集成
5. **更新文档**：更新README和相关文档

## 安全考虑

### 权限最小化

Lambda函数仅具有必要的最小权限：
- CloudWatch Logs写入权限
- SNS发布权限

### 输入验证

- 域名格式验证
- 环境变量清理
- 错误消息脱敏

### 网络安全

- 仅支持HTTPS连接
- 证书链验证
- 超时保护

## 成本估算

基于AWS定价（美国东部区域）：

| 服务 | 用量 | 月成本（USD） |
|------|------|---------------|
| Lambda | 每月1次执行，128MB，3分钟 | ~$0.01 |
| SNS | 每月最多几条消息 | ~$0.01 |
| CloudWatch Logs | 少量日志存储 | ~$0.01 |
| **总计** | | **~$0.03** |

> 注：实际成本可能因使用量和地区而异

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 贡献

欢迎提交Issue和Pull Request！

### 开发流程

1. Fork项目
2. 创建功能分支
3. 编写代码和测试
4. 提交Pull Request

### 代码规范

- 遵循PEP 8代码风格
- 编写单元测试
- 添加类型提示
- 更新文档

## 支持

如果您遇到问题或有建议，请：

1. 查看[故障排除](#故障排除)部分
2. 搜索现有的[Issues](../../issues)
3. 创建新的Issue描述问题

## 更新日志

### v1.0.0 (2024-01-15)

- 初始版本发布
- 支持SSL证书过期检查
- SNS邮件通知功能
- 完整的错误处理和重试机制
- CloudFormation和Terraform部署支持