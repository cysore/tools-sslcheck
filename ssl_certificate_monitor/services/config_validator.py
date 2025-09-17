"""
配置验证服务
"""
import os
import re
from typing import Dict, List, Any, Optional
import logging


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        """初始化配置验证器"""
        self.logger = logging.getLogger(__name__)
        
        # 必需的环境变量
        self.required_env_vars = {
            'DOMAINS': '域名列表（逗号分隔）'
        }
        
        # 可选的环境变量
        self.optional_env_vars = {
            'SNS_TOPIC_ARN': 'SNS主题ARN',
            'LOG_LEVEL': '日志级别',
            'AWS_LAMBDA_FUNCTION_NAME': 'Lambda函数名称',
            'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': 'Lambda内存大小',
            'AWS_LAMBDA_FUNCTION_TIMEOUT': 'Lambda超时时间'
        }
    
    def validate_all_configurations(self) -> Dict[str, Any]:
        """
        验证所有配置
        
        Returns:
            Dict[str, Any]: 验证结果
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'configurations': {}
        }
        
        try:
            # 验证环境变量
            env_validation = self.validate_environment_variables()
            validation_result['configurations']['environment'] = env_validation
            
            if not env_validation['is_valid']:
                validation_result['is_valid'] = False
                validation_result['errors'].extend(env_validation['errors'])
            
            validation_result['warnings'].extend(env_validation['warnings'])
            
            # 验证域名配置
            domains_validation = self.validate_domains_configuration()
            validation_result['configurations']['domains'] = domains_validation
            
            if not domains_validation['is_valid']:
                validation_result['is_valid'] = False
                validation_result['errors'].extend(domains_validation['errors'])
            
            # 验证SNS配置
            sns_validation = self.validate_sns_configuration()
            validation_result['configurations']['sns'] = sns_validation
            
            if not sns_validation['is_valid']:
                validation_result['warnings'].extend(sns_validation['errors'])
            
            # 验证Lambda配置
            lambda_validation = self.validate_lambda_configuration()
            validation_result['configurations']['lambda'] = lambda_validation
            
            validation_result['warnings'].extend(lambda_validation['warnings'])
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"配置验证时发生错误: {str(e)}")
        
        return validation_result
    
    def validate_environment_variables(self) -> Dict[str, Any]:
        """
        验证环境变量
        
        Returns:
            Dict[str, Any]: 环境变量验证结果
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'missing_required': [],
            'missing_optional': [],
            'present_vars': {}
        }
        
        # 检查必需的环境变量
        for var_name, description in self.required_env_vars.items():
            value = os.getenv(var_name)
            if not value:
                result['missing_required'].append({
                    'name': var_name,
                    'description': description
                })
                result['errors'].append(f"缺少必需的环境变量: {var_name} ({description})")
                result['is_valid'] = False
            else:
                result['present_vars'][var_name] = self._sanitize_env_value(var_name, value)
        
        # 检查可选的环境变量
        for var_name, description in self.optional_env_vars.items():
            value = os.getenv(var_name)
            if not value:
                result['missing_optional'].append({
                    'name': var_name,
                    'description': description
                })
                result['warnings'].append(f"缺少可选的环境变量: {var_name} ({description})")
            else:
                result['present_vars'][var_name] = self._sanitize_env_value(var_name, value)
        
        return result
    
    def validate_domains_configuration(self) -> Dict[str, Any]:
        """
        验证域名配置
        
        Returns:
            Dict[str, Any]: 域名配置验证结果
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'total_domains': 0,
            'valid_domains': [],
            'invalid_domains': []
        }
        
        domains_str = os.getenv('DOMAINS', '')
        
        if not domains_str.strip():
            result['is_valid'] = False
            result['errors'].append("DOMAINS环境变量为空")
            return result
        
        # 解析域名列表
        raw_domains = [domain.strip() for domain in domains_str.split(',')]
        result['total_domains'] = len(raw_domains)
        
        # 验证每个域名
        for domain in raw_domains:
            if domain:
                if self._validate_domain_format(domain):
                    result['valid_domains'].append(domain)
                else:
                    result['invalid_domains'].append(domain)
                    result['warnings'].append(f"域名格式无效: {domain}")
        
        if not result['valid_domains']:
            result['is_valid'] = False
            result['errors'].append("没有找到有效的域名")
        
        return result
    
    def validate_sns_configuration(self) -> Dict[str, Any]:
        """
        验证SNS配置
        
        Returns:
            Dict[str, Any]: SNS配置验证结果
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'topic_arn': None,
            'arn_format_valid': False
        }
        
        topic_arn = os.getenv('SNS_TOPIC_ARN')
        
        if not topic_arn:
            result['is_valid'] = False
            result['errors'].append("SNS_TOPIC_ARN环境变量未设置")
            return result
        
        result['topic_arn'] = topic_arn
        
        # 验证ARN格式
        arn_pattern = r'^arn:aws:sns:[a-z0-9-]+:\d{12}:[a-zA-Z0-9_-]+$'
        if re.match(arn_pattern, topic_arn):
            result['arn_format_valid'] = True
        else:
            result['is_valid'] = False
            result['errors'].append(f"SNS主题ARN格式无效: {topic_arn}")
        
        return result
    
    def validate_lambda_configuration(self) -> Dict[str, Any]:
        """
        验证Lambda配置
        
        Returns:
            Dict[str, Any]: Lambda配置验证结果
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'function_name': None,
            'memory_size': None,
            'timeout': None
        }
        
        # 检查Lambda函数名称
        function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME')
        if function_name:
            result['function_name'] = function_name
        else:
            result['warnings'].append("AWS_LAMBDA_FUNCTION_NAME未设置，可能不在Lambda环境中运行")
        
        # 检查内存大小
        memory_size = os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE')
        if memory_size:
            try:
                memory_mb = int(memory_size)
                result['memory_size'] = memory_mb
                
                if memory_mb < 128:
                    result['warnings'].append(f"Lambda内存大小过小: {memory_mb}MB，建议至少128MB")
                elif memory_mb > 3008:
                    result['warnings'].append(f"Lambda内存大小过大: {memory_mb}MB")
                    
            except ValueError:
                result['warnings'].append(f"Lambda内存大小格式无效: {memory_size}")
        
        # 检查超时时间
        timeout = os.getenv('AWS_LAMBDA_FUNCTION_TIMEOUT')
        if timeout:
            try:
                timeout_seconds = int(timeout)
                result['timeout'] = timeout_seconds
                
                if timeout_seconds < 30:
                    result['warnings'].append(f"Lambda超时时间过短: {timeout_seconds}秒，建议至少30秒")
                elif timeout_seconds > 900:
                    result['warnings'].append(f"Lambda超时时间过长: {timeout_seconds}秒")
                    
            except ValueError:
                result['warnings'].append(f"Lambda超时时间格式无效: {timeout}")
        
        return result
    
    def _validate_domain_format(self, domain: str) -> bool:
        """
        验证域名格式
        
        Args:
            domain: 域名
            
        Returns:
            bool: 是否有效
        """
        # 移除协议前缀
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1]
        
        # 移除路径
        if '/' in domain:
            domain = domain.split('/')[0]
        
        # 移除端口
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # 域名格式验证
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(domain_pattern, domain))
    
    def _sanitize_env_value(self, var_name: str, value: str) -> str:
        """
        清理环境变量值（隐藏敏感信息）
        
        Args:
            var_name: 变量名
            value: 变量值
            
        Returns:
            str: 清理后的值
        """
        sensitive_vars = {'SNS_TOPIC_ARN', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'}
        
        if var_name in sensitive_vars and value:
            if var_name == 'SNS_TOPIC_ARN' and value.startswith('arn:'):
                # ARN类型，只显示前缀和后缀
                parts = value.split(':')
                if len(parts) >= 6:
                    return f"{':'.join(parts[:3])}:***:{parts[-2]}:{parts[-1]}"
            
            # 其他敏感信息，只显示前几个字符
            return value[:8] + "***" if len(value) > 8 else "***"
        
        return value
    
    def get_configuration_summary(self) -> str:
        """
        获取配置摘要
        
        Returns:
            str: 配置摘要文本
        """
        validation_result = self.validate_all_configurations()
        
        lines = [
            "配置验证摘要",
            "=" * 30
        ]
        
        if validation_result['is_valid']:
            lines.append("✅ 配置验证通过")
        else:
            lines.append("❌ 配置验证失败")
        
        # 错误信息
        if validation_result['errors']:
            lines.append("\n错误:")
            for error in validation_result['errors']:
                lines.append(f"  • {error}")
        
        # 警告信息
        if validation_result['warnings']:
            lines.append("\n警告:")
            for warning in validation_result['warnings']:
                lines.append(f"  • {warning}")
        
        # 配置详情
        lines.append("\n配置详情:")
        
        # 环境变量
        env_config = validation_result['configurations'].get('environment', {})
        if env_config.get('present_vars'):
            lines.append("  环境变量:")
            for var_name, var_value in env_config['present_vars'].items():
                lines.append(f"    {var_name}: {var_value}")
        
        # 域名配置
        domains_config = validation_result['configurations'].get('domains', {})
        if domains_config.get('valid_domains'):
            lines.append(f"  有效域名数量: {len(domains_config['valid_domains'])}")
        
        return "\n".join(lines)