#!/bin/bash

# SSL证书监控器 Terraform部署脚本

set -e

# 配置变量
TERRAFORM_DIR="terraform"

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
    
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform 未安装。"
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI 未安装。"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS凭证未配置或无效。"
        exit 1
    fi
    
    if [ ! -d "$TERRAFORM_DIR" ]; then
        log_error "Terraform目录不存在: $TERRAFORM_DIR"
        exit 1
    fi
    
    log_info "要求检查通过。"
}

# 初始化Terraform
init_terraform() {
    log_info "初始化Terraform..."
    
    cd "$TERRAFORM_DIR"
    
    terraform init
    
    log_info "Terraform初始化完成。"
}

# 创建变量文件
create_tfvars() {
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        log_info "创建Terraform变量文件..."
        
        cp "$TERRAFORM_DIR/terraform.tfvars.example" "$TERRAFORM_DIR/terraform.tfvars"
        
        log_warn "请编辑 $TERRAFORM_DIR/terraform.tfvars 文件，设置正确的变量值。"
        log_warn "特别是 domains_to_monitor 和 notification_email 变量。"
        
        read -p "按回车键继续，或按 Ctrl+C 取消..."
    fi
}

# 验证配置
validate_config() {
    log_info "验证Terraform配置..."
    
    cd "$TERRAFORM_DIR"
    
    terraform validate
    
    log_info "配置验证通过。"
}

# 计划部署
plan_deployment() {
    log_info "生成Terraform执行计划..."
    
    cd "$TERRAFORM_DIR"
    
    terraform plan -out=tfplan
    
    log_info "执行计划生成完成。"
}

# 应用部署
apply_deployment() {
    log_info "应用Terraform配置..."
    
    cd "$TERRAFORM_DIR"
    
    terraform apply tfplan
    
    log_info "Terraform部署完成。"
}

# 显示输出
show_outputs() {
    log_info "Terraform输出:"
    
    cd "$TERRAFORM_DIR"
    
    terraform output
}

# 部署Lambda代码
deploy_lambda_code() {
    log_info "部署Lambda函数代码..."
    
    cd "$TERRAFORM_DIR"
    
    # 获取函数名称
    FUNCTION_NAME=$(terraform output -raw lambda_function_arn | cut -d':' -f7)
    
    cd ..
    
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
    
    cd "$TERRAFORM_DIR"
    
    FUNCTION_NAME=$(terraform output -raw lambda_function_arn | cut -d':' -f7)
    
    cd ..
    
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
    log_info "开始Terraform部署..."
    
    check_requirements
    create_tfvars
    init_terraform
    validate_config
    plan_deployment
    apply_deployment
    show_outputs
    
    cd ..
    
    if [ -f "ssl-certificate-monitor.zip" ]; then
        deploy_lambda_code
    fi
    
    test_deployment
    
    log_info "Terraform部署完成！"
    echo ""
    log_info "下一步:"
    echo "  1. 确认SNS邮件订阅（检查邮箱）"
    echo "  2. 如果需要，可以手动触发Lambda函数进行测试"
    echo "  3. 查看CloudWatch日志确认函数正常运行"
}

# 处理命令行参数
case "${1:-deploy}" in
    "init")
        check_requirements
        init_terraform
        ;;
    "plan")
        check_requirements
        create_tfvars
        cd "$TERRAFORM_DIR"
        terraform plan
        ;;
    "deploy")
        main
        ;;
    "destroy")
        log_warn "销毁Terraform管理的资源"
        read -p "确认销毁？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd "$TERRAFORM_DIR"
            terraform destroy
            log_info "资源销毁完成。"
        else
            log_info "取消销毁操作。"
        fi
        ;;
    "output")
        cd "$TERRAFORM_DIR"
        terraform output
        ;;
    *)
        echo "用法: $0 [init|plan|deploy|destroy|output]"
        echo "  init    - 初始化Terraform"
        echo "  plan    - 生成执行计划"
        echo "  deploy  - 完整部署（默认）"
        echo "  destroy - 销毁资源"
        echo "  output  - 显示输出"
        exit 1
        ;;
esac