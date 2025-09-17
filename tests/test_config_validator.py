"""
配置验证器测试
"""
import pytest
import os
from unittest.mock import patch

from ssl_certificate_monitor.services.config_validator import ConfigValidator


class TestConfigValidator:
    """配置验证器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.validator = ConfigValidator()
    
    def test_init(self):
        """测试初始化"""
        assert 'DOMAINS' in self.validator.required_env_vars
        assert 'SNS_TOPIC_ARN' in self.validator.optional_env_vars
    
    @patch.dict(os.environ, {
        'DOMAINS': 'example.com,test.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
        'LOG_LEVEL': 'INFO'
    })
    def test_validate_environment_variables_success(self):
        """测试环境变量验证成功"""
        result = self.validator.validate_environment_variables()
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
        assert 'DOMAINS' in result['present_vars']
        assert 'SNS_TOPIC_ARN' in result['present_vars']
        assert len(result['missing_required']) == 0
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_environment_variables_missing_required(self):
        """测试缺少必需环境变量"""
        result = self.validator.validate_environment_variables()
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
        assert len(result['missing_required']) > 0
        assert any('DOMAINS' in error for error in result['errors'])
    
    @patch.dict(os.environ, {'DOMAINS': 'example.com,test.org'})
    def test_validate_domains_configuration_success(self):
        """测试域名配置验证成功"""
        result = self.validator.validate_domains_configuration()
        
        assert result['is_valid'] is True
        assert result['total_domains'] == 2
        assert 'example.com' in result['valid_domains']
        assert 'test.org' in result['valid_domains']
        assert len(result['invalid_domains']) == 0
    
    @patch.dict(os.environ, {'DOMAINS': ''})
    def test_validate_domains_configuration_empty(self):
        """测试空域名配置"""
        result = self.validator.validate_domains_configuration()
        
        assert result['is_valid'] is False
        assert "DOMAINS环境变量为空" in result['errors']
    
    @patch.dict(os.environ, {'DOMAINS': 'example.com,invalid..domain,test.org'})
    def test_validate_domains_configuration_with_invalid(self):
        """测试包含无效域名的配置"""
        result = self.validator.validate_domains_configuration()
        
        assert result['is_valid'] is True  # 仍然有效，因为有有效域名
        assert result['total_domains'] == 3
        assert len(result['valid_domains']) == 2
        assert len(result['invalid_domains']) == 1
        assert 'invalid..domain' in result['invalid_domains']
        assert len(result['warnings']) > 0
    
    @patch.dict(os.environ, {'DOMAINS': 'invalid..domain,another..invalid'})
    def test_validate_domains_configuration_all_invalid(self):
        """测试所有域名都无效"""
        result = self.validator.validate_domains_configuration()
        
        assert result['is_valid'] is False
        assert "没有找到有效的域名" in result['errors']
    
    @patch.dict(os.environ, {'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts'})
    def test_validate_sns_configuration_success(self):
        """测试SNS配置验证成功"""
        result = self.validator.validate_sns_configuration()
        
        assert result['is_valid'] is True
        assert result['arn_format_valid'] is True
        assert result['topic_arn'] == 'arn:aws:sns:us-east-1:123456789012:ssl-alerts'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_sns_configuration_missing(self):
        """测试缺少SNS配置"""
        result = self.validator.validate_sns_configuration()
        
        assert result['is_valid'] is False
        assert "SNS_TOPIC_ARN环境变量未设置" in result['errors']
    
    @patch.dict(os.environ, {'SNS_TOPIC_ARN': 'invalid-arn-format'})
    def test_validate_sns_configuration_invalid_arn(self):
        """测试无效的SNS ARN格式"""
        result = self.validator.validate_sns_configuration()
        
        assert result['is_valid'] is False
        assert result['arn_format_valid'] is False
        assert "SNS主题ARN格式无效" in result['errors'][0]
    
    @patch.dict(os.environ, {
        'AWS_LAMBDA_FUNCTION_NAME': 'ssl-monitor',
        'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': '256',
        'AWS_LAMBDA_FUNCTION_TIMEOUT': '180'
    })
    def test_validate_lambda_configuration_success(self):
        """测试Lambda配置验证成功"""
        result = self.validator.validate_lambda_configuration()
        
        assert result['is_valid'] is True
        assert result['function_name'] == 'ssl-monitor'
        assert result['memory_size'] == 256
        assert result['timeout'] == 180
        assert len(result['warnings']) == 0
    
    @patch.dict(os.environ, {
        'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': '64',  # 太小
        'AWS_LAMBDA_FUNCTION_TIMEOUT': '15'      # 太短
    })
    def test_validate_lambda_configuration_warnings(self):
        """测试Lambda配置警告"""
        result = self.validator.validate_lambda_configuration()
        
        assert result['is_valid'] is True
        assert len(result['warnings']) >= 2
        assert any('内存大小过小' in warning for warning in result['warnings'])
        assert any('超时时间过短' in warning for warning in result['warnings'])
    
    @patch.dict(os.environ, {
        'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': 'invalid',
        'AWS_LAMBDA_FUNCTION_TIMEOUT': 'invalid'
    })
    def test_validate_lambda_configuration_invalid_format(self):
        """测试Lambda配置格式无效"""
        result = self.validator.validate_lambda_configuration()
        
        assert result['is_valid'] is True  # Lambda配置错误不影响整体有效性
        assert len(result['warnings']) >= 2
        assert any('内存大小格式无效' in warning for warning in result['warnings'])
        assert any('超时时间格式无效' in warning for warning in result['warnings'])
    
    def test_validate_domain_format(self):
        """测试域名格式验证"""
        valid_domains = [
            'example.com',
            'sub.example.com',
            'test-site.org',
            'https://example.com',
            'http://example.com/path',
            'example.com:443'
        ]
        
        invalid_domains = [
            '',
            'invalid..domain',
            '.example.com',
            'example.',
            'ex ample.com',
            '192.168.1.1'
        ]
        
        for domain in valid_domains:
            assert self.validator._validate_domain_format(domain) is True, f"域名 {domain} 应该是有效的"
        
        for domain in invalid_domains:
            assert self.validator._validate_domain_format(domain) is False, f"域名 {domain} 应该是无效的"
    
    def test_sanitize_env_value(self):
        """测试环境变量值清理"""
        # 敏感变量
        arn_value = 'arn:aws:sns:us-east-1:123456789012:ssl-alerts'
        sanitized_arn = self.validator._sanitize_env_value('SNS_TOPIC_ARN', arn_value)
        assert 'arn:aws:sns:***:123456789012:ssl-alerts' == sanitized_arn
        
        # 普通变量
        normal_value = 'example.com,test.org'
        sanitized_normal = self.validator._sanitize_env_value('DOMAINS', normal_value)
        assert sanitized_normal == normal_value
    
    @patch.dict(os.environ, {
        'DOMAINS': 'example.com,test.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
        'LOG_LEVEL': 'INFO'
    })
    def test_validate_all_configurations_success(self):
        """测试所有配置验证成功"""
        result = self.validator.validate_all_configurations()
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
        assert 'environment' in result['configurations']
        assert 'domains' in result['configurations']
        assert 'sns' in result['configurations']
        assert 'lambda' in result['configurations']
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_all_configurations_failure(self):
        """测试配置验证失败"""
        result = self.validator.validate_all_configurations()
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
    
    @patch.dict(os.environ, {
        'DOMAINS': 'example.com,test.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts'
    })
    def test_get_configuration_summary(self):
        """测试获取配置摘要"""
        summary = self.validator.get_configuration_summary()
        
        assert "配置验证摘要" in summary
        assert "✅ 配置验证通过" in summary
        assert "环境变量:" in summary
        assert "有效域名数量: 2" in summary
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_configuration_summary_with_errors(self):
        """测试包含错误的配置摘要"""
        summary = self.validator.get_configuration_summary()
        
        assert "配置验证摘要" in summary
        assert "❌ 配置验证失败" in summary
        assert "错误:" in summary