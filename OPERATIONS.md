# 运维操作指南

本文档提供SSL证书监控系统的日常运维操作指南，包括监控、维护、故障处理等。

## 日常监控

### 系统健康检查

#### 每日检查清单

```bash
#!/bin/bash
# daily-health-check.sh - 每日健康检查脚本

echo "=== SSL证书监控系统每日健康检查 ==="
echo "检查时间: $(date)"
echo

# 1. 检查Lambda函数状态
echo "1. 检查Lambda函数状态..."
FUNCTION_STATUS=$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.State' --output text 2>/dev/null)
if [ "$FUNCTION_STATUS" = "Active" ]; then
    echo "✓ Lambda函数状态正常"
else
    echo "✗ Lambda函数状态异常: $FUNCTION_STATUS"
fi

# 2. 检查最近24小时执行情况
echo "2. 检查最近24小时执行情况..."
RECENT_EXECUTIONS=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '24 hours ago' +%s)000 \
    --filter-pattern "START RequestId" \
    --query 'length(events)' --output text)

if [ "$RECENT_EXECUTIONS" -gt 0 ]; then
    echo "✓ 最近24小时有 $RECENT_EXECUTIONS 次执行"
else
    echo "⚠ 最近24小时无执行记录"
fi

# 3. 检查错误日志
echo "3. 检查最近24小时错误..."
ERROR_COUNT=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '24 hours ago' +%s)000 \
    --filter-pattern "ERROR" \
    --query 'length(events)' --output text)

if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "✓ 无错误日志"
else
    echo "⚠ 发现 $ERROR_COUNT 个错误，需要检查"
fi

# 4. 检查SNS主题状态
echo "4. 检查SNS主题状态..."
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)

if [ "$SNS_ARN" != "None" ] && [ "$SNS_ARN" != "null" ]; then
    CONFIRMED_SUBS=$(aws sns get-topic-attributes \
        --topic-arn "$SNS_ARN" \
        --query 'Attributes.SubscriptionsConfirmed' --output text)
    echo "✓ SNS主题正常，已确认订阅: $CONFIRMED_SUBS"
else
    echo "✗ SNS主题配置异常"
fi

echo
echo "=== 健康检查完成 ==="
```

#### 每周检查清单

```bash
#!/bin/bash
# weekly-health-check.sh - 每周健康检查脚本

echo "=== SSL证书监控系统每周健康检查 ==="
echo "检查时间: $(date)"
echo

# 1. 检查执行统计
echo "1. 最近7天执行统计..."
aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '7 days ago' +%s)000 \
    --filter-pattern "REPORT" \
    --query 'events[*].message' --output text | \
    grep -o 'Duration: [0-9.]*' | \
    awk '{sum+=$2; count++} END {
        if(count>0) {
            printf "平均执行时间: %.2f ms\n", sum/count
            printf "总执行次数: %d\n", count
        } else {
            print "无执行记录"
        }
    }'

# 2. 检查内存使用
echo "2. 内存使用统计..."
aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '7 days ago' +%s)000 \
    --filter-pattern "REPORT" \
    --query 'events[*].message' --output text | \
    grep -o 'Max Memory Used: [0-9]*' | \
    awk '{sum+=$4; count++; if($4>max) max=$4} END {
        if(count>0) {
            printf "平均内存使用: %.0f MB\n", sum/count
            printf "最大内存使用: %d MB\n", max
        }
    }'

# 3. 检查域名配置
echo "3. 当前监控域名..."
DOMAINS=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.DOMAINS' --output text)
echo "监控域名数量: $(echo $DOMAINS | tr ',' '\n' | wc -l)"
echo "域名列表: $DOMAINS"

# 4. 检查定时规则
echo "4. 检查定时规则..."
SCHEDULE=$(aws events describe-rule \
    --name ssl-certificate-monitor-schedule \
    --query 'ScheduleExpression' --output text)
STATE=$(aws events describe-rule \
    --name ssl-certificate-monitor-schedule \
    --query 'State' --output text)
echo "定时表达式: $SCHEDULE"
echo "规则状态: $STATE"

echo
echo "=== 每周检查完成 ==="
```

