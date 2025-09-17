# 故障排除指南

本文档提供SSL证书监控系统常见问题的诊断和解决方案。

## 快速诊断

### 系统健康检查

运行以下命令进行快速系统检查：

```bash
# 1. 检查Lambda函数状态
aws lambda get-function --function-name ssl-certificate-monitor

# 2. 检查最近的执行日志
aws logs tail /aws/lambda/ssl-certificate-monitor --since 1h

# 3. 检查EventBridge规则
aws events describe-rule --name ssl-certificate-monitor-schedule

# 4. 检查SNS主题和订阅
aws sns get-topic-attributes --topic-arn YOUR_SNS_TOPIC_ARN
aws sns list-subscriptions-by-topic --topic-arn YOUR_SNS_TOPIC_ARN
```

### 手动测试

```bash
# 手动触发Lambda函数
aws lambda invoke \
  --function-name ssl-certificate-monitor \
  --payload '{}' \
  --log-type Tail \
  response.json

# 查看响应和日志
cat response.json
```

## 常见问题分类

### 1. 部署问题

#### 1.1 权限错误

**症状**：
```
AccessDenied: User is not authorized to perform: lambda:CreateFunction
```

**原因**：部署用户缺少必要的IAM权限

**解决方案**：
```bash
# 检查当前用户权限
aws sts get-caller-identity
aws iam list-attached-user-policies --user-name YOUR_USERNAME

# 添加必要权限（需要管理员权限）
aws iam attach-user-policy \
  --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

#### 1.2 资源已存在

**症状**：
```
ResourceAlreadyExistsException: Function already exist: ssl-certificate-monitor
```

**原因**：Lambda函数或其他资源已存在

**解决方案**：
```bash
# 选项1：删除现有资源
aws lambda delete-function --function-name ssl-certificate-monitor

# 选项2：使用不同的函数名
# 修改部署脚本中的FUNCTION_NAME变量

# 选项3：更新现有函数
aws lambda update-function-code \
  --function-name ssl-certificate-monitor \
  --zip-file fileb://ssl-certificate-monitor.zip
```

#### 1.3 区域不匹配

**症状**：
```
InvalidParameterValueException: The role defined for the function cannot be assumed by Lambda
```

**原因**：IAM角色和Lambda函数在不同区域

**解决方案**：
```bash
# 检查当前区域
aws configure get region

# 设置正确的区域
aws configure set region us-east-1

# 或在命令中指定区域
aws lambda create-function --region us-east-1 ...
```

### 2. 运行时错误

#### 2.1 Lambda超时

**症状**：
```json
{
  "errorType": "Task timed out after 180.00 seconds"
}
```

**原因**：
- 检查的域名过多
- 网络连接缓慢
- SSL握手时间过长

**解决方案**：
```bash
# 增加超时时间
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --timeout 300

# 增加内存（可能提高网络性能）
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512

# 减少同时检查的域名数量
# 编辑环境变量，减少DOMAINS列表
```

**预防措施**：
```python
# 在代码中添加超时控制
from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker

# 使用较短的超时时间
checker = SSLCertificateChecker(timeout=10)
```

#### 2.2 内存不足

**症状**：
```json
{
  "errorType": "Runtime.OutOfMemory",
  "errorMessage": "RequestId: xxx Process exited before completing request"
}
```

**原因**：
- 处理大量域名
- 内存泄漏
- 数据结构过大

**解决方案**：
```bash
# 增加内存分配
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --memory-size 512

# 查看内存使用情况
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "REPORT"
```

#### 2.3 网络连接错误

**症状**：
```
[ERROR] gaierror: [Errno -2] Name or service not known
[ERROR] timeout: The read operation timed out
```

**原因**：
- DNS解析失败
- 网络连接超时
- 目标服务器不可达

**诊断步骤**：
```bash
# 1. 验证域名是否可解析
nslookup example.com

# 2. 测试SSL连接
openssl s_client -connect example.com:443 -servername example.com

# 3. 检查域名配置
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor \
  --query 'Environment.Variables.DOMAINS'
```

**解决方案**：
```bash
# 1. 修正域名拼写错误
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"corrected-domain.com,example.com",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts"
  }'

