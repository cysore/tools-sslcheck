#!/bin/bash

# SSL证书监控器 CloudFormation部署脚本

set -e

# 配置变量
STACK_NAME="ssl-certificate-monitor"
TEMPLATE_FILE="cloudformation-template.yaml"
PARAMETERS_FILE="cloudformation-parameters.json"

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

# 检查必需工具
check_requirements() {
    log_info "检查部署要求..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI 未安装。"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS凭证未配置或无效。"
        exit 1
    fi
    
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_error "CloudFormation模板文件不存在: $TEMPLATE_FILE"
        exit 1
    fi
    
    log_info "要求检查通过。"
}

# 创建参数文件
create_parameters_file() {
    if [ ! -f "$PARAMETERS_FILE" ]; then
        log_info "创建参数文件: $PARAMETERS_FILE"
        
        cat > "$PARAMETERS_FILE" << EOF
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
        "ParameterValue": "example.com,test.org"
    },
    {
        "ParameterKey": "NotificationEmail",
        "ParameterValue": "admin@example.com"
    },
    {
        "ParameterKey": "LogLevel",
        "ParameterValue": "INFO"
    }
]
EOF
        
        log_warn "请编辑 $PARAMETERS_FILE 文件，设置正确的参数值。"
        log_warn "特别是 DomainsToMonitor 和 NotificationEmail 参数。"
        
        read -p "按回车键继续，或按 Ctrl+C 取消..."
    fi
}

# 验证模板
validate_template() {
    log_info "验证CloudFormation模板..."
    
    aws cloudformation validate-template \
        --template-body file://"$TEMPLATE_FILE" > /dev/null
    
    log_info "模板验证通过。"
}

# 部署或更新堆栈
deploy_stack() {
    log_info "检查堆栈是否存在..."
    
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &> /dev/null; then
        log_info "更新现有堆栈: $STACK_NAME"
        
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://"$TEMPLATE_FILE" \
            --parameters file://"$PARAMETERS_FILE" \
            --capabilities CAPABILITY_NAMED_IAM
        
        log_info "等待堆栈更新完成..."
        aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME"
        
    else
        log_info "创建新堆栈: $STACK_NAME"
        
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://"$TEMPLATE_FILE" \
            --parameters file://"$PARAMETERS_FILE" \
            --capabilities CAPABILITY_NAMED_IAM
        
        log_info "等待堆栈创建完成..."
        aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
    fi
    
    log_info "堆栈部署完成。"
}

# 显示堆栈输出
show_outputs() {
    log_info "堆栈输出:"
    
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

# 部署Lambda代码
deploy_lambda_code() {
    log_info "部署Lambda函数代码..."
    
    # 获取函数名称
    FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Parameters[?ParameterKey==`FunctionName`].ParameterValue' \
        --output text)
    
    if [ -f "ssl-certificate-monitor.zip" ]; then
        aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file fileb://ssl-certificate-monitor.zip
        
        log_info "Lambda代码更新完成。"
    else
        log_warn "未找到部署包 ssl-certificate-monitor.zip"
        log_warn "请先运行 ./deploy.sh package 创建部署包。"
    fi
}

# 测试部署
test_deployment() {
    log_info "测试Lambda函数..."
    
    FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Parameters[?ParameterKey==`FunctionName`].ParameterValue' \
        --output text)
    
    aws lambda invoke \
        --function-name "$FUNCTION_NAME" \
        --payload '{}' \
        response.json
    
    if [ -f "response.json" ]; then
        log_info "Lambda函数响应:"
        cat response.json
        echo ""
        rm -f response.json
    fi
}

# 主函数
main() {
    log_info "开始CloudFormation部署..."
    
    check_requirements
    create_parameters_file
    validate_template
    deploy_stack
    show_outputs
    
    if [ -f "ssl-certificate-monitor.zip" ]; then
        deploy_lambda_code
    fi
    
    test_deployment
    
    log_info "CloudFormation部署完成！"
    echo ""
    log_info "下一步:"
    echo "  1. 确认SNS邮件订阅（检查邮箱）"
    echo "  2. 如果需要，可以手动触发Lambda函数进行测试"
    echo "  3. 查看CloudWatch日志确认函数正常运行"
}

# 处理命令行参数
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "delete")
        log_warn "删除CloudFormation堆栈: $STACK_NAME"
        read -p "确认删除？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            aws cloudformation delete-stack --stack-name "$STACK_NAME"
            log_info "等待堆栈删除完成..."
            aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
            log_info "堆栈删除完成。"
        else
            log_info "取消删除操作。"
        fi
        ;;
    "status")
        aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
            --query 'Stacks[0].[StackName,StackStatus]' --output table
        ;;
    "outputs")
        show_outputs
        ;;
    *)
        echo "用法: $0 [deploy|delete|status|outputs]"
        echo "  deploy  - 部署或更新堆栈（默认）"
        echo "  delete  - 删除堆栈"
        echo "  status  - 显示堆栈状态"
        echo "  outputs - 显示堆栈输出"
        exit 1
        ;;
esac