### 监控指标

#### 关键性能指标 (KPI)

1. **执行成功率**：应保持在95%以上
2. **平均执行时间**：应在60秒以内
3. **内存使用率**：应低于80%
4. **错误率**：应低于5%

#### CloudWatch指标监控

```bash
# 创建自定义指标监控脚本
#!/bin/bash
# metrics-monitor.sh

FUNCTION_NAME="ssl-certificate-monitor"
NAMESPACE="AWS/Lambda"

# 获取最近24小时的指标
START_TIME=$(date -d '24 hours ago' -u +%Y-%m-%dT%H:%M:%S)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)

echo "=== Lambda函数性能指标 ==="
echo "时间范围: $START_TIME 到 $END_TIME"
echo

# 1. 调用次数
echo "1. 调用次数:"
aws cloudwatch get-metric-statistics \
    --namespace $NAMESPACE \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 3600 \
    --statistics Sum \
    --query 'Datapoints[*].[Timestamp,Sum]' \
    --output table

# 2. 错误次数
echo "2. 错误次数:"
aws cloudwatch get-metric-statistics \
    --namespace $NAMESPACE \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 3600 \
    --statistics Sum \
    --query 'Datapoints[*].[Timestamp,Sum]' \
    --output table

# 3. 执行时间
echo "3. 执行时间统计:"
aws cloudwatch get-metric-statistics \
    --namespace $NAMESPACE \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --period 3600 \
    --statistics Average,Maximum \
    --query 'Datapoints[*].[Timestamp,Average,Maximum]' \
    --output table
```

## 配置管理

### 域名管理

#### 添加新域名

```bash
#!/bin/bash
# add-domain.sh - 添加新域名到监控列表

NEW_DOMAIN="$1"
if [ -z "$NEW_DOMAIN" ]; then
    echo "用法: $0 <新域名>"
    exit 1
fi

# 验证域名格式
if ! echo "$NEW_DOMAIN" | grep -E '^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$' > /dev/null; then
    echo "错误: 域名格式不正确"
    exit 1
fi

# 获取当前域名列表
CURRENT_DOMAINS=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.DOMAINS' --output text)

# 检查域名是否已存在
if echo "$CURRENT_DOMAINS" | grep -q "$NEW_DOMAIN"; then
    echo "域名 $NEW_DOMAIN 已在监控列表中"
    exit 0
fi

# 添加新域名
NEW_DOMAINS="$CURRENT_DOMAINS,$NEW_DOMAIN"
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)
LOG_LEVEL=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.LOG_LEVEL' --output text)

# 更新环境变量
aws lambda update-function-configuration \
    --function-name ssl-certificate-monitor \
    --environment Variables="{
        \"DOMAINS\":\"$NEW_DOMAINS\",
        \"SNS_TOPIC_ARN\":\"$SNS_ARN\",
        \"LOG_LEVEL\":\"$LOG_LEVEL\"
    }"

echo "成功添加域名: $NEW_DOMAIN"
echo "当前监控域名: $NEW_DOMAINS"
```

#### 删除域名