# 2. 增加重试机制（已在代码中实现）
# 3. 排除无法访问的域名
```

### 3. 通知问题

#### 3.1 未收到邮件通知

**症状**：证书即将过期但未收到邮件

**诊断步骤**：
```bash
# 1. 检查SNS主题状态
aws sns get-topic-attributes --topic-arn YOUR_SNS_TOPIC_ARN

# 2. 检查订阅状态
aws sns list-subscriptions-by-topic --topic-arn YOUR_SNS_TOPIC_ARN

# 3. 检查Lambda执行日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "SNS"

# 4. 手动发送测试消息
aws sns publish \
  --topic-arn YOUR_SNS_TOPIC_ARN \
  --message "Test message" \
  --subject "Test notification"
```

**常见原因和解决方案**：

1. **邮件订阅未确认**：
```bash
# 重新发送确认邮件
aws sns subscribe \
  --topic-arn YOUR_SNS_TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com
```

2. **邮件被垃圾邮件过滤**：
   - 检查垃圾邮件文件夹
   - 将AWS SNS添加到白名单

3. **SNS权限问题**：
```bash
# 检查Lambda执行角色权限
aws iam get-role-policy \
  --role-name ssl-certificate-monitor-role \
  --policy-name ssl-certificate-monitor-policy
```

#### 3.2 SNS发布失败

**症状**：
```
[ERROR] ClientError: An error occurred (NotFound) when calling the Publish operation: Topic does not exist
```

**原因**：
- SNS主题ARN错误
- 主题被删除
- 权限不足

**解决方案**：
```bash
# 1. 验证SNS主题ARN
aws sns list-topics

# 2. 重新创建主题（如果被删除）
SNS_TOPIC_ARN=$(aws sns create-topic \
  --name ssl-certificate-alerts \
  --query 'TopicArn' \
  --output text)

# 3. 更新Lambda环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com",
    "SNS_TOPIC_ARN":"'$SNS_TOPIC_ARN'",
    "LOG_LEVEL":"INFO"
  }'
```

### 4. 证书检查问题

#### 4.1 SSL握手失败

**症状**：
```
[ERROR] SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**原因**：
- 自签名证书
- 证书链不完整
- 证书已过期
- 主机名不匹配

**诊断**：
```bash
# 使用openssl检查证书
openssl s_client -connect example.com:443 -servername example.com -verify_return_error

# 检查证书链
openssl s_client -connect example.com:443 -servername example.com -showcerts
```

**解决方案**：
- 对于自签名证书，这是预期行为
- 检查服务器证书配置
- 确认域名拼写正确

#### 4.2 证书解析错误

**症状**：
```
[ERROR] ValueError: time data '...' does not match format '%b %d %H:%M:%S %Y %Z'
```

**原因**：证书日期格式不标准

**解决方案**：
```python
# 在ssl_checker.py中添加更多日期格式支持
def _parse_expiry_date(self, cert: dict) -> datetime:
    not_after = cert.get('notAfter')
    if not not_after:
        raise Exception("证书中未找到过期时间信息")
    
    # 尝试多种日期格式
    date_formats = [
        '%b %d %H:%M:%S %Y %Z',
        '%b %d %H:%M:%S %Y GMT',
        # 添加其他格式...
    ]
    
    for fmt in date_formats:
        try:
            expiry_date = datetime.strptime(not_after, fmt)
            return expiry_date.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    
    raise Exception(f"无法解析证书过期时间: {not_after}")
```

### 5. 配置问题

#### 5.1 环境变量错误

**症状**：
```
[ERROR] 没有找到要检查的域名
```

**诊断**：
```bash
# 检查环境变量
aws lambda get-function-configuration \
  --function-name ssl-certificate-monitor \
  --query 'Environment.Variables'
```

**解决方案**：
```bash
# 设置正确的环境变量
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com,test.org",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts",
    "LOG_LEVEL":"INFO"
  }'
```

#### 5.2 域名格式错误

**症状**：部分域名被跳过或检查失败

**原因**：域名格式不正确

**解决方案**：
```bash
# 正确的域名格式
DOMAINS="example.com,test.org,mysite.net"

# 错误的格式（避免）
DOMAINS="https://example.com, test.org , mysite.net/"

# 更新配置
aws lambda update-function-configuration \
  --function-name ssl-certificate-monitor \
  --environment Variables='{
    "DOMAINS":"example.com,test.org,mysite.net",
    "SNS_TOPIC_ARN":"arn:aws:sns:us-east-1:123456789012:alerts"
  }'
```

