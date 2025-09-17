#!/bin/bash

# 创建SSL证书监控器Lambda执行角色

set -e

ROLE_NAME="ssl-certificate-monitor-role"
POLICY_NAME="ssl-certificate-monitor-policy"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查AWS CLI
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI 未安装。"
    exit 1
fi

# 检查AWS凭证
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS凭证未配置或无效。"
    exit 1
fi

log_info "创建IAM角色: $ROLE_NAME"

# 创建IAM角色
if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    log_warn "IAM角色 $ROLE_NAME 已存在，跳过创建。"
else
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file://iam-trust-policy.json \
        --description "SSL证书监控器Lambda执行角色"
    
    log_info "IAM角色创建成功。"
fi

# 创建并附加策略
log_info "创建IAM策略: $POLICY_NAME"

# 获取账户ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if aws iam get-policy --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME" &> /dev/null; then
    log_warn "IAM策略 $POLICY_NAME 已存在，跳过创建。"
else
    POLICY_ARN=$(aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://iam-policy.json \
        --description "SSL证书监控器Lambda执行策略" \
        --query 'Policy.Arn' \
        --output text)
    
    log_info "IAM策略创建成功: $POLICY_ARN"
fi

# 附加策略到角色
log_info "附加策略到角色..."

POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN"

# 附加AWS管理的基本执行策略
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

log_info "策略附加完成。"

# 获取角色ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

log_info "IAM角色设置完成！"
echo ""
echo "角色ARN: $ROLE_ARN"
echo ""
log_info "请设置环境变量以用于部署:"
echo "export LAMBDA_ROLE_ARN=$ROLE_ARN"
echo ""
log_info "或者将以下内容添加到您的 .bashrc 或 .zshrc:"
echo "export LAMBDA_ROLE_ARN=$ROLE_ARN"