```bash
#!/bin/bash
# remove-domain.sh - 从监控列表中删除域名

REMOVE_DOMAIN="$1"
if [ -z "$REMOVE_DOMAIN" ]; then
    echo "用法: $0 <要删除的域名>"
    exit 1
fi

# 获取当前域名列表
CURRENT_DOMAINS=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.DOMAINS' --output text)

# 检查域名是否存在
if ! echo "$CURRENT_DOMAINS" | grep -q "$REMOVE_DOMAIN"; then
    echo "域名 $REMOVE_DOMAIN 不在监控列表中"
    exit 0
fi

# 删除域名
NEW_DOMAINS=$(echo "$CURRENT_DOMAINS" | sed "s/$REMOVE_DOMAIN,//g" | sed "s/,$REMOVE_DOMAIN//g" | sed "s/^$REMOVE_DOMAIN$//g")
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)
LOG_LEVEL=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.LOG_LEVEL' --output text)

# 更新环境变量
aws lambda update-function-configuration \
    --function-name ssl-certificate-monitor \
    --environment Variables="{
        \"DOMAINS\":\"$NEW_DOMAINS\",
        \"SNS_TOPIC_ARN\":\"$SNS_ARN\",
        \"LOG_LEVEL\":\"$LOG_LEVEL\"
    }"

echo "成功删除域名: $REMOVE_DOMAIN"
echo "当前监控域名: $NEW_DOMAINS"
```

### 通知管理

#### 添加邮件订阅者

```bash
#!/bin/bash
# add-email-subscriber.sh - 添加邮件订阅者

EMAIL="$1"
if [ -z "$EMAIL" ]; then
    echo "用法: $0 <邮箱地址>"
    exit 1
fi

# 验证邮箱格式
if ! echo "$EMAIL" | grep -E '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' > /dev/null; then
    echo "错误: 邮箱格式不正确"
    exit 1
fi

# 获取SNS主题ARN
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)

if [ "$SNS_ARN" = "None" ] || [ "$SNS_ARN" = "null" ]; then
    echo "错误: 未配置SNS主题ARN"
    exit 1
fi

# 检查是否已订阅
EXISTING_SUB=$(aws sns list-subscriptions-by-topic \
    --topic-arn "$SNS_ARN" \
    --query "Subscriptions[?Endpoint=='$EMAIL'].SubscriptionArn" \
    --output text)

if [ -n "$EXISTING_SUB" ] && [ "$EXISTING_SUB" != "None" ]; then
    echo "邮箱 $EMAIL 已订阅"
    exit 0
fi

# 添加订阅
aws sns subscribe \
    --topic-arn "$SNS_ARN" \
    --protocol email \
    --notification-endpoint "$EMAIL"

echo "已向 $EMAIL 发送订阅确认邮件"
echo "请检查邮箱并点击确认链接"
```

#### 查看订阅状态

```bash
#!/bin/bash
# list-subscribers.sh - 查看所有订阅者

SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)

if [ "$SNS_ARN" = "None" ] || [ "$SNS_ARN" = "null" ]; then
    echo "错误: 未配置SNS主题ARN"
    exit 1
fi

echo "=== SNS主题订阅状态 ==="
echo "主题ARN: $SNS_ARN"
echo

# 获取主题属性
echo "主题统计:"
aws sns get-topic-attributes \
    --topic-arn "$SNS_ARN" \
    --query 'Attributes.{已确认订阅:SubscriptionsConfirmed,待确认订阅:SubscriptionsPending,已删除订阅:SubscriptionsDeleted}' \
    --output table

echo
echo "订阅详情:"
aws sns list-subscriptions-by-topic \
    --topic-arn "$SNS_ARN" \
    --query 'Subscriptions[*].{协议:Protocol,端点:Endpoint,状态:SubscriptionArn}' \
    --output table
```

### 性能调优

#### 内存和超时优化

```bash
#!/bin/bash
# optimize-performance.sh - 性能优化脚本

DOMAIN_COUNT=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.DOMAINS' --output text | tr ',' '\n' | wc -l)

echo "当前监控域名数量: $DOMAIN_COUNT"

# 根据域名数量推荐配置
if [ "$DOMAIN_COUNT" -le 10 ]; then
    MEMORY=128
    TIMEOUT=180
    echo "推荐配置: 内存 ${MEMORY}MB, 超时 ${TIMEOUT}秒"
elif [ "$DOMAIN_COUNT" -le 30 ]; then
    MEMORY=256
    TIMEOUT=300
    echo "推荐配置: 内存 ${MEMORY}MB, 超时 ${TIMEOUT}秒"
elif [ "$DOMAIN_COUNT" -le 50 ]; then
    MEMORY=512
    TIMEOUT=600
    echo "推荐配置: 内存 ${MEMORY}MB, 超时 ${TIMEOUT}秒"
else
    MEMORY=1024
    TIMEOUT=900
    echo "推荐配置: 内存 ${MEMORY}MB, 超时 ${TIMEOUT}秒"
    echo "警告: 域名数量较多，建议考虑分批部署"
fi

# 询问是否应用配置
read -p "是否应用推荐配置? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    aws lambda update-function-configuration \
        --function-name ssl-certificate-monitor \
        --memory-size $MEMORY \
        --timeout $TIMEOUT
    echo "配置已更新"
else
    echo "配置未更改"
fi
```

