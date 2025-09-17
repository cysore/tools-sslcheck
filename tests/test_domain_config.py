"""
域名配置管理器测试
"""
import pytest
import os
from unittest.mock import patch

from ssl_certificate_monitor.services.domain_config import DomainConfigManager


class TestDomainConfigManager:
    """域名配置管理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.manager = DomainConfigManager()
    
    def test_validate_domain_valid(self):
        """测试有效域名验证"""
        valid_domains = [
            "example.com",
            "sub.example.com",
            "test-site.org",
            "a.b.c.d.com",
            "123.com",
            "xn--fsq.com"  # 国际化域名
        ]
        
        for domain in valid_domains:
            assert self.manager.validate_domain(domain) is True, f"域名 {domain} 应该是有效的"
    
    def test_validate_domain_invalid(self):
        """测试无效域名验证"""
        invalid_domains = [
            "",
            None,
            ".",
            ".com",
            "example.",
            "ex ample.com",
            "example..com",
            "-example.com",
            "example-.com",
            "a" * 254,  # 太长
            "example.c",  # TLD太短
            "192.168.1.1",  # IP地址
            "example.com:80"  # 包含端口
        ]
        
        for domain in invalid_domains:
            assert self.manager.validate_domain(domain) is False, f"域名 {domain} 应该是无效的"
    
    def test_clean_domain(self):
        """测试域名清理功能"""
        test_cases = [
            ("https://example.com", "example.com"),
            ("http://example.com", "example.com"),
            ("www.example.com", "example.com"),
            ("https://www.example.com", "example.com"),
            ("example.com:443", "example.com"),
            ("example.com/path", "example.com"),
            ("https://www.example.com:443/path", "example.com"),
            ("  EXAMPLE.COM  ", "example.com"),
            ("Example.Com", "example.com")
        ]
        
        for input_domain, expected in test_cases:
            result = self.manager._clean_domain(input_domain)
            assert result == expected, f"清理 {input_domain} 应该得到 {expected}，实际得到 {result}"
    
    @patch.dict(os.environ, {'DOMAINS': 'example.com,test.org,invalid..domain,sub.example.com'})
    def test_get_domains_from_env(self):
        """测试从环境变量获取域名"""
        domains = self.manager.get_domains()
        
        # 应该过滤掉无效域名
        expected = ['example.com', 'test.org', 'sub.example.com']
        assert domains == expected
    
    @patch.dict(os.environ, {'DOMAINS': '  https://www.example.com:443/path  ,  test.org  '})
    def test_get_domains_with_cleaning(self):
        """测试获取域名时的清理功能"""
        domains = self.manager.get_domains()
        
        expected = ['example.com', 'test.org']
        assert domains == expected
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_domains_empty_env(self):
        """测试环境变量为空时的处理"""
        domains = self.manager.get_domains()
        
        # 应该返回空的默认列表
        assert domains == []
    
    @patch.dict(os.environ, {'DOMAINS': 'invalid..domain,another..invalid'})
    def test_get_domains_all_invalid(self):
        """测试所有域名都无效时的处理"""
        domains = self.manager.get_domains()
        
        # 应该返回默认域名列表（空）
        assert domains == []
    
    def test_set_default_domains(self):
        """测试设置默认域名"""
        default_domains = [
            'default1.com',
            'https://www.default2.com',
            'invalid..domain',
            'default3.org'
        ]
        
        self.manager.set_default_domains(default_domains)
        
        # 应该只保留有效的域名，并且已清理
        expected = ['default1.com', 'default2.com', 'default3.org']
        assert self.manager.default_domains == expected
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_domains_with_defaults(self):
        """测试使用默认域名"""
        # 设置默认域名
        self.manager.set_default_domains(['default1.com', 'default2.com'])
        
        domains = self.manager.get_domains()
        
        assert domains == ['default1.com', 'default2.com']
    
    def test_get_domain_count(self):
        """测试获取域名数量"""
        with patch.object(self.manager, 'get_domains', return_value=['a.com', 'b.com', 'c.com']):
            count = self.manager.get_domain_count()
            assert count == 3
    
    @patch.dict(os.environ, {'DOMAINS': 'example.com,test.org'})
    def test_validate_configuration_with_env(self):
        """测试配置验证（有环境变量）"""
        config = self.manager.validate_configuration()
        
        assert config['env_var_name'] == 'DOMAINS'
        assert config['env_var_exists'] is True
        assert config['env_var_value'] == 'example.com,test.org'
        assert config['total_domains'] == 2
        assert config['valid_domains'] == ['example.com', 'test.org']
        assert config['using_defaults'] is False
        assert config['has_defaults'] is False
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_configuration_without_env(self):
        """测试配置验证（无环境变量）"""
        self.manager.set_default_domains(['default.com'])
        
        config = self.manager.validate_configuration()
        
        assert config['env_var_exists'] is False
        assert config['env_var_value'] == ''
        assert config['total_domains'] == 1
        assert config['using_defaults'] is True
        assert config['has_defaults'] is True
    
    def test_custom_env_var_name(self):
        """测试自定义环境变量名"""
        custom_manager = DomainConfigManager(env_var_name="CUSTOM_DOMAINS")
        
        with patch.dict(os.environ, {'CUSTOM_DOMAINS': 'custom.com'}):
            domains = custom_manager.get_domains()
            assert domains == ['custom.com']
    
    @patch.dict(os.environ, {'DOMAINS': 'example.com,test.org'})
    def test_logging(self):
        """测试日志记录"""
        with patch.object(self.manager.logger, 'info') as mock_info:
            # 测试成功加载日志
            self.manager.get_domains()
            mock_info.assert_called_with("成功加载 2 个域名")
        
        with patch.object(self.manager.logger, 'info') as mock_info:
            # 测试设置默认域名日志
            self.manager.set_default_domains(['default.com'])
            mock_info.assert_called_with("设置了 1 个默认域名")
    
    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空字符串清理
        assert self.manager._clean_domain("") == ""
        assert self.manager._clean_domain(None) == ""
        
        # 测试域名验证边界情况
        assert self.manager.validate_domain("") is False
        assert self.manager.validate_domain(None) is False
        assert self.manager.validate_domain(123) is False