### 6. 定时触发问题

#### 6.1 定时任务未执行

**症状**：Lambda函数从未自动执行

**诊断**：
```bash
# 检查EventBridge规则
aws events describe-rule --name ssl-certificate-monitor-schedule

# 检查规则目标
aws events list-targets-by-rule --rule ssl-certificate-monitor-schedule

# 检查Lambda权限
aws lambda get-policy --function-name ssl-certificate-monitor
```

**解决方案**：
```bash
# 重新创建EventBridge规则
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "rate(30 days)" \
  --state ENABLED

# 添加Lambda目标
aws events put-targets \
  --rule ssl-certificate-monitor-schedule \
  --targets "Id"="1","Arn"="$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.FunctionArn' --output text)"

# 授权EventBridge调用Lambda
aws lambda add-permission \
  --function-name ssl-certificate-monitor \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "$(aws events describe-rule --name ssl-certificate-monitor-schedule --query 'Arn' --output text)"
```

#### 6.2 定时表达式错误

**症状**：定时任务执行频率不正确

**常见错误**：
```bash
# 错误的表达式
"rate(30 day)"    # 应该是 "days"
"cron(0 9 * * *)" # 缺少年份字段

# 正确的表达式
"rate(30 days)"
"cron(0 9 * * ? *)"
```

**解决方案**：
```bash
# 更新定时表达式
aws events put-rule \
  --name ssl-certificate-monitor-schedule \
  --schedule-expression "rate(7 days)"
```

## 日志分析

### 启用详细日志

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

### 常见日志模式

#### 成功执行
```
[INFO] 开始SSL证书检查，共 3 个域名
[INFO] 证书正常 - 域名: example.com, 过期时间: 2024-06-15T23:59:59+00:00, 剩余天数: 120 天
[WARNING] 证书即将过期 - 域名: test.org, 过期时间: 2024-02-10T23:59:59+00:00, 剩余天数: 25 天
[INFO] SNS 通知发送成功，接收者数量: 1
[INFO] SSL证书检查完成
```

#### 网络错误
```
[WARNING] 尝试 1/4 失败: gaierror: [Errno -2] Name or service not known，1.0秒后重试
[WARNING] 尝试 2/4 失败: timeout: The read operation timed out，2.0秒后重试
[ERROR] 重试次数用尽，最终失败: gaierror: [Errno -2] Name or service not known
```

#### 配置错误
```
[WARNING] 环境变量 SNS_TOPIC_ARN 为空，使用默认域名列表
[ERROR] 没有找到要检查的域名
```

### 日志查询命令

```bash
# 查看最近1小时的错误日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"

# 查看特定域名的日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "example.com"

# 查看SNS相关日志
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "SNS"

# 查看执行统计
aws logs filter-log-events \
  --log-group-name /aws/lambda/ssl-certificate-monitor \
  --filter-pattern "REPORT"
```

## 性能优化

### 监控性能指标

```bash
# 查看Lambda性能指标
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=ssl-certificate-monitor \
  --start-time $(date -d '7 days ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum
```

### 优化建议

1. **批量处理优化**：
```python
# 在lambda_handler.py中调整批量大小
def _check_certificates_batch(self, domains: List[str], batch_size: int = 5):
    # 减少批量大小以避免超时
```

2. **并发控制**：
```python
# 限制并发连接数
import threading
semaphore = threading.Semaphore(5)  # 最多5个并发连接
```

3. **缓存机制**：
```python
# 添加简单的缓存避免重复检查
cache = {}
if domain in cache and cache[domain]['timestamp'] > recent_time:
    return cache[domain]['result']
```

## 监控和告警

### 设置CloudWatch告警

```bash
# Lambda错误告警
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

# Lambda超时告警
aws cloudwatch put-metric-alarm \
  --alarm-name "SSL-Monitor-Timeout" \
  --alarm-description "SSL证书监控Lambda函数超时" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Maximum \
  --period 300 \
  --threshold 270000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=ssl-certificate-monitor \
  --evaluation-periods 1
```

### 健康检查脚本

创建一个简单的健康检查脚本：