## 备份和恢复

### 配置备份

```bash
#!/bin/bash
# backup-config.sh - 备份系统配置

BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "创建配置备份到: $BACKUP_DIR"

# 1. 备份Lambda函数配置
echo "备份Lambda函数配置..."
aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor > "$BACKUP_DIR/lambda-config.json"

# 2. 备份Lambda函数代码
echo "备份Lambda函数代码..."
aws lambda get-function \
    --function-name ssl-certificate-monitor \
    --query 'Code.Location' --output text | \
    xargs curl -o "$BACKUP_DIR/function-code.zip"

# 3. 备份环境变量
echo "备份环境变量..."
aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables' > "$BACKUP_DIR/environment-variables.json"

# 4. 备份EventBridge规则
echo "备份EventBridge规则..."
aws events describe-rule \
    --name ssl-certificate-monitor-schedule > "$BACKUP_DIR/eventbridge-rule.json"

# 5. 备份SNS主题配置
echo "备份SNS主题配置..."
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)

if [ "$SNS_ARN" != "None" ] && [ "$SNS_ARN" != "null" ]; then
    aws sns get-topic-attributes \
        --topic-arn "$SNS_ARN" > "$BACKUP_DIR/sns-topic.json"
    aws sns list-subscriptions-by-topic \
        --topic-arn "$SNS_ARN" > "$BACKUP_DIR/sns-subscriptions.json"
fi

# 6. 备份IAM角色
echo "备份IAM角色..."
ROLE_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Role' --output text)
ROLE_NAME=$(echo "$ROLE_ARN" | cut -d'/' -f2)

aws iam get-role --role-name "$ROLE_NAME" > "$BACKUP_DIR/iam-role.json"
aws iam list-attached-role-policies --role-name "$ROLE_NAME" > "$BACKUP_DIR/iam-attached-policies.json"
aws iam list-role-policies --role-name "$ROLE_NAME" > "$BACKUP_DIR/iam-inline-policies.json"

# 创建恢复脚本
cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
# restore.sh - 恢复配置脚本

BACKUP_DIR=$(dirname "$0")
echo "从备份恢复配置: $BACKUP_DIR"

# 恢复环境变量
echo "恢复环境变量..."
ENV_VARS=$(cat "$BACKUP_DIR/environment-variables.json")
aws lambda update-function-configuration \
    --function-name ssl-certificate-monitor \
    --environment Variables="$ENV_VARS"

# 恢复函数配置
echo "恢复函数配置..."
MEMORY_SIZE=$(cat "$BACKUP_DIR/lambda-config.json" | jq -r '.MemorySize')
TIMEOUT=$(cat "$BACKUP_DIR/lambda-config.json" | jq -r '.Timeout')

aws lambda update-function-configuration \
    --function-name ssl-certificate-monitor \
    --memory-size "$MEMORY_SIZE" \
    --timeout "$TIMEOUT"

# 恢复函数代码
echo "恢复函数代码..."
aws lambda update-function-code \
    --function-name ssl-certificate-monitor \
    --zip-file "fileb://$BACKUP_DIR/function-code.zip"

echo "配置恢复完成"
EOF

chmod +x "$BACKUP_DIR/restore.sh"

echo "备份完成: $BACKUP_DIR"
echo "恢复命令: ./$BACKUP_DIR/restore.sh"
```

