#!/bin/bash

# SSL证书监控器Lambda部署脚本

set -e

# 配置变量
FUNCTION_NAME="ssl-certificate-monitor"
RUNTIME="python3.12"
HANDLER="ssl_certificate_monitor.lambda_handler.lambda_handler"
TIMEOUT=180
MEMORY_SIZE=256
DESCRIPTION="SSL证书过期监控系统"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必需的工具
check_requirements() {
    log_info "检查部署要求..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI 未安装。请安装 AWS CLI 并配置凭证。"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装。"
        exit 1
    fi
    
    if ! command -v zip &> /dev/null; then
        log_error "zip 命令未找到。"
        exit 1
    fi
    
    # 检查AWS凭证
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS凭证未配置或无效。请运行 'aws configure' 配置凭证。"
        exit 1
    fi
    
    log_info "所有要求检查通过。"
}

# 创建部署包
create_deployment_package() {
    log_info "创建Lambda部署包..."
    
    # 清理之前的构建
    rm -rf build/
    rm -f ssl-certificate-monitor.zip
    
    # 创建构建目录
    mkdir -p build
    
    # 复制源代码
    log_info "复制源代码..."
    cp -r ssl_certificate_monitor/ build/
    
    # 安装依赖（如果有的话）
    if [ -f "requirements-lambda.txt" ] && [ -s "requirements-lambda.txt" ]; then
        log_info "安装Lambda依赖..."
        pip install -r requirements-lambda.txt -t build/
    else
        log_info "没有Lambda依赖需要安装。"
    fi
    
    # 创建ZIP包
    log_info "创建ZIP部署包..."
    cd build
    zip -r ../ssl-certificate-monitor.zip . -x "*.pyc" "*/__pycache__/*" "*/tests/*" "*.git*"
    cd ..
    
    # 检查包大小
    PACKAGE_SIZE=$(du -h ssl-certificate-monitor.zip | cut -f1)
    log_info "部署包大小: $PACKAGE_SIZE"
    
    if [ $(stat -f%z ssl-certificate-monitor.zip 2>/dev/null || stat -c%s ssl-certificate-monitor.zip) -gt 52428800 ]; then
        log_warn "部署包大小超过50MB，可能需要使用S3部署。"
    fi
}

# 创建或更新Lambda函数
deploy_lambda() {
    log_info "部署Lambda函数..."
    
    # 检查函数是否存在
    if aws lambda get-function --function-name "$FUNCTION_NAME" &> /dev/null; then
        log_info "更新现有Lambda函数..."
        aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file fileb://ssl-certificate-monitor.zip
        
        # 更新函数配置
        aws lambda update-function-configuration \
            --function-name "$FUNCTION_NAME" \
            --runtime "$RUNTIME" \
            --handler "$HANDLER" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY_SIZE" \
            --description "$DESCRIPTION"
    else
        log_info "创建新的Lambda函数..."
        
        # 获取执行角色ARN
        if [ -z "$LAMBDA_ROLE_ARN" ]; then
            log_error "请设置环境变量 LAMBDA_ROLE_ARN 为Lambda执行角色的ARN"
            log_error "例如: export LAMBDA_ROLE_ARN=arn:aws:iam::123456789012:role/lambda-execution-role"
            exit 1
        fi
        
        aws lambda create-function \
            --function-name "$FUNCTION_NAME" \
            --runtime "$RUNTIME" \
            --role "$LAMBDA_ROLE_ARN" \
            --handler "$HANDLER" \
            --zip-file fileb://ssl-certificate-monitor.zip \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY_SIZE" \
            --description "$DESCRIPTION"
    fi
    
    log_info "Lambda函数部署完成。"
}

# 设置环境变量
set_environment_variables() {
    if [ -f ".env" ]; then
        log_info "设置环境变量..."
        
        # 读取.env文件并设置环境变量
        ENV_VARS=$(grep -v '^#' .env | grep -v '^$' | sed 's/^/"/; s/$/"/; s/=/":"/g' | tr '\n' ',' | sed 's/,$//')
        
        if [ ! -z "$ENV_VARS" ]; then
            aws lambda update-function-configuration \
                --function-name "$FUNCTION_NAME" \
                --environment "Variables={$ENV_VARS}"
            log_info "环境变量设置完成。"
        fi
    else
        log_warn "未找到.env文件，跳过环境变量设置。"
        log_warn "请手动在AWS控制台或使用AWS CLI设置以下环境变量："
        log_warn "  - DOMAINS: 要监控的域名列表（逗号分隔）"
        log_warn "  - SNS_TOPIC_ARN: SNS主题ARN"
        log_warn "  - LOG_LEVEL: 日志级别（可选，默认INFO）"
    fi
}

# 清理构建文件
cleanup() {
    log_info "清理构建文件..."
    rm -rf build/
    log_info "清理完成。"
}

# 显示部署信息
show_deployment_info() {
    log_info "部署信息:"
    echo "  函数名称: $FUNCTION_NAME"
    echo "  运行时: $RUNTIME"
    echo "  处理器: $HANDLER"
    echo "  超时时间: ${TIMEOUT}秒"
    echo "  内存大小: ${MEMORY_SIZE}MB"
    echo ""
    log_info "下一步:"
    echo "  1. 设置EventBridge规则以定期触发函数"
    echo "  2. 配置SNS主题和订阅"
    echo "  3. 测试函数执行"
    echo ""
    log_info "测试命令:"
    echo "  aws lambda invoke --function-name $FUNCTION_NAME --payload '{}' response.json"
}

# 主函数
main() {
    log_info "开始部署SSL证书监控器..."
    
    check_requirements
    create_deployment_package
    deploy_lambda
    set_environment_variables
    cleanup
    show_deployment_info
    
    log_info "部署完成！"
}

# 处理命令行参数
case "${1:-deploy}" in
    "package")
        log_info "仅创建部署包..."
        check_requirements
        create_deployment_package
        log_info "部署包创建完成: ssl-certificate-monitor.zip"
        ;;
    "deploy")
        main
        ;;
    "clean")
        log_info "清理构建文件..."
        rm -rf build/
        rm -f ssl-certificate-monitor.zip
        log_info "清理完成。"
        ;;
    *)
        echo "用法: $0 [package|deploy|clean]"
        echo "  package - 仅创建部署包"
        echo "  deploy  - 完整部署（默认）"
        echo "  clean   - 清理构建文件"
        exit 1
        ;;
esac