```bash
#!/bin/bash
# health-check.sh

FUNCTION_NAME="ssl-certificate-monitor"

echo "检查Lambda函数状态..."
aws lambda get-function --function-name $FUNCTION_NAME > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ Lambda函数存在"
else
    echo "✗ Lambda函数不存在"
    exit 1
fi

echo "检查最近执行..."
RECENT_LOGS=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/$FUNCTION_NAME \
    --start-time $(date -d '2 days ago' +%s)000 \
    --filter-pattern "START RequestId" \
    --query 'events[0]')

if [ "$RECENT_LOGS" != "null" ]; then
    echo "✓ 最近有执行记录"
else
    echo "⚠ 最近2天内无执行记录"
fi

echo "健康检查完成"
```

## 常见问题FAQ

### 一般问题

#### Q: 系统支持监控多少个域名？
A: 理论上没有限制，但建议：
- 少于20个域名：使用默认配置（128MB内存，180秒超时）
- 20-50个域名：增加到256MB内存，300秒超时
- 超过50个域名：考虑分批部署多个Lambda函数

#### Q: 可以修改检查频率吗？
A: 可以，通过修改EventBridge规则：
```bash
# 每周检查
aws events put-rule --name ssl-certificate-monitor-schedule --schedule-expression "rate(7 days)"

# 每天上午9点检查
aws events put-rule --name ssl-certificate-monitor-schedule --schedule-expression "cron(0 9 * * ? *)"
```

#### Q: 如何监控内网域名？
A: Lambda函数运行在AWS网络中，无法直接访问内网域名。解决方案：
1. 将Lambda部署到VPC中
2. 配置VPC路由到内网
3. 确保安全组允许HTTPS出站流量

#### Q: 支持自签名证书吗？
A: 系统会检查自签名证书，但会记录SSL验证错误。这是正常行为，不会影响过期时间检查。

### 配置问题

#### Q: 域名格式有什么要求？
A: 系统会自动清理域名格式：
```bash
# 输入格式（会自动清理）
https://example.com → example.com
www.example.com → example.com  
example.com:443 → example.com
example.com/path → example.com

# 不支持的格式
192.168.1.1  # IP地址
*.example.com  # 通配符域名
localhost  # 本地域名
```

#### Q: 如何设置不同的过期提醒天数？
A: 当前版本固定为30天。如需修改，需要更新代码中的 `EXPIRY_WARNING_DAYS` 常量。

#### Q: 可以发送到多个邮箱吗？
A: 可以，在SNS主题中添加多个邮箱订阅：
```bash
aws sns subscribe --topic-arn YOUR_TOPIC_ARN --protocol email --notification-endpoint admin1@company.com
aws sns subscribe --topic-arn YOUR_TOPIC_ARN --protocol email --notification-endpoint admin2@company.com
```

### 部署问题

#### Q: 部署时提示权限不足怎么办？
A: 确保部署用户具有以下权限：
- Lambda函数管理权限
- IAM角色创建和管理权限
- SNS主题管理权限
- EventBridge规则管理权限
- CloudWatch日志权限

#### Q: 可以部署到不同的AWS区域吗？
A: 可以，但需要注意：
1. 修改部署脚本中的区域设置
2. 确保SNS主题在同一区域
3. 更新环境变量中的SNS主题ARN

#### Q: 如何在多个AWS账户中部署？
A: 每个账户需要独立部署：
1. 在每个账户中运行部署脚本
2. 配置各自的域名列表
3. 设置各自的通知邮箱

### 运行问题

#### Q: 为什么有些域名检查失败？
A: 常见原因：
1. 域名拼写错误或不存在
2. 域名无法公开访问
3. SSL证书配置问题
4. 网络连接超时

检查方法：
```bash
# 验证域名可访问性
curl -I https://example.com
openssl s_client -connect example.com:443 -servername example.com
```

#### Q: Lambda函数执行时间过长怎么办？
A: 优化方案：
1. 增加内存分配（提高网络性能）
2. 减少同时检查的域名数量
3. 增加超时时间
4. 检查是否有域名响应缓慢

#### Q: 如何处理证书链不完整的情况？
A: 系统会记录证书链问题但继续检查过期时间。建议：
1. 联系域名管理员修复证书配置
2. 在监控中标记这些域名
3. 定期检查证书链完整性

### 通知问题

#### Q: 为什么没有收到过期通知？
A: 检查清单：
1. 确认邮箱订阅已确认
2. 检查垃圾邮件文件夹
3. 验证SNS主题ARN正确
4. 确认确实有证书即将过期
5. 检查Lambda执行日志