### 灾难恢复

#### 完整系统恢复

```bash
#!/bin/bash
# disaster-recovery.sh - 灾难恢复脚本

echo "=== SSL证书监控系统灾难恢复 ==="
echo "此脚本将重新创建整个系统"
echo

read -p "确认要执行灾难恢复? (yes/no): " -r
if [ "$REPLY" != "yes" ]; then
    echo "取消恢复"
    exit 0
fi

# 1. 重新创建IAM角色
echo "1. 重新创建IAM角色..."
./create-iam-role.sh

# 2. 重新创建SNS主题
echo "2. 重新创建SNS主题..."
SNS_TOPIC_ARN=$(aws sns create-topic \
    --name ssl-certificate-alerts \
    --query 'TopicArn' --output text)
echo "SNS主题ARN: $SNS_TOPIC_ARN"

# 3. 重新部署Lambda函数
echo "3. 重新部署Lambda函数..."
export LAMBDA_ROLE_ARN=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ssl-certificate-monitor-role
export SNS_TOPIC_ARN=$SNS_TOPIC_ARN
./deploy.sh

# 4. 重新创建定时规则
echo "4. 重新创建定时规则..."
aws events put-rule \
    --name ssl-certificate-monitor-schedule \
    --schedule-expression "rate(30 days)" \
    --state ENABLED

aws events put-targets \
    --rule ssl-certificate-monitor-schedule \
    --targets "Id"="1","Arn"="$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.FunctionArn' --output text)"

aws lambda add-permission \
    --function-name ssl-certificate-monitor \
    --statement-id allow-eventbridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "$(aws events describe-rule --name ssl-certificate-monitor-schedule --query 'Arn' --output text)"

echo "5. 系统恢复完成"
echo "请手动配置以下项目:"
echo "- 设置环境变量 (DOMAINS, SNS_TOPIC_ARN)"
echo "- 订阅邮件通知"
echo "- 测试系统功能"
```

## 故障处理

### 自动故障检测

```bash
#!/bin/bash
# auto-fault-detection.sh - 自动故障检测脚本

echo "=== 自动故障检测 ==="
echo "检测时间: $(date)"
echo

ISSUES_FOUND=0

# 1. 检查Lambda函数状态
FUNCTION_STATE=$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.State' --output text 2>/dev/null)
if [ "$FUNCTION_STATE" != "Active" ]; then
    echo "❌ 故障: Lambda函数状态异常 ($FUNCTION_STATE)"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# 2. 检查最近执行
RECENT_EXECUTIONS=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '48 hours ago' +%s)000 \
    --filter-pattern "START RequestId" \
    --query 'length(events)' --output text)

if [ "$RECENT_EXECUTIONS" -eq 0 ]; then
    echo "❌ 故障: 最近48小时无执行记录"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# 3. 检查错误率
ERROR_COUNT=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '24 hours ago' +%s)000 \
    --filter-pattern "ERROR" \
    --query 'length(events)' --output text)

TOTAL_COUNT=$(aws logs filter-log-events \
    --log-group-name /aws/lambda/ssl-certificate-monitor \
    --start-time $(date -d '24 hours ago' +%s)000 \
    --filter-pattern "START RequestId" \
    --query 'length(events)' --output text)

if [ "$TOTAL_COUNT" -gt 0 ]; then
    ERROR_RATE=$(echo "scale=2; $ERROR_COUNT * 100 / $TOTAL_COUNT" | bc)
    if (( $(echo "$ERROR_RATE > 10" | bc -l) )); then
        echo "❌ 故障: 错误率过高 ($ERROR_RATE%)"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# 4. 检查SNS主题
SNS_ARN=$(aws lambda get-function-configuration \
    --function-name ssl-certificate-monitor \
    --query 'Environment.Variables.SNS_TOPIC_ARN' --output text)

if [ "$SNS_ARN" = "None" ] || [ "$SNS_ARN" = "null" ]; then
    echo "❌ 故障: SNS主题ARN未配置"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    # 检查SNS主题是否存在
    aws sns get-topic-attributes --topic-arn "$SNS_ARN" >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ 故障: SNS主题不存在或无权限访问"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# 5. 检查定时规则
RULE_STATE=$(aws events describe-rule --name ssl-certificate-monitor-schedule --query 'State' --output text 2>/dev/null)
if [ "$RULE_STATE" != "ENABLED" ]; then
    echo "❌ 故障: EventBridge规则未启用 ($RULE_STATE)"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# 总结
echo
if [ "$ISSUES_FOUND" -eq 0 ]; then
    echo "✅ 系统状态正常，未发现故障"
    exit 0
else
    echo "⚠️ 发现 $ISSUES_FOUND 个故障，需要处理"
    exit 1
fi
```