#### Q: 可以自定义通知内容吗？
A: 可以修改代码中的通知模板。在 `sns_notification.py` 中找到 `format_notification_content` 方法进行自定义。

#### Q: 支持其他通知方式吗？
A: 当前仅支持SNS邮件通知。可以扩展支持：
1. SNS短信通知
2. Slack集成
3. 企业微信通知
4. 自定义Webhook

### 成本问题

#### Q: 运行成本是多少？
A: 基于AWS定价（美国东部区域）：
- Lambda：每月约$0.01（128MB，每月1次执行）
- SNS：每月约$0.01（少量消息）
- CloudWatch Logs：约$0.01（少量日志）
- 总计：约$0.03/月

#### Q: 如何优化成本？
A: 优化建议：
1. 设置合理的日志保留期（14天）
2. 使用最小必要的内存配置
3. 避免过于频繁的检查
4. 定期清理不需要的域名

## 获取支持

### 自助诊断工具

创建诊断脚本：
```bash
#!/bin/bash
# diagnose.sh - SSL证书监控系统诊断工具

echo "=== SSL证书监控系统诊断 ==="
echo "时间: $(date)"
echo

# 1. 检查AWS CLI配置
echo "1. 检查AWS CLI配置..."
aws --version
aws sts get-caller-identity
echo

# 2. 检查Lambda函数
echo "2. 检查Lambda函数..."
aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.[FunctionName,Runtime,MemorySize,Timeout,LastModified]' --output table
echo

# 3. 检查环境变量
echo "3. 检查环境变量..."
aws lambda get-function-configuration --function-name ssl-certificate-monitor --query 'Environment.Variables' --output table
echo

# 4. 检查最近执行
echo "4. 检查最近执行..."
aws logs filter-log-events --log-group-name /aws/lambda/ssl-certificate-monitor --start-time $(date -d '24 hours ago' +%s)000 --filter-pattern "START RequestId" --query 'events[0:3].[eventId,message]' --output table
echo

# 5. 检查错误日志
echo "5. 检查最近错误..."
aws logs filter-log-events --log-group-name /aws/lambda/ssl-certificate-monitor --start-time $(date -d '24 hours ago' +%s)000 --filter-pattern "ERROR" --query 'events[0:5].message' --output table
echo

# 6. 检查SNS配置
echo "6. 检查SNS配置..."
SNS_ARN=$(aws lambda get-function-configuration --function-name ssl-certificate-monitor --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)
if [ "$SNS_ARN" != "None" ]; then
    aws sns get-topic-attributes --topic-arn "$SNS_ARN" --query 'Attributes.[DisplayName,SubscriptionsConfirmed,SubscriptionsPending]' --output table
    aws sns list-subscriptions-by-topic --topic-arn "$SNS_ARN" --query 'Subscriptions[*].[Protocol,Endpoint,SubscriptionArn]' --output table
fi
echo

echo "=== 诊断完成 ==="
```

### 收集诊断信息

在寻求帮助时，请收集以下信息：

```bash
# 运行诊断脚本
chmod +x diagnose.sh
./diagnose.sh > diagnosis-report.txt

# 或手动收集信息
# 1. 系统信息
aws --version
aws sts get-caller-identity

# 2. Lambda配置
aws lambda get-function-configuration --function-name ssl-certificate-monitor

# 3. 最近的日志
aws logs tail /aws/lambda/ssl-certificate-monitor --since 1h

# 4. EventBridge配置
aws events describe-rule --name ssl-certificate-monitor-schedule

# 5. SNS配置
aws sns get-topic-attributes --topic-arn YOUR_SNS_TOPIC_ARN
```

### 联系支持

1. **GitHub Issues**：提交详细的问题报告
2. **AWS Support**：对于AWS服务相关问题
3. **社区论坛**：寻求社区帮助

### 问题报告模板

```markdown
## 问题描述
[简要描述问题]

## 环境信息
- AWS区域：
- Lambda函数名：
- 部署方式：[CloudFormation/Terraform/手动]

## 重现步骤
1. 
2. 
3. 

## 预期行为
[描述预期的行为]

## 实际行为
[描述实际发生的情况]

## 日志信息
```
[粘贴相关日志]
```

## 已尝试的解决方案
[列出已经尝试的解决方案]
```

通过遵循本故障排除指南，您应该能够诊断和解决大多数常见问题。如果问题仍然存在，请不要犹豫寻求帮助。