### 自动修复脚本

```bash
#!/bin/bash
# auto-repair.sh - 自动修复脚本

echo "=== 自动修复系统故障 ==="
echo "修复时间: $(date)"
echo

# 1. 修复Lambda函数状态
echo "1. 检查并修复Lambda函数状态..."
FUNCTION_STATE=$(aws lambda get-function --function-name ssl-certificate-monitor --query 'Configuration.State' --output text 2>/dev/null)
if [ "$FUNCTION_STATE" != "Active" ]; then
    echo "尝试重新部署Lambda函数..."
    ./deploy.sh package
    aws lambda update-function-code \
        --function-name ssl-certificate-monitor \
        --zip-file fileb://ssl-certificate-monitor.zip
    echo "Lambda函数已重新部署"
fi

# 2. 修复EventBridge规则
echo "2. 检查并修复EventBridge规则..."
RULE_STATE=$(aws events describe-rule --name ssl-certificate-monitor-schedule --query 'State' --output text 2>/dev/null)
if [ "$RULE_STATE" != "ENABLED" ]; then
    echo "启用EventBridge规则..."
    aws events enable-rule --name ssl-certificate-monitor-schedule
    echo "EventBridge规则已启用"
fi

# 3. 验证修复结果
echo "3. 验证修复结果..."
sleep 5

# 测试Lambda函数
echo "测试Lambda函数..."
aws lambda invoke \
    --function-name ssl-certificate-monitor \
    --payload '{}' \
    --log-type Tail \
    response.json >/dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Lambda函数测试成功"
else
    echo "❌ Lambda函数测试失败"
fi

# 检查规则状态
RULE_STATE=$(aws events describe-rule --name ssl-certificate-monitor-schedule --query 'State' --output text)
if [ "$RULE_STATE" = "ENABLED" ]; then
    echo "✅ EventBridge规则状态正常"
else
    echo "❌ EventBridge规则状态异常"
fi

echo
echo "=== 自动修复完成 ==="
```

## 最佳实践

### 运维自动化

1. **定期健康检查**：设置cron任务每日执行健康检查
2. **自动备份**：每周自动备份配置
3. **监控告警**：设置CloudWatch告警
4. **日志轮转**：定期清理旧日志

### 安全最佳实践

1. **最小权限**：定期审查IAM权限
2. **访问日志**：启用CloudTrail记录API调用
3. **敏感信息**：避免在日志中记录敏感信息
4. **网络安全**：使用VPC端点（如需要）

### 成本优化

1. **资源配置**：根据实际需求调整内存和超时
2. **日志保留**：设置合理的日志保留期
3. **监控成本**：定期检查AWS账单
4. **资源标签**：使用标签跟踪成本

### 文档维护

1. **操作记录**：记录所有运维操作
2. **变更日志**：维护系统变更历史
3. **故障记录**：记录故障和解决方案
4. **知识库**：建立运维知识库

通过遵循这些运维指南，您可以确保SSL证书监控系统的稳定运行和高效维护。